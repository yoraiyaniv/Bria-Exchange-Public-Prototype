"""
Bria Exchange — Semantic Scholar Tool
Searches academic papers via the Allen Institute's Semantic Scholar API.
Good for: AI/ML research claims, citation counts, paper existence,
          author h-index, and research trends.
"""

import os
import requests
from dotenv import load_dotenv

load_dotenv()

SS_API   = "https://api.semanticscholar.org/graph/v1"
SS_KEY   = os.environ.get("SEMANTIC_SCHOLAR_API_KEY", "")
TIMEOUT  = 10


SEMANTICSCHOLAR_TOOL_DEFINITION = {
    "name": "search_semantic_scholar",
    "description": (
        "Search Semantic Scholar for academic papers with citation graphs. "
        "Use for verifying claims about AI/ML research, paper citations, "
        "author publications, research benchmarks, and model performance claims. "
        "Especially strong for computer science and AI literature."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Paper title, topic, or author query (e.g. 'GPT-4 technical report OpenAI 2023').",
            },
            "fields": {
                "type": "string",
                "description": "Comma-separated fields to return. Default: 'title,authors,year,citationCount,abstract,venue'.",
                "default": "title,authors,year,citationCount,abstract,venue",
            },
        },
        "required": ["query"],
    },
}


def execute_semanticscholar_tool(tool_input: dict) -> dict:
    query  = tool_input.get("query", "")
    fields = tool_input.get("fields", "title,authors,year,citationCount,abstract,venue")

    if not query:
        return {"error": "query is required"}

    try:
        headers = {"User-Agent": "BriaExchange/1.0"}
        if SS_KEY:
            headers["x-api-key"] = SS_KEY
        resp = requests.get(
            f"{SS_API}/paper/search",
            params={"query": query, "limit": 5, "fields": fields},
            timeout=TIMEOUT,
            headers=headers,
        )
        resp.raise_for_status()
        data  = resp.json()
        papers = data.get("data", [])

        if not papers:
            return {
                "found":   False,
                "query":   query,
                "message": f"No papers found for '{query}' on Semantic Scholar.",
                "source":  "Semantic Scholar",
            }

        results = []
        for p in papers:
            authors = [a.get("name", "") for a in (p.get("authors") or [])[:3]]
            results.append({
                "paper_id":   p.get("paperId"),
                "title":      p.get("title"),
                "authors":    authors,
                "year":       p.get("year"),
                "venue":      p.get("venue"),
                "citations":  p.get("citationCount", 0),
                "abstract":   (p.get("abstract") or "")[:300],
                "url":        f"https://www.semanticscholar.org/paper/{p.get('paperId')}",
            })

        return {
            "found":   True,
            "query":   query,
            "papers":  results,
            "source":  "Semantic Scholar (Allen Institute for AI)",
        }

    except requests.RequestException as exc:
        return {"error": f"Semantic Scholar request failed: {exc}"}
