"""
Bria Exchange — Claim Extraction Module
Extracts atomic, verifiable claims from text using Claude.
Supports plain text, PDF, and DOCX inputs.
"""

import json
import re
import os
import uuid
from dataclasses import dataclass, asdict
from enum import Enum
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv
load_dotenv()

import anthropic
import fitz  # pymupdf
from docx import Document


# ── Types ──────────────────────────────────────────────────────────────────────

class ClaimType(str, Enum):
    FACTUAL      = "factual"       # asserting a fact about the world
    STATISTICAL  = "statistical"   # numerical / quantitative assertion
    CAUSAL       = "causal"        # X causes / leads to Y
    DEFINITIONAL = "definitional"  # X is defined as / means Y


class Verifiability(str, Enum):
    VERIFIABLE = "verifiable"   # can be checked against a corpus
    AMBIGUOUS  = "ambiguous"    # partially checkable, context-dependent
    SUBJECTIVE = "subjective"   # opinion / judgment, skip in matching


@dataclass
class Claim:
    id: str
    text: str
    claim_type: ClaimType
    verifiability: Verifiability
    source_span: Optional[dict]   # {"start": int, "end": int}
    raw_sentence: Optional[str]   # original sentence the claim came from

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ExtractionResult:
    input_hash: str               # sha256 of input text, for deduplication
    document_type: str            # "text" | "pdf" | "docx"
    claims: list[Claim]
    raw_text: str                 # normalized text that was sent to Claude
    token_usage: dict

    def to_dict(self) -> dict:
        return {
            "input_hash": self.input_hash,
            "document_type": self.document_type,
            "claims": [c.to_dict() for c in self.claims],
            "claim_count": len(self.claims),
            "verifiable_count": sum(
                1 for c in self.claims
                if c.verifiability == Verifiability.VERIFIABLE
            ),
            "token_usage": self.token_usage,
        }


# ── Document readers ───────────────────────────────────────────────────────────

def read_pdf(path: str) -> str:
    doc = fitz.open(path)
    pages = [page.get_text() for page in doc]
    return "\n\n".join(pages).strip()


def read_docx(path: str) -> str:
    doc = Document(path)
    return "\n\n".join(
        p.text for p in doc.paragraphs if p.text.strip()
    )


def load_input(source: str | Path) -> tuple[str, str]:
    """
    Returns (normalized_text, document_type).
    source can be a file path (str/Path) or raw text.
    """
    is_path_candidate = isinstance(source, str) and len(source) < 256 and "\n" not in source
    path = Path(source) if is_path_candidate and Path(source).exists() else None

    if path and path.suffix.lower() == ".pdf":
        return read_pdf(str(path)), "pdf"
    elif path and path.suffix.lower() in (".docx", ".doc"):
        return read_docx(str(path)), "docx"
    else:
        # treat as raw text
        return str(source).strip(), "text"


# ── Prompt ─────────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a claim extraction engine for a multi-domain fact-verification system.

Your job: extract every discrete, atomic, verifiable claim from the input text.

Extraction rules:
- One claim = one checkable assertion. Split compound sentences into separate claims.
- Preserve the original wording as closely as possible — do not paraphrase or summarise.
- Do NOT include claims that are purely rhetorical, hypothetical, or framed as questions.
- Statistical claims must include the specific number or percentage in the claim text.
- Causal claims must name both the cause and the effect explicitly.
- Named-entity claims (founding dates, headquarters, ownership) are factual — include them.

Claim type definitions:
- factual: an assertion about a real-world entity, event, date, or state of affairs
- statistical: a numerical or quantitative assertion (percentages, counts, prices, rates)
- causal: X causes / leads to / results in Y
- definitional: X is defined as / means / is classified as Y

Verifiability definitions:
- verifiable: can be checked against a database, publication, filing, or news source — use this for statistics, financial figures, clinical results, poll results, election outcomes, scientific findings, legal rulings, and any named fact
- ambiguous: partially checkable but depends on context, scope, or methodology
- subjective: a personal opinion, value judgement, or prediction with no objective ground truth — use sparingly; when in doubt default to verifiable

Return ONLY a valid JSON array. No preamble, no markdown fences, no explanation.

Schema per claim:
{
  "text": "<atomic claim text, preserving original wording>",
  "claim_type": "factual|statistical|causal|definitional",
  "verifiability": "verifiable|ambiguous|subjective",
  "source_span": {"start": <int>, "end": <int>},
  "raw_sentence": "<full original sentence the claim came from>"
}"""


def build_user_prompt(text: str) -> str:
    return f"Extract all claims from the following text:\n\n---\n{text}\n---"


# ── Extractor ──────────────────────────────────────────────────────────────────

class ClaimExtractor:
    def __init__(self, model: str = "claude-opus-4-5"):
        self.client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        self.model = model

    def extract(self, source: str | Path) -> ExtractionResult:
        text, doc_type = load_input(source)

        response = self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            messages=[
                {"role": "user", "content": build_user_prompt(text)}
            ]
        )

        raw_json = response.content[0].text.strip()
        claims = self._parse_claims(raw_json, text)

        import hashlib
        input_hash = hashlib.sha256(text.encode()).hexdigest()[:16]

        return ExtractionResult(
            input_hash=input_hash,
            document_type=doc_type,
            claims=claims,
            raw_text=text,
            token_usage={
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
            }
        )

    def _parse_claims(self, raw_json: str, source_text: str) -> list[Claim]:
        # strip accidental markdown fences if Claude adds them
        clean = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw_json, flags=re.MULTILINE).strip()

        try:
            items = json.loads(clean)
        except json.JSONDecodeError as e:
            raise ValueError(f"Claude returned invalid JSON: {e}\n\nRaw output:\n{raw_json}")

        claims = []
        for item in items:
            claim = Claim(
                id=str(uuid.uuid4())[:8],
                text=item.get("text", "").strip(),
                claim_type=ClaimType(item.get("claim_type", "factual")),
                verifiability=Verifiability(item.get("verifiability", "verifiable")),
                source_span=item.get("source_span"),
                raw_sentence=item.get("raw_sentence"),
            )
            claims.append(claim)

        return claims

if __name__ == "__main__":
    # Get test input
    file = open("test.txt", "r")
    text = file.read()
    file.close()
    
    
    extractor = ClaimExtractor()
    results = extractor.extract(text) 
    
    print(results)