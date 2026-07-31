"""
Bria Exchange — OpenAlex Tool
Searches the OpenAlex open catalogue of scholarly works via its free REST API.
Good for: verifying publication claims, citation impact, institutional
          affiliations, and research output across all academic disciplines.
          Covers 250M+ scholarly works with no API key required.
"""

import requests

OPENALEX_API = "https://api.openalex.org/works"
TIMEOUT      = 8

_HEADERS = {"User-Agent": "BriaExchange/1.0 (mailto:verify@briaexchange.com)"}


TOOL_DEFINITION = {
    "name": "search_openalex",
    "description": (
        "Search OpenAlex for academic works, authors, institutions, and citation counts. "
        "Use to verify publication claims, citation impact, institutional affiliations, "
        "and research output across all disciplines. Covers 250M+ scholarly works."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Title, author, or topic query (e.g. 'mRNA vaccine efficacy Pfizer', 'large language models scaling laws').",
            },
            "from_year": {
                "type": "integer",
                "description": "Filter results published from this year onward (e.g. 2018).",
            },
            "to_year": {
                "type": "integer",
                "description": "Filter results published up to and including this year (e.g. 2023).",
            },
            "type": {
                "type": "string",
                "description": "Filter by work type (e.g. 'article', 'book', 'dataset', 'preprint'). Leave empty for all types.",
            },
        },
        "required": ["query"],
    },
}


def execute_search_openalex_tool(tool_input: dict) -> dict:
    query     = tool_input.get("query", "").strip()
    from_year = tool_input.get("from_year")
    to_year   = tool_input.get("to_year")
    work_type = tool_input.get("type", "").strip()

    if not query:
        return {"error": "query is required"}

    params: dict = {
        "search":   query,
        "per-page": 5,
        "select":   "id,title,authorships,publication_year,cited_by_count,type,doi,primary_location",
    }

    filters = []
    if from_year and to_year:
        filters.append(f"publication_year:{from_year}-{to_year}")
    elif from_year:
        filters.append(f"publication_year:{from_year}-")
    elif to_year:
        filters.append(f"publication_year:-{to_year}")
    if work_type:
        filters.append(f"type:{work_type}")
    if filters:
        params["filter"] = ",".join(filters)

    try:
        resp = requests.get(OPENALEX_API, params=params, headers=_HEADERS, timeout=TIMEOUT)
        resp.raise_for_status()

        items = resp.json().get("results", [])

        if not items:
            return {
                "found":   False,
                "query":   query,
                "message": f"No OpenAlex works found for '{query}'.",
                "source":  "OpenAlex",
            }

        results = []
        for item in items:
            openalex_id = item.get("id", "")
            title       = item.get("title") or ""
            year        = item.get("publication_year")
            citations   = item.get("cited_by_count", 0)
            work_type_r = item.get("type", "")
            doi         = item.get("doi") or ""

            authors = [
                (a.get("author") or {}).get("display_name", "")
                for a in (item.get("authorships") or [])[:3]
            ]

            primary_loc  = item.get("primary_location") or {}
            src_obj      = primary_loc.get("source") or {}
            src_name     = src_obj.get("display_name") or ""

            url = f"https://openalex.org/{openalex_id.split('/')[-1]}" if openalex_id else ""

            results.append({
                "openalex_id": openalex_id,
                "title":       title,
                "authors":     authors,
                "year":        year,
                "citations":   citations,
                "type":        work_type_r,
                "doi":         doi,
                "source":      src_name,
                "url":         url,
            })

        return {
            "found":   True,
            "query":   query,
            "results": results,
            "source":  "OpenAlex",
        }

    except requests.RequestException as exc:
        return {"error": f"OpenAlex request failed: {exc}"}
