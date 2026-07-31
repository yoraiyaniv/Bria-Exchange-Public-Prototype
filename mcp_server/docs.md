# Bria Exchange — Developer Documentation

Bria Exchange is a verification infrastructure API. It takes AI-generated text, extracts every factual claim, checks each one against authoritative data sources (FRED, SEC EDGAR), and returns a structured verdict with scores, citations, and a Pass/Review/Block policy decision.

---

## Table of contents

- [How it works](#how-it-works)
- [Setup](#setup)
- [REST API](#rest-api)
- [MCP server](#mcp-server)
- [Response schema](#response-schema)
- [Scores](#scores)
- [Policy engine](#policy-engine)
- [Data sources](#data-sources)

---

## How it works

```
Input text
  → Claim extraction     (LLM extracts atomic factual claims)
  → Corpus matching      (each claim checked against FRED + EDGAR)
  → Scoring              (VS, ECR, SCI computed from verdicts)
  → Policy decision      (Pass / Review / Block)
  → Response             (verdicts + citations + audit log)
```

Each claim gets one of four statuses:

| Status | Meaning |
|---|---|
| `corroborated` | Official data confirms the claim |
| `contradicted` | Official data conflicts with the claim |
| `unsupported` | Relevant data exists but doesn't confirm or deny |
| `out_of_scope` | Cannot be verified with available sources |

Contradictions always surface — they cannot be configured away.

---

## Setup

**Requirements:** Python 3.12+, an Anthropic API key, a FRED API key.

```bash
# Clone and install dependencies
git clone <repo>
cd bria-exchange
pip install anthropic fastapi uvicorn mcp requests python-dotenv pymupdf python-docx
```

Create a `.env` file in the project root:

```
ANTHROPIC_API_KEY=sk-ant-...
FRED_API_KEY=your_fred_key_here
```

Get a free FRED API key at [fred.stlouisfed.org](https://fred.stlouisfed.org/docs/api/api_key.html). No EDGAR key is needed — the SEC API is free and keyless.

**Run tests:**

```bash
python -m pytest
```

---

## REST API

### Start the server

```bash
python api.py
```

The server starts at `http://localhost:8000`. Interactive docs are at `http://localhost:8000/docs`.

---

### POST /v1/verify

Verify a single document.

**Request body:**

```json
{
  "content": "Apple reported revenue of $124.3 billion for Q1 2026.",
  "request_id": "req_abc123",
  "policy": {
    "min_ecr_for_pass": 0.40,
    "min_vs_for_pass": 0.80,
    "max_vs_for_block": 0.40
  }
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `content` | string | yes | Text to verify. Minimum 10 characters. |
| `request_id` | string | no | Idempotency key. Auto-generated if omitted. |
| `policy` | object | no | Custom policy thresholds. See [Policy engine](#policy-engine). |

You can also pass `X-Request-Id` as a request header — it takes precedence over the body field.

**Example:**

```bash
curl -X POST http://localhost:8000/v1/verify \
  -H "Content-Type: application/json" \
  -d '{
    "content": "Apple reported fiscal Q1 2026 revenue of $124.3 billion. The Federal Reserve held rates at 3.75% in February 2026."
  }'
```

**Response:** See [Response schema](#response-schema).

---

### POST /v1/verify/batch

Verify up to 10 documents concurrently. Returns a list of responses in the same order as the input.

```json
[
  { "content": "First document to verify..." },
  { "content": "Second document to verify...", "request_id": "doc-2" }
]
```

```bash
curl -X POST http://localhost:8000/v1/verify/batch \
  -H "Content-Type: application/json" \
  -d '[
    {"content": "Apple reported revenue of $143.76 billion for Q1 2026."},
    {"content": "The Federal Reserve held rates at 3.75% in February 2026."}
  ]'
```

Maximum 10 documents per batch. Returns 400 if exceeded.

---

### GET /health

```bash
curl http://localhost:8000/health
# {"status": "ok", "version": "1.0.0"}
```

---

## MCP server

The MCP server exposes Bria Exchange as tools that Claude (and other MCP-compatible clients) can call directly — no HTTP required.

### Start the server

```bash
python mcp_server.py
```

The server runs over stdio, which is the standard MCP transport for local use.

---

### Connect to Claude Desktop

Add the following to `~/.claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "bria-exchange": {
      "command": "python",
      "args": ["/absolute/path/to/bria-exchange/mcp_server.py"],
      "env": {
        "ANTHROPIC_API_KEY": "sk-ant-...",
        "FRED_API_KEY": "your_fred_key_here"
      }
    }
  }
}
```

Restart Claude Desktop. Two tools will appear: `verify_document` and `verify_claim`.

---

### Tool: verify_document

Verify a full document. Equivalent to `POST /v1/verify`.

**Input:**

```json
{
  "content": "Apple reported revenue of $143.76 billion for Q1 2026.",
  "policy": {
    "min_ecr_for_pass": 0.40
  }
}
```

| Field | Required | Description |
|---|---|---|
| `content` | yes | Text to verify |
| `policy.min_ecr_for_pass` | no | Minimum ECR for a Pass (0.0–1.0) |
| `policy.min_vs_for_pass` | no | Minimum VS for a Pass (0.0–1.0) |
| `policy.max_vs_for_block` | no | VS at or below which a Block is issued (0.0–1.0) |

**Output:** Markdown-formatted summary with decision, scores, per-claim verdicts, and a collapsible full JSON block.

---

### Tool: verify_claim

Verify a single claim. Faster than `verify_document` — skips extraction and runs one agent loop directly.

**Input:**

```json
{
  "claim": "Apple reported revenue of $143.76 billion for Q1 2026."
}
```

**Output:**

```json
{
  "claim": "Apple reported revenue of $143.76 billion for Q1 2026.",
  "verdict": "corroborated",
  "confidence": 0.97,
  "reasoning": "SEC EDGAR 10-Q confirms Apple revenue of $143.76B for fiscal Q1 2026.",
  "citations": [
    {
      "source": "EDGAR",
      "identifier": "AAPL",
      "date": "2025-12-27",
      "value": 143756000000,
      "label": "Apple Inc. Fiscal Q1 2026 Revenue"
    }
  ]
}
```

---

## Response schema

Full response from `POST /v1/verify` and `verify_document`:

```json
{
  "request_id": "71f5e253-8b7d-45f8-8219-3f49c4236620",
  "input_hash": "5202c49f4bd3f61e",
  "document_type": "text",
  "scores": {
    "vs": 0.0,
    "ecr": 1.0,
    "sci": 0.95
  },
  "decision": "block",
  "decision_reason": "VS 0% is below block threshold (40%) with 100% evidence coverage.",
  "flags": [
    "3 contradicted claim(s) found"
  ],
  "claims": [
    {
      "claim_id": "641fba41",
      "text": "Apple reported fiscal Q1 2026 revenue of $124.3 billion",
      "claim_type": "statistical",
      "status": "contradicted",
      "confidence": 0.99,
      "reasoning": "Apple's 10-Q filing reports revenue of $143.76 billion, not $124.3 billion.",
      "citations": [
        {
          "source": "EDGAR",
          "identifier": "AAPL",
          "date": "2025-12-27",
          "value": 143756000000,
          "label": "Apple Inc. Fiscal Q1 2026 Revenue"
        }
      ]
    }
  ],
  "audit": {
    "request_id": "71f5e253-8b7d-45f8-8219-3f49c4236620",
    "input_hash": "5202c49f4bd3f61e",
    "document_type": "text",
    "timestamp": "2026-03-17T10:21:42.003407+00:00",
    "model": "claude-opus-4-5",
    "total_claims": 3,
    "decision": "block",
    "scores": { "vs": 0.0, "ecr": 1.0, "sci": 0.95 },
    "flags": ["3 contradicted claim(s) found"]
  },
  "meta": {
    "started_at": "2026-03-17T10:21:24.745477+00:00",
    "completed_at": "2026-03-17T10:21:42.003407+00:00",
    "total_claims": 3,
    "verified_claims": 3,
    "skipped_claims": 0,
    "error_claims": 0,
    "elapsed_seconds": 17.26
  }
}
```

### Claim types

| Type | Description |
|---|---|
| `statistical` | Numerical assertion (revenue, rates, percentages) |
| `factual` | Non-numerical factual assertion |
| `causal` | Cause-and-effect claim |
| `definitional` | Definition or description |

---

## Scores

### VS — Verification Score

Measures document accuracy over evidenced claims only. `out_of_scope` and `unsupported` claims do not affect VS.

```
VS = corroborated_confidence / (corroborated_confidence + contradicted_confidence)
```

A VS of 1.0 means all evidenced claims were corroborated. A VS of 0.0 means all evidenced claims were contradicted.

### ECR — Evidence Coverage Ratio

Measures what fraction of verifiable claims had evidence one way or the other.

```
ECR = (corroborated + contradicted + unsupported) / total_verifiable_claims
```

A low ECR means most claims could not be checked — either the company is not in the corpus or the claims reference data not available in free sources. Low ECR alone does not produce a Block.

### SCI — Source Confidence Index

Weighted average authority of the sources that produced verdicts.

| Source | Weight |
|---|---|
| EDGAR 10-K (annual filing) | 1.00 |
| EDGAR 10-Q (quarterly filing) | 0.95 |
| FRED (Federal Reserve data) | 0.95 |

A high SCI means the verdicts are backed by high-authority sources. A low SCI can downgrade a Block to Review — contradictions from low-quality sources should not automatically block.

---

## Policy engine

The policy engine applies configurable thresholds to the three scores and produces a `pass`, `review`, or `block` decision.

### Default thresholds

| Parameter | Default | Description |
|---|---|---|
| `min_ecr_for_pass` | 0.40 | Minimum evidence coverage for a Pass |
| `min_vs_for_pass` | 0.80 | Minimum verification score for a Pass |
| `max_vs_for_block` | 0.40 | VS at or below which a Block is issued |
| `min_sci_for_block` | 0.70 | Minimum source confidence required to trust a Block |

### Decision rules (in order)

1. **No evidence** → `review` — cannot assess the document
2. **Low VS + sufficient ECR + high SCI** → `block` — well-covered, mostly wrong, trusted sources
3. **Any contradiction** → `review` — contradictions always surface, never silently pass
4. **Insufficient ECR** → `review` — not enough coverage to pass or block
5. **High VS + sufficient ECR** → `pass` — well-covered, mostly correct
6. **Everything else** → `review`

Contradictions can never produce a `pass`. This is a core invariant.

### Overriding thresholds

Pass custom thresholds per request via the `policy` field:

```json
{
  "content": "...",
  "policy": {
    "min_ecr_for_pass": 0.60,
    "min_vs_for_pass": 0.90
  }
}
```

All threshold values must be between 0.0 and 1.0.

---

## Data sources

### FRED — Federal Reserve Bank of St. Louis

Used for macro and economic claims: interest rates, inflation, GDP, unemployment, Treasury yields, credit spreads.

Free API, no key required beyond registration. Get a key at [fred.stlouisfed.org](https://fred.stlouisfed.org/docs/api/api_key.html).

Common series used:

| Series ID | Description |
|---|---|
| `DFF` | Federal Funds Effective Rate (daily) |
| `FEDFUNDS` | Federal Funds Rate (monthly average) |
| `CPILFESL` | Core CPI (excludes food and energy) |
| `CPIAUCSL` | Headline CPI |
| `DGS10` | 10-year Treasury yield |
| `UNRATE` | Unemployment rate |
| `A191RL1Q225SBEA` | Real GDP growth (quarterly) |

### SEC EDGAR XBRL

Used for company-specific financial claims: revenue, net income, gross margin, EPS, debt, share counts, share repurchases.

Free API, no key required. Requires a `User-Agent` header identifying your application. Rate limit: 10 requests per second.

Supported financial concepts:

| Concept | Description |
|---|---|
| `revenue` | Total revenue |
| `net_income` | Net income / profit |
| `gross_profit` | Gross profit |
| `operating_income` | Operating income |
| `eps_basic` / `eps_diluted` | Earnings per share |
| `shares_outstanding` | Common shares outstanding |
| `long_term_debt` | Long-term debt |
| `cash` | Cash and equivalents |
| `share_repurchases` | Share buyback payments |

EDGAR coverage is limited to US public companies with SEC filings. Private companies, foreign companies not cross-listed in the US, and fictional tickers return `out_of_scope`.

---

## Error responses

All errors follow a consistent schema:

```json
{
  "error": {
    "code": "verification_failed",
    "message": "Verification failed: ..."
  }
}
```

| HTTP status | Code | Description |
|---|---|---|
| 400 | `invalid_policy_config` | Policy threshold out of range or invalid type |
| 400 | `batch_too_large` | Batch exceeds 10 documents |
| 422 | — | Request body validation failed (Pydantic) |
| 500 | `verification_failed` | Internal pipeline error |
| 503 | `service_unavailable` | Server not ready |