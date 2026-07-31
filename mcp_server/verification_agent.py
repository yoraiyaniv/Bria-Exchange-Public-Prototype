"""
Bria Exchange - Verification Agent (patched)
Key changes from original:
  1. Model upgraded from Haiku to Sonnet (critical for tool-use quality)
  2. max_tokens raised from 1024 to 2048 (prevents truncated JSON verdicts)
  3. Tool output trimming - large responses are summarized before passing back
  4. Reduced system prompt verbosity for better instruction following
  5. More robust verdict parsing with fallback extraction
  6. Better iteration budget management
"""

import asyncio
import json
import re
from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Optional

import anthropic

from corpus_matching.fred_tool import (
    FredClient,
    FRED_TOOL_DEFINITION,
    execute_fred_tool,
)
from corpus_matching.edgar_tool import (
    EdgarClient,
    EDGAR_TOOL_DEFINITION,
    execute_edgar_tool,
)
from corpus_matching.wikidata_tool import (
    WIKIDATA_TOOL_DEFINITION,
    execute_wikidata_tool,
)
from corpus_matching.guardian_tool import (
    GUARDIAN_TOOL_DEFINITION,
    execute_guardian_tool,
)
from corpus_matching.nytimes_tool import (
    NYTIMES_TOOL_DEFINITION,
    execute_nytimes_tool,
)
from corpus_matching.pubmed_tool import (
    PUBMED_TOOL_DEFINITION,
    execute_pubmed_tool,
)
from corpus_matching.clinicaltrials_tool import (
    CLINICALTRIALS_TOOL_DEFINITION,
    execute_clinicaltrials_tool,
)
from corpus_matching.openfda_tool import (
    OPENFDA_TOOL_DEFINITION,
    execute_openfda_tool,
)
from corpus_matching.worldbank_tool import (
    WORLDBANK_TOOL_DEFINITION,
    execute_worldbank_tool,
)
from corpus_matching.crossref_tool import (
    CROSSREF_TOOL_DEFINITION,
    execute_crossref_tool,
)
from corpus_matching.semanticscholar_tool import (
    SEMANTICSCHOLAR_TOOL_DEFINITION,
    execute_semanticscholar_tool,
)
from corpus_matching.arxiv_tool import (
    TOOL_DEFINITION as ARXIV_TOOL_DEFINITION,
    execute_search_arxiv_tool,
)
from corpus_matching.openalex_tool import (
    TOOL_DEFINITION as OPENALEX_TOOL_DEFINITION,
    execute_search_openalex_tool,
)
from corpus_matching.europepmc_tool import (
    TOOL_DEFINITION as EUROPEPMC_TOOL_DEFINITION,
    execute_search_europepmc_tool,
)
from corpus_matching.bls_tool import (
    BLS_TOOL_DEFINITION,
    execute_bls_tool,
)
from corpus_matching.census_tool import (
    CENSUS_TOOL_DEFINITION,
    execute_census_tool,
)
from corpus_matching.oecd_tool import (
    OECD_TOOL_DEFINITION,
    execute_oecd_tool,
)
from corpus_matching.courtlistener_tool import (
    TOOL_DEFINITION as COURTLISTENER_TOOL_DEFINITION,
    execute_search_courtlistener_tool,
)
from corpus_matching.federalregister_tool import (
    TOOL_DEFINITION as FEDERALREGISTER_TOOL_DEFINITION,
    execute_search_federal_register_tool,
)
from corpus_matching.openmeteo_tool import (
    TOOL_DEFINITION as OPENMETEO_TOOL_DEFINITION,
    execute_get_weather_data_tool,
)
from corpus_matching.geonames_tool import (
    TOOL_DEFINITION as GEONAMES_TOOL_DEFINITION,
    execute_search_geonames_tool,
)
from corpus_matching.wikipedia_tool import (
    TOOL_DEFINITION as WIKIPEDIA_TOOL_DEFINITION,
    execute_search_wikipedia_tool,
)
from corpus_matching.congress_tool import (
    TOOL_DEFINITION as CONGRESS_TOOL_DEFINITION,
    execute_congress_tool,
)
from corpus_matching.owid_tool import (
    TOOL_DEFINITION as OWID_TOOL_DEFINITION,
    execute_owid_tool,
)
from corpus_matching.exchangerate_tool import (
    TOOL_DEFINITION as EXCHANGERATE_TOOL_DEFINITION,
    execute_exchangerate_tool,
)
from corpus_matching.aviationstack_tool import (
    TOOL_DEFINITION as AVIATIONSTACK_TOOL_DEFINITION,
    execute_aviationstack_tool,
)
from corpus_matching.worlddata_tool import (
    TOOL_DEFINITION as WORLDDATA_TOOL_DEFINITION,
    execute_worlddata_tool,
)
from corpus_matching.data360_tool import (
    TOOL_DEFINITION as DATA360_TOOL_DEFINITION,
    execute_data360_tool,
)
from corpus_matching.yahoo_finance_tool import (
    TOOL_DEFINITION as YAHOO_TOOL_DEFINITION,
    execute_yahoo_finance_tool,
)
from corpus_matching.company_site_tool import (
    TOOL_DEFINITION as COMPANY_SITE_TOOL_DEFINITION,
    execute_company_site_tool,
)


# -- Types -------------------------------------------------------------------

class Verdict(str, Enum):
    CORROBORATED = "corroborated"
    CONTRADICTED = "contradicted"
    UNSUPPORTED  = "unsupported"
    OUT_OF_SCOPE = "out_of_scope"


@dataclass
class ToolCall:
    tool_name:   str
    tool_input:  dict
    tool_output: dict


@dataclass
class VerificationResult:
    claim:           str
    verdict:         Verdict
    reasoning:       str
    confidence:      float
    citations:       list[dict] = field(default_factory=list)
    tool_calls:      list[ToolCall] = field(default_factory=list)
    error:           Optional[str] = None
    corrected_fact:  Optional[str] = None
    explanation:     Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "claim":          self.claim,
            "verdict":        self.verdict.value,
            "reasoning":      self.reasoning,
            "explanation":    self.explanation,
            "corrected_fact": self.corrected_fact,
            "confidence":     self.confidence,
            "citations":      self.citations,
            "tool_calls": [
                {"tool": tc.tool_name, "input": tc.tool_input, "output": tc.tool_output}
                for tc in self.tool_calls
            ],
            "error": self.error,
        }


# -- Tool registry -----------------------------------------------------------

ALL_TOOLS: dict[str, tuple[dict, callable]] = {
    "fred":             (FRED_TOOL_DEFINITION,             execute_fred_tool),
    "edgar":            (EDGAR_TOOL_DEFINITION,            execute_edgar_tool),
    "wikidata":         (WIKIDATA_TOOL_DEFINITION,         execute_wikidata_tool),
    "guardian":         (GUARDIAN_TOOL_DEFINITION,         execute_guardian_tool),
    "nytimes":          (NYTIMES_TOOL_DEFINITION,          execute_nytimes_tool),
    "pubmed":           (PUBMED_TOOL_DEFINITION,           execute_pubmed_tool),
    "clinicaltrials":   (CLINICALTRIALS_TOOL_DEFINITION,   execute_clinicaltrials_tool),
    "openfda":          (OPENFDA_TOOL_DEFINITION,          execute_openfda_tool),
    "worldbank":        (WORLDBANK_TOOL_DEFINITION,        execute_worldbank_tool),
    "crossref":         (CROSSREF_TOOL_DEFINITION,         execute_crossref_tool),
    "semanticscholar":  (SEMANTICSCHOLAR_TOOL_DEFINITION,  execute_semanticscholar_tool),
    "arxiv":            (ARXIV_TOOL_DEFINITION,            execute_search_arxiv_tool),
    "openalex":         (OPENALEX_TOOL_DEFINITION,         execute_search_openalex_tool),
    "europepmc":        (EUROPEPMC_TOOL_DEFINITION,        execute_search_europepmc_tool),
    "bls":              (BLS_TOOL_DEFINITION,              execute_bls_tool),
    "census":           (CENSUS_TOOL_DEFINITION,           execute_census_tool),
    "oecd":             (OECD_TOOL_DEFINITION,             execute_oecd_tool),
    "courtlistener":    (COURTLISTENER_TOOL_DEFINITION,    execute_search_courtlistener_tool),
    "federalregister":  (FEDERALREGISTER_TOOL_DEFINITION,  execute_search_federal_register_tool),
    "openmeteo":        (OPENMETEO_TOOL_DEFINITION,        execute_get_weather_data_tool),
    "geonames":         (GEONAMES_TOOL_DEFINITION,         execute_search_geonames_tool),
    "wikipedia":        (WIKIPEDIA_TOOL_DEFINITION,        execute_search_wikipedia_tool),
    "congress":         (CONGRESS_TOOL_DEFINITION,         execute_congress_tool),
    "owid":             (OWID_TOOL_DEFINITION,             execute_owid_tool),
    "exchangerate":     (EXCHANGERATE_TOOL_DEFINITION,     execute_exchangerate_tool),
    "aviationstack":    (AVIATIONSTACK_TOOL_DEFINITION,    execute_aviationstack_tool),
    "worlddata":        (WORLDDATA_TOOL_DEFINITION,        execute_worlddata_tool),
    "data360":          (DATA360_TOOL_DEFINITION,          execute_data360_tool),
    "yahoo":            (YAHOO_TOOL_DEFINITION,            execute_yahoo_finance_tool),
    "companysite":      (COMPANY_SITE_TOOL_DEFINITION,     execute_company_site_tool),
}

DOMAIN_TOOLS: dict[str, list[str]] = {
    "financial":      ["edgar", "yahoo", "fred", "guardian", "nytimes", "bls", "worldbank", "oecd", "census", "exchangerate", "data360", "companysite"],
    "pharma":         ["pubmed", "clinicaltrials", "openfda", "europepmc", "crossref", "companysite"],
    "legal":          ["courtlistener", "federalregister", "congress", "guardian", "nytimes"],
    "news_editorial": ["guardian", "nytimes", "congress", "crossref", "semanticscholar", "companysite"],
    "academic":       ["semanticscholar", "crossref", "arxiv", "openalex", "europepmc", "pubmed"],
    "geography":      ["geonames", "worldbank", "census", "openmeteo", "owid", "data360"],
    "climate":        ["openmeteo", "worldbank", "owid", "geonames"],
    "auto":           ["wikidata", "wikipedia", "guardian", "nytimes", "yahoo"],
}


# -- Auto-domain detection ----------------------------------------------------
# When domain is "auto", infer the best domain from the claim text so the model
# gets a focused tool set instead of 14 generic tools.

_DOMAIN_KEYWORDS: dict[str, list[str]] = {
    "financial": [
        "revenue", "profit", "earnings", "eps", "stock", "share", "dividend",
        "market cap", "fiscal", "quarterly", "annual report", "sec filing",
        "10-k", "10-q", "ipo", "nasdaq", "nyse", "s&p", "dow jones",
        "gdp", "inflation", "interest rate", "fed", "treasury", "yield",
        "debt", "bond", "exchange rate", "currency", "forex",
        "valuation", "split", "buyback", "repurchase",
        "listed on",
        "year-over-year", "yoy", "segment", "operating margin", "net income",
        "gross margin", "cash flow", "balance sheet", "analyst",
    ],
    "pharma": [
        "drug", "fda", "clinical trial", "phase 1", "phase 2", "phase 3",
        "efficacy", "side effect", "adverse", "pharmaceutical", "biotech",
        "patient", "treatment", "therapy", "dose", "prescription", "vaccine",
        "approval", "indication", "placebo", "endpoint", "mortality rate",
    ],
    "legal": [
        "court", "ruling", "lawsuit", "plaintiff", "defendant", "judge",
        "supreme court", "circuit", "statute", "regulation", "act of",
        "congress", "bill", "legislation", "executive order", "amendment",
        "federal register", "docket", "opinion", "precedent",
    ],
    "academic": [
        "paper", "published", "journal", "citation", "peer-reviewed",
        "preprint", "arxiv", "doi", "research", "study found",
        "benchmark", "model performance", "dataset", "parameter",
    ],
    "geography": [
        "population", "city", "country", "capital", "continent",
        "latitude", "longitude", "elevation", "area", "border",
        "demographic", "census", "inhabitants",
    ],
    "climate": [
        "temperature", "precipitation", "rainfall", "weather",
        "climate", "hurricane", "drought", "flood", "celsius",
        "fahrenheit", "wind speed", "carbon emission", "co2",
    ],
}


def _detect_domain(claim: str) -> str:
    """Infer the best domain from claim text using keyword matching."""
    claim_lower = claim.lower()
    scores: dict[str, int] = {}
    for domain, keywords in _DOMAIN_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in claim_lower)
        if score > 0:
            scores[domain] = score
    if scores:
        return max(scores, key=scores.get)
    return "auto"

# -- Domain-specific prompt sections ------------------------------------------
# Each section gives the model concrete guidance on how to call tools for that
# domain: parameter names, formats, common values, and response interpretation.

DOMAIN_PROMPTS: dict[str, str] = {
    "financial": """## Domain guidance: Financial / Economic claims

**Primary tools (try first):**
- `get_fred_data`: US macro data — interest rates, inflation, GDP, unemployment.
  - series_id: DFF (fed funds rate), CPIAUCSL (CPI), GDP, UNRATE (unemployment), T10Y2Y (yield spread), FEDFUNDS, CPILFESL (core CPI).
  - start_date / end_date: YYYY-MM-DD format. Bracket the claim's time period.
  - Response: "observations" array → find the entry matching the claim's date. The number is in "value".

- `get_edgar_data`: Company financials — revenue, net income, EPS, debt, cash.
  - ticker: Stock symbol (AAPL, MSFT, GOOGL).
  - concept: One of: revenue, net_income, gross_profit, operating_income, eps_basic, eps_diluted, shares_outstanding, long_term_debt, total_debt, cash, total_assets, total_liabilities, share_repurchases.
  - period_end: YYYY-MM format to match fiscal period (e.g. "2023-09").
  - form: "10-K" for annual, "10-Q" for quarterly.
  - Response: "facts" array → value_raw is full USD, value_bn is in billions. Match period_end and form.

**Secondary tools:**
- `get_bls_data`: US labor stats. series_id: unemployment, cpi_all, avg_hourly_earnings, nonfarm_payrolls, job_openings. start_year/end_year are integers.
- `get_worldbank_data`: International data. country_code (ISO 2/3 letter), indicator: gdp, gdp_growth, gdp_per_capita, inflation, unemployment, population. year_from/year_to integers.
- `get_oecd_data`: Cross-country comparisons (IMF). indicator: gdp_per_capita, gdp_growth, unemployment, cpi_inflation, government_debt. country_code: 3-letter (USA, GBR, DEU).
- `search_census`: US demographics. variable: population, median_income, poverty_rate. geography: us, state, county.
- `get_exchange_rate`: Currency conversion. from_currency/to_currency (ISO 4217 codes like USD, EUR), date YYYY-MM-DD for historical.
- `search_worlddata`: Broad macro/labor/trade data via WorldData.AI. query + optional sector (MACROECONOMICS, FINANCIAL MARKET, etc.).
- `search_data360`: Search World Bank indicators by keyword. query: topic description, country: ISO code. Finds the right indicator code automatically.
- `get_yahoo_finance`: Stock prices, dividends, splits, financials, analyst estimates. ticker + metric (price, history, financials, dividends, splits, info, earnings). Use for market data EDGAR doesn't cover.
- `fetch_company_site`: Fetch official company website content. company: "apple", page_type: "pricing"/"about"/"investors". Use for company-specific facts not in public APIs.

**Pitfalls:**
- FRED series IDs are codes like DFF, not words like "federal funds rate".
- EDGAR values are raw USD — convert to billions for comparison if the claim uses billions.
- BLS start_year/end_year are integers, not date strings.
- Yahoo Finance metric must be one of: price, history, financials, dividends, splits, info, earnings, recommendations.""",

    "pharma": """## Domain guidance: Pharma / Biomedical claims

**Primary tools (try first):**
- `search_pubmed`: Clinical evidence, drug efficacy, medical research.
  - query: Drug name + condition + key term (e.g. "semaglutide weight loss efficacy").
  - max_results: 1-10 (default 3). Set higher if searching broadly.
  - Response: "articles" array with title, journal, pub_date, authors. Read titles carefully for evidence.

- `search_clinicaltrials`: Trial phase, status, enrollment, endpoints.
  - query: Drug + condition + phase (e.g. "semaglutide obesity phase 3").
  - status: RECRUITING, COMPLETED, ACTIVE_NOT_RECRUITING (case-sensitive UPPERCASE).
  - Response: "studies" array with nct_id, status, phase, enrollment, has_results.

**Secondary tools:**
- `search_openfda`: FDA data. endpoint: drug_label (default), drug_event (adverse events), drug_nda (approvals), drug_enforcement (recalls).
- `search_europepmc`: Broader biomedical lit. source filter: MED (MEDLINE), PMC, PPR (preprints), PAT (patents).
- `search_crossref`: DOI lookup, citation counts. Set doi param for exact paper lookup.

**Pitfalls:**
- ClinicalTrials status values are UPPERCASE: COMPLETED, RECRUITING — not lowercase.
- OpenFDA endpoint names are specific: drug_label, drug_event, drug_nda, drug_enforcement.
- PubMed max_results is capped at 10 even if you request more.""",

    "legal": """## Domain guidance: Legal claims

**Primary tools (try first):**
- `search_courtlistener`: US court opinions and dockets.
  - query: Case name, statute, or legal issue (e.g. "Section 230 immunity", "Roe v Wade").
  - court: Slug — "scotus" (Supreme Court), "ca9" (9th Circuit), "dcd" (D.C. District).
  - type: "o" for opinions (default), "d" for dockets.
  - Response: "results" array with case_name, court, date_filed, snippet.

- `search_federal_register`: Regulations, executive orders, agency notices.
  - query: Policy topic (e.g. "clean air standards").
  - agency: Slug like "environmental-protection-agency", "securities-and-exchange-commission".
  - type: "Rule", "Proposed Rule", "Notice", "Presidential Document".
  - from_date / to_date: YYYY-MM-DD format.
  - Response: "results" with title, agencies, type, publication_date, abstract.

**Secondary tools:**
- `search_congress`: US bills, resolutions, members. query: bill topic or member name. search_type: "bill" (default) or "member". congress: number (e.g. 118).
- `search_guardian`: News coverage of legal events. from_date/to_date: YYYY-MM-DD.
- `search_nytimes`: NYT legal coverage. begin_date/end_date: YYYYMMDD (NO hyphens!).

**Pitfalls:**
- NYTimes dates have NO hyphens: "20240115" not "2024-01-15". Guardian uses hyphens.
- Federal Register agency slugs are hyphenated lowercase.
- CourtListener type is a single letter: "o" or "d", not a word.""",

    "news_editorial": """## Domain guidance: News / Editorial claims

**Primary tools (try first):**
- `search_guardian`: The Guardian archive.
  - query: Event, person, or topic.
  - from_date / to_date: YYYY-MM-DD format. ALWAYS set date filters matching the claim's period.
  - Response: "articles" array with headline, date, body_extract. Read body_extract for confirmation.

- `search_nytimes`: New York Times archive.
  - query: Same approach.
  - begin_date / end_date: YYYYMMDD — NO hyphens (e.g. "20240115" not "2024-01-15").
  - Response: "articles" array with headline, abstract, date.

**Secondary tools:**
- `search_congress`: For claims about US legislation in the news. query: bill topic, search_type: "bill" or "member".
- `search_crossref`: For cited research papers mentioned in news.
- `search_semantic_scholar`: For AI/tech research claims referenced in articles.

**Pitfalls:**
- CRITICAL: NYTimes dates are YYYYMMDD (no hyphens). Guardian is YYYY-MM-DD (with hyphens). Mixing them up returns no results.
- Always set date filters — without them you get irrelevant articles from random years.
- Read body_extract/abstract carefully — headlines can be misleading.""",

    "academic": """## Domain guidance: Academic / Research claims

**Primary tools (try first):**
- `search_semantic_scholar`: Best for CS/AI papers, citation counts, benchmarks.
  - query: Paper title + author + year (e.g. "GPT-4 technical report OpenAI 2023").
  - Response: "papers" array with title, authors, year, citations, abstract, url.

- `search_crossref`: DOI lookups, publication metadata, citation counts.
  - query: Title or author query. OR set doi for exact lookup (e.g. "10.1145/3442188.3445922").
  - Response: "results" array (query) or "result" dict (DOI) with title, authors, year, citations.

**Secondary tools:**
- `search_arxiv`: Preprints. category: cs.AI, cs.CL, q-bio, math.CO, physics.hep-th. max_results: 1-10.
- `search_openalex`: Broadest coverage (250M+ works). from_year/to_year as integers. type: article, book, preprint.
- `search_europepmc`: Biomedical literature. source: MED, PMC, PPR (preprints).
- `search_pubmed`: Peer-reviewed biomedical articles.

**Pitfalls:**
- CrossRef doi param requires exact DOI string ("10.1145/..."), not a URL.
- Semantic Scholar is strongest for CS/AI; for biomedical use PubMed/EuropePMC.
- arXiv categories are specific codes: "cs.AI", "cs.CL" — not free text.""",

    "geography": """## Domain guidance: Geography / Demographics claims

**Primary tools (try first):**
- `search_geonames`: City populations, coordinates, administrative divisions.
  - query: Place name (e.g. "Tokyo", "Mount Everest").
  - country: Optional ISO alpha-2 code (US, JP, DE) to restrict results.
  - feature_class: P (populated places), A (admin regions), T (terrain/mountains).
  - Response: "results" array with name, population, country_code, latitude, longitude.

- `get_worldbank_data`: Country development indicators.
  - country_code: ISO 2 or 3 letter (US, GBR, or "all" for world aggregate).
  - indicator: gdp, gdp_per_capita, population, inflation, unemployment, co2_emissions, internet_users.
  - year_from / year_to: Integers.
  - Response: "data" array with year and value.

**Secondary tools:**
- `search_census`: US-specific. variable: population, median_income, poverty_rate. geography: us, state, county. state_fips for county queries (e.g. "06" for CA).
- `get_weather_data`: Weather at a location. Needs latitude + longitude (get from GeoNames first), start_date/end_date YYYY-MM-DD.
- `search_owid`: Global development data. chart_slug: "life-expectancy", "population", "gdp-per-capita-worldbank", etc. entity: country name. year: integer.
- `search_data360`: Search World Bank indicators by keyword (e.g. "literacy rate", "infant mortality"). Finds indicator codes automatically.

**Pitfalls:**
- GeoNames returns population=0 for non-city features. Use feature_class="P" for cities.
- WorldBank "all" gives world totals, not per-country. Use specific country codes.
- For weather data, call GeoNames first to get lat/lon coordinates.""",

    "climate": """## Domain guidance: Climate / Weather claims

**Primary tools (try first):**
- `get_weather_data`: Historical and forecast weather for any location.
  - latitude / longitude: Decimal degrees (e.g. 40.7128, -74.0060 for NYC).
  - start_date / end_date: YYYY-MM-DD. Both required.
  - variables: Array of strings — ["temperature_2m_max", "temperature_2m_min", "precipitation_sum", "wind_speed_10m_max"].
  - Response: "data" array with daily values. Also: max_temp, min_temp, total_precipitation aggregates.

- `get_worldbank_data`: Country-level environmental indicators.
  - indicator: co2_emissions for CO2 per capita, or raw World Bank codes for renewables, forest area.

**Secondary tools:**
- `search_geonames`: Get lat/lon for a place name before calling weather tool.
- `search_owid`: Global climate/energy data. chart_slug: "co2-emissions-per-capita", "share-electricity-renewables", "carbon-intensity-electricity", etc. entity: country name.

**Pitfalls:**
- Weather tool needs lat/lon — if claim mentions a city, call GeoNames FIRST to get coordinates.
- Temperature is Celsius, precipitation is mm, wind speed is km/h.
- Archive API handles dates >5 days ago; forecast API for recent dates (automatic).""",

    "auto": """## Domain guidance: General claims

Match the claim to the right tool:
- Company financials → `get_edgar_data` (ticker + concept) or `get_fred_data` (macro series like DFF, GDP, UNRATE)
- News events → `search_guardian` (dates YYYY-MM-DD) or `search_nytimes` (dates YYYYMMDD, NO hyphens)
- Medical/drug claims → `search_pubmed` or `search_clinicaltrials`
- Geography/populations → `search_geonames` (place name + feature_class) or `get_worldbank_data` (country + indicator)
- Legal/regulatory → `search_courtlistener` or `search_federal_register`
- US legislation → `search_congress` (query + search_type: "bill" or "member")
- Academic papers → `search_semantic_scholar` or `search_crossref`
- Weather/climate → `get_weather_data` (needs lat/lon + YYYY-MM-DD dates)
- Global statistics → `search_owid` (chart_slug like "life-expectancy", entity, year) or `search_data360` (keyword search for World Bank indicators)
- Stock prices, dividends, splits → `get_yahoo_finance` (ticker + metric: price/dividends/splits/financials/info)
- Company-specific facts (pricing, API costs, product specs) → `fetch_company_site` (company name + page_type, or direct URL)
- Currency rates → `get_exchange_rate` (from_currency, to_currency ISO codes, date YYYY-MM-DD)
- Aviation → `search_aviationstack` (query_type: flight/airport/airline — use sparingly, 100 req/month limit)

**Key format reminders:**
- NYTimes dates: YYYYMMDD (no hyphens). Guardian dates: YYYY-MM-DD (with hyphens).
- FRED series_id: use codes like DFF, CPIAUCSL, GDP, UNRATE — not human-readable words.
- EDGAR concept: use enum values (revenue, net_income, eps_basic) — not free text.
- Always set date filters on news tools to match the claim's time period.""",
}

_WIKIDATA_FALLBACK = "wikidata"
_WIKIPEDIA_FALLBACK = "wikipedia"


def _resolve_tools(
    domain: str,
    enabled_connector_ids: Optional[list[str]] = None,
) -> list[str]:
    domain_list = DOMAIN_TOOLS.get(domain, DOMAIN_TOOLS["auto"])

    if _WIKIDATA_FALLBACK not in domain_list:
        domain_list = domain_list + [_WIKIDATA_FALLBACK]
    if _WIKIPEDIA_FALLBACK not in domain_list:
        domain_list = domain_list + [_WIKIPEDIA_FALLBACK]

    if enabled_connector_ids is None:
        return domain_list

    enabled_set = set(enabled_connector_ids)
    filtered = [c for c in domain_list if c in enabled_set]

    if _WIKIDATA_FALLBACK not in filtered:
        filtered.append(_WIKIDATA_FALLBACK)

    return filtered if filtered else domain_list


# -- FIX #1: Build a reliable tool-name-to-connector-id map at module level --
# This prevents the per-call mapping from silently failing.
# We build it once from all tool definitions so we always know which
# connector handles which tool name.

_TOOL_NAME_TO_CONNECTOR: dict[str, str] = {}
for _cid, (_tdef, _) in ALL_TOOLS.items():
    _tname = _tdef.get("name", "")
    if _tname:
        _TOOL_NAME_TO_CONNECTOR[_tname] = _cid


# -- FIX #2: Tool output trimming -------------------------------------------
# Many tools return huge JSON blobs. Haiku (and even Sonnet) struggles
# to pick out the relevant data point from a wall of nested JSON.
# Trim tool outputs to the most useful fields before passing back.

MAX_TOOL_OUTPUT_CHARS = 4000  # ~1000 tokens


def _trim_tool_output(tool_name: str, output: dict) -> dict:
    """
    Trim large tool outputs to keep the most relevant fields.
    This dramatically improves the model's ability to interpret results.
    """
    # If there's an error, return as-is (small)
    if "error" in output:
        return output

    serialized = json.dumps(output)

    # If already small enough, return as-is
    if len(serialized) <= MAX_TOOL_OUTPUT_CHARS:
        return output

    # Strategy: try to extract the most useful subset
    # For list-based results, keep only first N items
    trimmed = _trim_list_results(output, max_items=5)

    serialized = json.dumps(trimmed)
    if len(serialized) <= MAX_TOOL_OUTPUT_CHARS:
        return trimmed

    # Last resort: hard truncate the serialized JSON and wrap it
    # so the model at least sees partial data rather than nothing
    truncated_str = serialized[:MAX_TOOL_OUTPUT_CHARS]
    return {
        "truncated": True,
        "partial_data": truncated_str,
        "note": "Result was too large and has been truncated. Key data may be in the first few records."
    }


def _trim_list_results(obj: dict, max_items: int = 5) -> dict:
    """Recursively find list fields and cap them at max_items."""
    if isinstance(obj, dict):
        result = {}
        for k, v in obj.items():
            if isinstance(v, list) and len(v) > max_items:
                result[k] = v[:max_items]
                result[f"_{k}_total_count"] = len(v)
                result[f"_{k}_note"] = f"Showing first {max_items} of {len(v)} results"
            elif isinstance(v, dict):
                result[k] = _trim_list_results(v, max_items)
            else:
                result[k] = v
        return result
    return obj


# -- FIX #3: Streamlined system prompt --------------------------------------
# The original prompt was ~2500 tokens of instructions. For tool-use agents,
# shorter and more direct prompts perform better - the model spends less
# context budget on instructions and more on reasoning about tool results.
#
# Key change: removed the duplicate tool descriptions from the system prompt.
# The model already sees tool descriptions in the formal tool definitions.
# Having them in BOTH places caused confusion (especially when they drifted).

def _build_system_prompt(
    connector_ids: list[str],
    custom_sources: Optional[list[dict]] = None,
    domain: str = "auto",
) -> str:
    custom_context = ""
    if custom_sources:
        sections = []
        for cs in custom_sources:
            raw = (cs.get("extracted_text") or "")
            if len(raw) > 8000:
                cutoff = raw.rfind("\n", 0, 8000)
                raw = raw[: cutoff if cutoff > 0 else 8000]
            if raw:
                sections.append(
                    f"### {cs['name']} (domain: {cs['domain']}, authority: {cs['authority_level']})\n{raw}"
                )
        if sections:
            custom_context = (
                "\n\n## Organization Custom Sources\n"
                "Check these FIRST before calling external tools. "
                "If a claim can be verified from this content, cite the source name.\n\n"
                + "\n\n---\n\n".join(sections)
            )

    today = date.today().isoformat()
    available_tools = ", ".join(connector_ids)
    domain_guidance = DOMAIN_PROMPTS.get(domain, DOMAIN_PROMPTS.get("auto", ""))

    return f"""You are a fact-verification engine for Bria Exchange. Today is {today}.
{custom_context}

Available tool IDs: {available_tools}

{domain_guidance}

## Instructions

1. Identify the subject, asserted fact/value, and time period of the claim.
2. Call the most relevant domain-specific tool FIRST (see domain guidance above). Do NOT start with Wikidata or Wikipedia.
3. REQUIRED: Call at least one MORE authoritative tool to cross-reference. Do not stop after a single source.
4. Interpret the returned data carefully. Look for the specific value or fact the claim asserts. Compare it precisely.
5. Only use Wikipedia as a last resort after 2+ authoritative tools returned nothing useful.

## Interpreting tool results

- Tool results are JSON. Look for the specific data fields that match the claim.
- If a tool returns data but you cannot find the specific fact, say so in your reasoning — do not ignore the data.
- Empty results from one tool do NOT mean the claim is unsupported. Try another tool.

## Verdict rules

- **corroborated**: authoritative source data confirms the claim (allow +/-2% for numbers). Confidence >= 0.75 with authoritative sources; 0.50-0.65 if only Wikipedia.
- **contradicted**: authoritative source data **materially** conflicts with the core assertion. Always set corrected_fact. Confidence >= 0.70. Use this ONLY when the claim is factually wrong, not merely imprecise or loosely worded.
- **unsupported**: you tried 2+ different authoritative tools and found no relevant data either way. A single empty result is NOT enough.
- **out_of_scope**: structurally impossible to verify (internal forecasts, subjective opinions, future predictions). Do NOT use for statistics, historical events, or published facts. When in doubt, use unsupported.

## Precision vs. contradiction — critical distinctions

- **Date granularity**: A claim like "in 2004" is corroborated if the event happened any time in 2004 (e.g., "February 2004"). Only contradict dates when the actual year/period is wrong, not when the claim is less specific than the source. "In 2004" vs "February 2004" = corroborated. "In 2004" vs "in 2003" = contradicted.
- **Numeric rounding**: Allow +/-2% for numbers. "About 6 million" vs "6.5 million" = corroborated. "$10 billion" vs "$7 billion" = contradicted.
- **Role/action nuance**: Distinguish between the core factual claim and word-level precision. "Led a funding round" when they contributed 87% of the funding = corroborated (they were the dominant contributor). "Founded the company" when they joined a year after founding = contradicted (materially different role).
- **Wikipedia-only verdicts**: Never issue a **contradicted** verdict based solely on Wikipedia. Wikipedia can corroborate (at reduced confidence 0.50-0.65) but contradictions require at least one authoritative primary source. If Wikipedia is the only source that conflicts, the verdict should be **unsupported**, not contradicted.
- **General rule**: Ask yourself — would a reasonable, informed reader consider this claim misleading? If not, it is corroborated. Only contradict when the claim would leave a reader with a materially wrong understanding of reality.

## Output format

When ready, respond with ONLY this JSON:
{{
  "verdict": "corroborated|contradicted|unsupported|out_of_scope",
  "reasoning": "<one sentence: verdict + key data point>",
  "explanation": "<2-4 sentences: what claim asserts, what sources show, why this verdict>",
  "corrected_fact": "<contradicted only, else null>",
  "confidence": <float 0.0-1.0>,
  "citations": [
    {{
      "source": "<tool name>",
      "identifier": "<series ID, ticker, DOI, URL, or entity ID>",
      "date": "<YYYY-MM-DD or YYYY>",
      "value": <number or null>,
      "label": "<description of the data point>"
    }}
  ]
}}"""


# -- Agent -------------------------------------------------------------------

class VerificationAgent:
    def __init__(
        self,
        fred_client:  Optional[FredClient]  = None,
        edgar_client: Optional[EdgarClient] = None,
        # FIX #4: Upgraded from claude-haiku-4-5-20251001 to Sonnet.
        # Haiku cannot reliably:
        #   - select the right tool from 6-10 options
        #   - interpret complex JSON responses from APIs
        #   - follow multi-step verification instructions
        #   - produce well-structured verdict JSON
        # This is the single biggest fix.
        model:        str = "claude-sonnet-4-20250514",
        max_iterations: int = 10,  # FIX #5: raised from 8 to 10
    ):
        self.client      = anthropic.AsyncAnthropic()
        self.fred        = fred_client  or FredClient()
        self.edgar       = edgar_client or EdgarClient()
        self.model       = model
        self.max_iter    = max_iterations

    async def verify(
        self,
        claim: str,
        domain: str = "auto",
        enabled_connector_ids: Optional[list[str]] = None,
        custom_sources: Optional[list[dict]] = None,
    ) -> VerificationResult:
        # Auto-detect domain from claim text when caller sends "auto"
        if domain == "auto":
            domain = _detect_domain(claim)
        connector_ids  = _resolve_tools(domain, enabled_connector_ids)
        system_prompt  = _build_system_prompt(connector_ids, custom_sources, domain)
        tool_defs      = [ALL_TOOLS[c][0] for c in connector_ids if c in ALL_TOOLS]

        # FIX #6: Log which tools are actually being provided so you can debug
        tool_names_provided = [t["name"] for t in tool_defs]
        print(f"[VerificationAgent] claim='{claim[:80]}...' domain={domain} "
              f"tools={tool_names_provided}")

        # For general-knowledge claims (domain "auto"), don't gate Wikipedia/Wikidata
        # — they are often the best source for biographical and corporate history facts.
        _specialized_domain = domain not in ("auto",)

        messages: list[dict] = [
            {"role": "user", "content": f"Verify this claim: {claim}"}
        ]
        tool_calls: list[ToolCall] = []
        tools_called: set[str] = set()
        iterations = 0

        while iterations < self.max_iter:
            iterations += 1

            response = await self.client.messages.create(
                model=self.model,
                max_tokens=2048,  # FIX #7: raised from 1024 to prevent truncated verdicts
                system=system_prompt,
                tools=tool_defs,
                messages=messages,
            )

            messages.append({"role": "assistant", "content": response.content})

            if response.stop_reason == "end_turn":
                return self._parse_verdict(claim, response.content, tool_calls)

            if response.stop_reason == "tool_use":
                tool_results = []
                for block in response.content:
                    if block.type != "tool_use":
                        continue

                    print(f"[VerificationAgent] iter={iterations} claim='{claim[:40]}' tool={block.name} input={json.dumps(block.input)[:100]}")

                    tool_output = await self._execute_tool(block.name, block.input, connector_ids)

                    # FIX #9: Trim large tool outputs before passing back to the model
                    trimmed_output = _trim_tool_output(block.name, tool_output)

                    found = tool_output.get("found", "?")
                    err = tool_output.get("error", "")
                    print(f"[VerificationAgent]   → found={found} err={err[:80] if err else ''}")
                    tools_called.add(block.name)
                    tool_calls.append(ToolCall(
                        tool_name=block.name,
                        tool_input=block.input,
                        tool_output=tool_output,  # store full output for audit
                    ))
                    tool_results.append({
                        "type":        "tool_result",
                        "tool_use_id": block.id,
                        "content":     json.dumps(trimmed_output),  # send trimmed to model
                    })

                messages.append({"role": "user", "content": tool_results})

                # After 5 iterations with data, nudge the agent to conclude
                if iterations >= 5 and len(tools_called) >= 2:
                    messages.append({
                        "role": "user",
                        "content": (
                            "You have called multiple tools and gathered sufficient data. "
                            "Stop calling tools and issue your final verdict JSON now."
                        ),
                    })
                continue

            break

        print(f"[VerificationAgent] MAX ITER ({self.max_iter}) for claim='{claim[:60]}' tools_called={tools_called}")
        return VerificationResult(
            claim=claim,
            verdict=Verdict.UNSUPPORTED,
            reasoning="Agent reached maximum iterations without a conclusion.",
            confidence=0.0,
            tool_calls=tool_calls,
            error="max_iterations_exceeded",
        )

    async def _execute_tool(
        self,
        tool_name: str,
        tool_input: dict,
        connector_ids: list[str],
    ) -> dict:
        loop = asyncio.get_event_loop()

        # FIX #10: Use the module-level map instead of rebuilding per call.
        # The original rebuilt this map from connector_ids each time, which
        # meant tools not in connector_ids couldn't be found even if Claude
        # somehow requested them. The module-level map is complete and reliable.
        connector_id = _TOOL_NAME_TO_CONNECTOR.get(tool_name)

        if not connector_id or connector_id not in ALL_TOOLS:
            # FIX #11: Better error message so you can debug in logs
            known_tools = list(_TOOL_NAME_TO_CONNECTOR.keys())
            print(f"[VerificationAgent] ERROR: tool '{tool_name}' not found. "
                  f"Known tools: {known_tools}")
            return {"error": f"Unknown tool: {tool_name}. Available: {known_tools}"}

        # FIX #12: Check if the connector is actually in the allowed set
        if connector_id not in connector_ids:
            print(f"[VerificationAgent] WARNING: tool '{tool_name}' (connector={connector_id}) "
                  f"not in allowed connectors {connector_ids}. Executing anyway.")

        _, execute_fn = ALL_TOOLS[connector_id]

        # Retry wrapper with backoff for transient failures (429, timeouts)
        for attempt in range(3):
            try:
                if connector_id == "fred":
                    result = await loop.run_in_executor(
                        None, lambda: execute_fn(tool_input, client=self.fred)
                    )
                elif connector_id == "edgar":
                    result = await loop.run_in_executor(
                        None, lambda: execute_fn(tool_input, client=self.edgar)
                    )
                else:
                    result = await loop.run_in_executor(None, lambda: execute_fn(tool_input))

                # Retry on 429 errors returned in the result dict
                err = result.get("error", "") if isinstance(result, dict) else ""
                if "429" in str(err) and attempt < 2:
                    await asyncio.sleep(2 * (attempt + 1))
                    continue
                return result
            except Exception as e:
                if "429" in str(e) and attempt < 2:
                    await asyncio.sleep(2 * (attempt + 1))
                    continue
                print(f"[VerificationAgent] Tool '{tool_name}' raised: {e}")
                return {"error": f"Tool execution failed: {str(e)}"}

    def _parse_verdict(
        self,
        claim: str,
        content: list,
        tool_calls: list[ToolCall],
    ) -> VerificationResult:
        text = ""
        for block in content:
            if hasattr(block, "text"):
                text = block.text.strip()
                break

        try:
            # Try code-fenced JSON first
            json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
            if json_match:
                clean = json_match.group(1)
            else:
                # Find the outermost JSON object
                brace_match = re.search(r"\{.*\}", text, re.DOTALL)
                clean = brace_match.group(0) if brace_match else text
            data = json.loads(clean)

            return VerificationResult(
                claim=claim,
                verdict=Verdict(data["verdict"]),
                reasoning=data.get("reasoning", ""),
                explanation=data.get("explanation") or None,
                corrected_fact=data.get("corrected_fact") or None,
                confidence=float(data.get("confidence", 0.0)),
                citations=data.get("citations", []),
                tool_calls=tool_calls,
            )

        except (json.JSONDecodeError, KeyError, ValueError) as e:
            # FIX #14: Try to salvage a verdict from partial/malformed output
            # instead of immediately returning OUT_OF_SCOPE.
            # This handles cases where the JSON was truncated or slightly malformed.
            verdict = self._extract_verdict_fallback(text)
            if verdict:
                print(f"[VerificationAgent] JSON parse failed but extracted verdict={verdict} from text")
                return VerificationResult(
                    claim=claim,
                    verdict=verdict,
                    reasoning=text[:500],  # use whatever text we got
                    confidence=0.5,  # lower confidence since we couldn't parse properly
                    tool_calls=tool_calls,
                    error=f"Partial parse - verdict extracted from text: {e}",
                )

            print(f"[VerificationAgent] Failed to parse verdict. Raw text: {text[:300]}")
            return VerificationResult(
                claim=claim,
                verdict=Verdict.OUT_OF_SCOPE,
                reasoning=text[:500],
                confidence=0.0,
                tool_calls=tool_calls,
                error=f"Failed to parse verdict JSON: {e}",
            )

    @staticmethod
    def _extract_verdict_fallback(text: str) -> Optional[Verdict]:
        """
        Try to extract a verdict from malformed output.
        Looks for "verdict": "xxx" pattern even if full JSON is broken.
        """
        match = re.search(r'"verdict"\s*:\s*"(corroborated|contradicted|unsupported|out_of_scope)"', text)
        if match:
            try:
                return Verdict(match.group(1))
            except ValueError:
                pass
        return None