"""
Bria Exchange — ExchangeRate.host Tool
Fetches currency exchange rates and conversions.
Good for: verifying claims about exchange rates, currency values, conversion amounts.
Requires EXCHANGERATE_API_KEY env var.
"""

import os
import requests
from dotenv import load_dotenv

load_dotenv()

TIMEOUT = 10
API_KEY = os.environ.get("EXCHANGERATE_API_KEY", "")

TOOL_DEFINITION = {
    "name": "get_exchange_rate",
    "description": (
        "Fetch currency exchange rates from ExchangeRate.host. Use to verify claims "
        "about exchange rates, currency values, and conversion amounts. "
        "Supports 168+ fiat currencies and crypto. Provide ISO 4217 codes."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "from_currency": {
                "type": "string",
                "description": "Source currency ISO 4217 code (e.g. 'USD', 'EUR', 'GBP', 'JPY').",
            },
            "to_currency": {
                "type": "string",
                "description": "Target currency ISO 4217 code.",
            },
            "date": {
                "type": "string",
                "description": "Historical rate date in YYYY-MM-DD format. If omitted, returns latest rate.",
            },
            "amount": {
                "type": "number",
                "description": "Amount to convert (default: 1).",
            },
        },
        "required": ["from_currency", "to_currency"],
    },
}


def execute_exchangerate_tool(tool_input: dict) -> dict:
    if not API_KEY:
        return {"error": "EXCHANGERATE_API_KEY not set"}

    from_cur = tool_input.get("from_currency", "").upper().strip()
    to_cur = tool_input.get("to_currency", "").upper().strip()
    date = tool_input.get("date")
    amount = tool_input.get("amount", 1)

    if not from_cur or not to_cur:
        return {"error": "from_currency and to_currency are required"}

    try:
        # Use convert endpoint (HTTP for free tier)
        params = {
            "access_key": API_KEY,
            "from": from_cur,
            "to": to_cur,
            "amount": amount,
        }
        if date:
            params["date"] = date

        resp = requests.get(
            "http://api.exchangerate.host/convert",
            params=params,
            timeout=TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()

        if not data.get("success", False):
            err = data.get("error", {})
            msg = err.get("info") or err.get("type") or "Unknown error"
            return {"error": f"ExchangeRate API error: {msg}"}

        info = data.get("info", {})
        rate = info.get("quote") or info.get("rate")
        result_val = data.get("result")

        # Compute rate if not directly available
        if rate is None and result_val is not None and amount:
            rate = result_val / amount

        return {
            "found": True,
            "from_currency": from_cur,
            "to_currency": to_cur,
            "amount": amount,
            "rate": rate,
            "converted_amount": result_val,
            "date": date or "latest",
            "source": "ExchangeRate.host",
        }

    except requests.RequestException as exc:
        return {"error": f"ExchangeRate request failed: {exc}"}
    except Exception as exc:
        return {"error": f"ExchangeRate error: {exc}"}


if __name__ == "__main__":
    result = execute_exchangerate_tool({
        "from_currency": "USD",
        "to_currency": "EUR",
        "amount": 100,
    })
    import json
    print(json.dumps(result, indent=2))
