"""
Bria Exchange — Bureau of Labor Statistics (BLS) Tool
Fetches official US labor and price statistics from the BLS public API.
Used to verify claims about employment, unemployment, wages, CPI components,
job openings, and workplace injuries with authoritative government data.
"""

import os

import requests
from dotenv import load_dotenv

load_dotenv()

BLS_API_V2  = "https://api.bls.gov/publicAPI/v2/timeseries/data/"
BLS_API_V1  = "https://api.bls.gov/publicAPI/v1/timeseries/data/"
BLS_API_KEY = os.getenv("BLS_API_KEY")
TIMEOUT     = 8

# Maps human-readable claim topics to BLS series IDs.
SERIES_REGISTRY = {
    "unemployment":              "LNS14000000",        # national unemployment rate
    "labor_force_participation": "LNS11300000",        # labor force participation rate
    "cpi_all":                   "CUUR0000SA0",        # CPI all items, all urban
    "cpi_food":                  "CUUR0000SAF1",       # CPI food
    "cpi_energy":                "CUUR0000SA0E",       # CPI energy
    "cpi_shelter":               "CUUR0000SAH1",       # CPI shelter
    "avg_hourly_earnings":       "CES0500000003",      # average hourly earnings, private
    "nonfarm_payrolls":          "CES0000000001",      # total nonfarm payrolls
    "job_openings":              "JTS000000000000000JOL",  # job openings level
}

# Reverse map: series ID → registry key, for labeling results
_ID_TO_KEY = {v: k for k, v in SERIES_REGISTRY.items()}


BLS_TOOL_DEFINITION = {
    "name": "get_bls_data",
    "description": (
        "Fetch official US labor statistics from the Bureau of Labor Statistics. "
        "Use to verify claims about employment, wages, CPI components, and workplace injuries. "
        "Returns authoritative government data for US economic claims."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "series_id": {
                "type": "string",
                "description": (
                    "BLS series ID or a human-readable registry key. "
                    f"Known keys: {', '.join(SERIES_REGISTRY.keys())}. "
                    "Or pass a raw BLS series ID like 'LNS14000000'."
                ),
            },
            "start_year": {
                "type": "integer",
                "description": "First year of data to retrieve (e.g. 2020).",
            },
            "end_year": {
                "type": "integer",
                "description": "Last year of data to retrieve (e.g. 2023).",
            },
        },
        "required": ["series_id"],
    },
}


def execute_bls_tool(tool_input: dict) -> dict:
    raw_id     = tool_input.get("series_id", "")
    start_year = tool_input.get("start_year")
    end_year   = tool_input.get("end_year")

    if not raw_id:
        return {"error": "series_id is required"}

    # Resolve registry key → actual series ID
    series_id   = SERIES_REGISTRY.get(raw_id, raw_id)
    series_name = _ID_TO_KEY.get(series_id, series_id)

    try:
        if BLS_API_KEY:
            # v2 API — supports date range and higher rate limits
            payload: dict = {
                "seriesid":        [series_id],
                "registrationkey": BLS_API_KEY,
            }
            if start_year:
                payload["startyear"] = str(start_year)
            if end_year:
                payload["endyear"] = str(end_year)

            resp = requests.post(BLS_API_V2, json=payload, timeout=TIMEOUT)
            resp.raise_for_status()
            body = resp.json()
        else:
            # v1 public API — no key required, limited rate
            url    = f"{BLS_API_V1}{series_id}"
            params = {}
            if start_year:
                params["startyear"] = str(start_year)
            if end_year:
                params["endyear"] = str(end_year)

            resp = requests.get(url, params=params, timeout=TIMEOUT)
            resp.raise_for_status()
            body = resp.json()

        if body.get("status") != "REQUEST_SUCCEEDED":
            message = "; ".join(body.get("message", ["BLS API request failed"]))
            return {"error": f"BLS API error: {message}"}

        series_list = body.get("Results", {}).get("series", [])
        if not series_list:
            return {
                "found":       False,
                "series_id":   series_id,
                "series_name": series_name,
                "message":     f"No BLS data returned for series {series_id}.",
                "source":      "Bureau of Labor Statistics (BLS)",
            }

        raw_data = series_list[0].get("data", [])
        if not raw_data:
            return {
                "found":       False,
                "series_id":   series_id,
                "series_name": series_name,
                "message":     f"No observations found for series {series_id}.",
                "source":      "Bureau of Labor Statistics (BLS)",
            }

        # Keep at most the last 12 observations (API returns newest first)
        observations = [
            {"year": obs["year"], "period": obs["period"], "value": obs["value"]}
            for obs in raw_data[:12]
            if obs.get("value") not in (None, "-")
        ]

        return {
            "found":       True,
            "series_id":   series_id,
            "series_name": series_name,
            "data":        observations,
            "source":      "Bureau of Labor Statistics (BLS)",
        }

    except requests.RequestException as exc:
        return {"error": f"BLS request failed: {exc}"}
