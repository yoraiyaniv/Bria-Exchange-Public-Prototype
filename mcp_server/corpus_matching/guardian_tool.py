"""
Bria Exchange — The Guardian Tool
Searches The Guardian's article archive via the open Content API.
Good for: news events, published statements, editorial facts, company news.
"""

import os
import requests

GUARDIAN_API  = "https://content.guardianapis.com/search"
GUARDIAN_KEY  = os.environ.get("GUARDIAN_API_KEY", "test")  # 'test' key works with rate limits
TIMEOUT       = 8


GUARDIAN_TOOL_DEFINITION = {
    "name": "search_guardian",
    "description": (
        "Search The Guardian's article archive for news facts, published statements, "
        "and editorial claims. Use for verifying claims about world events, company news, "
        "political facts, and anything covered by quality journalism. "
        "Returns article headlines, dates, and section context."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search terms (e.g. 'Evident AI Index ranking 2024', 'OpenAI revenue').",
            },
            "from_date": {
                "type": "string",
                "description": "Start date filter in YYYY-MM-DD format (optional).",
            },
            "to_date": {
                "type": "string",
                "description": "End date filter in YYYY-MM-DD format (optional).",
            },
        },
        "required": ["query"],
    },
}


def execute_guardian_tool(tool_input: dict) -> dict:
    query     = tool_input.get("query", "")
    from_date = tool_input.get("from_date")
    to_date   = tool_input.get("to_date")

    if not query:
        return {"error": "query is required"}

    params = {
        "q":        query,
        "api-key":  GUARDIAN_KEY,
        "page-size": 5,
        "show-fields": "trailText,bodyText",
        "order-by": "relevance",
    }
    if from_date:
        params["from-date"] = from_date
    if to_date:
        params["to-date"] = to_date

    try:
        resp = requests.get(GUARDIAN_API, params=params, timeout=TIMEOUT)
        resp.raise_for_status()
        data    = resp.json().get("response", {})
        results = data.get("results", [])

        if not results:
            return {
                "found":   False,
                "query":   query,
                "message": f"No Guardian articles found for '{query}'.",
                "source":  "The Guardian",
            }

        articles = []
        for r in results:
            fields = r.get("fields") or {}
            body = fields.get("bodyText", "")
            articles.append({
                "headline":   r.get("webTitle"),
                "date":       r.get("webPublicationDate", "")[:10],
                "section":    r.get("sectionName"),
                "url":        r.get("webUrl"),
                "summary":    fields.get("trailText", ""),
                "body_extract": body[:1500] if body else "",
            })

        return {
            "found":    True,
            "query":    query,
            "total":    data.get("total", len(articles)),
            "articles": articles,
            "source":   "The Guardian",
        }

    except requests.RequestException as exc:
        return {"error": f"Guardian request failed: {exc}"}
