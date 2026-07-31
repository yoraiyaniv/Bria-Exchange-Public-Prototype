"""
Bria Exchange — PubMed / MEDLINE Tool
Searches biomedical literature via NCBI eutils.
Good for: clinical trial results, drug efficacy, medical statistics,
          disease prevalence, treatment outcomes.
"""

import os
import requests

ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
EFETCH_URL  = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
ESUMMARY_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
NCBI_KEY    = os.environ.get("NCBI_API_KEY", "")
TIMEOUT     = 10


PUBMED_TOOL_DEFINITION = {
    "name": "search_pubmed",
    "description": (
        "Search PubMed / MEDLINE for peer-reviewed biomedical research. "
        "Use for verifying claims about drug efficacy, clinical trial results, "
        "disease statistics, treatment outcomes, and medical facts. "
        "Returns article titles, authors, journal, publication date, and abstracts."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "PubMed search query (e.g. 'semaglutide weight loss efficacy', 'COVID-19 vaccine mRNA safety').",
            },
            "max_results": {
                "type": "integer",
                "description": "Maximum number of articles to return (1–10). Default: 3.",
                "default": 3,
            },
        },
        "required": ["query"],
    },
}


def execute_pubmed_tool(tool_input: dict) -> dict:
    query       = tool_input.get("query", "")
    max_results = min(int(tool_input.get("max_results", 3)), 10)

    if not query:
        return {"error": "query is required"}

    params: dict = {
        "db":      "pubmed",
        "term":    query,
        "retmax":  max_results,
        "retmode": "json",
        "sort":    "relevance",
    }
    if NCBI_KEY:
        params["api_key"] = NCBI_KEY

    try:
        # Search for PMIDs
        search_resp = requests.get(ESEARCH_URL, params=params, timeout=TIMEOUT)
        search_resp.raise_for_status()
        id_list = search_resp.json().get("esearchresult", {}).get("idlist", [])

        if not id_list:
            return {
                "found":   False,
                "query":   query,
                "message": f"No PubMed articles found for '{query}'.",
                "source":  "PubMed / MEDLINE",
            }

        # Fetch summaries
        summary_params: dict = {
            "db":      "pubmed",
            "id":      ",".join(id_list),
            "retmode": "json",
        }
        if NCBI_KEY:
            summary_params["api_key"] = NCBI_KEY

        summary_resp = requests.get(ESUMMARY_URL, params=summary_params, timeout=TIMEOUT)
        summary_resp.raise_for_status()
        result_data = summary_resp.json().get("result", {})

        articles = []
        for pmid in id_list:
            doc = result_data.get(pmid, {})
            if not doc:
                continue
            authors = [a.get("name", "") for a in (doc.get("authors") or [])[:3]]
            articles.append({
                "pmid":      pmid,
                "title":     doc.get("title", ""),
                "authors":   authors,
                "journal":   doc.get("fulljournalname", doc.get("source", "")),
                "pub_date":  doc.get("pubdate", ""),
                "url":       f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
            })

        return {
            "found":    True,
            "query":    query,
            "articles": articles,
            "source":   "PubMed / MEDLINE (NCBI)",
        }

    except requests.RequestException as exc:
        return {"error": f"PubMed request failed: {exc}"}
