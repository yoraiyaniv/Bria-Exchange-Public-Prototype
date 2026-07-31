# Bria Exchange — Claims Verification Logic

This document explains the end-to-end logic of how Bria Exchange verifies claims in AI-generated text. The system is a five-stage pipeline, each stage implemented in its own module.

---

## Architecture Overview

```
Input Text / Document
        │
        ▼
┌─────────────────────┐
│  1. Claim Extraction │  claim_extraction.py
│     (Claude Opus)    │
└────────┬────────────┘
         │ list of Claim objects
         ▼
┌─────────────────────┐
│  2. Pipeline Runner  │  verification_pipeline.py
│  (partition + fan-   │
│   out concurrently)  │
└────────┬────────────┘
         │ per-claim async tasks
         ▼
┌─────────────────────┐
│  3. Verification     │  verification_agent.py
│     Agent Loop       │  + corpus_matching/*.py
│  (Claude Haiku +     │
│   20 tool connectors)│
└────────┬────────────┘
         │ VerificationResult per claim
         ▼
┌─────────────────────┐
│  4. Scoring          │  scoring.py
│  VS / ECR / SCI      │
└────────┬────────────┘
         │ Scores object
         ▼
┌─────────────────────┐
│  5. Policy Engine    │  policy_engine.py
│  Pass / Review /     │
│  Block decision      │
└────────┬────────────┘
         │ PolicyResult
         ▼
┌─────────────────────┐
│  6. Assembler        │  assembler.py
│  Final API response  │
└─────────────────────┘
```

---

## Stage 1 — Claim Extraction (`claim_extraction.py`)

### What it does
Sends the input text to **Claude Opus** with a strict system prompt that instructs the model to parse every atomic, verifiable assertion from the document. Supports plain text, PDF (via PyMuPDF), and DOCX inputs.

### Key design decisions
- **One claim = one checkable assertion.** Compound sentences are split.
- Wording is preserved as-is — no paraphrasing.
- Each claim gets a `claim_type` label:
  - `factual` — an assertion about a real-world fact
  - `statistical` — a numerical or percentage claim
  - `causal` — X causes / leads to Y (both sides must be named)
  - `definitional` — X is defined as Y
- Each claim gets a `verifiability` label:
  - `verifiable` — can be checked against external data
  - `ambiguous` — partially checkable, context-dependent
  - `subjective` — opinion or judgment; **these are skipped in verification**
- `source_span` records character offsets in the original text.
- Claude must return pure JSON (no markdown), and the parser strips any accidental fences before `json.loads()`.

### Output
An `ExtractionResult` containing a list of `Claim` dataclasses plus token usage and an `input_hash` (first 16 hex chars of SHA-256 of the raw text, used for deduplication).

---

## Stage 2 — Pipeline Runner (`verification_pipeline.py`)

### What it does
Orchestrates extraction → verification as a two-step async pipeline.

### Flow

1. **Extract** — calls `ClaimExtractor.extract()` in a thread pool executor (it is sync) to get all claims.
2. **Partition** — claims labelled `SUBJECTIVE` are moved to a `skipped` list and never sent to the agent. All others go to `to_verify`.
3. **Fan-out** — runs `_verify_one()` for every verifiable claim concurrently using `asyncio.gather()`. A `asyncio.Semaphore(concurrency)` (default: 10) caps how many agent loops run in parallel to avoid Claude API rate limits.
4. **Collect** — zips claims with results. If a claim's verification raises an exception it is captured as a structured error dict; no exception is re-raised and no claim is silently dropped.

### Output
A `PipelineResult` that tracks every claim, the verdict for each, any errors, timing, and token usage from extraction. Convenience properties (`corroborated`, `contradicted`, `unsupported`, `out_of_scope`) filter `verifications` by verdict.

---

## Stage 3 — Verification Agent (`verification_agent.py`)

This is the core reasoning layer. For each claim it runs an **agentic loop** with Claude Haiku and up to 20 external data connectors.

### Domain routing

Before any API call the agent resolves which connectors to load:

```python
DOMAIN_TOOLS = {
    "financial":      ["fred", "edgar", "worldbank", "bls", "oecd", "census"],
    "pharma":         ["pubmed", "clinicaltrials", "openfda", "europepmc", "crossref"],
    "legal":          ["courtlistener", "federalregister", "guardian", "wikidata"],
    "news_editorial": ["guardian", "nytimes", "wikidata", "crossref", "semanticscholar"],
    "academic":       ["arxiv", "semanticscholar", "crossref", "openalex", "europepmc", "pubmed"],
    "geography":      ["geonames", "worldbank", "census", "openmeteo", "wikidata"],
    "climate":        ["openmeteo", "worldbank", "wikidata"],
    "auto":           ["fred", "edgar", "wikidata", "guardian", "pubmed", "worldbank", "wikipedia"],
}
```

**Wikidata is always appended as a fallback** for every domain even if not in the list.

If `enabled_connector_ids` is provided (the org's connected sources from the database), the list is filtered to only those connectors. Wikidata is always kept regardless.

If no domain is specified, `"auto"` is used — a broad cross-domain default.

### Custom sources

If the org has uploaded private data sources, their extracted text is injected directly into the system prompt under an `## Organization Custom Sources` section. The agent is instructed to check these **first** before calling any external tool.

### The agentic loop

```
while iterations < max_iterations (default: 5):
    call Claude with: system_prompt, tool_defs, message history

    if stop_reason == "end_turn":
        parse the JSON verdict → return VerificationResult

    if stop_reason == "tool_use":
        for each tool_use block:
            execute the tool (async, thread pool for sync connectors)
            append tool_result to messages
        continue loop

    break on unexpected stop reason

# If max iterations reached → OUT_OF_SCOPE with error="max_iterations_exceeded"
```

### System prompt instructions to Claude

Claude is told to:
1. Check custom sources first if present.
2. Identify the most appropriate tool for the claim type.
3. If a tool returns no results, **retry with different keywords or a different tool** before giving up.
4. Only consider a claim `unsupported` after **at least two distinct queries or tools**.
5. Return a final JSON verdict once sufficient evidence is found.

**Retry rules are explicit in the prompt** — e.g. if EDGAR returns nothing for a company name, try the ticker; if FRED returns nothing for a series, try related series IDs.

### Verdict definitions

| Verdict | Meaning |
|---|---|
| `corroborated` | Data directly confirms the claim (±1% rounding tolerance for numbers) |
| `contradicted` | Data directly conflicts with the claim |
| `unsupported` | Searched with ≥2 queries/tools, found no relevant data either way |
| `out_of_scope` | Inherently unverifiable by any available tool (e.g. internal projections, future predictions) |

### Tool connectors (20 total)

| Connector ID | Source | Best for |
|---|---|---|
| `fred` | Federal Reserve Economic Data | US macro: CPI, GDP, unemployment, fed funds rate |
| `edgar` | SEC EDGAR | Public company financials from 10-K / 10-Q filings |
| `wikidata` | Wikidata | Entity facts, founding dates, HQ, CEO, rankings |
| `guardian` | The Guardian | News events, published statements, company announcements |
| `nytimes` | New York Times | US-focused business/finance reporting |
| `pubmed` | PubMed / MEDLINE | Drug efficacy, clinical studies, medical statistics |
| `clinicaltrials` | ClinicalTrials.gov | Trial phase, status, enrollment, endpoints |
| `openfda` | OpenFDA | FDA drug approvals, adverse events, recalls |
| `worldbank` | World Bank Open Data | Country-level GDP, inflation, development indicators |
| `crossref` | CrossRef | Academic paper metadata, DOIs, journal, year |
| `semanticscholar` | Semantic Scholar | AI/ML research papers, citation counts, benchmarks |
| `arxiv` | arXiv | CS/physics/math preprints, cutting-edge research |
| `openalex` | OpenAlex | Broad academic coverage, 250M+ works |
| `europepmc` | Europe PubMed Central | Biomedical preprints, non-US medical sources |
| `bls` | Bureau of Labor Statistics | US labor: payrolls, job openings, wage growth |
| `census` | US Census Bureau (ACS 5-Year) | US demographics, income, poverty, housing |
| `oecd` | OECD | Cross-country health, education, inequality comparisons |
| `courtlistener` | CourtListener | US court opinions, case law, legal precedents |
| `federalregister` | US Federal Register | US regulations, proposed rules, executive orders |
| `openmeteo` | Open-Meteo | Historical/forecast weather, temperature records |
| `geonames` | GeoNames | City populations, coordinates, geographic facts |
| `wikipedia` | Wikipedia | General knowledge fallback |

### Output
A `VerificationResult` with `verdict`, `reasoning`, `confidence` (0.0–1.0), `citations` (structured list of source/identifier/date/value), and a log of every `ToolCall` made.

---

## Stage 4 — Scoring (`scoring.py`)

Computes three normalized metrics from the `PipelineResult`.

### VS — Verification Score

Measures accuracy over **evidenced claims only** (corroborated + contradicted):

```
VS = sum(confidence for corroborated claims) /
     (sum(confidence for corroborated) + sum(confidence for contradicted))
```

- VS = 1.0 → everything confirmed is corroborated.
- VS = 0.0 → everything confirmed is contradicted.
- If no evidence either way, VS = 0.0.

### ECR — Evidence Coverage Ratio

Measures how much of the document was actually checked:

```
ECR = len(evidenced claims) / len(verifiable claims)
```

`evidenced` = corroborated + contradicted + unsupported (i.e. any claim the agent found data for or searched hard enough to call unsupported). Subjective/skipped claims do not count toward the denominator.

### SCI — Source Confidence Index

Weighted average authority of all citations used:

```
SCI = mean(source_weight for every citation)
```

Source weights:
- `edgar_10k` (audited annual): **1.00**
- `edgar_10q` (quarterly filing): **0.95**
- `fred` (official government data): **0.95**
- `edgar` (form unknown): **0.95**
- `news`: **0.60**
- `unknown`: **0.50**

EDGAR citations use the `form` field to choose between 10-K and 10-Q weights. If no citations exist, SCI = 0.

---

## Stage 5 — Policy Engine (`policy_engine.py`)

Translates scores into an actionable `Pass / Review / Block` decision.

### Default thresholds (configurable per customer)

| Threshold | Default | Meaning |
|---|---|---|
| `min_ecr_for_pass` | 0.40 | Minimum evidence coverage to allow a Pass |
| `min_vs_for_pass` | 0.80 | Minimum VS required for Pass |
| `max_vs_for_block` | 0.40 | VS at or below this triggers Block |
| `contradiction_review_threshold` | 0.70 | Contradiction confidence forcing Review |
| `contradiction_block_threshold` | 0.90 | Contradiction confidence forcing Block |
| `min_sci_for_block` | 0.70 | Minimum source quality to trust a Block decision |

### Decision rules (evaluated in order)

1. **No evidence at all** → `REVIEW`
   "Cannot assess accuracy — no data found."

2. **Contradiction + sufficient coverage + high source quality + VS ≤ block threshold** → `BLOCK`
   Hard fail: reliable sources contradict the document.

3. **Any contradiction** → `REVIEW`
   Softer fail: contradictions exist but not severe enough to block outright.

4. **ECR < min_ecr_for_pass** → `REVIEW`
   Not enough of the document was checked to issue a Pass.

5. **VS ≥ min_vs_for_pass** → `PASS`
   Sufficient coverage and accuracy.

6. **Everything else** → `REVIEW`
   VS is between the block and pass thresholds.

### Design principles
- Contradictions **always surface** — a contradiction can never produce a Pass.
- Low coverage → Review, not Pass (absence of evidence ≠ evidence of absence).
- Blocks require both sufficient coverage **and** high source confidence — if sources are low quality, Block downgrades to Review.

### Policy profiles (MCP server)

The MCP server maps agent-level policy profiles to concrete thresholds:

| Profile | min_ecr_for_pass | min_vs_for_pass | max_vs_for_block |
|---|---|---|---|
| `strict` | 0.60 | 0.85 | 0.50 |
| `moderate` (default) | 0.40 | 0.80 | 0.40 |
| `permissive` | 0.20 | 0.65 | 0.30 |

---

## Stage 6 — Response Assembler (`assembler.py`)

Packages everything into the final `VerificationResponse` returned to the client.

### What it produces

- **Top-level scores**: VS, ECR, SCI
- **Policy decision**: Pass / Review / Block + human-readable reason + flags
- **Per-claim verdicts**: `ClaimVerdict` for every claim (including skipped subjective claims and error claims, both surfaced as `out_of_scope`)
- **Audit entry**: immutable record with request ID, input hash, document type, timestamp, model, decision, and scores — for compliance logging
- **Metadata**: timing, claim counts by category

### Per-claim verdict fields
```
claim_id     — short UUID from extraction
text         — original claim text
claim_type   — factual | statistical | causal | definitional
status       — corroborated | contradicted | unsupported | out_of_scope
confidence   — 0.0–1.0
reasoning    — one or two sentence explanation from the agent
citations    — list of {source, identifier, date, value, label}
```

---

## API Entry Points

### REST API (`api.py`)

| Endpoint | Description |
|---|---|
| `POST /v1/verify` | Verify a single document. Accepts `content`, optional `domain`, `policy`, `enabled_connector_ids`, `custom_sources`. |
| `POST /v1/verify/batch` | Verify up to 10 documents concurrently. |
| `GET /health` | Health check. |

Custom policy thresholds can be passed per-request via the `policy` field (maps to `PolicyConfig` kwargs).

### MCP Server (`mcp_server.py`)

Exposes two MCP tools over HTTP/SSE. Each agent connecting via SSE authenticates with an API key that maps to their agent record in the database. The server loads their connected sources, custom sources, and policy profile automatically.

| MCP Tool | Description |
|---|---|
| `verify_document` | Full pipeline — extract + verify all claims in a document. Returns decision, scores, and per-claim verdicts. |
| `verify_claim` | Single-claim verification — skips extraction, calls the agent directly. Returns verdict, confidence, reasoning, citations. |

The MCP server also routes `Review` and `Block` decisions to a **review queue** (`review_status = 'pending_review'`) stored in the database for human inspection.

---

## Data Flow Summary

```
1. Text arrives at POST /v1/verify or via MCP tool call
2. ClaimExtractor sends text to Claude Opus → JSON array of claims
3. PipelineRunner partitions: subjective claims are skipped
4. For each verifiable claim (concurrently, max 10 at once):
   a. Domain resolved → connector list selected
   b. Claude Haiku reads system prompt with tool descriptions + optional custom source text
   c. Claude calls tools (FRED, EDGAR, PubMed, etc.) until evidence found
   d. Claude emits final JSON verdict {verdict, reasoning, confidence, citations}
5. Scorer computes VS, ECR, SCI from all verdicts
6. PolicyEngine evaluates thresholds → Pass / Review / Block
7. Assembler packages everything into VerificationResponse
8. Response returned to client; if Review/Block, stored to DB review queue
```