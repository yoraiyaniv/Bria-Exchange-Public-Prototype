"""
Bria Exchange — Wikipedia Tool
Searches Wikipedia for factual summaries, definitions, and encyclopedic information.
Good for: general knowledge claims about people, organisations, events,
          concepts, and places where more specialised sources don't apply.
"""

import re
import requests
from urllib.parse import quote

WIKIPEDIA_API_PHP   = "https://{lang}.wikipedia.org/w/api.php"
WIKIPEDIA_REST_V1   = "https://{lang}.wikipedia.org/api/rest_v1/page/summary/{title}"
TIMEOUT             = 10
_MAX_EXTRACT_CHARS  = 10000  # Cover History, IPO, Founding, and other key sections
_UA                 = {"User-Agent": "BriaExchange/1.0 (fact-verification)"}


TOOL_DEFINITION = {
    "name": "search_wikipedia",
    "description": (
        "Search Wikipedia for factual summaries and detailed article content. "
        "Returns both a short summary AND a longer extract with key facts from the article. "
        "Use for general knowledge claims about people, organizations, "
        "events, concepts, and places."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search term or topic (e.g. 'Tesla Inc history', 'Marie Curie', 'French Revolution').",
            },
            "language": {
                "type": "string",
                "description": "ISO 639-1 language code for the Wikipedia edition to query. Default: 'en'.",
                "default": "en",
            },
        },
        "required": ["query"],
    },
}


def _strip_html(html: str, remove_tables: bool = False) -> str:
    """Lightweight HTML → plain text (no external deps)."""
    # Remove infobox / sidebar tables that inflate text without narrative value
    if remove_tables:
        html = re.sub(r'<table[^>]*class="[^"]*infobox[^"]*"[^>]*>.*?</table>', '', html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r'<table[^>]*class="[^"]*sidebar[^"]*"[^>]*>.*?</table>', '', html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r'<table[^>]*class="[^"]*mbox[^"]*"[^>]*>.*?</table>', '', html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r'<div[^>]*class="[^"]*navbox[^"]*"[^>]*>.*?</div>', '', html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL)
    text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL)
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'&nbsp;', ' ', text)
    text = re.sub(r'&amp;', '&', text)
    text = re.sub(r'&lt;', '<', text)
    text = re.sub(r'&gt;', '>', text)
    text = re.sub(r'&#\d+;', '', text)
    text = re.sub(r'\[\d+\]', '', text)        # citation brackets
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def _fetch_full_extract(title: str, language: str) -> str:
    """Fetch the plain-text content of a Wikipedia article's key sections.

    Uses the MediaWiki parse API to retrieve the intro + first several
    narrative sections (History, Founding, IPO, etc.) as plain text.
    Much richer than the TextExtracts API which is limited to the intro.
    """
    api_url = WIKIPEDIA_API_PHP.format(lang=language)
    sections_text = []

    try:
        # Step 1: Get section list
        sec_resp = requests.get(
            api_url,
            params={
                "action": "parse",
                "page":   title,
                "prop":   "sections",
                "format": "json",
            },
            timeout=TIMEOUT,
            headers=_UA,
        )
        sec_resp.raise_for_status()
        sections = sec_resp.json().get("parse", {}).get("sections", [])

        # Step 2: Fetch intro (section 0)
        intro_resp = requests.get(
            api_url,
            params={
                "action":  "parse",
                "page":    title,
                "prop":    "text",
                "section": 0,
                "format":  "json",
            },
            timeout=TIMEOUT,
            headers=_UA,
        )
        intro_resp.raise_for_status()
        intro_html = intro_resp.json().get("parse", {}).get("text", {}).get("*", "")
        intro_text = _strip_html(intro_html, remove_tables=True)
        if intro_text:
            sections_text.append(intro_text)

        # Step 3: Fetch key narrative sections (first 6 level-2/3 sections)
        # These typically cover History, Founding, IPO, Key events, etc.
        fetched = 0
        total_chars = len(intro_text)
        for sec in sections:
            if fetched >= 6 or total_chars >= _MAX_EXTRACT_CHARS:
                break
            level = int(sec.get("level", 2))
            if level > 3:
                continue  # skip deeply nested sections (individual products, etc.)
            idx = sec.get("index")
            sec_name = sec.get("line", "")
            # Skip non-narrative sections
            skip_names = {"see also", "references", "external links", "notes",
                          "further reading", "bibliography", "gallery"}
            if sec_name.lower() in skip_names:
                continue

            try:
                sec_resp = requests.get(
                    api_url,
                    params={
                        "action":  "parse",
                        "page":    title,
                        "prop":    "text",
                        "section": idx,
                        "format":  "json",
                    },
                    timeout=TIMEOUT,
                    headers=_UA,
                )
                sec_resp.raise_for_status()
                sec_html = sec_resp.json().get("parse", {}).get("text", {}).get("*", "")
                sec_text = _strip_html(sec_html)
                if sec_text:
                    sections_text.append(f"\n=== {sec_name} ===\n{sec_text}")
                    total_chars += len(sec_text)
                    fetched += 1
            except requests.RequestException:
                continue

        return "\n".join(sections_text)[:_MAX_EXTRACT_CHARS]

    except requests.RequestException:
        pass
    return ""


def _extract_infobox_text(wikitext: str) -> str:
    """Extract just the infobox template from wikitext, handling nested braces."""
    start = -1
    for pattern in [r'\{\{Infobox', r'\{\{infobox']:
        m = re.search(pattern, wikitext)
        if m:
            start = m.start()
            break
    if start < 0:
        return ""
    # Track brace depth to find the matching closing }}
    depth = 0
    i = start
    while i < len(wikitext):
        if wikitext[i:i+2] == '{{':
            depth += 1
            i += 2
        elif wikitext[i:i+2] == '}}':
            depth -= 1
            if depth == 0:
                return wikitext[start:i+2]
            i += 2
        else:
            i += 1
    return wikitext[start:]  # unclosed — return what we have


def _clean_wiki_value(val: str) -> str:
    """Clean a wiki markup value to plain text."""
    # Remove <ref>...</ref> and self-closing <ref/>
    val = re.sub(r'<ref[^>]*>.*?</ref>', '', val, flags=re.DOTALL)
    val = re.sub(r'<ref[^>]*/>', '', val)
    val = re.sub(r'<!--.*?-->', '', val, flags=re.DOTALL)
    # Resolve {{Start date|Y|M|D}} → Y-M-D
    val = re.sub(r'\{\{(?:Start date(?: and age)?|birth date(?: and age)?|end date)\|(\d{4})\|(\d{1,2})\|(\d{1,2})[^}]*\}\}',
                 r'\1-\2-\3', val, flags=re.IGNORECASE)
    # Resolve {{nowrap|X}} → X
    val = re.sub(r'\{\{nowrap\|([^}]*)\}\}', r'\1', val, flags=re.IGNORECASE)
    # Remove remaining {{ }} templates
    val = re.sub(r'\{\{[^}]*\}\}', '', val)
    # Clean [[ ]] wiki links: [[Target|Display]] → Display, [[Target]] → Target
    val = re.sub(r'\[\[(?:[^|\]]*\|)?([^\]]*)\]\]', r'\1', val)
    # Remove HTML tags
    val = re.sub(r'<[^>]+>', ' ', val)
    val = val.replace('&nbsp;', ' ')
    val = re.sub(r'&\w+;', '', val)
    val = re.sub(r'\]\]', '', val)            # stray closing brackets
    val = re.sub(r'\s+', ' ', val).strip().strip('|').strip()
    return val


def _fetch_infobox_data(title: str, language: str) -> dict:
    """Fetch structured infobox data via the raw wikitext parse endpoint.

    Extracts key=value pairs from the article's infobox, handling
    multi-line values like {{Unbulleted list|...}} properly.
    """
    api_url = WIKIPEDIA_API_PHP.format(lang=language)
    try:
        resp = requests.get(
            api_url,
            params={
                "action": "parse",
                "page":   title,
                "prop":   "wikitext",
                "section": 0,
                "format": "json",
            },
            timeout=TIMEOUT,
            headers=_UA,
        )
        resp.raise_for_status()
        wikitext = resp.json().get("parse", {}).get("wikitext", {}).get("*", "")

        # First, isolate just the infobox template
        infobox_text = _extract_infobox_text(wikitext)
        if not infobox_text:
            return {}

        # Split on top-level "| key =" boundaries
        # Each field starts with \n| or \n | at the top level of the infobox
        infobox = {}
        skip_keys = frozenset({
            'image', 'logo', 'image_size', 'caption', 'alt',
            'logo_upright', 'image_upright', 'image_caption', 'small',
            'audio', 'module', 'embed',
        })

        # Use regex to find "| key = value" blocks, where value may span multiple lines
        # Split the infobox into field chunks
        field_pattern = re.compile(r'^\s*\|\s*(\w[\w\s]*?)\s*=\s*', re.MULTILINE)
        matches = list(field_pattern.finditer(infobox_text))

        for i, match in enumerate(matches):
            key = match.group(1).strip().lower().replace(" ", "_")
            if key in skip_keys:
                continue

            # Value runs from end of key= to the start of the next field (or end of infobox)
            val_start = match.end()
            val_end = matches[i + 1].start() if i + 1 < len(matches) else len(infobox_text) - 2
            raw_val = infobox_text[val_start:val_end].strip()

            # Handle list templates: extract items from multi-line {{Unbulleted list|...}}
            list_match = re.match(r'\{\{(?:Unbulleted list|Plainlist|Flatlist|Ubl|Hlist)', raw_val, re.IGNORECASE)
            if list_match:
                # Extract items: each on a line starting with |
                items = re.findall(r'\|\s*(.+)', raw_val)
                cleaned_items = []
                for item in items:
                    cleaned = _clean_wiki_value(item)
                    if cleaned and len(cleaned) > 1:
                        cleaned_items.append(cleaned)
                val = "; ".join(cleaned_items) if cleaned_items else ""
            else:
                val = _clean_wiki_value(raw_val)

            # Filter out garbage values
            if val and len(val) > 1 and not val.startswith('{'):
                infobox[key] = val

        return infobox
    except (requests.RequestException, KeyError):
        return {}


def execute_search_wikipedia_tool(tool_input: dict, _retries: int = 2) -> dict:
    """Search Wikipedia with automatic retry on transient failures."""
    query    = tool_input.get("query", "").strip()
    language = tool_input.get("language", "en").strip() or "en"

    if not query:
        return {"error": "query is required"}

    search_url  = WIKIPEDIA_API_PHP.format(lang=language)
    summary_url = WIKIPEDIA_REST_V1.format(lang=language, title="{title}")

    try:
        # Step 1: Full-text search for matching page titles
        search_resp = requests.get(
            search_url,
            params={
                "action":   "query",
                "list":     "search",
                "srsearch": query,
                "srlimit":  3,
                "format":   "json",
            },
            timeout=TIMEOUT,
            headers=_UA,
        )
        search_resp.raise_for_status()
        search_data = search_resp.json()

        search_hits = search_data.get("query", {}).get("search", [])
        if not search_hits:
            return {
                "found":   False,
                "query":   query,
                "message": f"No Wikipedia articles found for '{query}'.",
                "source":  "Wikipedia",
            }

        top_title   = search_hits[0].get("title", "")
        other_hits  = search_hits[1:]

        # Step 2: Fetch the REST summary (short intro paragraph)
        encoded_title = quote(top_title.replace(" ", "_"), safe="")
        summary_resp  = requests.get(
            summary_url.format(title=encoded_title),
            timeout=TIMEOUT,
            headers=_UA,
        )
        summary_resp.raise_for_status()
        summary_data = summary_resp.json()

        short_summary  = summary_data.get("extract", "")
        desktop_url    = (
            summary_data.get("content_urls", {})
            .get("desktop", {})
            .get("page", f"https://{language}.wikipedia.org/wiki/{encoded_title}")
        )

        # Step 3: Fetch the full plain-text extract (much more detail)
        full_extract = _fetch_full_extract(top_title, language)

        # Step 4: Fetch structured infobox data (dates, exchanges, key people)
        infobox = _fetch_infobox_data(top_title, language)

        other_results = [
            {
                "title":   hit.get("title", ""),
                "snippet": hit.get("snippet", ""),
            }
            for hit in other_hits
        ]

        return {
            "found":          True,
            "query":          query,
            "title":          summary_data.get("title", top_title),
            "description":    summary_data.get("description", ""),
            "summary":        short_summary,
            "full_extract":   full_extract,
            "infobox":        infobox if infobox else None,
            "url":            desktop_url,
            "last_modified":  summary_data.get("timestamp", ""),
            "other_results":  other_results,
            "source":         "Wikipedia",
        }

    except requests.RequestException as exc:
        if _retries > 0:
            import time; time.sleep(1)
            return execute_search_wikipedia_tool(tool_input, _retries - 1)
        return {"error": f"Wikipedia request failed: {exc}"}
