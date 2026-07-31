"""
Bria Exchange — arXiv Tool
Searches arXiv for preprints via the public Atom XML feed.
Good for: verifying cutting-edge research claims before peer review,
          finding paper existence, authors, abstracts, and submission dates
          across physics, CS, math, biology, and economics.
"""

import requests
import xml.etree.ElementTree as ET

ARXIV_API = "http://export.arxiv.org/api/query"
TIMEOUT   = 8

_NS = "{http://www.w3.org/2005/Atom}"


TOOL_DEFINITION = {
    "name": "search_arxiv",
    "description": (
        "Search arXiv for preprints in physics, CS, math, biology, and economics. "
        "Use to verify cutting-edge research claims before peer review, find paper "
        "existence, authors, abstracts, and submission dates."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Title, author, or topic query (e.g. 'attention is all you need Vaswani', 'CRISPR gene editing').",
            },
            "max_results": {
                "type": "integer",
                "description": "Maximum number of results to return (1–10). Default: 5.",
                "default": 5,
            },
            "category": {
                "type": "string",
                "description": (
                    "Optional arXiv category filter (e.g. 'cs.AI', 'q-bio', 'math.CO', 'physics.hep-th'). "
                    "Leave empty to search all categories."
                ),
            },
        },
        "required": ["query"],
    },
}


def execute_search_arxiv_tool(tool_input: dict) -> dict:
    query       = tool_input.get("query", "").strip()
    max_results = min(int(tool_input.get("max_results", 5)), 10)
    category    = tool_input.get("category", "").strip()

    if not query:
        return {"error": "query is required"}

    search_query = f"all:{query}"
    if category:
        search_query = f"cat:{category} AND all:{query}"

    try:
        resp = requests.get(
            ARXIV_API,
            params={
                "search_query": search_query,
                "max_results":  max_results,
                "sortBy":       "relevance",
            },
            timeout=TIMEOUT,
        )
        resp.raise_for_status()

        root    = ET.fromstring(resp.content)
        entries = root.findall(f"{_NS}entry")

        if not entries:
            return {
                "found":   False,
                "query":   query,
                "message": f"No arXiv preprints found for '{query}'.",
                "source":  "arXiv",
            }

        results = []
        for entry in entries:
            arxiv_id   = (entry.findtext(f"{_NS}id") or "").split("/abs/")[-1]
            title      = (entry.findtext(f"{_NS}title") or "").strip().replace("\n", " ")
            abstract   = (entry.findtext(f"{_NS}summary") or "").strip().replace("\n", " ")[:300]
            submitted  = entry.findtext(f"{_NS}published") or ""

            authors = [
                (a.findtext(f"{_NS}name") or "").strip()
                for a in entry.findall(f"{_NS}author")
            ][:3]

            categories = [
                tag.get("term", "")
                for tag in entry.findall("{http://arxiv.org/schemas/atom}primary_category")
            ]
            # Also collect all subject tags
            for tag in entry.findall("{http://www.w3.org/2005/Atom}category"):
                term = tag.get("term", "")
                if term and term not in categories:
                    categories.append(term)

            url = f"https://arxiv.org/abs/{arxiv_id}" if arxiv_id else ""

            results.append({
                "arxiv_id":   arxiv_id,
                "title":      title,
                "authors":    authors,
                "abstract":   abstract,
                "submitted":  submitted,
                "categories": categories,
                "url":        url,
            })

        return {
            "found":   True,
            "query":   query,
            "results": results,
            "source":  "arXiv",
        }

    except requests.RequestException as exc:
        return {"error": f"arXiv request failed: {exc}"}
