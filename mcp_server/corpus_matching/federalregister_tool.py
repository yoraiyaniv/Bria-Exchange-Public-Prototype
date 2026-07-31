"""
Bria Exchange — US Federal Register Tool
Searches the Federal Register for US government regulations, proposed rules,
executive orders, and agency notices.
Good for: verifying claims about regulatory actions, rule-making,
          agency guidance, and US government policy decisions.
"""

import requests

FEDERALREGISTER_API = "https://www.federalregister.gov/api/v1"
TIMEOUT             = 8


TOOL_DEFINITION = {
    "name": "search_federal_register",
    "description": (
        "Search the US Federal Register for government regulations, proposed rules, "
        "executive orders, and agency notices. Use to verify claims about regulatory "
        "actions, rule-making, and US government policy."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search term for the regulation or policy topic (e.g. 'clean air standards', 'cryptocurrency exchange').",
            },
            "agency": {
                "type": "string",
                "description": (
                    "Optional agency slug to filter results "
                    "(e.g. 'environmental-protection-agency', 'securities-and-exchange-commission'). "
                    "Leave empty to search all agencies."
                ),
            },
            "type": {
                "type": "string",
                "description": "Document type filter: 'Rule', 'Proposed Rule', 'Notice', or 'Presidential Document'.",
            },
            "from_date": {
                "type": "string",
                "description": "Start of publication date range in YYYY-MM-DD format.",
            },
            "to_date": {
                "type": "string",
                "description": "End of publication date range in YYYY-MM-DD format.",
            },
        },
        "required": ["query"],
    },
}


def execute_search_federal_register_tool(tool_input: dict) -> dict:
    query     = tool_input.get("query", "").strip()
    agency    = tool_input.get("agency", "").strip()
    doc_type  = tool_input.get("type", "").strip()
    from_date = tool_input.get("from_date", "").strip()
    to_date   = tool_input.get("to_date", "").strip()

    if not query:
        return {"error": "query is required"}

    params: list = [
        ("conditions[term]", query),
        ("per_page",         5),
        ("fields[]",         "document_number"),
        ("fields[]",         "title"),
        ("fields[]",         "agency_names"),
        ("fields[]",         "type"),
        ("fields[]",         "publication_date"),
        ("fields[]",         "abstract"),
        ("fields[]",         "html_url"),
    ]
    if agency:
        params.append(("conditions[agencies][]", agency))
    if doc_type:
        params.append(("conditions[type][]", doc_type))
    if from_date:
        params.append(("conditions[publication_date][gte]", from_date))
    if to_date:
        params.append(("conditions[publication_date][lte]", to_date))

    try:
        resp = requests.get(
            f"{FEDERALREGISTER_API}/documents.json",
            params=params,
            timeout=TIMEOUT,
            headers={"User-Agent": "BriaExchange/1.0 (fact-verification)"},
        )
        resp.raise_for_status()
        data = resp.json()

        documents = data.get("results", [])
        if not documents:
            return {
                "found":   False,
                "query":   query,
                "message": f"No Federal Register documents found for '{query}'.",
                "source":  "US Federal Register",
            }

        results = []
        for doc in documents:
            abstract_raw = doc.get("abstract") or ""
            results.append({
                "document_number": doc.get("document_number", ""),
                "title":           doc.get("title", ""),
                "agencies":        doc.get("agency_names", []),
                "type":            doc.get("type", ""),
                "publication_date": doc.get("publication_date", ""),
                "abstract":        abstract_raw[:200],
                "url":             doc.get("html_url", ""),
            })

        return {
            "found":   True,
            "query":   query,
            "results": results,
            "source":  "US Federal Register",
        }

    except requests.RequestException as exc:
        return {"error": f"Federal Register request failed: {exc}"}
