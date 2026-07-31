"""
Bria Exchange — EDGAR XBRL Tool
Fetches official company financial data from the SEC's EDGAR XBRL API.
Used to verify company-specific financial claims: revenue, earnings,
margins, debt, share counts, and similar reported figures.
"""

import time
from dataclasses import dataclass
from typing import Optional

import requests


EDGAR_BASE_URL    = "https://data.sec.gov"
TICKERS_URL       = "https://www.sec.gov/files/company_tickers.json"
REQUEST_DELAY     = 0.11   # SEC asks for max 10 req/s

# ── GAAP tag registry ──────────────────────────────────────────────────────────
# Maps plain-English financial concepts to US GAAP XBRL tags.
# Each concept lists tags in priority order — first match wins.

GAAP_TAG_REGISTRY = {
    "revenue": [
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "Revenues",
        "SalesRevenueNet",
        "RevenueFromContractWithCustomerIncludingAssessedTax",
    ],
    "net_income": [
        "NetIncomeLoss",
        "ProfitLoss",
        "NetIncomeLossAvailableToCommonStockholdersBasic",
    ],
    "gross_profit": [
        "GrossProfit",
    ],
    "operating_income": [
        "OperatingIncomeLoss",
    ],
    "ebitda": [
        "EarningsBeforeInterestTaxesDepreciationAndAmortization",
    ],
    "eps_basic": [
        "EarningsPerShareBasic",
    ],
    "eps_diluted": [
        "EarningsPerShareDiluted",
    ],
    "shares_outstanding": [
        "CommonStockSharesOutstanding",
        "WeightedAverageNumberOfSharesOutstandingBasic",
    ],
    "shares_diluted": [
        "WeightedAverageNumberOfDilutedSharesOutstanding",
    ],
    "long_term_debt": [
        "LongTermDebt",
        "LongTermDebtNoncurrent",
        "LongTermNotesPayable",
    ],
    "total_debt": [
        "DebtAndCapitalLeaseObligations",
        "LongTermDebtAndCapitalLeaseObligations",
    ],
    "cash": [
        "CashAndCashEquivalentsAtCarryingValue",
        "CashCashEquivalentsAndShortTermInvestments",
    ],
    "total_assets": [
        "Assets",
    ],
    "total_liabilities": [
        "Liabilities",
    ],
    "gross_margin": [
        "GrossProfit",   # derived: GrossProfit / Revenues
    ],
    "share_repurchases": [
        "PaymentsForRepurchaseOfCommonStock",
        "StockRepurchasedAndRetiredDuringPeriodValue",
    ],
}

# Scale suffixes used in analyst notes → multiplier to get raw USD
SCALE_MAP = {
    "billion":  1_000_000_000,
    "billions": 1_000_000_000,
    "million":  1_000_000,
    "millions": 1_000_000,
    "thousand": 1_000,
    "b":        1_000_000_000,
    "m":        1_000_000,
    "k":        1_000,
}


# ── Types ──────────────────────────────────────────────────────────────────────

@dataclass
class EdgarFact:
    ticker:      str
    cik:         str
    company:     str
    concept:     str          # plain-English concept (e.g. "revenue")
    gaap_tag:    str          # the GAAP tag that matched
    period_end:  str          # YYYY-MM-DD
    value_raw:   float        # raw value from EDGAR (full USD)
    value_bn:    float        # value in billions for readability
    form:        str          # e.g. "10-Q", "10-K"
    filed:       str          # filing date YYYY-MM-DD
    unit:        str          # "USD", "shares", etc.
    source:      str = "SEC EDGAR XBRL"

    def to_dict(self) -> dict:
        return {
            "ticker":     self.ticker,
            "cik":        self.cik,
            "company":    self.company,
            "concept":    self.concept,
            "gaap_tag":   self.gaap_tag,
            "period_end": self.period_end,
            "value_raw":  self.value_raw,
            "value_bn":   self.value_bn,
            "form":       self.form,
            "filed":      self.filed,
            "unit":       self.unit,
            "source":     self.source,
        }

    def to_sentence(self) -> str:
        if self.unit == "USD":
            return (
                f"According to SEC EDGAR ({self.form} filed {self.filed}), "
                f"{self.company} reported {self.concept} of "
                f"${self.value_bn:.2f}B for the period ending {self.period_end}."
            )
        return (
            f"According to SEC EDGAR ({self.form} filed {self.filed}), "
            f"{self.company} reported {self.concept} of "
            f"{self.value_raw:,.0f} {self.unit} for the period ending {self.period_end}."
        )


@dataclass
class EdgarResult:
    ticker:  str
    facts:   list[EdgarFact]
    error:   Optional[str] = None

    @property
    def latest(self) -> Optional[EdgarFact]:
        return self.facts[-1] if self.facts else None

    def to_dict(self) -> dict:
        return {
            "ticker": self.ticker,
            "facts":  [f.to_dict() for f in self.facts],
            "error":  self.error,
        }


# ── EDGAR client ───────────────────────────────────────────────────────────────

class EdgarClient:
    def __init__(self, user_agent: str = "BriaExchange/1.0 contact@briaexchange.com"):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": user_agent})
        self._ticker_map: Optional[dict] = None   # cached ticker → CIK map

    def _get(self, url: str) -> dict:
        time.sleep(REQUEST_DELAY)   # respect SEC rate limit
        response = self.session.get(url)
        response.raise_for_status()
        return response.json()

    def _load_ticker_map(self) -> dict:
        """Download and cache the SEC ticker → CIK mapping."""
        if self._ticker_map is None:
            data = self._get(TICKERS_URL)
            # Response is a dict of index → {cik, name, ticker}
            self._ticker_map = {
                v["ticker"].upper(): str(v.get("cik_str") or v.get("cik", "")).zfill(10)
                for v in data.values()
                if v.get("ticker")
            }
        return self._ticker_map

    def ticker_to_cik(self, ticker: str) -> Optional[str]:
        """Resolve a ticker symbol to a zero-padded CIK string."""
        mapping = self._load_ticker_map()
        return mapping.get(ticker.upper())

    def get_company_facts(self, cik: str) -> dict:
        """Fetch all XBRL facts for a company by CIK."""
        url = f"{EDGAR_BASE_URL}/api/xbrl/companyfacts/CIK{cik}.json"
        return self._get(url)

    def get_facts_for_concept(
        self,
        ticker:     str,
        concept:    str,
        period_end: Optional[str] = None,   # YYYY-MM-DD — filter to specific period
        form:       Optional[str] = None,   # "10-K" or "10-Q" filter
        limit:      int = 8,
    ) -> EdgarResult:
        """
        Fetch reported values for a financial concept for a given company.

        Args:
            ticker:     Stock ticker symbol (e.g. "AAPL")
            concept:    Plain-English concept from GAAP_TAG_REGISTRY
                        (e.g. "revenue", "net_income", "long_term_debt")
            period_end: Optional ISO date to filter to a specific reporting period
            form:       Optional filing form filter ("10-K" or "10-Q")
            limit:      Max number of most-recent facts to return

        Returns:
            EdgarResult with list of EdgarFact objects
        """
        try:
            cik = self.ticker_to_cik(ticker)
            if not cik:
                return EdgarResult(ticker=ticker, facts=[], error=f"Ticker '{ticker}' not found in EDGAR")

            all_facts   = self.get_company_facts(cik)
            company     = all_facts.get("entityName", ticker)
            gaap_facts  = all_facts.get("facts", {}).get("us-gaap", {})

            # Try each GAAP tag in priority order until we find data
            tags = GAAP_TAG_REGISTRY.get(concept, [concept])
            observations = []
            matched_tag  = None

            for tag in tags:
                tag_data = gaap_facts.get(tag, {})
                usd_data = tag_data.get("units", {}).get("USD", [])
                if usd_data:
                    observations = usd_data
                    matched_tag  = tag
                    break

            # Try shares if USD didn't match (for share count concepts)
            if not observations:
                for tag in tags:
                    tag_data    = gaap_facts.get(tag, {})
                    shares_data = tag_data.get("units", {}).get("shares", [])
                    if shares_data:
                        observations = shares_data
                        matched_tag  = tag
                        break

            if not observations or not matched_tag:
                return EdgarResult(
                    ticker=ticker,
                    facts=[],
                    error=f"No EDGAR data found for concept '{concept}' for {ticker}"
                )

            # Filter and sort
            if form:
                observations = [o for o in observations if o.get("form") == form]
            if period_end:
                observations = [o for o in observations if o.get("end", "").startswith(period_end[:7])]

            # Sort by period end date, take most recent
            observations = sorted(observations, key=lambda o: o.get("end", ""))[-limit:]

            # Determine unit
            tag_data = gaap_facts.get(matched_tag, {})
            unit     = "USD" if tag_data.get("units", {}).get("USD") else "shares"

            facts = []
            for obs in observations:
                raw = float(obs.get("val", 0))
                facts.append(EdgarFact(
                    ticker=ticker,
                    cik=cik,
                    company=company,
                    concept=concept,
                    gaap_tag=matched_tag,
                    period_end=obs.get("end", ""),
                    value_raw=raw,
                    value_bn=raw / 1_000_000_000 if unit == "USD" else raw,
                    form=obs.get("form", ""),
                    filed=obs.get("filed", ""),
                    unit=unit,
                ))

            return EdgarResult(ticker=ticker, facts=facts)

        except requests.HTTPError as e:
            return EdgarResult(ticker=ticker, facts=[], error=str(e))
        except Exception as e:
            return EdgarResult(ticker=ticker, facts=[], error=str(e))


# ── Tool definition for Claude ─────────────────────────────────────────────────

EDGAR_TOOL_DEFINITION = {
    "name": "get_edgar_data",
    "description": (
        "Fetch official company financial data from the SEC EDGAR XBRL API. "
        "Use this to verify company-specific financial claims: revenue, net income, "
        "gross profit, EPS, share counts, long-term debt, cash, share repurchases, "
        "and other reported financial figures. "
        "Requires a stock ticker and a financial concept. "
        "Returns reported values with filing dates and form types."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "ticker": {
                "type": "string",
                "description": "Stock ticker symbol (e.g. 'AAPL', 'MSFT', 'GOOGL').",
            },
            "concept": {
                "type": "string",
                "description": (
                    "Financial concept to look up. Supported values: "
                    "revenue, net_income, gross_profit, operating_income, "
                    "eps_basic, eps_diluted, shares_outstanding, shares_diluted, "
                    "long_term_debt, total_debt, cash, total_assets, "
                    "total_liabilities, share_repurchases."
                ),
            },
            "period_end": {
                "type": "string",
                "description": (
                    "Optional. Filter to a specific reporting period. "
                    "Format: YYYY-MM (e.g. '2025-12' for Q4 2025). "
                    "Leave blank to get the most recent values."
                ),
            },
            "form": {
                "type": "string",
                "description": "Optional. Filter by filing form: '10-K' (annual) or '10-Q' (quarterly).",
            },
        },
        "required": ["ticker", "concept"],
    },
}


def execute_edgar_tool(tool_input: dict, client: Optional[EdgarClient] = None) -> dict:
    """
    Execute an EDGAR tool call from Claude.
    Receives the tool_input dict from Claude's tool_use block
    and returns a result dict to pass back as tool_result.
    """
    client     = client or EdgarClient()
    ticker     = tool_input["ticker"]
    concept    = tool_input["concept"]
    period_end = tool_input.get("period_end")
    form       = tool_input.get("form")

    result = client.get_facts_for_concept(
        ticker=ticker,
        concept=concept,
        period_end=period_end,
        form=form,
    )

    if result.error:
        return {"error": result.error}

    if not result.facts:
        return {"error": f"No data found for {ticker} {concept}."}

    return {
        "ticker":   result.ticker,
        "concept":  concept,
        "facts":    [f.to_dict() for f in result.facts],
        "summary":  result.latest.to_sentence() if result.latest else None,
    }

if __name__ == "__main__":
    client = EdgarClient()

    result = client.get_facts_for_concept(
        ticker     = "AAPL",
        concept    = "revenue",
        period_end = "2024-12",
        form       = "10-Q",
    )

    if result.error:
        print(f"Error: {result.error}")
    else:
        for fact in result.facts:
            print(f"{fact.period_end}  ${fact.value_bn:.2f}B  ({fact.form} filed {fact.filed})")
        print(f"\n{result.latest.to_sentence()}")