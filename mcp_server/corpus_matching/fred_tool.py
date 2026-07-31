"""
Bria Exchange — FRED API Tool
Fetches official economic data from the Federal Reserve Bank of St. Louis.
Used to verify macro/numerical claims against authoritative source data.
"""

import os
from dataclasses import dataclass
from datetime import datetime, date
from typing import Optional

import requests
from dotenv import load_dotenv

load_dotenv()

FRED_BASE_URL = "https://api.stlouisfed.org/fred"
FRED_API_KEY  = os.getenv("FRED_API_KEY")

# ── Known series registry ──────────────────────────────────────────────────────
# Maps human-readable claim topics to FRED series IDs.
# Claude uses this to resolve the right series for a given claim.

SERIES_REGISTRY = {
    "fed_funds_rate":        "DFF",           # daily effective fed funds rate
    "fed_funds_rate_monthly":"FEDFUNDS",       # monthly average
    "core_cpi":              "CPILFESL",       # core CPI, excludes food & energy
    "headline_cpi":          "CPIAUCSL",       # all-items CPI
    "pce_inflation":         "PCEPI",          # PCE price index (Fed's preferred)
    "core_pce":              "PCEPILFE",       # core PCE
    "treasury_10y":          "DGS10",          # 10-year Treasury yield
    "treasury_2y":           "DGS2",           # 2-year Treasury yield
    "treasury_3m":           "DGS3MO",         # 3-month Treasury yield
    "gdp_growth":            "A191RL1Q225SBEA",# real GDP % change, quarterly
    "unemployment":          "UNRATE",         # unemployment rate
    "ig_credit_spread":      "BAMLC0A0CM",     # investment grade OAS
    "hy_credit_spread":      "BAMLH0A0HYM2",   # high yield OAS
}


# ── Types ──────────────────────────────────────────────────────────────────────

@dataclass
class FredObservation:
    series_id:   str
    series_name: str
    date:        str
    value:       float
    units:       str
    source:      str = "Federal Reserve Bank of St. Louis (FRED)"

    def to_dict(self) -> dict:
        return {
            "series_id":   self.series_id,
            "series_name": self.series_name,
            "date":        self.date,
            "value":       self.value,
            "units":       self.units,
            "source":      self.source,
        }

    def to_sentence(self) -> str:
        """
        Renders observation as a natural language sentence.
        Used when passing evidence to Claude for verdict reasoning.
        """
        return (
            f"According to FRED ({self.series_id}), "
            f"{self.series_name} was {self.value} {self.units} "
            f"as of {self.date}."
        )


@dataclass
class FredResult:
    series_id:    str
    observations: list[FredObservation]
    error:        Optional[str] = None

    @property
    def latest(self) -> Optional[FredObservation]:
        return self.observations[-1] if self.observations else None

    def to_dict(self) -> dict:
        return {
            "series_id":    self.series_id,
            "observations": [o.to_dict() for o in self.observations],
            "error":        self.error,
        }


# ── FRED client ────────────────────────────────────────────────────────────────

class FredClient:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or FRED_API_KEY
        if not self.api_key:
            raise ValueError(
                "FRED_API_KEY not set. Get a free key at https://fred.stlouisfed.org/docs/api/api_key.html"
            )
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "BriaExchange/1.0"})

    def _get(self, endpoint: str, params: dict) -> dict:
        params["api_key"]   = self.api_key
        params["file_type"] = "json"
        response = self.session.get(f"{FRED_BASE_URL}{endpoint}", params=params)
        response.raise_for_status()
        return response.json()

    def get_series_info(self, series_id: str) -> dict:
        """Fetch metadata for a series (name, units, frequency)."""
        data = self._get("/series", {"series_id": series_id})
        return data["seriess"][0]

    def get_observations(
        self,
        series_id:   str,
        start_date:  Optional[str] = None,
        end_date:    Optional[str] = None,
    ) -> FredResult:
        """
        Fetch observations for a series over a date range.

        Args:
            series_id:  FRED series ID (e.g. "DFF", "CPILFESL")
            start_date: ISO date string "YYYY-MM-DD" (optional)
            end_date:   ISO date string "YYYY-MM-DD" (optional)

        Returns:
            FredResult with list of FredObservation objects
        """
        try:
            info   = self.get_series_info(series_id)
            name   = info.get("title", series_id)
            units  = info.get("units_short", info.get("units", ""))

            params = {"series_id": series_id}
            if start_date:
                params["observation_start"] = start_date
            if end_date:
                params["observation_end"] = end_date

            data         = self._get("/series/observations", params)
            observations = []

            for obs in data.get("observations", []):
                if obs["value"] == ".":
                    continue
                observations.append(FredObservation(
                    series_id=series_id,
                    series_name=name,
                    date=obs["date"],
                    value=float(obs["value"]),
                    units=units,
                ))

            return FredResult(series_id=series_id, observations=observations)

        except requests.HTTPError as e:
            return FredResult(series_id=series_id, observations=[], error=str(e))
        except Exception as e:
            return FredResult(series_id=series_id, observations=[], error=str(e))

    def get_value_for_period(
        self,
        series_id: str,
        year:      int,
        month:     int,
    ) -> Optional[FredObservation]:
        """
        Convenience method: get the observation closest to a given year/month.
        Fetches a small window around the target date to handle
        series with different frequencies (daily, monthly, quarterly).
        """
        target    = date(year, month, 1)
        start     = date(year, max(1, month - 1), 1).isoformat()
        end       = date(year, min(12, month + 1), 1).isoformat()
        result    = self.get_observations(series_id, start, end)

        if not result.observations:
            return None

        # return observation closest to target date
        return min(
            result.observations,
            key=lambda o: abs(
                (datetime.strptime(o.date, "%Y-%m-%d").date() - target).days
            )
        )


# ── Tool definition for Claude ─────────────────────────────────────────────────
# This is the tool schema you pass to the Anthropic API when building
# the verification agent. Claude uses this to decide when and how to call FRED.

FRED_TOOL_DEFINITION = {
    "name": "get_fred_data",
    "description": (
        "Fetch official economic data from the Federal Reserve Bank of St. Louis (FRED). "
        "Use this to verify macro and numerical claims about interest rates, inflation, "
        "GDP, unemployment, Treasury yields, and credit spreads. "
        "Returns the official value for the requested series and time period."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "series_id": {
                "type": "string",
                "description": (
                    "FRED series ID. Common values: "
                    "DFF (fed funds rate daily), "
                    "FEDFUNDS (fed funds monthly), "
                    "CPILFESL (core CPI), "
                    "CPIAUCSL (headline CPI), "
                    "DGS10 (10-year Treasury), "
                    "UNRATE (unemployment), "
                    "A191RL1Q225SBEA (real GDP growth)."
                ),
            },
            "start_date": {
                "type": "string",
                "description": "Start of date range in YYYY-MM-DD format.",
            },
            "end_date": {
                "type": "string",
                "description": "End of date range in YYYY-MM-DD format.",
            },
        },
        "required": ["series_id"],
    },
}


def execute_fred_tool(tool_input: dict, client: Optional[FredClient] = None) -> dict:
    """
    Execute a FRED tool call from Claude.
    Receives the tool_input dict from Claude's tool_use block
    and returns a result dict to pass back as tool_result.
    """
    client     = client or FredClient()
    series_id  = tool_input["series_id"]
    start_date = tool_input.get("start_date")
    end_date   = tool_input.get("end_date")

    result = client.get_observations(series_id, start_date, end_date)

    if result.error:
        return {"error": result.error}

    if not result.observations:
        return {"error": f"No data found for {series_id} in the requested range."}

    return {
        "series_id":    result.series_id,
        "observations": [o.to_dict() for o in result.observations],
        "summary":      result.latest.to_sentence() if result.latest else None,
    }


if __name__ == "__main__":
    results = FredClient().get_observations("DFF", "2026-02-01", "2026-02-28")
    print(results)