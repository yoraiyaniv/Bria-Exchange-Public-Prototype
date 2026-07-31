"""
Bria Exchange — Wikidata Tool
Searches Wikidata for entity facts, dates, and relationships.
Good for: rankings, company founding dates, CEO names, stock exchanges,
          IPO data, key people, country data, industry classifications,
          and general factual claims.
"""

import requests

WIKIDATA_API = "https://www.wikidata.org/w/api.php"
SPARQL_URL   = "https://query.wikidata.org/sparql"
TIMEOUT      = 10
_UA          = {"User-Agent": "BriaExchange/1.0 (fact-verification)"}

# ── Property catalogue ────────────────────────────────────────────────────────
# Broad set of commonly needed properties for fact verification.
# Multi-valued properties (founders, board members, exchanges) return ALL values.

PROP_LABELS = {
    # Identity & classification
    "P31":   "instance_of",
    "P17":   "country",
    "P159":  "headquarters",
    "P452":  "industry",
    "P361":  "part_of",
    # Founding & history
    "P571":  "inception_date",
    "P112":  "founders",
    "P576":  "dissolved_date",
    # People & leadership
    "P169":  "ceo",
    "P3320": "board_members",
    "P488":  "chairperson",
    # Corporate structure
    "P127":  "owned_by",
    "P749":  "parent_org",
    "P355":  "subsidiaries",
    "P1128": "employees",
    # Financial & market
    "P414":  "stock_exchange",
    "P249":  "ticker_symbol",
    "P2138": "total_revenue",
    "P2403": "total_assets",
    "P2295": "net_profit",
    # Products & websites
    "P856":  "official_website",
    "P1056": "products",
    # Awards, rankings
    "P166":  "awards_received",
}

# Properties that commonly have multiple values — return all of them
_MULTI_VALUE_PROPS = {
    "P112", "P3320", "P488", "P414", "P249", "P355",
    "P166", "P1056", "P31",
}


WIKIDATA_TOOL_DEFINITION = {
    "name": "search_wikidata",
    "description": (
        "Search Wikidata for structured factual information about entities — companies, people, "
        "organisations, rankings, events, and general knowledge claims. "
        "Returns founding dates, founders, stock exchanges, board members, CEO, headquarters, "
        "revenue, employees, and many more structured facts. "
        "Use for claims about company characteristics, founding dates, leadership, IPO details, "
        "stock exchange listings, country facts, and anything not covered by financial or medical sources."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search term or entity name (e.g. 'Tesla Inc', 'OpenAI', 'Google DeepMind').",
            },
            "language": {
                "type": "string",
                "description": "Language code for labels. Default: 'en'.",
                "default": "en",
            },
        },
        "required": ["query"],
    },
}


def _resolve_entity_labels(entity_ids: list[str], language: str) -> dict[str, str]:
    """Batch-resolve Wikidata entity IDs (e.g. Q30) to human-readable labels."""
    if not entity_ids:
        return {}
    # API allows up to 50 IDs per call
    labels = {}
    for i in range(0, len(entity_ids), 50):
        batch = entity_ids[i:i+50]
        try:
            resp = requests.get(
                WIKIDATA_API,
                params={
                    "action":    "wbgetentities",
                    "ids":       "|".join(batch),
                    "props":     "labels",
                    "languages": f"{language}|en",
                    "format":    "json",
                },
                timeout=TIMEOUT,
                headers=_UA,
            )
            resp.raise_for_status()
            entities = resp.json().get("entities", {})
            for eid, edata in entities.items():
                elabels = edata.get("labels", {})
                lbl = elabels.get(language, elabels.get("en", {}))
                if isinstance(lbl, dict):
                    labels[eid] = lbl.get("value", eid)
                else:
                    labels[eid] = eid
        except requests.RequestException:
            # On failure, return the raw IDs
            for eid in batch:
                labels.setdefault(eid, eid)
    return labels


def _extract_value(snak: dict) -> tuple[str, str | None]:
    """Extract a human-readable value from a Wikidata snak.

    Returns (value_string, entity_id_or_None).
    """
    dv = snak.get("datavalue", {})
    dtype = dv.get("type")

    if dtype == "string":
        return dv["value"], None
    elif dtype == "wikibase-entityid":
        eid = dv["value"].get("id", "")
        return eid, eid  # placeholder — will be resolved to label later
    elif dtype == "time":
        return dv["value"].get("time", ""), None
    elif dtype == "quantity":
        amount = dv["value"].get("amount", "")
        unit = dv["value"].get("unit", "")
        # Unit is a Wikidata URL like http://www.wikidata.org/entity/Q4917
        unit_id = unit.split("/")[-1] if "/" in unit else ""
        return f"{amount} [{unit_id}]" if unit_id and unit_id != "1" else amount, unit_id if unit_id and unit_id != "1" else None
    elif dtype == "monolingualtext":
        return dv["value"].get("text", ""), None
    else:
        return str(dv.get("value", "")), None


def execute_wikidata_tool(tool_input: dict) -> dict:
    query    = tool_input.get("query", "")
    language = tool_input.get("language", "en")

    if not query:
        return {"error": "query is required"}

    try:
        # Entity search
        search_resp = requests.get(
            WIKIDATA_API,
            params={
                "action":   "wbsearchentities",
                "search":   query,
                "language": language,
                "format":   "json",
                "limit":    5,
            },
            timeout=TIMEOUT,
            headers=_UA,
        )
        search_resp.raise_for_status()
        search_data = search_resp.json()

        results = search_data.get("search", [])
        if not results:
            return {
                "found": False,
                "query": query,
                "message": f"No Wikidata entities found for '{query}'.",
            }

        # Return top matches with descriptions
        entities = [
            {
                "id":          r.get("id"),
                "label":       r.get("label"),
                "description": r.get("description"),
                "url":         f"https://www.wikidata.org/wiki/{r.get('id')}",
            }
            for r in results
        ]

        # Fetch claims for the top entity
        top_id = results[0]["id"]
        claims_resp = requests.get(
            WIKIDATA_API,
            params={
                "action":    "wbgetentities",
                "ids":       top_id,
                "props":     "claims|labels|descriptions|sitelinks",
                "languages": f"{language}|en",
                "format":    "json",
            },
            timeout=TIMEOUT,
            headers=_UA,
        )
        claims_resp.raise_for_status()
        entity_data = claims_resp.json().get("entities", {}).get(top_id, {})

        elabels      = entity_data.get("labels", {})
        descriptions = entity_data.get("descriptions", {})
        label       = elabels.get(language, elabels.get("en", {})).get("value", results[0].get("label"))
        description = descriptions.get(language, descriptions.get("en", {})).get("value", results[0].get("description"))

        # ── Extract facts from all tracked properties ─────────────────────────
        raw_claims = entity_data.get("claims", {})
        notable = {}
        entity_ids_to_resolve = []  # collect entity IDs for batch label resolution

        for prop, name in PROP_LABELS.items():
            if prop not in raw_claims:
                continue

            claims_list = raw_claims[prop]
            is_multi = prop in _MULTI_VALUE_PROPS

            if is_multi:
                values = []
                for claim in claims_list:
                    snak = claim.get("mainsnak", {})
                    val, eid = _extract_value(snak)
                    if eid:
                        entity_ids_to_resolve.append(eid)
                    values.append(val)
                notable[name] = values
            else:
                snak = claims_list[0].get("mainsnak", {})
                val, eid = _extract_value(snak)
                if eid:
                    entity_ids_to_resolve.append(eid)
                notable[name] = val

        # ── Resolve entity IDs to human-readable labels ───────────────────────
        if entity_ids_to_resolve:
            label_map = _resolve_entity_labels(list(set(entity_ids_to_resolve)), language)

            # Replace entity IDs with labels in notable facts
            for key, val in notable.items():
                if isinstance(val, list):
                    notable[key] = [label_map.get(v, v) if isinstance(v, str) and v.startswith("Q") else v for v in val]
                elif isinstance(val, str) and val.startswith("Q") and val in label_map:
                    notable[key] = label_map[val]

        return {
            "found":          True,
            "query":          query,
            "top_entity":     {"id": top_id, "label": label, "description": description},
            "notable_facts":  notable,
            "other_matches":  entities[1:],
            "source":         "Wikidata",
        }

    except requests.RequestException as exc:
        return {"error": f"Wikidata request failed: {exc}"}
