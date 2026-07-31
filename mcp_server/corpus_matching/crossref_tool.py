"""
Bria Exchange — CrossRef Tool
Searches CrossRef for academic citation metadata and DOI resolution.
Good for: verifying publication claims, citation counts, journal facts,
          paper existence, and author affiliations.
"""

import requests

CROSSREF_API = "https://api.crossref.org/works"
TIMEOUT      = 8


CROSSREF_TOOL_DEFINITION = {
    "name": "search_crossref",
    "description": (
        "Search CrossRef for academic publication metadata. "
        "Use for verifying claims about research papers, citation counts, "
        "journal publications, author affiliations, and DOI-linked content. "
        "Covers journals, conference proceedings, and books."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Title, author, or topic query (e.g. 'transformer attention is all you need Vaswani').",
            },
            "doi": {
                "type": "string",
                "description": "Specific DOI to look up directly (e.g. '10.1145/3442188.3445922'). If provided, query is ignored.",
            },
        },
        "required": ["query"],
    },
}


def execute_crossref_tool(tool_input: dict) -> dict:
    query = tool_input.get("query", "")
    doi   = tool_input.get("doi", "").strip()

    try:
        if doi:
            # Direct DOI lookup
            resp = requests.get(
                f"{CROSSREF_API}/{doi}",
                timeout=TIMEOUT,
                headers={"User-Agent": "BriaExchange/1.0 (mailto:verify@briaexchange.com)"},
            )
            if resp.status_code == 404:
                return {"found": False, "doi": doi, "message": "DOI not found in CrossRef.", "source": "CrossRef"}
            resp.raise_for_status()
            item = resp.json().get("message", {})
            return {
                "found":     True,
                "doi":       doi,
                "result":    _format_work(item),
                "source":    "CrossRef",
            }

        if not query:
            return {"error": "query or doi is required"}

        resp = requests.get(
            CROSSREF_API,
            params={"query": query, "rows": 5, "select": "DOI,title,author,published,container-title,is-referenced-by-count,type"},
            timeout=TIMEOUT,
            headers={"User-Agent": "BriaExchange/1.0 (mailto:verify@briaexchange.com)"},
        )
        resp.raise_for_status()
        items = resp.json().get("message", {}).get("items", [])

        if not items:
            return {
                "found":   False,
                "query":   query,
                "message": f"No CrossRef works found for '{query}'.",
                "source":  "CrossRef",
            }

        return {
            "found":   True,
            "query":   query,
            "results": [_format_work(i) for i in items],
            "source":  "CrossRef",
        }

    except requests.RequestException as exc:
        return {"error": f"CrossRef request failed: {exc}"}


def _format_work(item: dict) -> dict:
    title   = (item.get("title") or [""])[0]
    authors = [
        f"{a.get('given', '')} {a.get('family', '')}".strip()
        for a in (item.get("author") or [])[:3]
    ]
    journal    = (item.get("container-title") or [""])[0]
    published  = item.get("published", {}).get("date-parts", [[]])[0]
    year       = published[0] if published else None
    citations  = item.get("is-referenced-by-count", 0)
    return {
        "doi":       item.get("DOI"),
        "title":     title,
        "authors":   authors,
        "journal":   journal,
        "year":      year,
        "citations": citations,
        "type":      item.get("type"),
    }
