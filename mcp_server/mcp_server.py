"""
Bria Exchange — MCP Server (HTTP/SSE)

Exposes verification as MCP tools. Each agent registered in the dashboard
gets its own API key. Developers use that key to connect their AI clients.

Connect from Claude Desktop (~/.claude/claude_desktop_config.json):
    {
      "mcpServers": {
        "bria-exchange": {
          "type": "sse",
          "url": "http://localhost:8002/sse?api_key=bx_agent_xxxx"
        }
      }
    }

Connect from the Anthropic SDK:
    client = anthropic.Anthropic()
    # Use MCP server URL: http://localhost:8002/sse?api_key=bx_agent_xxxx
"""

import hashlib
import json
import os
import secrets
import time
import uuid
from contextlib import asynccontextmanager
from typing import Optional

import asyncpg
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from mcp.server import Server
from mcp.server.sse import SseServerTransport
from mcp.types import CallToolResult, ListToolsResult, TextContent, Tool

from assembler import ResponseAssembler
from policy_engine import PolicyConfig
from verification_agent import VerificationAgent
from verification_pipeline import PipelineRunner

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

DASHBOARD_DATABASE_URL = os.environ.get("DASHBOARD_DATABASE_URL", "")
MCP_DATABASE_URL       = os.environ.get("MCP_DATABASE_URL", "")

# ---------------------------------------------------------------------------
# App state
# ---------------------------------------------------------------------------

_dash_pool: Optional[asyncpg.Pool] = None
_mcp_pool:  Optional[asyncpg.Pool] = None
_runner:    Optional[PipelineRunner]    = None
_assembler: Optional[ResponseAssembler] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _dash_pool, _mcp_pool, _runner, _assembler
    if DASHBOARD_DATABASE_URL:
        _dash_pool = await asyncpg.create_pool(DASHBOARD_DATABASE_URL, min_size=1, max_size=5)
    if MCP_DATABASE_URL:
        _mcp_pool = await asyncpg.create_pool(MCP_DATABASE_URL, min_size=1, max_size=5)
    _runner    = PipelineRunner(concurrency=5)
    _assembler = ResponseAssembler()
    yield
    if _dash_pool: await _dash_pool.close()
    if _mcp_pool:  await _mcp_pool.close()


app = FastAPI(title="Bria Exchange MCP Server", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# One SSE transport instance shared across all connections
sse_transport = SseServerTransport("/messages/")


# ---------------------------------------------------------------------------
# Auth — resolve API key → agent record
# ---------------------------------------------------------------------------

async def get_agent_by_key(api_key: str) -> Optional[dict]:
    if not _dash_pool or not api_key:
        return None
    async with _dash_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM agents WHERE api_key = $1", api_key
        )
        if not row:
            return None
        agent = dict(row)

        # Fetch the user's active connected sources
        source_rows = await conn.fetch(
            "SELECT connector_id FROM connected_sources WHERE user_id=$1 AND status='active'",
            agent["user_id"],
        )
        agent["enabled_connector_ids"] = [r["connector_id"] for r in source_rows] or None

        # Fetch active custom sources (extracted text included for verification context)
        custom_rows = await conn.fetch(
            "SELECT name, domain, authority_level, extracted_text FROM custom_sources WHERE user_id=$1 AND status='active'",
            agent["user_id"],
        )
        agent["custom_sources"] = [dict(r) for r in custom_rows] or None

    # Parse policy JSON
    policy = agent.get("policy") or {}
    if isinstance(policy, str):
        try:
            policy = json.loads(policy)
        except Exception:
            policy = {}
    agent["policy"] = policy
    return agent


# ---------------------------------------------------------------------------
# Policy mapping — frontend PolicyConfig → verification PolicyConfig
# ---------------------------------------------------------------------------

_PROFILE_THRESHOLDS = {
    "strict":     {"min_ecr_for_pass": 0.60, "min_vs_for_pass": 0.85, "max_vs_for_block": 0.50},
    "moderate":   {"min_ecr_for_pass": 0.40, "min_vs_for_pass": 0.80, "max_vs_for_block": 0.40},
    "permissive": {"min_ecr_for_pass": 0.20, "min_vs_for_pass": 0.65, "max_vs_for_block": 0.30},
}


def _map_policy(agent_policy: dict) -> PolicyConfig:
    profile = agent_policy.get("policy_profile", "moderate")
    thresholds = _PROFILE_THRESHOLDS.get(profile, _PROFILE_THRESHOLDS["moderate"])
    contradiction = agent_policy.get("contradiction_policy", "flag")
    return PolicyConfig(
        min_ecr_for_pass=thresholds["min_ecr_for_pass"],
        min_vs_for_pass=thresholds["min_vs_for_pass"],
        max_vs_for_block=thresholds["max_vs_for_block"],
        # Lower the block threshold if the agent is configured to block on contradictions
        contradiction_block_threshold=0.75 if contradiction == "block" else 0.90,
    )


# ---------------------------------------------------------------------------
# DB persistence — store verification tagged to agent
# ---------------------------------------------------------------------------

async def _store_verification(agent: dict, content: str, response: dict, elapsed: float, model: str = "claude-haiku-4-5-20251001"):
    if not _mcp_pool:
        return

    scores  = response.get("scores", {})
    meta    = response.get("meta", {})
    claims  = response.get("claims", [])

    corroborated = sum(1 for c in claims if c["status"] == "corroborated")
    contradicted  = sum(1 for c in claims if c["status"] == "contradicted")
    unsupported   = sum(1 for c in claims if c["status"] == "unsupported")
    out_of_scope  = sum(1 for c in claims if c["status"] == "out_of_scope")

    decision = response.get("decision", "block")
    policy   = agent.get("policy") or {}

    # Route to review queue for flagged/blocked agent output
    review_status = "not_required"
    if decision in ("review", "block"):
        review_status = "pending_review"

    request_id = response.get("request_id", str(uuid.uuid4()))
    input_hash  = hashlib.sha256(content.encode()).hexdigest()[:16]

    decision_reasons = json.dumps([
        {"claim": c["text"], "reason": c.get("reasoning", "")}
        for c in claims if c["status"] in ("contradicted", "unsupported") and c.get("reasoning")
    ])

    # model is passed explicitly from the runner (actual model used for inference)

    try:
        async with _mcp_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO requests (
                    request_id, api_key, tool, content, input_hash,
                    decision, vs, ecr, sci,
                    total_claims, corroborated_count, contradicted_count,
                    unsupported_count, out_of_scope_count, elapsed_seconds,
                    model, agent_id, review_status, domain, decision_reasons, full_response
                ) VALUES (
                    $1, $2, 'mcp_verify_document', $3, $4,
                    $5, $6, $7, $8,
                    $9, $10, $11, $12, $13, $14,
                    $20, $15, $16, $17, $18::jsonb, $19::jsonb
                )
                ON CONFLICT (request_id) DO NOTHING
                """,
                request_id,
                agent.get("api_key", ""),
                content,
                input_hash,
                decision,
                scores.get("vs", 0),
                scores.get("ecr", 0),
                scores.get("sci", 0),
                meta.get("total_claims", len(claims)),
                corroborated,
                contradicted,
                unsupported,
                out_of_scope,
                round(elapsed, 3),
                str(agent.get("id", "")),
                review_status,
                policy.get("domain", "financial"),
                decision_reasons,
                json.dumps(response),
                model,
            )
    except Exception as exc:
        print(f"[mcp_server] Failed to store verification: {exc}")


# ---------------------------------------------------------------------------
# MCP tool definitions
# ---------------------------------------------------------------------------

TOOLS = [
    Tool(
        name="verify_document",
        description=(
            "Fact-check a full piece of text that may contain multiple factual claims. "
            "ALWAYS use this tool — not verify_claim — when the text contains more than one assertion "
            "or when you are verifying a sentence, paragraph, document, report, article, or summary. "
            "Do NOT split the text into individual claims yourself; this tool extracts and verifies "
            "every claim automatically. "
            "Sources checked: FRED (US macroeconomic data), SEC EDGAR (company financials), "
            "World Bank (international indicators), PubMed / ClinicalTrials.gov / OpenFDA "
            "(biomedical and pharmaceutical claims), The Guardian / New York Times (news and editorial "
            "facts), CrossRef / Semantic Scholar (academic citations), and Wikidata (entity facts, "
            "rankings, general knowledge). "
            "Returns a Pass / Review / Block decision, a Verification Score, per-claim verdicts "
            "(corroborated / contradicted / unsupported / out_of_scope), confidence scores, "
            "source citations, detailed explanations, and corrected facts for any contradicted claims."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "The full text to verify. Must be at least 10 characters.",
                    "minLength": 10,
                },
            },
            "required": ["content"],
        },
    ),
    Tool(
        name="verify_claim",
        description=(
            "Fact-check a single isolated assertion. "
            "Use this ONLY when you have exactly one specific claim to spot-check — for example, "
            "a single number, statistic, date, or fact you want to confirm before stating it. "
            "If the text contains two or more claims, use verify_document instead. "
            "Do NOT call this tool in a loop to verify a document claim-by-claim — that is "
            "exactly what verify_document is for. "
            "Sources: FRED, SEC EDGAR, World Bank, PubMed, ClinicalTrials.gov, OpenFDA, "
            "The Guardian, New York Times, CrossRef, Semantic Scholar, Wikidata. "
            "Returns a verdict (corroborated / contradicted / unsupported / out_of_scope), "
            "confidence score, detailed explanation, corrected fact if contradicted, and citations."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "claim": {
                    "type": "string",
                    "description": (
                        "The specific assertion to verify. Be precise — include the subject, "
                        "value, and time period where applicable. "
                        "Examples: 'Apple revenue was $124.3B in Q1 2026', "
                        "'The US unemployment rate was 3.7% in January 2025', "
                        "'Ozempic (semaglutide) showed 15% weight reduction in the STEP-1 trial', "
                        "'The Guardian published a report on Binance regulatory violations in 2023'."
                    ),
                },
            },
            "required": ["claim"],
        },
    ),
]


# ---------------------------------------------------------------------------
# Per-connection MCP server factory
# ---------------------------------------------------------------------------

def _create_mcp_server(agent: dict) -> Server:
    """
    Creates a fresh MCP Server bound to a specific agent.
    Each SSE connection gets its own server instance carrying the agent context.
    """
    server = Server("bria-exchange")
    policy = _map_policy(agent.get("policy") or {})

    @server.list_tools()
    async def list_tools() -> ListToolsResult:
        return ListToolsResult(tools=TOOLS)

    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> CallToolResult:
        try:
            if name == "verify_document":
                return await _handle_verify_document(arguments, agent, policy)
            if name == "verify_claim":
                return await _handle_verify_claim(arguments, agent)
            return CallToolResult(
                content=[TextContent(type="text", text=f"Unknown tool: {name}")],
                isError=True,
            )
        except Exception as exc:
            return CallToolResult(
                content=[TextContent(type="text", text=f"Verification error: {exc}")],
                isError=True,
            )

    return server


# ---------------------------------------------------------------------------
# Tool handlers
# ---------------------------------------------------------------------------

async def _handle_verify_document(arguments: dict, agent: dict, policy: PolicyConfig) -> CallToolResult:
    content = arguments.get("content", "")
    if len(content) < 10:
        return CallToolResult(
            content=[TextContent(type="text", text="content must be at least 10 characters")],
            isError=True,
        )

    domain = (agent.get("policy") or {}).get("domain", "auto")
    enabled_connector_ids = agent.get("enabled_connector_ids")
    custom_sources = agent.get("custom_sources")

    started         = time.perf_counter()
    pipeline_result = await _runner.run(content, domain=domain, enabled_connector_ids=enabled_connector_ids, custom_sources=custom_sources)
    response        = _assembler.assemble(pipeline_result, policy_config=policy)
    elapsed         = time.perf_counter() - started

    response_dict = response.to_dict()
    response_dict["meta"]["elapsed_seconds"] = round(elapsed, 2)

    actual_model = _runner.agent.model if _runner and hasattr(_runner, "agent") else "claude-haiku-4-5-20251001"
    await _store_verification(agent, content, response_dict, elapsed, model=actual_model)

    return CallToolResult(
        content=[TextContent(type="text", text=_format_document_result(response_dict, agent))]
    )


async def _handle_verify_claim(arguments: dict, agent: dict) -> CallToolResult:
    claim = arguments.get("claim", "")
    if not claim:
        return CallToolResult(
            content=[TextContent(type="text", text="claim is required")],
            isError=True,
        )

    domain = (agent.get("policy") or {}).get("domain", "auto")
    enabled_connector_ids = agent.get("enabled_connector_ids")
    custom_sources = agent.get("custom_sources")
    verification_agent = VerificationAgent()
    result = await verification_agent.verify(claim, domain=domain, enabled_connector_ids=enabled_connector_ids, custom_sources=custom_sources)

    output = {
        "claim":      claim,
        "verdict":    result.verdict.value,
        "confidence": result.confidence,
        "reasoning":  result.reasoning,
        "citations":  result.citations,
        "agent":      agent["name"],
    }

    return CallToolResult(
        content=[TextContent(type="text", text=json.dumps(output, indent=2))]
    )


# ---------------------------------------------------------------------------
# Response formatter
# ---------------------------------------------------------------------------

def _format_document_result(response: dict, agent: dict) -> str:
    scores   = response["scores"]
    decision = response["decision"].upper()
    claims   = response["claims"]

    contradicted = [c for c in claims if c["status"] == "contradicted"]
    corroborated = [c for c in claims if c["status"] == "corroborated"]
    unsupported  = [c for c in claims if c["status"] == "unsupported"]
    out_of_scope = [c for c in claims if c["status"] == "out_of_scope"]

    lines = [
        f"## Bria Exchange — Verification Result",
        f"**Agent:** {agent['name']} · **Policy:** {agent.get('policy', {}).get('policy_profile', 'moderate')}",
        f"",
        f"**Decision: {decision}**",
        f"_{response['decision_reason']}_",
        f"",
        f"**Scores**",
        f"- VS  (Verification Score):      {scores['vs']:.1%}",
        f"- ECR (Evidence Coverage Ratio): {scores['ecr']:.1%}",
        f"- SCI (Source Confidence Index): {scores['sci']:.1%}",
        f"",
        f"**Claims** ({response['meta']['total_claims']} total · "
        f"{len(corroborated)} corroborated · {len(contradicted)} contradicted · "
        f"{len(unsupported)} unsupported · {len(out_of_scope)} out of scope)",
    ]

    if contradicted:
        lines += ["", "**⚠ Contradicted claims — do not publish**"]
        for c in contradicted:
            lines.append(f"- [{c['confidence']:.0%}] {c['text']}")
            lines.append(f"  → {c['reasoning']}")
            for citation in c.get("citations", []):
                lines.append(
                    f"  → Source: {citation.get('source')} {citation.get('identifier')} "
                    f"({citation.get('date')}): {citation.get('value')}"
                )

    if corroborated:
        lines += ["", "**✓ Corroborated claims**"]
        for c in corroborated:
            lines.append(f"- [{c['confidence']:.0%}] {c['text']}")

    if unsupported:
        lines += ["", "**? Unsupported claims — consider removing or qualifying**"]
        for c in unsupported:
            lines.append(f"- {c['text']}")

    if decision in ("REVIEW", "BLOCK"):
        lines += [
            "",
            f"> This verification has been routed to the Bria Exchange review queue.",
            f"> A human reviewer will inspect it before publication is approved.",
        ]

    lines += [
        "",
        "---",
        f"Request ID: `{response['request_id']}`",
        f"Elapsed: {response['meta'].get('elapsed_seconds', 0):.1f}s",
    ]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# SSE routes
# ---------------------------------------------------------------------------

@app.get("/health")
async def health():
    return {"status": "ok", "service": "bria-exchange-mcp"}


@app.get("/sse")
async def handle_sse(request: Request, api_key: str = Query(..., description="Agent API key from the Bria Exchange dashboard")):
    agent = await get_agent_by_key(api_key)
    if not agent:
        raise HTTPException(status_code=401, detail="Invalid agent API key")

    mcp_server = _create_mcp_server(agent)

    async with sse_transport.connect_sse(
        request.scope, request.receive, request._send
    ) as streams:
        await mcp_server.run(
            streams[0],
            streams[1],
            mcp_server.create_initialization_options(),
        )


@app.post("/messages/")
async def handle_post_message(request: Request):
    await sse_transport.handle_post_message(
        request.scope, request.receive, request._send
    )
