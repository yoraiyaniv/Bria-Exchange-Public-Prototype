"""
Bria Exchange — Open-Meteo Weather Tool
Fetches historical and forecast weather data from Open-Meteo (free, no API key).
Good for: verifying claims about weather events, temperature records,
          precipitation totals, wind, and climate conditions for any location.
"""

import requests
from datetime import date, datetime

OPENMETEO_ARCHIVE_API  = "https://archive-api.open-meteo.com/v1/archive"
OPENMETEO_FORECAST_API = "https://api.open-meteo.com/v1/forecast"
TIMEOUT                = 8

_ARCHIVE_CUTOFF_DAYS = 5


TOOL_DEFINITION = {
    "name": "get_weather_data",
    "description": (
        "Fetch historical and forecast weather data for any location. "
        "Use to verify claims about weather events, temperature records, "
        "precipitation, and climate conditions for any location."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "latitude": {
                "type": "number",
                "description": "Latitude of the location (decimal degrees, e.g. 40.7128 for New York City).",
            },
            "longitude": {
                "type": "number",
                "description": "Longitude of the location (decimal degrees, e.g. -74.0060 for New York City).",
            },
            "start_date": {
                "type": "string",
                "description": "Start date in YYYY-MM-DD format. Dates more than 5 days ago use the historical archive.",
            },
            "end_date": {
                "type": "string",
                "description": "End date in YYYY-MM-DD format.",
            },
            "variables": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "Daily weather variables to fetch. "
                    "Default: ['temperature_2m_max', 'temperature_2m_min', 'precipitation_sum', 'wind_speed_10m_max']. "
                    "Other options include: 'weathercode', 'snowfall_sum', 'shortwave_radiation_sum'."
                ),
            },
        },
        "required": ["latitude", "longitude", "start_date", "end_date"],
    },
}


def execute_get_weather_data_tool(tool_input: dict) -> dict:
    latitude   = tool_input.get("latitude")
    longitude  = tool_input.get("longitude")
    start_date = tool_input.get("start_date", "").strip()
    end_date   = tool_input.get("end_date", "").strip()
    variables  = tool_input.get("variables") or [
        "temperature_2m_max",
        "temperature_2m_min",
        "precipitation_sum",
        "wind_speed_10m_max",
    ]

    if latitude is None or longitude is None:
        return {"error": "latitude and longitude are required"}
    if not start_date or not end_date:
        return {"error": "start_date and end_date are required"}

    try:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d").date()
    except ValueError:
        return {"error": f"Invalid start_date format: '{start_date}'. Use YYYY-MM-DD."}

    # Choose archive vs forecast endpoint
    days_ago = (date.today() - start_dt).days
    api_url  = OPENMETEO_ARCHIVE_API if days_ago > _ARCHIVE_CUTOFF_DAYS else OPENMETEO_FORECAST_API

    params = {
        "latitude":  latitude,
        "longitude": longitude,
        "start_date": start_date,
        "end_date":   end_date,
        "daily":      ",".join(variables),
        "timezone":   "auto",
    }

    try:
        resp = requests.get(api_url, params=params, timeout=TIMEOUT)
        resp.raise_for_status()
        data = resp.json()

        daily      = data.get("daily", {})
        dates_list = daily.get("time", [])

        if not dates_list:
            return {
                "found":   False,
                "location": {"lat": latitude, "lon": longitude},
                "message": "No weather data returned for the requested period.",
                "source":  "Open-Meteo",
            }

        # Build per-day records
        records = []
        for i, d in enumerate(dates_list):
            record = {"date": d}
            for var in variables:
                var_data = daily.get(var, [])
                record[var] = var_data[i] if i < len(var_data) else None
            records.append(record)

        # Compute aggregates across the period
        max_temps   = [r.get("temperature_2m_max") for r in records if r.get("temperature_2m_max") is not None]
        min_temps   = [r.get("temperature_2m_min") for r in records if r.get("temperature_2m_min") is not None]
        precip_vals = [r.get("precipitation_sum")  for r in records if r.get("precipitation_sum")  is not None]

        aggregates: dict = {}
        if max_temps:
            aggregates["max_temp"] = max(max_temps)
        if min_temps:
            aggregates["min_temp"] = min(min_temps)
        if precip_vals:
            aggregates["total_precipitation"] = round(sum(precip_vals), 2)

        return {
            "found":    True,
            "location": {"lat": latitude, "lon": longitude},
            "timezone": data.get("timezone", ""),
            "data":     records,
            **aggregates,
            "source":   "Open-Meteo",
        }

    except requests.RequestException as exc:
        return {"error": f"Open-Meteo request failed: {exc}"}
