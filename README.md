# Bria Exchange

**Independent, third-party verification infrastructure for AI-generated content.**

Bria Exchange is an API that takes AI-generated text, extracts every factual claim it contains, checks each one against authoritative external data sources, and returns a structured verdict: per-claim status, confidence scoring, citations, and a Pass / Review / Block policy decision. It's built to sit between an LLM and a consequential decision — the independent check an enterprise needs before it trusts what a model said.

This is not RAG. Bria Exchange doesn't help a model generate — it checks what a model (any model, from any vendor) already generated, against a source of truth it never had access to.

> **Public prototype.** This repository is a working demo environment for showcasing the product: full pipeline, dashboard, and public verification tool, running against live financial data sources.

---

## The problem

- **Unverified decisions.** AI is increasingly used to inform consequential decisions, with no independent check on whether the underlying claims are true, sourced, or current.
- **Human review bottlenecks.** Manual fact-checking and compliance review slow AI deployment to the point where AI's speed advantage disappears.

Bria Exchange gives AI output a fast, structured, independently-verified trust signal, so teams can automate what's safe to automate and route only genuine exceptions to a human.

## How it works

```
Input text
  → Claim extraction     (Claude Opus extracts atomic factual claims)
  → Corpus matching      (each claim checked against FRED + SEC EDGAR)
  → Scoring               (VS, ECR, SCI computed from verdicts)
  → Policy decision       (Pass / Review / Block)
  → Response              (verdicts + citations + audit log)
```

Every claim resolves to one of four statuses:

| Status | Meaning |
|---|---|
| `corroborated` | Official data confirms the claim |
| `contradicted` | Official data conflicts with the claim |
| `unsupported` | Relevant data exists but doesn't confirm or deny |
| `out_of_scope` | Cannot be verified with available sources |

**Contradictions always surface.** This is a core, non-negotiable invariant of the policy engine — a contradicted claim can never resolve to a silent `pass`, regardless of configuration.

### Scores

- **VS — Verification Score.** Accuracy over evidenced claims only (contradicted vs. corroborated).
- **ECR — Evidence Coverage Ratio.** Share of claims that could be checked at all.
- **SCI — Source Confidence Index.** Authority-weighted confidence in the sources used.

### Data sources

The prototype verifies claims against two free, authoritative sources:

- **FRED** (Federal Reserve Bank of St. Louis) — macro and economic claims: rates, inflation, GDP, unemployment, Treasury yields.
- **SEC EDGAR XBRL** — company-specific financial claims: revenue, net income, EPS, debt, share counts, buybacks, for US public companies.

Full detail on the scoring formulas, policy thresholds, and pipeline stages is in [`mcp_server/docs.md`](mcp_server/docs.md) and [`mcp_server/CLAIMS_VERIFICATION_LOGIC.md`](mcp_server/CLAIMS_VERIFICATION_LOGIC.md).

## Architecture

| Service | What it is | Local port |
|---|---|---|
| `mcp_server` (`api.py`) | Core verification REST API — claim extraction, corpus matching, scoring, policy engine | `8000` |
| `mcp_server` (`dashboard_api.py`) | Dashboard/public-facing API — auth, billing, history, orchestrates calls to the core verify API | `8001` |
| `mcp_server` (`mcp_server.py`) | MCP server — exposes `verify_document` and `verify_claim` as tools for Claude Desktop / MCP clients | `8002` |
| `frontend` | Next.js operator dashboard — agents, policy config, review queue, audit log, sources, cost, settings | `3000` |
| `exchange-frontend` | Next.js public verification tool (`verify.briaexchange.com`) — submit content, check history | `3001` (→ `3000` in-container) |
| `postgres` | Two databases: `bria_mcp` (verification pipeline) and `bria_dashboard` (dashboard/exchange app data) | `5432` |
| `caddy` | HTTPS reverse proxy routing the subdomains below | `80` / `443` |

In production this maps to:

- `briaexchange.com` — marketing landing page with a live verify playground
- `platform.briaexchange.com` — operator dashboard (`frontend`)
- `verify.briaexchange.com` — public verification tool (`exchange-frontend`)
- `api.briaexchange.com` — public API (`dashboard-api`)
- `mcp.briaexchange.com` — MCP server

## Getting started

### Requirements

- Docker and Docker Compose
- An [Anthropic API key](https://console.anthropic.com/)
- A free [FRED API key](https://fred.stlouisfed.org/docs/api/api_key.html) (SEC EDGAR needs no key)

### Run with Docker Compose

```bash
git clone https://github.com/yoraiyaniv/Bria-Exchange-Public-Prototype.git
cd Bria-Exchange-Public-Prototype
cp .env.example .env   # fill in ANTHROPIC_API_KEY, FRED_API_KEY, etc.
make start
```

```bash
make status   # check container health
make logs     # tail logs
make stop     # tear down
```

The dashboard is reachable at `http://localhost:3000` once containers are healthy.

### Run the verification API standalone

For working on the core pipeline without the full stack:

```bash
cd mcp_server
pip install -e .
# or: pip install anthropic fastapi uvicorn mcp requests python-dotenv pymupdf python-docx

# .env in mcp_server/ (or project root)
# ANTHROPIC_API_KEY=sk-ant-...
# FRED_API_KEY=your_fred_key_here

python api.py
```

The API is then live at `http://localhost:8000`, with interactive docs at `http://localhost:8000/docs`.

```bash
curl -X POST http://localhost:8000/v1/verify \
  -H "Content-Type: application/json" \
  -d '{
    "content": "Apple reported fiscal Q1 2026 revenue of $124.3 billion. The Federal Reserve held rates at 3.75% in February 2026."
  }'
```

See [`mcp_server/docs.md`](mcp_server/docs.md) for the full REST API reference, response schema, MCP tool definitions, and policy engine configuration.

## Repository layout

```
mcp_server/           Python verification engine (FastAPI) + MCP server
  api.py                 Core verify API (extraction → matching → scoring → policy)
  dashboard_api.py       Public/dashboard-facing API (auth, billing, history)
  mcp_server.py          MCP tool server (verify_document, verify_claim)
  claim_extraction.py    Stage 1 — atomic claim extraction
  corpus_matching/       Stage 2 — FRED / EDGAR matching
  scoring.py             Stage 3 — VS / ECR / SCI
  policy_engine.py       Stage 4 — Pass / Review / Block
  assembler.py           Stage 5 — response assembly
  docs.md                 Full API + architecture reference
  CLAIMS_VERIFICATION_LOGIC.md   Pipeline design deep-dive

frontend/              Next.js operator dashboard (platform.briaexchange.com)
exchange-frontend/     Next.js public verification tool (verify.briaexchange.com)
docker/                Landing page, Caddy config, feature screenshots
docker-compose.yml     Full-stack orchestration
Makefile               start / stop / restart / status / logs
```

## Status

This is a prototype environment for demonstrating the product concept, pipeline design, and API surface — shared for evaluation purposes, not a production deployment target.
