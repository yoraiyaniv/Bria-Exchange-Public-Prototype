"""
Bria Exchange — New York Times Tool
Searches NYT article archive via the Article Search API.
Good for: news events, published statements, editorial facts.
Requires a free NYT API key (NYTIMES_API_KEY env var).
"""

import os
import requests
from dotenv import load_dotenv

load_dotenv()

NYT_API      = "https://api.nytimes.com/svc/search/v2/articlesearch.json"
NYT_KEY      = os.environ.get("NYTIMES_API_KEY", "")
TIMEOUT      = 8


NYTIMES_TOOL_DEFINITION = {
    "name": "search_nytimes",
    "description": (
        "Search The New York Times article archive for news facts and published statements. "
        "Use for verifying claims about world events, business news, and editorial content. "
        "Returns article headlines, dates, abstracts, and section context."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search terms (e.g. 'AI benchmark ranking 2024', 'Apple earnings').",
            },
            "begin_date": {
                "type": "string",
                "description": "Start date in YYYYMMDD format (optional).",
            },
            "end_date": {
                "type": "string",
                "description": "End date in YYYYMMDD format (optional).",
            },
        },
        "required": ["query"],
    },
}


def execute_nytimes_tool(tool_input: dict) -> dict:
    if not NYT_KEY:
        return {"error": "NYTIMES_API_KEY not configured"}

    query      = tool_input.get("query", "")
    begin_date = tool_input.get("begin_date")
    end_date   = tool_input.get("end_date")

    if not query:
        return {"error": "query is required"}

    params: dict = {
        "q":       query,
        "api-key": NYT_KEY,
        "sort":    "relevance",
        "fl":      "headline,abstract,pub_date,section_name,web_url",
    }
    if begin_date:
        params["begin_date"] = begin_date
    if end_date:
        params["end_date"] = end_date

    try:
        resp = requests.get(NYT_API, params=params, timeout=TIMEOUT)
        resp.raise_for_status()
        data    = resp.json().get("response", {})
        docs    = data.get("docs", [])

        if not docs:
            return {
                "found":   False,
                "query":   query,
                "message": f"No NYT articles found for '{query}'.",
                "source":  "New York Times",
            }

        articles = [
            {
                "headline": (d.get("headline") or {}).get("main", ""),
                "abstract": d.get("abstract", ""),
                "date":     d.get("pub_date", "")[:10],
                "section":  d.get("section_name", ""),
                "url":      d.get("web_url", ""),
            }
            for d in docs[:5]
        ]

        return {
            "found":    True,
            "query":    query,
            "total":    data.get("meta", {}).get("hits", len(articles)),
            "articles": articles,
            "source":   "New York Times",
        }

    except requests.RequestException as exc:
        return {"error": f"NYT request failed: {exc}"}
