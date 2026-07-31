"""
Bria Exchange — OpenFDA Tool
Queries the FDA's open data API for drug approvals, adverse events,
drug labels, and enforcement actions.
"""

import requests

OPENFDA_BASE = "https://api.fda.gov"
TIMEOUT      = 8


OPENFDA_TOOL_DEFINITION = {
    "name": "search_openfda",
    "description": (
        "Search FDA data for drug approvals, adverse event reports, drug labels, "
        "and enforcement/recall actions. "
        "Use for verifying claims about drug approval status, safety signals, "
        "labeling information, and FDA enforcement actions."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Drug name, ingredient, or search term (e.g. 'semaglutide', 'Ozempic', 'Pfizer').",
            },
            "endpoint": {
                "type": "string",
                "description": "FDA data type: 'drug_event' (adverse events), 'drug_label' (labeling), 'drug_nda' (approvals), 'drug_enforcement' (recalls). Default: 'drug_label'.",
                "enum": ["drug_event", "drug_label", "drug_nda", "drug_enforcement"],
                "default": "drug_label",
            },
        },
        "required": ["query"],
    },
}

_ENDPOINT_PATHS = {
    "drug_event":       "/drug/event.json",
    "drug_label":       "/drug/label.json",
    "drug_nda":         "/drug/nda.json",
    "drug_enforcement": "/drug/enforcement.json",
}

_SEARCH_FIELDS = {
    "drug_event":       "patient.drug.medicinalproduct",
    "drug_label":       "openfda.brand_name",
    "drug_nda":         "openfda.brand_name",
    "drug_enforcement": "product_description",
}


def execute_openfda_tool(tool_input: dict) -> dict:
    query    = tool_input.get("query", "")
    endpoint = tool_input.get("endpoint", "drug_label")

    if not query:
        return {"error": "query is required"}
    if endpoint not in _ENDPOINT_PATHS:
        endpoint = "drug_label"

    path         = _ENDPOINT_PATHS[endpoint]
    search_field = _SEARCH_FIELDS[endpoint]
    url          = f"{OPENFDA_BASE}{path}"

    try:
        resp = requests.get(
            url,
            params={"search": f'{search_field}:"{query}"', "limit": 3},
            timeout=TIMEOUT,
        )

        # 404 = no results, not an error
        if resp.status_code == 404:
            return {
                "found":    False,
                "query":    query,
                "endpoint": endpoint,
                "message":  f"No FDA {endpoint} records found for '{query}'.",
                "source":   "OpenFDA",
            }

        resp.raise_for_status()
        data    = resp.json()
        results = data.get("results", [])

        if not results:
            return {
                "found":    False,
                "query":    query,
                "endpoint": endpoint,
                "message":  f"No FDA {endpoint} records found for '{query}'.",
                "source":   "OpenFDA",
            }

        # Shape output by endpoint type
        formatted = []
        for r in results:
            ofda = r.get("openfda", {})
            if endpoint == "drug_label":
                formatted.append({
                    "brand_name":    (ofda.get("brand_name") or [None])[0],
                    "generic_name":  (ofda.get("generic_name") or [None])[0],
                    "manufacturer":  (ofda.get("manufacturer_name") or [None])[0],
                    "indications":   (r.get("indications_and_usage") or [None])[0],
                    "warnings":      (r.get("warnings") or [None])[0],
                })
            elif endpoint == "drug_nda":
                formatted.append({
                    "brand_name":    (ofda.get("brand_name") or [None])[0],
                    "application_number": (ofda.get("application_number") or [None])[0],
                    "manufacturer":  (ofda.get("manufacturer_name") or [None])[0],
                    "route":         (ofda.get("route") or [None])[0],
                })
            elif endpoint == "drug_enforcement":
                formatted.append({
                    "product":       r.get("product_description", "")[:200],
                    "reason":        r.get("reason_for_recall", ""),
                    "status":        r.get("status"),
                    "recall_date":   r.get("recall_initiation_date"),
                    "firm":          r.get("recalling_firm"),
                })
            else:
                formatted.append({"raw": str(r)[:300]})

        return {
            "found":    True,
            "query":    query,
            "endpoint": endpoint,
            "results":  formatted,
            "source":   "OpenFDA (FDA)",
        }

    except requests.RequestException as exc:
        return {"error": f"OpenFDA request failed: {exc}"}
