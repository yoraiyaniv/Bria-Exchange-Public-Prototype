"""
Bria Exchange — World Bank Open Data Tool
Queries World Bank indicators: GDP, trade, development, country profiles.
Good for: international economic claims not covered by FRED.
"""

import requests

WB_API   = "https://api.worldbank.org/v2"
TIMEOUT  = 8

# Common indicator registry
INDICATOR_REGISTRY = {
    "gdp":                    "NY.GDP.MKTP.CD",      # GDP (current USD)
    "gdp_growth":             "NY.GDP.MKTP.KD.ZG",   # GDP growth (annual %)
    "gdp_per_capita":         "NY.GDP.PCAP.CD",       # GDP per capita
    "inflation":              "FP.CPI.TOTL.ZG",       # Inflation (CPI, annual %)
    "unemployment":           "SL.UEM.TOTL.ZS",       # Unemployment (% of labor force)
    "population":             "SP.POP.TOTL",           # Total population
    "trade_pct_gdp":          "NE.TRD.GNFS.ZS",       # Trade as % of GDP
    "exports":                "NE.EXP.GNFS.CD",        # Exports of goods/services
    "imports":                "NE.IMP.GNFS.CD",        # Imports of goods/services
    "fdi_inflows":            "BX.KLT.DINV.CD.WD",    # FDI net inflows
    "internet_users":         "IT.NET.USER.ZS",        # Internet users (% population)
    "co2_emissions":          "EN.ATM.CO2E.PC",        # CO2 emissions per capita
}


WORLDBANK_TOOL_DEFINITION = {
    "name": "get_worldbank_data",
    "description": (
        "Fetch World Bank development indicators for countries or regions. "
        "Use for verifying international economic claims: GDP, trade, unemployment, "
        "population, inflation, and development metrics for any country. "
        "Covers nearly all countries with data back to 1960."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "country_code": {
                "type": "string",
                "description": "ISO 3166-1 alpha-2 or alpha-3 country code (e.g. 'US', 'CN', 'GBR', 'all' for world aggregate).",
            },
            "indicator": {
                "type": "string",
                "description": (
                    "Indicator key or World Bank indicator code. "
                    f"Known keys: {', '.join(INDICATOR_REGISTRY.keys())}. "
                    "Or pass a raw indicator code like 'NY.GDP.MKTP.CD'."
                ),
            },
            "year_from": {
                "type": "integer",
                "description": "Start year (e.g. 2020). Default: 3 years ago.",
            },
            "year_to": {
                "type": "integer",
                "description": "End year (e.g. 2023). Default: most recent available.",
            },
        },
        "required": ["country_code", "indicator"],
    },
}


def execute_worldbank_tool(tool_input: dict) -> dict:
    country   = tool_input.get("country_code", "").upper()
    indicator_key = tool_input.get("indicator", "")
    year_from = tool_input.get("year_from")
    year_to   = tool_input.get("year_to")

    if not country or not indicator_key:
        return {"error": "country_code and indicator are required"}

    # Resolve indicator code
    indicator = INDICATOR_REGISTRY.get(indicator_key.lower(), indicator_key)

    params: dict = {
        "format":   "json",
        "per_page": 10,
        "mrv":      5,  # most recent 5 values if no date range
    }
    if year_from and year_to:
        params["date"] = f"{year_from}:{year_to}"
        del params["mrv"]

    url = f"{WB_API}/country/{country}/indicator/{indicator}"

    try:
        resp = requests.get(url, params=params, timeout=TIMEOUT)
        resp.raise_for_status()
        payload = resp.json()

        if not payload or len(payload) < 2:
            return {"error": "Unexpected World Bank API response format"}

        meta   = payload[0]
        values = payload[1]

        if not values:
            return {
                "found":      False,
                "country":    country,
                "indicator":  indicator,
                "message":    f"No World Bank data for {country} / {indicator}.",
                "source":     "World Bank Open Data",
            }

        data_points = [
            {"year": v.get("date"), "value": v.get("value")}
            for v in values
            if v.get("value") is not None
        ]

        country_info = (values[0].get("country") or {})

        return {
            "found":        True,
            "country":      country_info.get("value", country),
            "country_code": country,
            "indicator":    indicator,
            "indicator_key": indicator_key,
            "data":         data_points,
            "source":       "World Bank Open Data",
        }

    except requests.RequestException as exc:
        return {"error": f"World Bank request failed: {exc}"}
