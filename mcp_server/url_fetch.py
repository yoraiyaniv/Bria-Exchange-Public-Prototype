"""URL fetching utility for Exchange public verification.

Extracts the main article body from a web page and strips
navigation, references, captions, and other wrapper noise so
only verifiable prose reaches the pipeline.
"""

import re
from html.parser import HTMLParser

import httpx
import trafilatura

# Maximum characters to send to the verification pipeline.
# The verification API can reliably process ~250 words before
# the LLM output exceeds its JSON response budget. Keep this
# tight to avoid pipeline 500s on claim-dense articles.
_MAX_TEXT_CHARS = 1_500


class _MetaExtractor(HTMLParser):
    """Extract og:site_name and <title> from raw HTML."""

    def __init__(self):
        super().__init__()
        self.og_site_name: str | None = None
        self.title: str | None = None
        self._in_title = False
        self._title_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]):
        if tag == "meta":
            attr_dict = {k: v for k, v in attrs if v is not None}
            if attr_dict.get("property") == "og:site_name":
                self.og_site_name = attr_dict.get("content")
        if tag == "title":
            self._in_title = True

    def handle_endtag(self, tag: str):
        if tag == "title":
            self._in_title = False
            self.title = "".join(self._title_parts).strip()

    def handle_data(self, data: str):
        if self._in_title:
            self._title_parts.append(data)


def _extract_publication(html: str) -> str | None:
    parser = _MetaExtractor()
    try:
        parser.feed(html)
    except Exception:
        return None

    if parser.og_site_name:
        return parser.og_site_name

    if parser.title:
        for sep in [" - ", " | "]:
            if sep in parser.title:
                return parser.title.rsplit(sep, 1)[-1].strip()

    return None


# ── Post-extraction cleanup ──────────────────────────────────────────────

# Wikipedia-style citation brackets: [1], [27], [a], [edit], [citation needed]
_RE_WIKI_BRACKETS = re.compile(r"\[(?:\d+|[a-z]|edit|citation needed)\]", re.IGNORECASE)

# Lines that are clearly section headers / nav / boilerplate
_BOILERPLATE_PATTERNS = re.compile(
    r"^\s*("
    r"(see also|references|external links|further reading|notes|bibliography|sources)"
    r"|skip to .*content"
    r"|advertisement"
    r"|share this article"
    r"|sign up for"
    r"|subscribe"
    r"|newsletter"
    r"|related (articles|stories|posts)"
    r"|read (more|next)"
    r"|copyright ©"
    r"|all rights reserved"
    r"|terms (of|and) (use|service)"
    r"|privacy policy"
    r"|cookie (policy|settings)"
    r")\s*$",
    re.IGNORECASE,
)

# Lines that look like reference entries (start with "- " and contain "Retrieved" or " via ")
_RE_REFERENCE_LINE = re.compile(
    r"^-\s+.*(?:Retrieved|accessed|archived|– via |ISBN|doi:|https?://)\s*",
    re.IGNORECASE,
)

# Image captions often start with these
_RE_CAPTION = re.compile(
    r"^(?:Image|Photo|Figure|Illustration|Getty|AP Photo|Credit|Source)\s*[:;]",
    re.IGNORECASE,
)


def _clean_extracted_text(text: str) -> str:
    """Strip noise from trafilatura output to isolate article prose."""

    # Remove wiki-style citation brackets
    text = _RE_WIKI_BRACKETS.sub("", text)

    lines = text.split("\n")
    cleaned: list[str] = []
    in_references = False

    for line in lines:
        stripped = line.strip()
        if not stripped:
            # Keep paragraph breaks but don't accumulate empties
            if cleaned and cleaned[-1] != "":
                cleaned.append("")
            continue

        # Detect start of a reference / "See also" / "External links" section
        if re.match(
            r"^(References|See also|External links|Further reading|Notes|Bibliography|Sources)\s*$",
            stripped,
            re.IGNORECASE,
        ):
            in_references = True
            continue

        # Once in a references section, skip everything
        if in_references:
            # A new substantial paragraph (>80 chars, no dash prefix) might mean
            # the article continues after references (rare, but possible)
            if len(stripped) > 80 and not stripped.startswith("-"):
                in_references = False
            else:
                continue

        # Skip individual reference lines even outside the References section
        if _RE_REFERENCE_LINE.match(stripped):
            continue

        # Skip boilerplate nav / footer lines
        if _BOILERPLATE_PATTERNS.match(stripped):
            continue

        # Skip image captions
        if _RE_CAPTION.match(stripped):
            continue

        # Skip very short lines that look like UI elements (< 5 words, no period)
        words = stripped.split()
        if len(words) < 4 and not stripped.endswith(".") and not stripped.endswith(":"):
            continue

        cleaned.append(stripped)

    result = "\n".join(cleaned).strip()

    # Truncate to max length on a sentence boundary
    if len(result) > _MAX_TEXT_CHARS:
        truncated = result[:_MAX_TEXT_CHARS]
        # Find the last sentence-ending punctuation
        last_period = max(
            truncated.rfind(". "),
            truncated.rfind(".\n"),
            truncated.rfind("? "),
            truncated.rfind("! "),
        )
        if last_period > _MAX_TEXT_CHARS // 2:
            result = truncated[: last_period + 1]
        else:
            result = truncated

    return result


async def fetch_url_content(url: str) -> dict:
    """Fetch a URL and extract readable text content.

    Returns {"text": str, "publication": str | None, "url": str}.
    Raises TimeoutError on timeout, ValueError on inaccessible/empty content.
    """
    try:
        async with httpx.AsyncClient(follow_redirects=True) as client:
            resp = await client.get(
                url,
                timeout=10.0,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/124.0.0.0 Safari/537.36"
                    ),
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.5",
                },
            )
    except httpx.TimeoutException:
        raise TimeoutError("Could not reach this page within 10 seconds.")

    html = resp.text
    publication = _extract_publication(html)

    # Use precision mode + strip links/images to reduce noise
    text = trafilatura.extract(
        html,
        include_comments=False,
        include_tables=False,
        include_links=False,
        include_images=False,
        favor_precision=True,
        deduplicate=True,
    )

    if resp.status_code in (401, 403) or not text:
        if text:
            # Partial text despite auth error — return cleaned version
            return {
                "text": _clean_extracted_text(text),
                "publication": publication,
                "url": url,
            }
        raise ValueError(
            "We could only access part of this page. Results are based on what was publicly available."
        )

    cleaned = _clean_extracted_text(text)

    if not cleaned:
        raise ValueError(
            "We could only access part of this page. Results are based on what was publicly available."
        )

    return {"text": cleaned, "publication": publication, "url": url}
