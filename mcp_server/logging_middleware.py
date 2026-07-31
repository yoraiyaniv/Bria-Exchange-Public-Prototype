"""
Bria Exchange — MCP request logger
Writes every verify_document / verify_claim call to PostgreSQL (mcp_db).
All failures are silently swallowed — logging must never break the tool call.
"""

import os
import sys
import uuid
import asyncio
from typing import Optional

try:
    import asyncpg
    _HAS_ASYNCPG = True
except ImportError:
    _HAS_ASYNCPG = False

_pool: Optional[object] = None
_pool_lock = asyncio.Lock()
_DATABASE_URL = os.environ.get("MCP_DATABASE_URL", "")


async def _get_pool():
    global _pool
    if not _HAS_ASYNCPG or not _DATABASE_URL:
        return None
    async with _pool_lock:
        if _pool is None:
            try:
                _pool = await asyncpg.create_pool(
                    _DATABASE_URL, min_size=1, max_size=5
                )
            except Exception as exc:
                print(f"[logging_middleware] pool init failed: {exc}", file=sys.stderr)
                return None
    return _pool


async def log_verify_document(
    api_key: Optional[str],
    content: str,
    response: dict,
    elapsed_seconds: float,
) -> None:
    """Log a verify_document call. Never raises."""
    asyncio.ensure_future(_do_log_document(api_key, content, response, elapsed_seconds))


async def _do_log_document(api_key, content, response, elapsed_seconds):
    try:
        pool = await _get_pool()
        if pool is None:
            return

        request_id = response.get("request_id") or str(uuid.uuid4())
        input_hash = str(response.get("input_hash") or "")
        scores     = response.get("scores", {})
        decision   = response.get("decision", "unknown")
        claims_raw = response.get("claims", [])
        audit      = response.get("audit", {})
        meta       = response.get("meta", {})
        model      = audit.get("model", "")
        total      = meta.get("total_claims", len(claims_raw))

        corroborated  = sum(1 for c in claims_raw if c.get("status") == "corroborated")
        contradicted  = sum(1 for c in claims_raw if c.get("status") == "contradicted")
        unsupported   = sum(1 for c in claims_raw if c.get("status") == "unsupported")
        out_of_scope  = sum(1 for c in claims_raw if c.get("status") == "out_of_scope")

        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO requests
                    (api_key, tool, request_id, content, input_hash,
                     decision, vs, ecr, sci,
                     total_claims, corroborated_count, contradicted_count,
                     unsupported_count, out_of_scope_count,
                     elapsed_seconds, model)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16)
                ON CONFLICT (request_id) DO NOTHING
                """,
                api_key, "verify_document", request_id, content, input_hash,
                decision,
                scores.get("vs"),  scores.get("ecr"), scores.get("sci"),
                total, corroborated, contradicted, unsupported, out_of_scope,
                elapsed_seconds, model,
            )

            for claim in claims_raw:
                row = await conn.fetchrow(
                    """
                    INSERT INTO claims (request_id, claim_id, text, claim_type, status, confidence, reasoning)
                    VALUES ($1,$2,$3,$4,$5,$6,$7)
                    ON CONFLICT (request_id, claim_id) DO NOTHING
                    RETURNING id
                    """,
                    request_id,
                    claim.get("claim_id", ""),
                    claim.get("text", ""),
                    claim.get("claim_type", ""),
                    claim.get("status", ""),
                    claim.get("confidence"),
                    claim.get("reasoning", ""),
                )
                if row is None:
                    continue
                claim_db_id = row["id"]
                for citation in claim.get("citations", []):
                    await conn.execute(
                        """
                        INSERT INTO citations (claim_id, source, identifier, date, value, label)
                        VALUES ($1,$2,$3,$4,$5,$6)
                        """,
                        claim_db_id,
                        citation.get("source"),
                        citation.get("identifier"),
                        citation.get("date"),
                        str(citation["value"]) if citation.get("value") is not None else None,
                        citation.get("label"),
                    )
    except Exception as exc:
        print(f"[logging_middleware] log_verify_document failed: {exc}", file=sys.stderr)


async def log_verify_claim(
    api_key: Optional[str],
    claim_text: str,
    result: dict,
    elapsed_seconds: float,
) -> None:
    """Log a verify_claim call. Never raises."""
    asyncio.ensure_future(_do_log_claim(api_key, claim_text, result, elapsed_seconds))


async def _do_log_claim(api_key, claim_text, result, elapsed_seconds):
    try:
        pool = await _get_pool()
        if pool is None:
            return

        request_id = str(uuid.uuid4())
        verdict    = result.get("verdict", "unknown")
        input_hash = ""

        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO requests
                    (api_key, tool, request_id, content, input_hash,
                     decision, total_claims,
                     corroborated_count, contradicted_count, unsupported_count, out_of_scope_count,
                     elapsed_seconds)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)
                """,
                api_key, "verify_claim", request_id, claim_text, input_hash,
                verdict, 1,
                1 if verdict == "corroborated" else 0,
                1 if verdict == "contradicted" else 0,
                1 if verdict == "unsupported"  else 0,
                1 if verdict == "out_of_scope" else 0,
                elapsed_seconds,
            )

            row = await conn.fetchrow(
                """
                INSERT INTO claims (request_id, claim_id, text, status, confidence, reasoning)
                VALUES ($1,$2,$3,$4,$5,$6)
                RETURNING id
                """,
                request_id, "claim_0", claim_text,
                verdict,
                result.get("confidence"),
                result.get("reasoning", ""),
            )
            if row is None:
                return

            claim_db_id = row["id"]
            for citation in result.get("citations", []):
                await conn.execute(
                    """
                    INSERT INTO citations (claim_id, source, identifier, date, value, label)
                    VALUES ($1,$2,$3,$4,$5,$6)
                    """,
                    claim_db_id,
                    citation.get("source"),
                    citation.get("identifier"),
                    citation.get("date"),
                    str(citation["value"]) if citation.get("value") is not None else None,
                    citation.get("label"),
                )
    except Exception as exc:
        print(f"[logging_middleware] log_verify_claim failed: {exc}", file=sys.stderr)
