"""
Bria Exchange — GeoNames Tool
Searches the GeoNames geographical database for place facts.
Good for: verifying claims about city populations, country demographics,
          coordinates, elevation, administrative divisions, and geographic attributes.
"""

import os

import requests
from dotenv import load_dotenv

load_dotenv()

GEONAMES_API      = "http://api.geonames.org"
GEONAMES_USERNAME = os.getenv("GEONAMES_USERNAME", "demo")
TIMEOUT           = 8


TOOL_DEFINITION = {
    "name": "search_geonames",
    "description": (
        "Search GeoNames for geographic facts — city populations, country information, "
        "coordinates, elevation, and administrative divisions. Use to verify claims about "
        "city sizes, country demographics, and geographic attributes."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Place name to search for (e.g. 'Tokyo', 'California', 'Mount Everest').",
            },
            "country": {
                "type": "string",
                "description": "Optional ISO alpha-2 country code to restrict results (e.g. 'US', 'DE', 'JP').",
            },
            "feature_class": {
                "type": "string",
                "description": (
                    "Optional GeoNames feature class filter: "
                    "'P' for populated places, 'A' for administrative regions, 'T' for terrain/mountains."
                ),
            },
        },
        "required": ["query"],
    },
}


def execute_search_geonames_tool(tool_input: dict) -> dict:
    query         = tool_input.get("query", "").strip()
    country       = tool_input.get("country", "").strip().upper()
    feature_class = tool_input.get("feature_class", "").strip()

    if not query:
        return {"error": "query is required"}

    params: dict = {
        "q":        query,
        "maxRows":  5,
        "username": GEONAMES_USERNAME,
        "type":     "json",
    }
    if country:
        params["country"] = country
    if feature_class:
        params["featureClass"] = feature_class

    try:
        resp = requests.get(
            f"{GEONAMES_API}/searchJSON",
            params=params,
            timeout=TIMEOUT,
            headers={"User-Agent": "BriaExchange/1.0 (fact-verification)"},
        )
        resp.raise_for_status()
        data = resp.json()

        raw_places = data.get("geonames", [])

        # Filter out zero-population entries for populated place queries
        if feature_class == "P":
            places = [p for p in raw_places if p.get("population", 0) and int(p.get("population", 0)) > 0]
        else:
            places = raw_places

        if not places:
            return {
                "found":   False,
                "query":   query,
                "message": f"No GeoNames results found for '{query}'.",
                "source":  "GeoNames",
            }

        results = []
        for place in places:
            geonames_id = place.get("geonameId")
            results.append({
                "geonames_id":   geonames_id,
                "name":          place.get("name", ""),
                "country_code":  place.get("countryCode", ""),
                "country_name":  place.get("countryName", ""),
                "feature_class": place.get("fcl", ""),
                "feature_code":  place.get("fcode", ""),
                "population":    place.get("population"),
                "latitude":      place.get("lat"),
                "longitude":     place.get("lng"),
                "admin1_name":   place.get("adminName1", ""),
                "url":           f"https://www.geonames.org/{geonames_id}" if geonames_id else "",
            })

        return {
            "found":   True,
            "query":   query,
            "results": results,
            "source":  "GeoNames",
        }

    except requests.RequestException as exc:
        return {"error": f"GeoNames request failed: {exc}"}
