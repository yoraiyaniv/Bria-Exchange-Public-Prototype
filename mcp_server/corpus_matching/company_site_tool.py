"""
Bria Exchange — Official Company Site Tool
Fetches and extracts text from official company websites.
Use to verify claims about pricing, product specs, team, and company facts
that are only available on the company's own website.

Only returns content from the exact domain requested — no third-party sources.
"""

import re
from urllib.parse import urlparse

import requests

TIMEOUT = 15
MAX_CONTENT_LENGTH = 8000  # chars to return

# Well-known official domains for common companies
KNOWN_DOMAINS: dict[str, str] = {
    "openai": "https://openai.com",
    "anthropic": "https://www.anthropic.com",
    "google": "https://about.google",
    "microsoft": "https://www.microsoft.com",
    "apple": "https://www.apple.com",
    "meta": "https://about.meta.com",
    "amazon": "https://www.aboutamazon.com",
    "tesla": "https://www.tesla.com",
    "nvidia": "https://www.nvidia.com",
    "netflix": "https://www.netflix.com",
    "spotify": "https://www.spotify.com",
    "salesforce": "https://www.salesforce.com",
    "adobe": "https://www.adobe.com",
    "ibm": "https://www.ibm.com",
    "oracle": "https://www.oracle.com",
    "intel": "https://www.intel.com",
    "amd": "https://www.amd.com",
    "stripe": "https://stripe.com",
    "shopify": "https://www.shopify.com",
    "uber": "https://www.uber.com",
    "airbnb": "https://www.airbnb.com",
    "twitter": "https://about.x.com",
    "x": "https://about.x.com",
}

# Common useful page paths to try
USEFUL_PATHS: dict[str, list[str]] = {
    "pricing": ["/pricing", "/api/pricing", "/plans", "/products"],
    "about": ["/about", "/about-us", "/company", "/about/company"],
    "team": ["/about/team", "/team", "/leadership", "/about/leadership"],
    "product": ["/products", "/platform", "/solutions"],
    "api": ["/api", "/docs/api", "/developers", "/api/pricing"],
    "investors": ["/investor-relations", "/investors", "/ir"],
}

TOOL_DEFINITION = {
    "name": "fetch_company_site",
    "description": (
        "Fetch content from an official company website. Use to verify claims about "
        "pricing, product features, API costs, company facts, team members, and other "
        "information only available on the company's own site. "
        "Provide either a full URL or a company name + page_type. "
        "ONLY returns content from the official company domain — no third-party sources."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": (
                    "Full URL to fetch (e.g. 'https://openai.com/api/pricing'). "
                    "If provided, company and page_type are ignored."
                ),
            },
            "company": {
                "type": "string",
                "description": (
                    "Company name (e.g. 'openai', 'anthropic', 'apple'). "
                    "Used with page_type to construct the URL."
                ),
            },
            "page_type": {
                "type": "string",
                "enum": ["pricing", "about", "team", "product", "api", "investors"],
                "description": "Type of page to fetch. Used with company to find the right URL.",
            },
            "search_text": {
                "type": "string",
                "description": (
                    "Text to search for in the page content. If provided, only paragraphs "
                    "containing this text (case-insensitive) are returned."
                ),
            },
        },
        "required": [],
    },
}


def _extract_text(html: str) -> str:
    """Extract readable text from HTML, stripping tags and scripts."""
    try:
        import trafilatura
        text = trafilatura.extract(html, include_tables=True, include_links=False)
        if text:
            return text
    except Exception:
        pass

    # Fallback: simple tag stripping
    text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<style[^>]*>.*?</style>", "", html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def execute_company_site_tool(tool_input: dict) -> dict:
    url = (tool_input.get("url") or "").strip()
    company = (tool_input.get("company") or "").strip().lower()
    page_type = (tool_input.get("page_type") or "").strip().lower()
    search_text = (tool_input.get("search_text") or "").strip()

    if not url and not company:
        return {"error": "Provide either 'url' or 'company' parameter."}

    # Build URL from company + page_type if no direct URL
    urls_to_try = []
    if url:
        urls_to_try = [url]
    else:
        base = KNOWN_DOMAINS.get(company)
        if not base:
            # Try constructing from company name
            base = f"https://www.{company}.com"

        if page_type and page_type in USEFUL_PATHS:
            for path in USEFUL_PATHS[page_type]:
                urls_to_try.append(base + path)
        else:
            urls_to_try.append(base)

    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; BriaExchange/1.0; fact-verification)",
        "Accept": "text/html,application/xhtml+xml",
    }

    last_error = None
    for try_url in urls_to_try:
        try:
            resp = requests.get(try_url, headers=headers, timeout=TIMEOUT, allow_redirects=True)
            if resp.status_code == 404:
                last_error = f"Page not found: {try_url}"
                continue
            if resp.status_code >= 400:
                last_error = f"HTTP {resp.status_code} from {try_url}"
                continue

            # Verify we're on the official domain (prevent redirects to third-party)
            final_domain = urlparse(resp.url).netloc.lower()
            if company:
                expected = company.replace(" ", "").replace("-", "")
                if expected not in final_domain.replace(".", "").replace("-", ""):
                    return {
                        "found": False,
                        "url": try_url,
                        "message": f"Redirected to {final_domain} which is not the official {company} site.",
                        "source": f"Official site ({company})",
                    }

            text = _extract_text(resp.text)
            if not text:
                last_error = f"No extractable text from {try_url}"
                continue

            # Filter by search text if provided
            if search_text:
                paragraphs = text.split("\n")
                matching = [p for p in paragraphs if search_text.lower() in p.lower()]
                if matching:
                    text = "\n".join(matching)
                else:
                    # Try sentence-level matching
                    sentences = re.split(r"[.!?]\s+", text)
                    matching = [s for s in sentences if search_text.lower() in s.lower()]
                    if matching:
                        text = ". ".join(matching) + "."
                    # If nothing matches, return full text (let model decide)

            # Truncate
            if len(text) > MAX_CONTENT_LENGTH:
                cutoff = text.rfind("\n", 0, MAX_CONTENT_LENGTH)
                text = text[: cutoff if cutoff > 0 else MAX_CONTENT_LENGTH]

            return {
                "found": True,
                "url": resp.url,
                "domain": final_domain,
                "content": text,
                "content_length": len(text),
                "source": f"Official site ({final_domain})",
            }

        except requests.RequestException as exc:
            last_error = f"Request failed for {try_url}: {exc}"
            continue

    return {
        "found": False,
        "urls_tried": urls_to_try,
        "message": last_error or "Could not fetch content from any URL.",
        "source": "Official company site",
    }


if __name__ == "__main__":
    import json
    result = execute_company_site_tool({
        "company": "openai",
        "page_type": "pricing",
        "search_text": "token",
    })
    print(json.dumps(result, indent=2)[:2000])
