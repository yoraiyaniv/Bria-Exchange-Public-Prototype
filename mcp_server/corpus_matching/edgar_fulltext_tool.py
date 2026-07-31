"""
Bria Exchange — EDGAR Full-Text Search (EFTS) Tool
Searches the full text of SEC filings (10-K, 10-Q, S-1, 8-K, etc.)
for specific facts about companies — founding dates, IPO details,
funding rounds, acquisitions, leadership changes, and more.

This complements the XBRL tool (edgar_tool.py) which only has
structured financial figures. EFTS searches the actual prose of filings.
"""

import re
import time
import requests

EFTS_URL = "https://efts.sec.gov/LATEST/search-index"
TIMEOUT = 10
REQUEST_DELAY = 0.12  # SEC asks for max 10 req/s
_UA = {"User-Agent": "BriaExchange/1.0 contact@briaexchange.com"}


EDGAR_FULLTEXT_TOOL_DEFINITION = {
    "name": "search_edgar_filings",
    "description": (
        "Search the full text of SEC EDGAR filings (10-K, 10-Q, S-1, 8-K, etc.) "
        "for specific facts about US public companies. This searches the actual prose "
        "of filings — company history, IPO details, founding information, risk factors, "
        "executive changes, acquisitions, funding rounds, share prices. "
        "Returns filing metadata with company name, form type, and filing date. "
        "This is an authoritative US government source (SEC)."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": (
                    "Search terms to find in filing text. Use quotes for exact phrases. "
                    "Examples: '\"initial public offering\" \"per share\"', "
                    "'\"Series A\" funding', '\"incorporated in\" \"2003\"'. "
                    "Boolean operators AND, OR, NOT are supported."
                ),
            },
            "company": {
                "type": "string",
                "description": "Company name to include in the search (e.g. 'Tesla', 'Apple').",
            },
            "forms": {
                "type": "string",
                "description": (
                    "Comma-separated filing types. Common: "
                    "S-1 (IPO registration), 10-K (annual report), 10-Q (quarterly), "
                    "8-K (material events). Leave blank for all types."
                ),
            },
            "start_date": {
                "type": "string",
                "description": "Start date in YYYY-MM-DD format (optional).",
            },
            "end_date": {
                "type": "string",
                "description": "End date in YYYY-MM-DD format (optional).",
            },
        },
        "required": ["query"],
    },
}


def _fetch_filing_snippet(cik: str, adsh: str, search_terms: list[str], max_chars: int = 1500) -> str:
    """Fetch the primary filing document and extract a text snippet around search terms."""
    try:
        cik_clean = cik.lstrip("0")
        adsh_clean = adsh.replace("-", "")
        base_url = f"https://www.sec.gov/Archives/edgar/data/{cik_clean}/{adsh_clean}"

        # Use the JSON index to find the main filing document
        time.sleep(REQUEST_DELAY)
        idx_resp = requests.get(f"{base_url}/index.json", timeout=TIMEOUT, headers=_UA)
        idx_resp.raise_for_status()
        items = idx_resp.json().get("directory", {}).get("item", [])

        # Find the largest HTM file (typically the main filing document)
        htm_files = []
        for item in items:
            name = item.get("name", "")
            if name.endswith(".htm") and not name.startswith("0") and "index" not in name.lower():
                try:
                    size = int(item.get("size", "0").replace(",", ""))
                except (ValueError, AttributeError):
                    size = 0
                htm_files.append((name, size))

        if not htm_files:
            return ""

        # Pick the largest HTM file (main document)
        htm_files.sort(key=lambda x: x[1], reverse=True)
        doc_name = htm_files[0][0]
        doc_size = htm_files[0][1]

        # For very large filings, only fetch the first 500KB
        time.sleep(REQUEST_DELAY)
        doc_url = f"{base_url}/{doc_name}"
        doc_resp = requests.get(
            doc_url, timeout=15, headers={**_UA, "Range": f"bytes=0-{min(doc_size, 500000)}"},
        )
        # Some servers ignore Range header — that's fine, we'll just truncate
        raw_text = doc_resp.text[:500000]

        # Strip HTML to plain text
        text = re.sub(r'<style[^>]*>.*?</style>', '', raw_text, flags=re.DOTALL)
        text = re.sub(r'<[^>]+>', ' ', text)
        text = re.sub(r'&nbsp;', ' ', text)
        text = re.sub(r'&amp;', '&', text)
        text = re.sub(r'&#\d+;', '', text)
        text = re.sub(r'\s+', ' ', text).strip()

        # Find the best snippet around the search terms
        # Skip past TOC — find where the actual body starts
        text_lower = text.lower()

        # Detect body start: look for section headers that mark prose content
        body_start = 0
        for marker in ["prospectus summary", "summary this prospectus", "business overview",
                        "overview we", "our company", "item 1.", "part i"]:
            idx = text_lower.find(marker)
            if idx > 2000:  # must be past the TOC header area
                body_start = idx
                break
        if body_start == 0:
            body_start = min(15000, len(text) // 4)  # aggressive TOC skip

        for term in search_terms:
            term_clean = term.strip('"').lower()
            idx = text_lower.find(term_clean, body_start)
            if idx >= 0:
                start = max(0, idx - 300)
                end = min(len(text), idx + max_chars - 300)
                return text[start:end].strip()

        # Fallback: return content from body start
        if body_start > 0 and body_start < len(text):
            return text[body_start:body_start + max_chars].strip()

        return ""
    except Exception:
        return ""


def execute_search_edgar_filings(tool_input: dict) -> dict:
    query = tool_input.get("query", "").strip()
    company = tool_input.get("company", "").strip()
    forms = tool_input.get("forms", "").strip()
    start_date = tool_input.get("start_date", "")
    end_date = tool_input.get("end_date", "")

    if not query:
        return {"error": "query is required"}

    # Build query — include company name in search
    full_query = f'{query} "{company}"' if company else query

    params = {"q": full_query, "from": 0}
    if forms:
        params["forms"] = forms
    if start_date:
        params["startdt"] = start_date
    if end_date:
        params["enddt"] = end_date

    time.sleep(REQUEST_DELAY)

    try:
        resp = requests.get(EFTS_URL, params=params, timeout=TIMEOUT, headers=_UA)
        resp.raise_for_status()
        data = resp.json()

        total = data.get("hits", {}).get("total", {}).get("value", 0)
        hits = data.get("hits", {}).get("hits", [])

        if not hits:
            return {
                "found": False,
                "query": query,
                "company": company or None,
                "message": f"No SEC filings found matching '{query}'.",
                "source": "SEC EDGAR (EFTS)",
            }

        # Extract search terms for snippet highlighting
        search_terms = re.findall(r'"([^"]+)"', query)
        if not search_terms:
            search_terms = query.split()[:3]

        # Filter to find the target company's filing first
        target_hits = hits
        if company:
            company_lower = company.lower()
            filtered = [h for h in hits if company_lower in str(h.get("_source", {}).get("display_names", "")).lower()]
            if filtered:
                target_hits = filtered

        filings = []
        for hit in target_hits[:3]:
            source = hit.get("_source", {})
            cik = (source.get("ciks") or [""])[0]
            adsh = source.get("adsh", "")
            display = (source.get("display_names") or ["Unknown"])[0]

            # Fetch a text snippet from the actual filing
            snippet = _fetch_filing_snippet(cik, adsh, search_terms) if cik and adsh else ""

            filings.append({
                "company": display,
                "form_type": source.get("form", ""),
                "filed_date": source.get("file_date", ""),
                "description": source.get("file_description") or source.get("form", ""),
                "snippet": snippet[:1500] if snippet else "Filing found but text snippet unavailable.",
                "source": "SEC EDGAR",
            })

        return {
            "found": True,
            "query": query,
            "company": company or None,
            "total": total,
            "filings": filings,
            "source": "SEC EDGAR (EFTS)",
        }

    except requests.RequestException as exc:
        return {"error": f"EDGAR full-text search failed: {exc}"}
