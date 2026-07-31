"""
Bria Exchange — Europe PubMed Central Tool
Searches Europe PMC for biomedical literature via its free REST API.
Good for: biomedical journal articles, preprints, patents, and clinical
          guidelines. Broader than PubMed — includes full-text links and
          covers non-US sources. No API key required.
"""

import requests

EUROPEPMC_API = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
TIMEOUT       = 8


TOOL_DEFINITION = {
    "name": "search_europepmc",
    "description": (
        "Search Europe PubMed Central for biomedical literature including journal "
        "articles, preprints, patents, and clinical guidelines. Broader than PubMed "
        "— includes full-text links and covers non-US sources."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query (e.g. 'COVID-19 long-term symptoms', 'BRCA1 breast cancer risk').",
            },
            "result_type": {
                "type": "string",
                "description": "Level of detail in results: 'core' (default, full metadata) or 'lite' (minimal fields).",
                "default": "core",
            },
            "source": {
                "type": "string",
                "description": (
                    "Filter by record source: 'MED' (MEDLINE/PubMed), 'PMC' (PubMed Central full text), "
                    "'PPR' (preprints), 'PAT' (patents), 'CTX' (clinical trials). Leave empty for all sources."
                ),
            },
        },
        "required": ["query"],
    },
}


def execute_search_europepmc_tool(tool_input: dict) -> dict:
    query       = tool_input.get("query", "").strip()
    result_type = tool_input.get("result_type", "core").strip() or "core"
    src_filter  = tool_input.get("source", "").strip().upper()

    if not query:
        return {"error": "query is required"}

    full_query = query
    if src_filter:
        full_query = f"{query} AND SRC:{src_filter}"

    params = {
        "query":      full_query,
        "format":     "json",
        "pageSize":   5,
        "resultType": result_type,
    }

    try:
        resp = requests.get(EUROPEPMC_API, params=params, timeout=TIMEOUT)
        resp.raise_for_status()

        result_list = resp.json().get("resultList", {}).get("result", [])

        if not result_list:
            return {
                "found":   False,
                "query":   query,
                "message": f"No Europe PMC results found for '{query}'.",
                "source":  "Europe PubMed Central",
            }

        results = []
        for item in result_list:
            record_id     = item.get("id", "")
            record_source = item.get("source", "")
            title         = item.get("title", "")
            author_string = item.get("authorString", "")
            journal_title = item.get("journalTitle", "")
            pub_year      = item.get("pubYear", "")
            citation_count = item.get("citedByCount", 0)
            has_pdf       = item.get("hasPDF", "N") == "Y"
            doi           = item.get("doi", "")
            url           = (
                f"https://europepmc.org/article/{record_source}/{record_id}"
                if record_source and record_id
                else ""
            )

            results.append({
                "id":             record_id,
                "source":         record_source,
                "title":          title,
                "author_string":  author_string,
                "journal_title":  journal_title,
                "pub_year":       pub_year,
                "citation_count": citation_count,
                "has_pdf":        has_pdf,
                "doi":            doi,
                "url":            url,
            })

        return {
            "found":   True,
            "query":   query,
            "results": results,
            "source":  "Europe PubMed Central",
        }

    except requests.RequestException as exc:
        return {"error": f"Europe PMC request failed: {exc}"}
