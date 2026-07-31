"""
Bria Exchange — Congress.gov Tool
Searches Congress.gov for US bills, resolutions, and members of Congress.
Good for: verifying claims about legislation, bill status, congressional actions,
          sponsors, and legislative history.
Requires a Congress.gov API key (CONGRESS_API_KEY env var).
"""

import os
import requests
from dotenv import load_dotenv

load_dotenv()

CONGRESS_BASE_URL = "https://api.congress.gov/v3"
CONGRESS_API_KEY  = os.environ.get("CONGRESS_API_KEY", "")
TIMEOUT           = 10


TOOL_DEFINITION = {
    "name": "search_congress",
    "description": (
        "Search Congress.gov for US bills, resolutions, and members of Congress. "
        "Use to verify claims about legislation, bill status, congressional actions, "
        "sponsors, and legislative history."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search term for bills or members (e.g. 'infrastructure investment', 'Nancy Pelosi').",
            },
            "congress": {
                "type": "integer",
                "description": "Congress number (e.g. 118 for 2023-2024, 117 for 2021-2022).",
            },
            "search_type": {
                "type": "string",
                "enum": ["bill", "member"],
                "description": "Type of search. Default: bill.",
            },
            "bill_type": {
                "type": "string",
                "enum": ["hr", "s", "hjres", "sjres"],
                "description": "Bill type filter. hr=House bill, s=Senate bill.",
            },
        },
        "required": ["query"],
    },
}


def execute_congress_tool(tool_input: dict) -> dict:
    if not CONGRESS_API_KEY:
        return {"error": "CONGRESS_API_KEY not set"}

    query       = tool_input.get("query", "").strip()
    congress    = tool_input.get("congress")
    search_type = tool_input.get("search_type", "bill")
    bill_type   = tool_input.get("bill_type")

    if not query:
        return {"error": "query is required"}

    headers = {"Accept": "application/json"}

    try:
        if search_type == "member":
            return _search_members(query, headers)
        else:
            return _search_bills(query, congress, bill_type, headers)

    except requests.RequestException as exc:
        return {"error": f"Congress.gov request failed: {exc}"}


def _search_bills(query: str, congress: int | None, bill_type: str | None, headers: dict) -> dict:
    params: dict = {
        "query":   query,
        "offset":  0,
        "limit":   5,
        "api_key": CONGRESS_API_KEY,
    }
    if congress is not None:
        params["congress"] = congress

    resp = requests.get(
        f"{CONGRESS_BASE_URL}/bill",
        params=params,
        headers=headers,
        timeout=TIMEOUT,
    )
    resp.raise_for_status()
    data  = resp.json()
    bills = data.get("bills", [])

    if bill_type:
        bills = [b for b in bills if b.get("type", "").lower() == bill_type.lower()]

    if not bills:
        return {
            "found":   False,
            "query":   query,
            "message": f"No bills found for '{query}'.",
            "source":  "Congress.gov",
        }

    results = []
    for bill in bills:
        latest_action = bill.get("latestAction") or {}
        results.append({
            "title":         bill.get("title", ""),
            "congress":      bill.get("congress", ""),
            "bill_type":     bill.get("type", ""),
            "bill_number":   bill.get("number", ""),
            "latest_action": latest_action.get("text", ""),
            "action_date":   latest_action.get("actionDate", ""),
            "sponsor":       bill.get("sponsor", {}),
            "url":           bill.get("url", ""),
        })

    return {
        "found":   True,
        "query":   query,
        "results": results,
        "source":  "Congress.gov",
    }


def _search_members(query: str, headers: dict) -> dict:
    params: dict = {
        "name":    query,
        "offset":  0,
        "limit":   5,
        "api_key": CONGRESS_API_KEY,
    }

    resp = requests.get(
        f"{CONGRESS_BASE_URL}/member",
        params=params,
        headers=headers,
        timeout=TIMEOUT,
    )
    resp.raise_for_status()
    data    = resp.json()
    members = data.get("members", [])

    if not members:
        return {
            "found":   False,
            "query":   query,
            "message": f"No members of Congress found for '{query}'.",
            "source":  "Congress.gov",
        }

    results = []
    for member in members:
        results.append({
            "name":    member.get("name", ""),
            "state":   member.get("state", ""),
            "party":   member.get("partyName", ""),
            "chamber": member.get("chamber", ""),
            "url":     member.get("url", ""),
        })

    return {
        "found":   True,
        "query":   query,
        "results": results,
        "source":  "Congress.gov",
    }


if __name__ == "__main__":
    result = execute_congress_tool({"query": "infrastructure", "search_type": "bill"})
    print(result)
