"""
Bria Exchange — US Census Bureau Tool
Queries ACS 5-year estimates from the US Census Bureau API.
Used to verify claims about US population counts, income levels, housing costs,
poverty rates, and demographic composition by state or county.
"""

import os

import requests
from dotenv import load_dotenv

load_dotenv()

CENSUS_BASE_URL = "https://api.census.gov/data"
CENSUS_API_KEY  = os.getenv("CENSUS_API_KEY")
TIMEOUT         = 8

# Maps human-readable variable names to ACS Census variable codes.
VARIABLE_REGISTRY = {
    "population":        "B01001_001E",   # total population
    "median_income":     "B19013_001E",   # median household income
    "poverty_rate":      "B17001_002E",   # population below poverty level
    "median_age":        "B01002_001E",   # median age
    "housing_units":     "B25001_001E",   # total housing units
    "median_home_value": "B25077_001E",   # median value of owner-occupied housing
    "unemployment":      "B23025_005E",   # unemployed population (civilian labor force)
}

# Reverse map: variable code → registry key
_CODE_TO_KEY = {v: k for k, v in VARIABLE_REGISTRY.items()}


CENSUS_TOOL_DEFINITION = {
    "name": "search_census",
    "description": (
        "Query US Census Bureau data for population, demographics, housing, and economic statistics. "
        "Use to verify claims about US population counts, income levels, housing costs, poverty rates, "
        "and demographic composition by state or county."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "variable": {
                "type": "string",
                "description": (
                    "Census variable key or raw ACS variable code. "
                    f"Known keys: {', '.join(VARIABLE_REGISTRY.keys())}. "
                    "Or pass a raw variable code like 'B19013_001E'."
                ),
            },
            "geography": {
                "type": "string",
                "description": (
                    "Geographic level to query. One of: "
                    "'us' (national total), 'state' (all states), 'county' (all counties or filtered by state)."
                ),
            },
            "state_fips": {
                "type": "string",
                "description": (
                    "Two-digit FIPS code to restrict county queries to a single state "
                    "(e.g. '06' for California, '36' for New York). Only used when geography='county'."
                ),
            },
            "year": {
                "type": "integer",
                "description": "ACS survey year (e.g. 2022). Defaults to 2022.",
            },
        },
        "required": ["variable", "geography"],
    },
}


def execute_census_tool(tool_input: dict) -> dict:
    raw_variable = tool_input.get("variable", "")
    geography    = tool_input.get("geography", "").lower()
    state_fips   = tool_input.get("state_fips")
    year         = tool_input.get("year", 2022)

    if not raw_variable:
        return {"error": "variable is required"}
    if geography not in ("us", "state", "county"):
        return {"error": "geography must be one of: 'us', 'state', 'county'"}

    # Resolve registry key → actual Census variable code
    variable      = VARIABLE_REGISTRY.get(raw_variable, raw_variable)
    variable_name = _CODE_TO_KEY.get(variable, variable)

    # Build the 'for' geography filter
    if geography == "us":
        for_param = "us:1"
    elif geography == "state":
        for_param = "state:*"
    else:
        for_param = "county:*"

    url    = f"{CENSUS_BASE_URL}/{year}/acs/acs5"
    params: dict = {
        "get": f"NAME,{variable}",
        "for": for_param,
    }

    # Restrict county query to a specific state if provided
    if geography == "county" and state_fips:
        params["in"] = f"state:{state_fips}"

    if CENSUS_API_KEY:
        params["key"] = CENSUS_API_KEY

    try:
        resp = requests.get(url, params=params, timeout=TIMEOUT)
        resp.raise_for_status()
        rows = resp.json()

        if not rows or len(rows) < 2:
            return {
                "found":         False,
                "variable":      variable,
                "variable_name": variable_name,
                "geography":     geography,
                "year":          year,
                "message":       f"No Census data returned for {variable} ({geography}, {year}).",
                "source":        "US Census Bureau (ACS 5-Year)",
            }

        # First row is the header
        header = rows[0]
        name_idx = header.index("NAME") if "NAME" in header else None
        try:
            val_idx = header.index(variable)
        except ValueError:
            return {"error": f"Variable '{variable}' not found in Census response headers"}

        results = []
        for row in rows[1:]:
            entry: dict = {"value": row[val_idx]}
            if name_idx is not None:
                entry["name"] = row[name_idx]
            results.append(entry)

        return {
            "found":         True,
            "variable":      variable,
            "variable_name": variable_name,
            "geography":     geography,
            "year":          year,
            "results":       results,
            "source":        "US Census Bureau (ACS 5-Year)",
        }

    except requests.RequestException as exc:
        return {"error": f"Census Bureau request failed: {exc}"}
