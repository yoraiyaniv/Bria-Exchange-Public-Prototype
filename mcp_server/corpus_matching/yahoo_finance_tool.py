"""
Bria Exchange — Yahoo Finance Tool
Fetches stock prices, dividends, splits, financial statements, and key metrics
using Yahoo Finance's public JSON API (no library dependency).
Complements EDGAR (structured XBRL filings) with real-time market data.
No API key required.
"""

import requests
from datetime import datetime, timedelta

TIMEOUT = 15
BASE_URL = "https://query2.finance.yahoo.com"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; BriaExchange/1.0)",
}

TOOL_DEFINITION = {
    "name": "get_yahoo_finance",
    "description": (
        "Fetch stock market data from Yahoo Finance. Use to verify claims about "
        "stock prices, market cap, P/E ratios, dividends, stock splits, "
        "quarterly financials (revenue, net income, EPS), and company info. "
        "Complements EDGAR for real-time and historical market data."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "ticker": {
                "type": "string",
                "description": "Stock ticker symbol (e.g. 'AAPL', 'MSFT', 'GOOGL', 'TSLA').",
            },
            "metric": {
                "type": "string",
                "enum": [
                    "quote", "history", "financials", "dividends", "splits", "profile",
                ],
                "description": (
                    "Data type to fetch. "
                    "quote: current price, market cap, P/E, 52-week range. "
                    "history: historical daily prices (use with date or period). "
                    "financials: income statement (quarterly revenue, net income, EPS). "
                    "dividends: dividend payment history. "
                    "splits: stock split history. "
                    "profile: company overview (sector, employees, website, description)."
                ),
            },
            "date": {
                "type": "string",
                "description": (
                    "For 'history': target date in YYYY-MM-DD. "
                    "Returns price data around this date."
                ),
            },
            "period": {
                "type": "string",
                "description": (
                    "For 'history': lookback period — '1mo', '3mo', '6mo', '1y', '5y'. "
                    "Default: '3mo'. Ignored if date is set."
                ),
            },
        },
        "required": ["ticker", "metric"],
    },
}


def _fetch_chart(ticker: str, period1: int, period2: int, interval: str = "1d",
                 events: str = "") -> dict | None:
    """Fetch from Yahoo Finance v8 chart API."""
    params = {
        "period1": period1,
        "period2": period2,
        "interval": interval,
    }
    if events:
        params["events"] = events

    url = f"{BASE_URL}/v8/finance/chart/{ticker}"
    resp = requests.get(url, params=params, headers=HEADERS, timeout=TIMEOUT)
    if resp.status_code != 200:
        return None
    data = resp.json()
    result = data.get("chart", {}).get("result")
    if not result:
        return None
    return result[0]


def _fetch_quoteSummary(ticker: str, modules: str) -> dict | None:
    """Fetch from Yahoo Finance v10 quoteSummary API."""
    url = f"{BASE_URL}/v10/finance/quoteSummary/{ticker}"
    params = {"modules": modules}
    try:
        resp = requests.get(url, params=params, headers=HEADERS, timeout=TIMEOUT)
        if resp.status_code != 200:
            return None
        data = resp.json()
        result = data.get("quoteSummary", {}).get("result")
        if not result:
            return None
        return result[0]
    except Exception:
        return None


def _yf_val(obj: dict | None, key: str = "raw"):
    """Extract raw value from Yahoo Finance's {raw: ..., fmt: ...} format."""
    if obj is None:
        return None
    if isinstance(obj, dict):
        return obj.get(key, obj.get("raw"))
    return obj


def execute_yahoo_finance_tool(tool_input: dict) -> dict:
    ticker = tool_input.get("ticker", "").strip().upper()
    metric = tool_input.get("metric", "").strip()
    target_date = tool_input.get("date")
    period = tool_input.get("period", "3mo")

    if not ticker:
        return {"error": "ticker is required"}
    if not metric:
        return {"error": "metric is required"}

    try:
        if metric == "quote":
            return _get_quote(ticker)
        elif metric == "history":
            return _get_history(ticker, target_date, period)
        elif metric == "financials":
            return _get_financials(ticker)
        elif metric == "dividends":
            return _get_dividends(ticker)
        elif metric == "splits":
            return _get_splits(ticker)
        elif metric == "profile":
            return _get_profile(ticker)
        else:
            return {"error": f"Unknown metric: {metric}. Use: quote, history, financials, dividends, splits, profile."}
    except requests.RequestException as exc:
        return {"error": f"Yahoo Finance request failed: {exc}"}
    except Exception as exc:
        return {"error": f"Yahoo Finance error: {exc}"}


def _get_quote(ticker: str) -> dict:
    # Use chart API for last day
    now = int(datetime.now().timestamp())
    start = now - 86400 * 5
    chart = _fetch_chart(ticker, start, now)
    if not chart:
        return {"found": False, "ticker": ticker, "message": "No quote data.", "source": "Yahoo Finance"}

    meta = chart.get("meta", {})
    return {
        "found": True,
        "ticker": ticker,
        "metric": "quote",
        "data": {
            "price": meta.get("regularMarketPrice"),
            "previous_close": meta.get("previousClose") or meta.get("chartPreviousClose"),
            "currency": meta.get("currency"),
            "exchange": meta.get("exchangeName"),
            "market_state": meta.get("marketState"),
            "fifty_two_week_high": meta.get("fiftyTwoWeekHigh"),
            "fifty_two_week_low": meta.get("fiftyTwoWeekLow"),
        },
        "source": "Yahoo Finance",
    }


def _get_history(ticker: str, target_date: str | None, period: str) -> dict:
    if target_date:
        try:
            dt = datetime.strptime(target_date, "%Y-%m-%d")
            p1 = int((dt - timedelta(days=7)).timestamp())
            p2 = int((dt + timedelta(days=7)).timestamp())
        except ValueError:
            return {"error": f"Invalid date: {target_date}. Use YYYY-MM-DD."}
    else:
        period_map = {"1mo": 30, "3mo": 90, "6mo": 180, "1y": 365, "5y": 1825}
        days = period_map.get(period, 90)
        now = int(datetime.now().timestamp())
        p1 = now - 86400 * days
        p2 = now

    chart = _fetch_chart(ticker, p1, p2)
    if not chart:
        return {"found": False, "ticker": ticker, "message": "No history data.", "source": "Yahoo Finance"}

    timestamps = chart.get("timestamp") or []
    indicators = chart.get("indicators", {}).get("quote", [{}])[0]
    opens = indicators.get("open") or []
    highs = indicators.get("high") or []
    lows = indicators.get("low") or []
    closes = indicators.get("close") or []
    volumes = indicators.get("volume") or []

    rows = []
    for i, ts in enumerate(timestamps):
        dt = datetime.utcfromtimestamp(ts).strftime("%Y-%m-%d")
        rows.append({
            "date": dt,
            "open": round(opens[i], 2) if i < len(opens) and opens[i] else None,
            "high": round(highs[i], 2) if i < len(highs) and highs[i] else None,
            "low": round(lows[i], 2) if i < len(lows) and lows[i] else None,
            "close": round(closes[i], 2) if i < len(closes) and closes[i] else None,
            "volume": volumes[i] if i < len(volumes) else None,
        })

    # Keep last 15 entries
    rows = rows[-15:]

    return {
        "found": True,
        "ticker": ticker,
        "metric": "history",
        "data": rows,
        "source": "Yahoo Finance",
    }


def _get_financials(ticker: str) -> dict:
    summary = _fetch_quoteSummary(ticker, "incomeStatementHistoryQuarterly,defaultKeyStatistics,financialData")
    if not summary:
        return {"found": False, "ticker": ticker, "message": "No financials.", "source": "Yahoo Finance"}

    results = []

    # Quarterly income statements
    stmts = (summary.get("incomeStatementHistoryQuarterly", {})
             .get("incomeStatementHistory", []))
    for stmt in stmts[:4]:
        results.append({
            "period": _yf_val(stmt.get("endDate"), "fmt"),
            "total_revenue": _yf_val(stmt.get("totalRevenue")),
            "net_income": _yf_val(stmt.get("netIncome")),
            "gross_profit": _yf_val(stmt.get("grossProfit")),
            "operating_income": _yf_val(stmt.get("operatingIncome")),
            "ebitda": _yf_val(stmt.get("ebitda")),
        })

    # Key stats
    key_stats = summary.get("defaultKeyStatistics", {})
    fin_data = summary.get("financialData", {})
    overview = {
        "trailing_eps": _yf_val(key_stats.get("trailingEps")),
        "forward_eps": _yf_val(key_stats.get("forwardEps")),
        "pe_ratio": _yf_val(key_stats.get("trailingPE") or key_stats.get("forwardPE")),
        "market_cap": _yf_val(fin_data.get("marketCap") or key_stats.get("marketCap")),
        "enterprise_value": _yf_val(key_stats.get("enterpriseValue")),
        "profit_margins": _yf_val(key_stats.get("profitMargins")),
        "revenue_growth": _yf_val(fin_data.get("revenueGrowth")),
        "earnings_growth": _yf_val(fin_data.get("earningsGrowth")),
    }

    return {
        "found": True,
        "ticker": ticker,
        "metric": "financials",
        "quarterly_income": results,
        "key_stats": overview,
        "source": "Yahoo Finance",
    }


def _get_dividends(ticker: str) -> dict:
    now = int(datetime.now().timestamp())
    start = now - 86400 * 365 * 5  # 5 years
    chart = _fetch_chart(ticker, start, now, events="div")
    if not chart:
        return {"found": False, "ticker": ticker, "message": "No dividend data.", "source": "Yahoo Finance"}

    events = chart.get("events", {}).get("dividends", {})
    if not events:
        return {"found": False, "ticker": ticker, "message": "No dividends found.", "source": "Yahoo Finance"}

    rows = []
    for ts_key, div in sorted(events.items(), key=lambda x: int(x[0])):
        dt = datetime.utcfromtimestamp(int(ts_key)).strftime("%Y-%m-%d")
        rows.append({
            "date": dt,
            "dividend": round(div.get("amount", 0), 4),
        })

    return {
        "found": True,
        "ticker": ticker,
        "metric": "dividends",
        "data": rows[-20:],  # last 20
        "source": "Yahoo Finance",
    }


def _get_splits(ticker: str) -> dict:
    now = int(datetime.now().timestamp())
    start = now - 86400 * 365 * 20  # 20 years
    chart = _fetch_chart(ticker, start, now, events="split")
    if not chart:
        return {"found": False, "ticker": ticker, "message": "No split data.", "source": "Yahoo Finance"}

    events = chart.get("events", {}).get("splits", {})
    if not events:
        return {"found": False, "ticker": ticker, "message": "No stock splits found.", "source": "Yahoo Finance"}

    rows = []
    for ts_key, sp in sorted(events.items(), key=lambda x: int(x[0])):
        dt = datetime.utcfromtimestamp(int(ts_key)).strftime("%Y-%m-%d")
        num = sp.get("numerator", 0)
        den = sp.get("denominator", 1)
        rows.append({
            "date": dt,
            "ratio": f"{num}:{den}",
            "numerator": num,
            "denominator": den,
        })

    return {
        "found": True,
        "ticker": ticker,
        "metric": "splits",
        "data": rows,
        "source": "Yahoo Finance",
    }


def _get_profile(ticker: str) -> dict:
    summary = _fetch_quoteSummary(ticker, "assetProfile,price")
    if not summary:
        return {"found": False, "ticker": ticker, "message": "No profile.", "source": "Yahoo Finance"}

    profile = summary.get("assetProfile", {})
    price = summary.get("price", {})

    data = {
        "name": _yf_val(price.get("shortName")) or _yf_val(price.get("longName")),
        "sector": profile.get("sector"),
        "industry": profile.get("industry"),
        "country": profile.get("country"),
        "website": profile.get("website"),
        "employees": profile.get("fullTimeEmployees"),
        "summary": (profile.get("longBusinessSummary") or "")[:500],
        "market_cap": _yf_val(price.get("marketCap")),
        "currency": _yf_val(price.get("currency")),
        "exchange": _yf_val(price.get("exchangeName")),
    }

    return {
        "found": True,
        "ticker": ticker,
        "metric": "profile",
        "data": data,
        "source": "Yahoo Finance",
    }


if __name__ == "__main__":
    import json
    result = execute_yahoo_finance_tool({"ticker": "AAPL", "metric": "quote"})
    print(json.dumps(result, indent=2, default=str))
