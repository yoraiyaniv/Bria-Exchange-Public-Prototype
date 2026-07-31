"""
Bria Exchange — IMF DataMapper Tool (replaces OECD SDMX which migrated APIs)
Fetches international economic statistics from the IMF DataMapper API.
Used to verify cross-country comparisons of GDP, unemployment, inflation,
and other macroeconomic indicators for any IMF member country.
No API key required.
"""

import requests

IMF_API  = "https://www.imf.org/external/datamapper/api/v1"
TIMEOUT  = 10

# Maps human-readable keys to IMF indicator codes
DATASET_REGISTRY = {
    "gdp_per_capita":     "NGDPDPC",   # GDP per capita, current USD
    "gdp_growth":         "NGDP_RPCH", # Real GDP growth, %
    "gdp_total":          "NGDPD",     # GDP, current prices (billions USD)
    "unemployment":       "LUR",        # Unemployment rate, %
    "cpi_inflation":      "PCPIPCH",   # Inflation, avg consumer prices, %
    "current_account":    "BCA_NGDPD", # Current account balance, % of GDP
    "government_debt":    "GGXWDG_NGDP", # General govt gross debt, % of GDP
    "government_deficit": "GGXCNL_NGDP", # Net lending/borrowing, % of GDP
    "population":         "LP",         # Population (millions)
}


OECD_TOOL_DEFINITION = {
    "name": "get_oecd_data",
    "description": (
        "Fetch international economic statistics from the IMF DataMapper. "
        "Use to verify cross-country comparisons of GDP, unemployment, inflation, "
        "government debt, and current account balances. Covers all IMF member countries. "
        "Equivalent to OECD data for macro indicators."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "indicator": {
                "type": "string",
                "description": (
                    "Economic indicator to fetch. "
                    f"Known keys: {', '.join(DATASET_REGISTRY.keys())}. "
                    "Or pass a raw IMF indicator code (e.g. 'NGDPDPC', 'LUR')."
                ),
            },
            "country_code": {
                "type": "string",
                "description": (
                    "IMF 3-letter country code (e.g. 'USA', 'GBR', 'DEU', 'FRA', 'JPN', 'CHN'). "
                    "Separate multiple countries with commas: 'USA,GBR,DEU'."
                ),
            },
            "start_year": {
                "type": "integer",
                "description": "First year of data to retrieve (e.g. 2015).",
            },
            "end_year": {
                "type": "integer",
                "description": "Last year of data to retrieve (e.g. 2023).",
            },
        },
        "required": ["indicator", "country_code"],
    },
}


def execute_oecd_tool(tool_input: dict) -> dict:
    indicator    = tool_input.get("indicator", "").strip()
    country_code = tool_input.get("country_code", "").strip().upper()
    start_year   = tool_input.get("start_year")
    end_year     = tool_input.get("end_year")

    if not indicator:
        return {"error": "indicator is required"}
    if not country_code:
        return {"error": "country_code is required"}

    # Resolve indicator code
    imf_code = DATASET_REGISTRY.get(indicator, indicator)

    # Build periods param if year range provided
    params: dict = {}
    if start_year and end_year:
        params["periods"] = ",".join(str(y) for y in range(start_year, end_year + 1))
    elif start_year:
        params["periods"] = ",".join(str(y) for y in range(start_year, 2026))
    elif end_year:
        params["periods"] = ",".join(str(y) for y in range(2000, end_year + 1))

    # Support comma-separated countries
    countries = "/".join(c.strip() for c in country_code.split(","))
    url = f"{IMF_API}/{imf_code}/{countries}"

    try:
        resp = requests.get(url, params=params, timeout=TIMEOUT)
        resp.raise_for_status()
        body = resp.json()

        values = body.get("values", {})
        indicator_data = values.get(imf_code, {})

        if not indicator_data:
            return {
                "found":     False,
                "indicator": indicator,
                "imf_code":  imf_code,
                "country":   country_code,
                "message":   f"No IMF data found for '{indicator}' / '{country_code}'.",
                "source":    "IMF DataMapper",
            }

        results = {}
        for country, year_values in indicator_data.items():
            data_points = [
                {"year": year, "value": val}
                for year, val in sorted(year_values.items())
                if val is not None
            ]
            results[country] = data_points

        return {
            "found":     True,
            "indicator": indicator,
            "imf_code":  imf_code,
            "countries": results,
            # Convenience flat list if single country
            "data":      results.get(list(results.keys())[0], []) if len(results) == 1 else None,
            "source":    "IMF DataMapper",
        }

    except requests.RequestException as exc:
        return {"error": f"IMF request failed: {exc}"}
