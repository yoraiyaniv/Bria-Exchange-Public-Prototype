"""
Bria Exchange — CourtListener Tool
Searches CourtListener for US court opinions, dockets, and case law.
Good for: verifying legal claims about court rulings, case outcomes,
          precedents, ongoing litigation, and federal/state court decisions.
"""

import requests

COURTLISTENER_API = "https://www.courtlistener.com/api/rest/v4"
TIMEOUT           = 8


TOOL_DEFINITION = {
    "name": "search_courtlistener",
    "description": (
        "Search CourtListener for US court opinions, dockets, and case law. "
        "Use to verify legal claims about court rulings, case outcomes, precedents, "
        "and ongoing litigation."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query — case name, legal issue, statute, or topic (e.g. 'Section 230 immunity', 'Roe v Wade').",
            },
            "court": {
                "type": "string",
                "description": (
                    "Optional court slug to limit results (e.g. 'scotus' for Supreme Court, "
                    "'ca9' for 9th Circuit, 'dcd' for D.C. District). Leave empty to search all courts."
                ),
            },
            "type": {
                "type": "string",
                "description": "Result type: 'o' for opinions (default), 'd' for dockets.",
                "default": "o",
            },
        },
        "required": ["query"],
    },
}


def execute_search_courtlistener_tool(tool_input: dict) -> dict:
    query       = tool_input.get("query", "").strip()
    court       = tool_input.get("court", "").strip()
    result_type = tool_input.get("type", "o").strip() or "o"

    if not query:
        return {"error": "query is required"}

    params: dict = {
        "q":         query,
        "type":      result_type,
        "page_size": 5,
        "format":    "json",
    }
    if court:
        params["court"] = court

    try:
        resp = requests.get(
            f"{COURTLISTENER_API}/search/",
            params=params,
            timeout=TIMEOUT,
            headers={"User-Agent": "BriaExchange/1.0 (fact-verification)"},
        )
        resp.raise_for_status()
        data = resp.json()

        hits = data.get("results", [])
        if not hits:
            return {
                "found":   False,
                "query":   query,
                "message": f"No CourtListener results found for '{query}'.",
                "source":  "CourtListener",
            }

        results = []
        for hit in hits:
            absolute_url = hit.get("absolute_url", "")
            url          = f"https://www.courtlistener.com{absolute_url}" if absolute_url else ""

            snippet_raw  = hit.get("snippet", "") or ""
            snippet      = snippet_raw[:200] if snippet_raw else ""

            results.append({
                "case_name":  hit.get("caseName") or hit.get("case_name", ""),
                "court":      hit.get("court", ""),
                "date_filed": hit.get("dateFiled") or hit.get("date_filed", ""),
                "status":     hit.get("status", ""),
                "url":        url,
                "snippet":    snippet,
            })

        return {
            "found":   True,
            "query":   query,
            "results": results,
            "source":  "CourtListener",
        }

    except requests.RequestException as exc:
        return {"error": f"CourtListener request failed: {exc}"}
