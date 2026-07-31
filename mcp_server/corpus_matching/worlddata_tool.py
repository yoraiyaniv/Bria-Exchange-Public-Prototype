"""
Bria Exchange — WorldData.AI Tool
Searches WorldData.AI for global macro, financial, labor, health, and trade statistics.
Covers sectors: agriculture, climate, demographics, education, energy, environment,
financial markets, health, industry, labor, macroeconomics, population,
science & technology, trade, transportation.
Requires WORLDDATA_API_KEY env var.
"""

import os
import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.environ.get("WORLDDATA_API_KEY", "")
BASE_URL = "https://api.worlddata.ai"
TIMEOUT = 15

TOOL_DEFINITION = {
    "name": "search_worlddata",
    "description": (
        "Search WorldData.AI for global macro, financial, labor, health, and trade "
        "statistics. Covers sectors: agriculture, climate change, demographics, "
        "education, energy, environment, financial market, health, industry, "
        "labor statistics, macroeconomics, population, science & technology, "
        "trade, transportation. Provides time-series data across countries."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": (
                    "Search term (e.g. 'US unemployment rate', 'China GDP growth', "
                    "'world population 2023')."
                ),
            },
            "sector": {
                "type": "string",
                "enum": [
                    "AGRICULTURE", "CLIMATE CHANGE", "DEMOGRAPHICS", "EDUCATION",
                    "ENERGY", "ENVIRONMENT", "FINANCIAL MARKET", "HEALTH",
                    "INDUSTRY", "LABOR STATISTICS", "MACROECONOMICS",
                    "POPULATION", "SCIENCE & TECHNOLOGY", "TRADE",
                    "TRANSPORTATION",
                ],
                "description": "Sector to search within.",
            },
            "country": {
                "type": "string",
                "description": "Country name to filter results (e.g. 'United States', 'Germany').",
            },
            "year_start": {
                "type": "integer",
                "description": "Start year for data range.",
            },
            "year_end": {
                "type": "integer",
                "description": "End year for data range.",
            },
        },
        "required": ["query"],
    },
}


def execute_worlddata_tool(tool_input: dict) -> dict:
    if not API_KEY:
        return {"error": "WORLDDATA_API_KEY not set"}

    query = tool_input.get("query", "").strip()
    sector = tool_input.get("sector")
    country = tool_input.get("country")
    year_start = tool_input.get("year_start")
    year_end = tool_input.get("year_end")

    if not query:
        return {"error": "query is required"}

    headers = {
        "x-api-key": API_KEY,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    try:
        # Step 1: Search for datasets
        search_body = {"query": query}
        if sector:
            search_body["sector"] = sector

        search_resp = requests.post(
            f"{BASE_URL}/v1/search",
            json=search_body,
            headers=headers,
            timeout=TIMEOUT,
        )

        if search_resp.status_code == 404:
            # Try alternate endpoint
            search_resp = requests.get(
                f"{BASE_URL}/v1/search",
                params={"query": query, "sector": sector or ""},
                headers=headers,
                timeout=TIMEOUT,
            )

        if search_resp.status_code in (401, 403):
            return {"error": "WorldData.AI API: invalid or expired API key."}

        if search_resp.status_code >= 400:
            return {
                "error": (
                    f"WorldData.AI API returned HTTP {search_resp.status_code}. "
                    "API may require different endpoint format."
                )
            }

        search_data = search_resp.json()

        # Extract results — handle various response formats
        datasets = []
        if isinstance(search_data, list):
            datasets = search_data
        elif isinstance(search_data, dict):
            datasets = (
                search_data.get("results")
                or search_data.get("data")
                or search_data.get("datasets")
                or []
            )

        if not datasets:
            return {
                "found": False,
                "query": query,
                "results": [],
                "message": f"No datasets found for '{query}'.",
                "source": "WorldData.AI",
            }

        # Step 2: Try to fetch data for top results
        results = []
        for ds in datasets[:5]:
            trend_id = (
                ds.get("trend_id")
                or ds.get("id")
                or ds.get("dataset_id")
            )
            indicator = (
                ds.get("indicator")
                or ds.get("name")
                or ds.get("title")
                or str(trend_id)
            )
            ds_sector = ds.get("sector") or sector or ""
            ds_country = ds.get("country") or ""

            if country and ds_country and country.lower() not in ds_country.lower():
                continue

            entry = {
                "indicator": indicator,
                "country": ds_country,
                "sector": ds_sector,
            }

            # Try to get time-series data if trend_id available
            if trend_id:
                try:
                    data_params = {"trend_id": trend_id}
                    if ds_sector:
                        data_params["sector"] = ds_sector
                    data_resp = requests.get(
                        f"{BASE_URL}/v1/data",
                        params=data_params,
                        headers=headers,
                        timeout=TIMEOUT,
                    )
                    if data_resp.status_code == 200:
                        ts_data = data_resp.json()
                        points = []
                        raw_points = ts_data if isinstance(ts_data, list) else (
                            ts_data.get("data") or ts_data.get("values") or []
                        )
                        for pt in raw_points:
                            yr = pt.get("year") or pt.get("date")
                            val = pt.get("value")
                            if yr is not None and val is not None:
                                try:
                                    yr_int = int(str(yr)[:4])
                                except (ValueError, TypeError):
                                    continue
                                if year_start and yr_int < year_start:
                                    continue
                                if year_end and yr_int > year_end:
                                    continue
                                points.append({
                                    "year": yr_int,
                                    "value": val,
                                    "unit": pt.get("unit", ""),
                                })
                        entry["data"] = points[:20]
                except Exception:
                    pass

            results.append(entry)

        return {
            "found": bool(results),
            "query": query,
            "results": results,
            "source": "WorldData.AI",
        }

    except requests.RequestException as exc:
        return {"error": f"WorldData.AI request failed: {exc}"}
    except Exception as exc:
        return {"error": f"WorldData.AI error: {exc}"}


if __name__ == "__main__":
    result = execute_worlddata_tool({"query": "US GDP growth"})
    import json
    print(json.dumps(result, indent=2))
