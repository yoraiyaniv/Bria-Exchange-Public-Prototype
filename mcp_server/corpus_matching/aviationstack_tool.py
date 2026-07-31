"""
Bria Exchange — AviationStack Tool
Searches aviation data for flights, airports, and airlines.
Good for: verifying claims about flight routes, airline operations, airport info.
Free tier: HTTP only, 100 requests/month. Use sparingly.
Requires AVIATIONSTACK_API_KEY env var.
"""

import os
import requests
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "http://api.aviationstack.com/v1"  # HTTP only on free tier
API_KEY = os.environ.get("AVIATIONSTACK_API_KEY", "")
TIMEOUT = 10

TOOL_DEFINITION = {
    "name": "search_aviationstack",
    "description": (
        "Search aviation data for flights, airports, and airlines. Use to verify "
        "claims about flight routes, airline operations, and airport information. "
        "Note: limited to 100 requests/month — use only for aviation-specific claims."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "query_type": {
                "type": "string",
                "enum": ["flight", "airport", "airline"],
                "description": "Type of aviation data to search.",
            },
            "flight_iata": {
                "type": "string",
                "description": "Flight IATA code (e.g. 'AA100', 'UA232'). Used when query_type=flight.",
            },
            "airline_name": {
                "type": "string",
                "description": "Airline name to search (e.g. 'American Airlines'). Used when query_type=airline.",
            },
            "airport_search": {
                "type": "string",
                "description": "Airport name or IATA code (e.g. 'JFK', 'Heathrow'). Used when query_type=airport.",
            },
            "flight_date": {
                "type": "string",
                "description": "Flight date in YYYY-MM-DD format.",
            },
        },
        "required": ["query_type"],
    },
}


def execute_aviationstack_tool(tool_input: dict) -> dict:
    if not API_KEY:
        return {"error": "AVIATIONSTACK_API_KEY not set"}

    query_type = tool_input.get("query_type", "").strip()
    if query_type not in ("flight", "airport", "airline"):
        return {"error": "query_type must be 'flight', 'airport', or 'airline'"}

    try:
        if query_type == "flight":
            return _search_flights(tool_input)
        elif query_type == "airport":
            return _search_airports(tool_input)
        else:
            return _search_airlines(tool_input)
    except requests.RequestException as exc:
        return {"error": f"AviationStack request failed: {exc}"}
    except Exception as exc:
        return {"error": f"AviationStack error: {exc}"}


def _search_flights(tool_input: dict) -> dict:
    params = {"access_key": API_KEY, "limit": 5}
    flight_iata = tool_input.get("flight_iata", "").strip()
    flight_date = tool_input.get("flight_date", "").strip()

    if flight_iata:
        params["flight_iata"] = flight_iata
    if flight_date:
        params["flight_date"] = flight_date

    resp = requests.get(f"{BASE_URL}/flights", params=params, timeout=TIMEOUT)
    resp.raise_for_status()
    data = resp.json()

    items = data.get("data") or []
    if not items:
        return {
            "found": False,
            "query_type": "flight",
            "message": "No flights found.",
            "source": "AviationStack",
        }

    results = []
    for f in items[:5]:
        dep = f.get("departure") or {}
        arr = f.get("arrival") or {}
        airline = f.get("airline") or {}
        flight = f.get("flight") or {}
        results.append({
            "flight_date": f.get("flight_date"),
            "flight_status": f.get("flight_status"),
            "airline": airline.get("name"),
            "flight_iata": flight.get("iata"),
            "departure_airport": dep.get("airport"),
            "departure_iata": dep.get("iata"),
            "departure_scheduled": dep.get("scheduled"),
            "arrival_airport": arr.get("airport"),
            "arrival_iata": arr.get("iata"),
            "arrival_scheduled": arr.get("scheduled"),
        })

    return {
        "found": True,
        "query_type": "flight",
        "results": results,
        "source": "AviationStack",
    }


def _search_airports(tool_input: dict) -> dict:
    params = {"access_key": API_KEY, "limit": 5}
    search = tool_input.get("airport_search", "").strip()
    if search:
        params["search"] = search

    resp = requests.get(f"{BASE_URL}/airports", params=params, timeout=TIMEOUT)
    resp.raise_for_status()
    data = resp.json()

    items = data.get("data") or []
    if not items:
        return {
            "found": False,
            "query_type": "airport",
            "message": "No airports found.",
            "source": "AviationStack",
        }

    results = []
    for a in items[:5]:
        results.append({
            "airport_name": a.get("airport_name"),
            "iata_code": a.get("iata_code"),
            "country_name": a.get("country_name"),
            "city_iata_code": a.get("city_iata_code"),
            "latitude": a.get("latitude"),
            "longitude": a.get("longitude"),
            "timezone": a.get("timezone"),
        })

    return {
        "found": True,
        "query_type": "airport",
        "results": results,
        "source": "AviationStack",
    }


def _search_airlines(tool_input: dict) -> dict:
    params = {"access_key": API_KEY, "limit": 5}
    search = tool_input.get("airline_name", "").strip()
    if search:
        params["search"] = search

    resp = requests.get(f"{BASE_URL}/airlines", params=params, timeout=TIMEOUT)
    resp.raise_for_status()
    data = resp.json()

    items = data.get("data") or []
    if not items:
        return {
            "found": False,
            "query_type": "airline",
            "message": "No airlines found.",
            "source": "AviationStack",
        }

    results = []
    for a in items[:5]:
        results.append({
            "airline_name": a.get("airline_name"),
            "iata_code": a.get("iata_code"),
            "country_name": a.get("country_name"),
            "fleet_size": a.get("fleet_size"),
            "type": a.get("type"),
            "status": a.get("status"),
        })

    return {
        "found": True,
        "query_type": "airline",
        "results": results,
        "source": "AviationStack",
    }


if __name__ == "__main__":
    result = execute_aviationstack_tool({
        "query_type": "airport",
        "airport_search": "JFK",
    })
    import json
    print(json.dumps(result, indent=2))
