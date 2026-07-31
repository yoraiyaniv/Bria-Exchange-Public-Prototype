"""
Bria Exchange — Our World in Data Tool
Fetches global development data from Our World in Data (OWID).
Good for: life expectancy, poverty, CO2 emissions, child mortality, population,
          GDP, literacy, vaccination rates, energy, and other global indicators.
No API key required — completely free and open.
"""

import csv
import io
import os
import requests

TIMEOUT = 15

TOOL_DEFINITION = {
    "name": "search_owid",
    "description": (
        "Fetch global development data from Our World in Data. Use to verify claims "
        "about life expectancy, poverty rates, CO2 emissions, child mortality, "
        "population, GDP per capita, literacy, vaccination rates, energy use, and "
        "other worldwide indicators. "
        "Common chart_slug values: life-expectancy, child-mortality, "
        "share-of-population-in-extreme-poverty, gdp-per-capita-worldbank, "
        "co2-emissions-per-capita, share-electricity-renewables, literacy-rate, "
        "population, infant-mortality, maternal-mortality, access-to-electricity, "
        "share-of-adults-who-are-obese, human-development-index, democracy-index, "
        "homicide-rate, prevalence-of-undernourishment, military-expenditure-share-gdp, "
        "forest-area-as-share-of-land-area, urban-population-share, "
        "total-fertility-rate, internet-users-by-world-region, "
        "mobile-cellular-subscriptions, nuclear-energy-generation, "
        "electricity-generation, carbon-intensity-electricity, "
        "suicide-death-rates, natural-disaster-deaths, government-expenditure-education."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "chart_slug": {
                "type": "string",
                "description": (
                    "Chart identifier (e.g. 'life-expectancy', 'co2-emissions-per-capita'). "
                    "Use hyphen-separated lowercase words."
                ),
            },
            "entity": {
                "type": "string",
                "description": (
                    "Country or region name to filter (e.g. 'United States', 'World', "
                    "'China', 'India'). Case-insensitive partial match."
                ),
            },
            "year": {
                "type": "integer",
                "description": "Specific year to look up (e.g. 2020).",
            },
        },
        "required": ["chart_slug"],
    },
}


def execute_owid_tool(tool_input: dict) -> dict:
    chart_slug = tool_input.get("chart_slug", "").strip()
    entity = tool_input.get("entity", "")
    year = tool_input.get("year")

    if not chart_slug:
        return {"error": "chart_slug is required"}

    url = (
        f"https://ourworldindata.org/grapher/{chart_slug}"
        "?v=1&csvType=full&useColumnShortNames=false"
    )
    headers = {"Accept": "text/csv", "User-Agent": "BriaExchange/1.0"}

    try:
        resp = requests.get(url, headers=headers, timeout=TIMEOUT)
        if resp.status_code == 404:
            return {
                "found": False,
                "chart_slug": chart_slug,
                "message": f"Chart '{chart_slug}' not found on Our World in Data.",
                "source": "Our World in Data",
            }
        resp.raise_for_status()

        text = resp.text
        if not text or len(text) < 10:
            return {
                "found": False,
                "chart_slug": chart_slug,
                "message": "Empty response from Our World in Data.",
                "source": "Our World in Data",
            }

        reader = csv.DictReader(io.StringIO(text))
        columns = reader.fieldnames or []

        # Identify the entity and year columns
        entity_col = None
        year_col = None
        for c in columns:
            cl = c.lower()
            if cl == "entity":
                entity_col = c
            elif cl in ("year", "day"):
                year_col = c

        rows = []
        total_matched = 0
        for row in reader:
            # Filter by entity
            if entity and entity_col:
                row_entity = row.get(entity_col, "")
                if entity.lower() not in row_entity.lower():
                    continue

            # Filter by year
            if year and year_col:
                row_year = row.get(year_col, "")
                try:
                    if int(row_year) != year:
                        continue
                except (ValueError, TypeError):
                    continue

            total_matched += 1
            if len(rows) < 20:
                rows.append(row)

        if not rows:
            return {
                "found": False,
                "chart_slug": chart_slug,
                "columns": columns,
                "data": [],
                "total_rows_matched": 0,
                "message": f"No data matched filters (entity={entity!r}, year={year}).",
                "source": "Our World in Data",
            }

        return {
            "found": True,
            "chart_slug": chart_slug,
            "columns": columns,
            "data": rows,
            "total_rows_matched": total_matched,
            "source": "Our World in Data",
        }

    except requests.RequestException as exc:
        return {"error": f"Our World in Data request failed: {exc}"}
    except Exception as exc:
        return {"error": f"Failed to parse OWID data: {exc}"}


if __name__ == "__main__":
    result = execute_owid_tool({
        "chart_slug": "life-expectancy",
        "entity": "World",
        "year": 2020,
    })
    import json
    print(json.dumps(result, indent=2))
