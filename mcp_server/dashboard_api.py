"""
Bria Exchange — Dashboard API
FastAPI application serving the monitoring dashboard.
Two DB pools: MCP_DATABASE_URL (requests/claims) + DASHBOARD_DATABASE_URL (users/keys).
"""

import csv
import io
import json
import os
import sys
import secrets
import hashlib
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import asyncpg
import httpx
from fastapi import BackgroundTasks, Body, FastAPI, Depends, File, Form, HTTPException, Query, Request, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import bcrypt as _bcrypt
from jose import JWTError, jwt
from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

JWT_SECRET       = os.environ.get("JWT_SECRET", "change_me_to_a_random_secret")
JWT_ALGORITHM    = "HS256"
JWT_EXPIRE_DAYS  = 7

VERIFY_API_URL = os.environ.get("VERIFY_API_URL", "http://localhost:8000")

MCP_DATABASE_URL       = os.environ.get("MCP_DATABASE_URL", "")
DASHBOARD_DATABASE_URL = os.environ.get("DASHBOARD_DATABASE_URL", "")

# ---------------------------------------------------------------------------
# App + CORS
# ---------------------------------------------------------------------------

app = FastAPI(title="Bria Exchange Dashboard API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# DB Pools (module-level singletons)
# ---------------------------------------------------------------------------

_mcp_pool: Optional[asyncpg.Pool] = None
_dash_pool: Optional[asyncpg.Pool] = None


async def get_mcp_pool() -> asyncpg.Pool:
    global _mcp_pool
    if _mcp_pool is None:
        if not MCP_DATABASE_URL:
            raise HTTPException(status_code=500, detail={"error": "MCP_DATABASE_URL not set"})
        try:
            _mcp_pool = await asyncpg.create_pool(MCP_DATABASE_URL, min_size=1, max_size=5)
        except Exception as exc:
            raise HTTPException(status_code=500, detail={"error": f"MCP DB pool init failed: {exc}"})
    return _mcp_pool


async def get_dash_pool() -> asyncpg.Pool:
    global _dash_pool
    if _dash_pool is None:
        if not DASHBOARD_DATABASE_URL:
            raise HTTPException(status_code=500, detail={"error": "DASHBOARD_DATABASE_URL not set"})
        try:
            _dash_pool = await asyncpg.create_pool(DASHBOARD_DATABASE_URL, min_size=1, max_size=5)
        except Exception as exc:
            raise HTTPException(status_code=500, detail={"error": f"Dashboard DB pool init failed: {exc}"})
    return _dash_pool


@app.on_event("startup")
async def startup():
    global _mcp_pool, _dash_pool
    if MCP_DATABASE_URL:
        try:
            _mcp_pool = await asyncpg.create_pool(MCP_DATABASE_URL, min_size=1, max_size=5)
        except Exception as exc:
            print(f"[dashboard_api] MCP pool init failed: {exc}", file=sys.stderr)
    else:
        print("[dashboard_api] MCP_DATABASE_URL not set — requests/stats endpoints will fail", file=sys.stderr)

    if DASHBOARD_DATABASE_URL:
        try:
            _dash_pool = await asyncpg.create_pool(DASHBOARD_DATABASE_URL, min_size=1, max_size=5)
        except Exception as exc:
            print(f"[dashboard_api] Dashboard pool init failed: {exc}", file=sys.stderr)
    else:
        print("[dashboard_api] DASHBOARD_DATABASE_URL not set — auth/keys endpoints will fail", file=sys.stderr)


@app.on_event("shutdown")
async def shutdown():
    if _mcp_pool:
        await _mcp_pool.close()
    if _dash_pool:
        await _dash_pool.close()


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@app.get("/health")
async def health():
    return {"ok": True}


# ---------------------------------------------------------------------------
# Auth utilities
# ---------------------------------------------------------------------------

bearer_scheme = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    return _bcrypt.hashpw(password.encode(), _bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return _bcrypt.checkpw(plain.encode(), hashed.encode())


def create_jwt(user_id: int) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=JWT_EXPIRE_DAYS)
    return jwt.encode({"sub": str(user_id), "exp": expire}, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_jwt(token: str) -> int:
    payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    return int(payload["sub"])


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    pool: asyncpg.Pool = Depends(get_dash_pool),
):
    if not credentials:
        raise HTTPException(status_code=401, detail={"error": "Missing authorization header"})
    try:
        user_id = decode_jwt(credentials.credentials)
    except JWTError:
        raise HTTPException(status_code=401, detail={"error": "Invalid or expired token"})
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT id, email, display_name, avatar_url, org_name, role FROM users WHERE id = $1",
                user_id,
            )
    except Exception as exc:
        raise HTTPException(status_code=500, detail={"error": str(exc)})
    if row is None:
        raise HTTPException(status_code=401, detail={"error": "User not found"})
    return dict(row)


def _build_user_response(row: dict, token: str, api_key: str = "") -> dict:
    """Shape the auth response the frontend expects."""
    user_id = row["id"]
    email = row.get("email", "")
    name = row.get("display_name") or (email.split("@")[0] if email else "User")
    role = row.get("role") or "admin"
    org_name = row.get("org_name") or "My Organisation"
    return {
        "user": {
            "id": str(user_id),
            "name": name,
            "email": email,
            "role": role,
        },
        "org": {
            "id": str(user_id),  # user IS the org in this single-tenant model
            "name": org_name,
            "apiKey": api_key,
        },
        "token": token,
    }


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class SignupBody(BaseModel):
    name: str
    email: str
    password: str
    orgName: str

class LoginBody(BaseModel):
    email: str
    password: str

class CreateKeyBody(BaseModel):
    label: Optional[str] = None

class RequestsFilter(BaseModel):
    page: int = 1
    per_page: int = 20
    decision: Optional[str] = None
    tool: Optional[str] = None
    date_from: Optional[str] = None
    date_to: Optional[str] = None

class GoogleSyncBody(BaseModel):
    googleId: str
    email: str
    name: Optional[str] = None
    avatar: Optional[str] = None


# ---------------------------------------------------------------------------
# Auth routes
# ---------------------------------------------------------------------------

@app.post("/auth/signup")
async def signup(body: SignupBody, pool: asyncpg.Pool = Depends(get_dash_pool)):
    try:
        async with pool.acquire() as conn:
            existing = await conn.fetchrow("SELECT id FROM users WHERE email = $1", body.email)
            if existing:
                raise HTTPException(status_code=400, detail={"error": "Email already registered"})
            password_hash = hash_password(body.password)
            row = await conn.fetchrow(
                """
                INSERT INTO users (email, password_hash, display_name, org_name, role)
                VALUES ($1, $2, $3, $4, 'admin')
                RETURNING id, email, display_name, org_name, role
                """,
                body.email, password_hash, body.name, body.orgName,
            )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail={"error": str(exc)})
    token = create_jwt(row["id"])
    return _build_user_response(dict(row), token)


@app.post("/auth/login")
async def login(body: LoginBody, pool: asyncpg.Pool = Depends(get_dash_pool)):
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT id, email, password_hash, display_name, org_name, role FROM users WHERE email = $1",
                body.email,
            )
    except Exception as exc:
        raise HTTPException(status_code=500, detail={"error": str(exc)})

    if row is None or not verify_password(body.password, row["password_hash"] or ""):
        raise HTTPException(status_code=401, detail={"error": "Invalid credentials"})

    token = create_jwt(row["id"])
    user_dict = dict(row)

    # Look up the user's first active API key prefix to return as the org's apiKey
    api_key_prefix = ""
    try:
        async with pool.acquire() as conn:
            key_row = await conn.fetchrow(
                "SELECT key_prefix FROM api_keys WHERE user_id=$1 AND is_active=TRUE ORDER BY created_at LIMIT 1",
                row["id"],
            )
        if key_row:
            api_key_prefix = key_row["key_prefix"] + "…"
    except Exception:
        pass

    return _build_user_response(user_dict, token, api_key_prefix)


@app.get("/auth/me")
async def me(current_user: dict = Depends(get_current_user)):
    return current_user


@app.post("/auth/google/sync")
async def google_sync(body: GoogleSyncBody, pool: asyncpg.Pool = Depends(get_dash_pool)):
    """
    Called by the Next.js frontend after NextAuth completes the Google OAuth flow.
    Creates or updates the user in the DB and returns a backend JWT.
    """
    try:
        async with pool.acquire() as conn:
            existing = await conn.fetchrow(
                "SELECT id, email, display_name, org_name, role FROM users WHERE google_id = $1",
                body.googleId,
            )
            if existing:
                await conn.execute(
                    "UPDATE users SET display_name=$1, avatar_url=$2 WHERE id=$3",
                    body.name, body.avatar, existing["id"],
                )
                row = await conn.fetchrow(
                    "SELECT id, email, display_name, org_name, role FROM users WHERE id=$1",
                    existing["id"],
                )
            else:
                row = await conn.fetchrow(
                    """
                    INSERT INTO users (email, google_id, display_name, avatar_url)
                    VALUES ($1, $2, $3, $4)
                    ON CONFLICT (email) DO UPDATE
                        SET google_id=$2, display_name=$3, avatar_url=$4
                    RETURNING id, email, display_name, org_name, role
                    """,
                    body.email, body.googleId, body.name, body.avatar,
                )
    except Exception as exc:
        raise HTTPException(status_code=500, detail={"error": str(exc)})

    token = create_jwt(row["id"])

    api_key_prefix = ""
    try:
        async with pool.acquire() as conn:
            key_row = await conn.fetchrow(
                "SELECT key_prefix FROM api_keys WHERE user_id=$1 AND is_active=TRUE ORDER BY created_at LIMIT 1",
                row["id"],
            )
        if key_row:
            api_key_prefix = key_row["key_prefix"] + "…"
    except Exception:
        pass

    return _build_user_response(dict(row), token, api_key_prefix)


# ---------------------------------------------------------------------------
# API Key routes
# ---------------------------------------------------------------------------

@app.get("/keys")
async def list_keys(
    current_user: dict = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_dash_pool),
):
    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, key_prefix, label, created_at, last_used_at, is_active
                FROM api_keys
                WHERE user_id = $1
                ORDER BY created_at DESC
                """,
                current_user["id"],
            )
    except Exception as exc:
        raise HTTPException(status_code=500, detail={"error": str(exc)})
    return [dict(r) for r in rows]


@app.post("/keys", status_code=201)
async def create_key(
    body: CreateKeyBody,
    current_user: dict = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_dash_pool),
):
    raw_key    = "bx_" + secrets.token_hex(20)
    key_hash   = hashlib.sha256(raw_key.encode()).hexdigest()
    key_prefix = raw_key[:12]

    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO api_keys (user_id, key_hash, key_prefix, label)
                VALUES ($1, $2, $3, $4)
                RETURNING id, key_prefix, label, created_at
                """,
                current_user["id"], key_hash, key_prefix, body.label,
            )
    except Exception as exc:
        raise HTTPException(status_code=500, detail={"error": str(exc)})

    return {
        "id":         row["id"],
        "key":        raw_key,
        "key_prefix": row["key_prefix"],
        "label":      row["label"],
        "created_at": row["created_at"],
    }


@app.delete("/keys/{key_id}", status_code=204)
async def revoke_key(
    key_id: int,
    current_user: dict = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_dash_pool),
):
    try:
        async with pool.acquire() as conn:
            result = await conn.execute(
                "UPDATE api_keys SET is_active=FALSE WHERE id=$1 AND user_id=$2",
                key_id, current_user["id"],
            )
    except Exception as exc:
        raise HTTPException(status_code=500, detail={"error": str(exc)})
    if result == "UPDATE 0":
        raise HTTPException(status_code=404, detail={"error": "Key not found"})


# ---------------------------------------------------------------------------
# Request routes  (reads from MCP DB) — kept for legacy Vite dashboard
# ---------------------------------------------------------------------------

@app.get("/requests")
async def list_requests(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    decision: Optional[str] = Query(None),
    tool: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    current_user: dict = Depends(get_current_user),
    mcp_pool: asyncpg.Pool = Depends(get_mcp_pool),
    dash_pool: asyncpg.Pool = Depends(get_dash_pool),
):
    try:
        async with dash_pool.acquire() as conn:
            key_rows = await conn.fetch(
                "SELECT key_prefix FROM api_keys WHERE user_id=$1 AND is_active=TRUE",
                current_user["id"],
            )
    except Exception as exc:
        raise HTTPException(status_code=500, detail={"error": str(exc)})

    prefixes = [r["key_prefix"] for r in key_rows]
    if not prefixes:
        return {"items": [], "total": 0, "page": page, "per_page": per_page}

    conditions = ["LEFT(r.api_key, 12) = ANY($1::text[])"]
    params: list = [prefixes]
    idx = 2

    if decision:
        conditions.append(f"r.decision = ${idx}")
        params.append(decision)
        idx += 1
    if tool:
        conditions.append(f"r.tool = ${idx}")
        params.append(tool)
        idx += 1
    if date_from:
        conditions.append(f"r.created_at >= ${idx}::timestamptz")
        params.append(date_from)
        idx += 1
    if date_to:
        conditions.append(f"r.created_at < (${idx}::date + INTERVAL '1 day')::timestamptz")
        params.append(date_to)
        idx += 1

    where = " AND ".join(conditions)
    offset = (page - 1) * per_page

    try:
        async with mcp_pool.acquire() as conn:
            count_row = await conn.fetchrow(
                f"SELECT COUNT(*) AS total FROM requests r WHERE {where}", *params
            )
            total = count_row["total"]

            rows = await conn.fetch(
                f"""
                SELECT r.request_id, r.tool, r.decision,
                       r.vs, r.ecr, r.sci,
                       r.total_claims, r.elapsed_seconds, r.created_at,
                       LEFT(r.api_key, 12) AS key_prefix
                FROM requests r
                WHERE {where}
                ORDER BY r.created_at DESC
                LIMIT ${idx} OFFSET ${idx+1}
                """,
                *params, per_page, offset,
            )
    except Exception as exc:
        raise HTTPException(status_code=500, detail={"error": str(exc)})

    return {
        "items":    [dict(r) for r in rows],
        "total":    total,
        "page":     page,
        "per_page": per_page,
    }


@app.get("/requests/{request_id}")
async def get_request(
    request_id: str,
    current_user: dict = Depends(get_current_user),
    mcp_pool: asyncpg.Pool = Depends(get_mcp_pool),
    dash_pool: asyncpg.Pool = Depends(get_dash_pool),
):
    try:
        async with dash_pool.acquire() as conn:
            key_rows = await conn.fetch(
                "SELECT key_prefix FROM api_keys WHERE user_id=$1 AND is_active=TRUE",
                current_user["id"],
            )
    except Exception as exc:
        raise HTTPException(status_code=500, detail={"error": str(exc)})

    prefixes = [r["key_prefix"] for r in key_rows]

    try:
        async with mcp_pool.acquire() as conn:
            req_row = await conn.fetchrow(
                """
                SELECT request_id, tool, decision, vs, ecr, sci,
                       total_claims, elapsed_seconds, created_at,
                       LEFT(api_key, 12) AS key_prefix,
                       content, model
                FROM requests
                WHERE request_id = $1
                  AND LEFT(api_key, 12) = ANY($2::text[])
                """,
                request_id, prefixes,
            )
            if req_row is None:
                raise HTTPException(status_code=404, detail={"error": "Request not found"})

            claim_rows = await conn.fetch(
                """
                SELECT id, claim_id, text, claim_type, status, confidence, reasoning
                FROM claims
                WHERE request_id = $1
                ORDER BY id
                """,
                request_id,
            )

            claims = []
            for claim in claim_rows:
                citation_rows = await conn.fetch(
                    "SELECT source, identifier, date, value, label FROM citations WHERE claim_id = $1",
                    claim["id"],
                )
                claims.append({
                    **dict(claim),
                    "citations": [dict(c) for c in citation_rows],
                })
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail={"error": str(exc)})

    return {**dict(req_row), "claims": claims}


# ---------------------------------------------------------------------------
# Stats route — legacy
# ---------------------------------------------------------------------------

@app.get("/stats")
async def get_stats(
    current_user: dict = Depends(get_current_user),
    mcp_pool: asyncpg.Pool = Depends(get_mcp_pool),
    dash_pool: asyncpg.Pool = Depends(get_dash_pool),
):
    try:
        async with dash_pool.acquire() as conn:
            key_rows = await conn.fetch(
                "SELECT key_prefix FROM api_keys WHERE user_id=$1 AND is_active=TRUE",
                current_user["id"],
            )
    except Exception as exc:
        raise HTTPException(status_code=500, detail={"error": str(exc)})

    prefixes = [r["key_prefix"] for r in key_rows]
    if not prefixes:
        return {
            "total_requests": 0,
            "pass_count": 0, "review_count": 0, "block_count": 0,
            "avg_vs": None, "avg_ecr": None, "avg_sci": None,
            "requests_over_time": [],
        }

    try:
        async with mcp_pool.acquire() as conn:
            agg = await conn.fetchrow(
                """
                SELECT
                    COUNT(*)                                         AS total_requests,
                    COUNT(*) FILTER (WHERE decision = 'pass')       AS pass_count,
                    COUNT(*) FILTER (WHERE decision = 'review')     AS review_count,
                    COUNT(*) FILTER (WHERE decision = 'block')      AS block_count,
                    AVG(vs)                                          AS avg_vs,
                    AVG(ecr)                                         AS avg_ecr,
                    AVG(sci)                                         AS avg_sci
                FROM requests
                WHERE LEFT(api_key, 12) = ANY($1::text[])
                """,
                prefixes,
            )

            daily_rows = await conn.fetch(
                """
                SELECT
                    DATE_TRUNC('day', created_at)::date AS date,
                    COUNT(*)                            AS count
                FROM requests
                WHERE LEFT(api_key, 12) = ANY($1::text[])
                  AND created_at >= NOW() - INTERVAL '30 days'
                GROUP BY 1
                ORDER BY 1
                """,
                prefixes,
            )
    except Exception as exc:
        raise HTTPException(status_code=500, detail={"error": str(exc)})

    return {
        "total_requests":      agg["total_requests"],
        "pass_count":          agg["pass_count"],
        "review_count":        agg["review_count"],
        "block_count":         agg["block_count"],
        "avg_vs":              float(agg["avg_vs"]) if agg["avg_vs"] is not None else None,
        "avg_ecr":             float(agg["avg_ecr"]) if agg["avg_ecr"] is not None else None,
        "avg_sci":             float(agg["avg_sci"]) if agg["avg_sci"] is not None else None,
        "requests_over_time":  [{"date": str(r["date"]), "count": r["count"]} for r in daily_rows],
    }


# ===========================================================================
# NEW /api/* routes — consumed by the Next.js frontend
# ===========================================================================

def _build_fix(status: str, reasoning: str) -> Optional[dict]:
    if status == "contradicted":
        return {"suggested_text": None, "confidence": "low", "basis": reasoning}
    if status == "unsupported":
        return {"suggested_text": None, "action": "remove_or_qualify", "suggestion": reasoning or "Claim could not be supported by available sources."}
    if status == "out_of_scope":
        return {"suggested_text": None, "action": "flag_for_human_review", "suggestion": reasoning or "Claim is outside the scope of connected sources."}
    return None


def _period_to_days(period: str) -> int:
    mapping = {"7d": 7, "30d": 30, "90d": 90, "180d": 180, "1y": 365}
    return mapping.get(period, 30)


async def _get_user_agents(user_id: int, dash_pool: asyncpg.Pool) -> dict:
    """Returns {agent_id: agent_name} for all agents belonging to this user."""
    async with dash_pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id, name FROM agents WHERE user_id=$1", user_id
        )
    return {r["id"]: r["name"] for r in rows}


async def _get_user_prefixes(user_id: int, dash_pool: asyncpg.Pool) -> list[str]:
    async with dash_pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT key_prefix FROM api_keys WHERE user_id=$1 AND is_active=TRUE",
            user_id,
        )
        agent_rows = await conn.fetch(
            "SELECT api_key FROM agents WHERE user_id=$1 AND api_key IS NOT NULL",
            user_id,
        )
    prefixes = [r["key_prefix"] for r in rows]
    # Include agent key prefixes so MCP requests appear in dashboard
    prefixes += [r["api_key"][:12] for r in agent_rows if r.get("api_key")]
    return prefixes


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

@app.get("/api/dashboard")
async def api_dashboard(
    period: str = Query("30d"),
    current_user: dict = Depends(get_current_user),
    mcp_pool: asyncpg.Pool = Depends(get_mcp_pool),
    dash_pool: asyncpg.Pool = Depends(get_dash_pool),
):
    days = _period_to_days(period)
    prefixes = await _get_user_prefixes(current_user["id"], dash_pool)

    empty = {
        "period": period,
        "totalVerifications": 0, "passCount": 0, "flagCount": 0, "blockCount": 0,
        "totalClaims": 0, "corroboratedCount": 0, "contradictedCount": 0,
        "unsupportedCount": 0, "outOfScopeCount": 0,
        "claimsPreventedFromPublication": 0, "avgCoverageRatio": 0.0,
        "avgCorroborationRate": 0.0, "estimatedHoursSaved": 0.0,
        "deltas": {"totalVerifications": 0, "claimsPreventedFromPublication": 0,
                   "avgCorroborationRate": 0.0, "estimatedHoursSaved": 0.0},
        "verificationsByDay": [], "decisionByDay": [],
        "corroborationRateByDay": [], "coverageRatioByDay": [], "outOfScopeRateByDay": [],
        "byDomain": {"pharma": 0, "legal": 0, "financial": 0, "news_editorial": 0},
        "discrepancyTypeBreakdown": {}, "confirmationStrengthBreakdown": {"strong": 0, "moderate": 0, "weak": 0},
        "sourceAuthorityBreakdown": {"primary": 0, "institutional": 0, "secondary": 0, "tertiary": 0},
        "sourceFreshnessBreakdown": {"current": 0, "aging": 0, "stale": 0, "deprecated": 0},
        "agentLeaderboard": [], "reviewerLeaderboard": [],
        "topDecisionReasons": [], "recentActivity": [],
        "pendingReviewCount": 0, "pendingReviewHasBlock": False,
        "reviewOperations": {"avgReviewTimeMs": 0, "approvedCount": 0, "rejectedCount": 0, "reVerificationRate": 0.0},
    }

    if not prefixes:
        return empty

    try:
        async with mcp_pool.acquire() as conn:
            agg = await conn.fetchrow(
                """
                SELECT
                    COUNT(*)                                              AS total,
                    COUNT(*) FILTER (WHERE decision='pass')              AS pass_count,
                    COUNT(*) FILTER (WHERE decision='review')            AS flag_count,
                    COUNT(*) FILTER (WHERE decision='block')             AS block_count,
                    COALESCE(SUM(total_claims), 0)                       AS total_claims,
                    COALESCE(SUM(corroborated_count), 0)                 AS corroborated,
                    COALESCE(SUM(contradicted_count), 0)                 AS contradicted,
                    COALESCE(SUM(unsupported_count), 0)                  AS unsupported,
                    COALESCE(SUM(out_of_scope_count), 0)                 AS out_of_scope,
                    COALESCE(AVG(ecr), 0)                                AS avg_ecr,
                    COALESCE(AVG(vs), 0)                                 AS avg_vs
                FROM requests
                WHERE LEFT(api_key, 12) = ANY($1::text[])
                  AND created_at >= NOW() - ($2 || ' days')::interval
                """,
                prefixes, str(days),
            )

            # Per-day counts
            daily = await conn.fetch(
                """
                SELECT
                    DATE_TRUNC('day', created_at)::date AS day,
                    COUNT(*)                            AS total,
                    COUNT(*) FILTER (WHERE decision='pass')   AS pass_c,
                    COUNT(*) FILTER (WHERE decision='review')  AS flag_c,
                    COUNT(*) FILTER (WHERE decision='block')  AS block_c,
                    COALESCE(AVG(vs), 0)                      AS avg_vs,
                    COALESCE(AVG(ecr), 0)                     AS avg_ecr,
                    COALESCE(
                        SUM(out_of_scope_count)::float /
                        NULLIF(SUM(total_claims), 0), 0
                    ) AS oos_rate
                FROM requests
                WHERE LEFT(api_key, 12) = ANY($1::text[])
                  AND created_at >= NOW() - ($2 || ' days')::interval
                GROUP BY 1
                ORDER BY 1
                """,
                prefixes, str(days),
            )

            # Recent activity (last 10)
            recent = await conn.fetch(
                """
                SELECT request_id, content, decision, created_at,
                       vs, total_claims, corroborated_count, contradicted_count
                FROM requests
                WHERE LEFT(api_key, 12) = ANY($1::text[])
                ORDER BY created_at DESC
                LIMIT 10
                """,
                prefixes,
            )
    except Exception as exc:
        raise HTTPException(status_code=500, detail={"error": str(exc)})

    prevented = int(agg["contradicted"]) + int(agg["unsupported"])
    hours_saved = round(prevented * 0.25, 1)  # 15min per claim prevented

    recent_activity = [
        {
            "id": r["request_id"],
            "inputPreview": (r["content"] or "")[:120],
            "domain": "financial",
            "agentName": None,
            "decision": "flag" if r["decision"] == "review" else r["decision"],
            "reviewStatus": "pending",
            "contradictedCount": r["contradicted_count"] or 0,
            "corroborationRate": float(r["vs"] or 0),
            "createdAt": r["created_at"].isoformat(),
        }
        for r in recent
    ]

    return {
        "period": period,
        "totalVerifications": int(agg["total"]),
        "passCount": int(agg["pass_count"]),
        "flagCount": int(agg["flag_count"]),
        "blockCount": int(agg["block_count"]),
        "totalClaims": int(agg["total_claims"]),
        "corroboratedCount": int(agg["corroborated"]),
        "contradictedCount": int(agg["contradicted"]),
        "unsupportedCount": int(agg["unsupported"]),
        "outOfScopeCount": int(agg["out_of_scope"]),
        "claimsPreventedFromPublication": prevented,
        "avgCoverageRatio": round(float(agg["avg_ecr"]), 4),
        "avgCorroborationRate": round(float(agg["avg_vs"]), 4),
        "estimatedHoursSaved": hours_saved,
        "deltas": {
            "totalVerifications": 0, "claimsPreventedFromPublication": 0,
            "avgCorroborationRate": 0.0, "estimatedHoursSaved": 0.0,
        },
        "verificationsByDay": [
            {"date": str(r["day"]), "value": int(r["total"])} for r in daily
        ],
        "decisionByDay": [
            {"date": str(r["day"]), "pass": int(r["pass_c"]),
             "flag": int(r["flag_c"]), "block": int(r["block_c"])}
            for r in daily
        ],
        "corroborationRateByDay": [
            {"date": str(r["day"]), "value": round(float(r["avg_vs"]), 4)} for r in daily
        ],
        "coverageRatioByDay": [
            {"date": str(r["day"]), "value": round(float(r["avg_ecr"]), 4)} for r in daily
        ],
        "outOfScopeRateByDay": [
            {"date": str(r["day"]), "value": round(float(r["oos_rate"]), 4)} for r in daily
        ],
        "byDomain": {"pharma": 0, "legal": 0, "financial": int(agg["total"]), "news_editorial": 0},
        "discrepancyTypeBreakdown": {},
        "confirmationStrengthBreakdown": {"strong": 0, "moderate": 0, "weak": 0},
        "sourceAuthorityBreakdown": {"primary": 0, "institutional": 0, "secondary": 0, "tertiary": 0},
        "sourceFreshnessBreakdown": {"current": 0, "aging": 0, "stale": 0, "deprecated": 0},
        "agentLeaderboard": [],
        "reviewerLeaderboard": [],
        "topDecisionReasons": [],
        "recentActivity": recent_activity,
        "pendingReviewCount": 0,
        "pendingReviewHasBlock": False,
        "reviewOperations": {
            "avgReviewTimeMs": 0, "approvedCount": 0,
            "rejectedCount": 0, "reVerificationRate": 0.0,
        },
    }


# ---------------------------------------------------------------------------
# Cost Estimation
# ---------------------------------------------------------------------------

# Pricing per 1M tokens (USD)
_MODEL_PRICING: dict[str, dict[str, float]] = {
    "claude-opus-4-6":            {"input": 15.0, "output": 75.0},
    "claude-opus-4-5":            {"input": 15.0, "output": 75.0},
    "claude-sonnet-4-6":          {"input": 3.0,  "output": 15.0},
    "claude-sonnet-4-5":          {"input": 3.0,  "output": 15.0},
    "claude-haiku-4-5":           {"input": 0.8,  "output": 4.0},
    "claude-haiku-4-5-20251001":  {"input": 0.8,  "output": 4.0},
}
_DEFAULT_MODEL_PRICING = {"input": 15.0, "output": 75.0}


def _estimate_cost_usd(total_chars: int, total_output_tokens: int, model: str, total_claims: int = 0) -> float:
    pricing = _MODEL_PRICING.get(model, _DEFAULT_MODEL_PRICING)
    # Input = document text + system prompt overhead (~2000 tokens per claim across ~2.5 turns)
    input_tokens = total_chars / 4.0 + total_claims * 2000
    return (input_tokens / 1_000_000) * pricing["input"] + (total_output_tokens / 1_000_000) * pricing["output"]


@app.get("/api/cost")
async def api_cost(
    period: str = Query("30d"),
    current_user: dict = Depends(get_current_user),
    mcp_pool: asyncpg.Pool = Depends(get_mcp_pool),
    dash_pool: asyncpg.Pool = Depends(get_dash_pool),
):
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    days = _period_to_days(period)
    prefixes = await _get_user_prefixes(current_user["id"], dash_pool)
    agent_map = await _get_user_agents(current_user["id"], dash_pool)

    empty = {
        "period": period,
        "totalCostUsd": 0.0,
        "totalInputTokensEst": 0,
        "totalOutputTokensEst": 0,
        "totalVerifications": 0,
        "avgCostPerVerification": 0.0,
        "projectedMonthlyCost": 0.0,
        "deltaPercent": 0.0,
        "costByDay": [],
        "byAgent": [],
        "byModel": [],
    }

    if not prefixes:
        return empty

    try:
        async with mcp_pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT
                    DATE_TRUNC('day', created_at)::date               AS day,
                    COALESCE(agent_id, 'direct')                      AS agent_id,
                    COALESCE(model, 'claude-haiku-4-5-20251001')       AS model,
                    SUM(LENGTH(COALESCE(content, '')))                AS total_chars,
                    SUM(COALESCE(total_claims, 0) * 300 + 500)        AS total_output_tokens,
                    SUM(COALESCE(total_claims, 0))                    AS total_claims_sum,
                    COUNT(*)                                          AS verifications
                FROM requests
                WHERE LEFT(api_key, 12) = ANY($1::text[])
                  AND created_at >= NOW() - ($2 || ' days')::interval
                GROUP BY 1, 2, 3
                ORDER BY 1
                """,
                prefixes, str(days),
            )

            prev_rows = await conn.fetch(
                """
                SELECT
                    COALESCE(model, 'claude-haiku-4-5-20251001')       AS model,
                    SUM(LENGTH(COALESCE(content, '')))                AS total_chars,
                    SUM(COALESCE(total_claims, 0) * 300 + 500)        AS total_output_tokens,
                    SUM(COALESCE(total_claims, 0))                    AS total_claims_sum
                FROM requests
                WHERE LEFT(api_key, 12) = ANY($1::text[])
                  AND created_at >= NOW() - ($3 || ' days')::interval
                  AND created_at < NOW() - ($2 || ' days')::interval
                GROUP BY model
                """,
                prefixes, str(days), str(days * 2),
            )

        # Aggregate current period
        day_costs: dict[str, float] = {}
        agent_costs: dict[str, dict] = {}
        model_costs: dict[str, dict] = {}
        total_cost = 0.0
        total_input_tokens = 0
        total_output_tokens = 0
        total_verifications = 0

        for row in rows:
            chars = int(row["total_chars"] or 0)
            out_tokens = int(row["total_output_tokens"] or 0)
            claims_sum = int(row["total_claims_sum"] or 0)
            model = row["model"]
            agent_id = row["agent_id"]
            day = str(row["day"])
            verifs = int(row["verifications"])

            input_tokens = chars // 4 + claims_sum * 2000
            cost = _estimate_cost_usd(chars, out_tokens, model, claims_sum)

            total_cost += cost
            total_input_tokens += input_tokens
            total_output_tokens += out_tokens
            total_verifications += verifs

            day_costs[day] = day_costs.get(day, 0.0) + cost

            if agent_id not in agent_costs:
                agent_costs[agent_id] = {"inputTokens": 0, "outputTokens": 0, "cost": 0.0, "verifications": 0}
            agent_costs[agent_id]["inputTokens"] += input_tokens
            agent_costs[agent_id]["outputTokens"] += out_tokens
            agent_costs[agent_id]["cost"] += cost
            agent_costs[agent_id]["verifications"] += verifs

            if model not in model_costs:
                model_costs[model] = {"cost": 0.0, "verifications": 0}
            model_costs[model]["cost"] += cost
            model_costs[model]["verifications"] += verifs

        # Previous period cost for delta
        prev_cost = sum(
            _estimate_cost_usd(int(r["total_chars"] or 0), int(r["total_output_tokens"] or 0), r["model"], int(r["total_claims_sum"] or 0))
            for r in prev_rows
        )
        delta_percent = round(((total_cost - prev_cost) / prev_cost) * 100, 1) if prev_cost > 0 else 0.0
        projected_monthly = round((total_cost / days) * 30, 4) if days > 0 and total_cost > 0 else 0.0

        return {
            "period": period,
            "totalCostUsd": round(total_cost, 4),
            "totalInputTokensEst": total_input_tokens,
            "totalOutputTokensEst": total_output_tokens,
            "totalVerifications": total_verifications,
            "avgCostPerVerification": round(total_cost / total_verifications, 4) if total_verifications > 0 else 0.0,
            "projectedMonthlyCost": projected_monthly,
            "deltaPercent": delta_percent,
            "costByDay": [{"date": d, "costUsd": round(c, 4)} for d, c in sorted(day_costs.items())],
            "byAgent": sorted(
                [
                    {
                        "agentId": aid,
                        "agentName": agent_map.get(aid, "Direct / Unknown"),
                        "verifications": v["verifications"],
                        "inputTokensEst": v["inputTokens"],
                        "outputTokensEst": v["outputTokens"],
                        "costUsd": round(v["cost"], 4),
                    }
                    for aid, v in agent_costs.items()
                ],
                key=lambda x: -x["costUsd"],
            ),
            "byModel": sorted(
                [
                    {"model": m, "verifications": v["verifications"], "costUsd": round(v["cost"], 4)}
                    for m, v in model_costs.items()
                ],
                key=lambda x: -x["costUsd"],
            ),
        }

    except Exception as exc:
        raise HTTPException(status_code=500, detail={"error": str(exc)})


# ---------------------------------------------------------------------------
# Audit log
# ---------------------------------------------------------------------------

@app.get("/api/audit")
async def api_audit(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    decision: Optional[str] = Query(None),
    agentId: Optional[str] = Query(None),
    dateFrom: Optional[str] = Query(None),
    dateTo: Optional[str] = Query(None),
    current_user: dict = Depends(get_current_user),
    mcp_pool: asyncpg.Pool = Depends(get_mcp_pool),
    dash_pool: asyncpg.Pool = Depends(get_dash_pool),
):
    prefixes = await _get_user_prefixes(current_user["id"], dash_pool)
    if not prefixes:
        return {"verifications": [], "total": 0, "page": page, "limit": limit}

    conditions = ["LEFT(api_key, 12) = ANY($1::text[])"]
    params: list = [prefixes]
    idx = 2

    # Map frontend 'flag' → DB 'review'
    if decision:
        db_decision = "review" if decision == "flag" else decision
        conditions.append(f"decision = ${idx}")
        params.append(db_decision)
        idx += 1
    if agentId:
        conditions.append(f"agent_id = ${idx}")
        params.append(agentId)
        idx += 1
    if dateFrom:
        conditions.append(f"created_at >= ${idx}::timestamptz")
        params.append(dateFrom)
        idx += 1
    if dateTo:
        conditions.append(f"created_at < (${idx}::date + INTERVAL '1 day')::timestamptz")
        params.append(dateTo)
        idx += 1

    where = " AND ".join(conditions)
    offset = (page - 1) * limit

    try:
        async with mcp_pool.acquire() as conn:
            count_row = await conn.fetchrow(
                f"SELECT COUNT(*) AS total FROM requests WHERE {where}", *params
            )
            total = count_row["total"]
            rows = await conn.fetch(
                f"""
                SELECT request_id, content, decision, vs, ecr, sci,
                       total_claims, corroborated_count, contradicted_count,
                       unsupported_count, out_of_scope_count, elapsed_seconds,
                       created_at, review_status, reviewed_by, reviewed_at,
                       review_note, review_actions, corrected_text, agent_id,
                       parent_request_id, domain, decision_reasons, full_response,
                       config, trace_id
                FROM requests
                WHERE {where}
                ORDER BY created_at DESC
                LIMIT ${idx} OFFSET ${idx+1}
                """,
                *params, limit, offset,
            )
    except Exception as exc:
        raise HTTPException(status_code=500, detail={"error": str(exc)})

    agents = await _get_user_agents(current_user["id"], dash_pool)
    return {
        "verifications": [_request_to_verification(dict(r), agents=agents) for r in rows],
        "total": int(total),
        "page": page,
        "limit": limit,
    }


@app.get("/api/audit/export")
async def api_audit_export(
    decision: Optional[str] = Query(None),
    dateFrom: Optional[str] = Query(None),
    dateTo: Optional[str] = Query(None),
    current_user: dict = Depends(get_current_user),
    mcp_pool: asyncpg.Pool = Depends(get_mcp_pool),
    dash_pool: asyncpg.Pool = Depends(get_dash_pool),
):
    prefixes = await _get_user_prefixes(current_user["id"], dash_pool)
    if not prefixes:
        return Response(content="id,inputText,domain,decision,totalClaims,coverageRatio,createdAt\n",
                        media_type="text/csv",
                        headers={"Content-Disposition": "attachment; filename=audit.csv"})

    conditions = ["LEFT(api_key, 12) = ANY($1::text[])"]
    params: list = [prefixes]
    idx = 2

    if decision:
        db_decision = "review" if decision == "flag" else decision
        conditions.append(f"decision = ${idx}")
        params.append(db_decision)
        idx += 1
    if dateFrom:
        conditions.append(f"created_at >= ${idx}::timestamptz")
        params.append(dateFrom)
        idx += 1
    if dateTo:
        conditions.append(f"created_at < (${idx}::date + INTERVAL '1 day')::timestamptz")
        params.append(dateTo)
        idx += 1

    where = " AND ".join(conditions)
    try:
        async with mcp_pool.acquire() as conn:
            rows = await conn.fetch(
                f"""
                SELECT request_id, content, decision, vs, ecr,
                       total_claims, corroborated_count, contradicted_count,
                       unsupported_count, out_of_scope_count, elapsed_seconds,
                       created_at, domain, review_status
                FROM requests
                WHERE {where}
                ORDER BY created_at DESC
                LIMIT 10000
                """,
                *params,
            )
    except Exception as exc:
        raise HTTPException(status_code=500, detail={"error": str(exc)})

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "id", "inputText", "domain", "decision", "reviewStatus",
        "totalClaims", "corroboratedCount", "contradictedCount",
        "unsupportedCount", "outOfScopeCount", "coverageRatio",
        "corroborationRate", "latencyMs", "createdAt",
    ])
    for r in rows:
        decision_val = "flag" if r["decision"] == "review" else r["decision"]
        writer.writerow([
            r["request_id"],
            (r["content"] or "")[:200].replace("\n", " "),
            r.get("domain") or "financial",
            decision_val,
            r.get("review_status") or "not_required",
            r["total_claims"] or 0,
            r["corroborated_count"] or 0,
            r["contradicted_count"] or 0,
            r["unsupported_count"] or 0,
            r["out_of_scope_count"] or 0,
            round(float(r["ecr"] or 0), 4),
            round(float(r["vs"] or 0), 4),
            int((r["elapsed_seconds"] or 0) * 1000),
            r["created_at"].isoformat(),
        ])

    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=audit.csv"},
    )


# ---------------------------------------------------------------------------
# Review queue
# ---------------------------------------------------------------------------

def _request_to_verification(r: dict, agents: dict | None = None) -> dict:
    decision_reasons = r.get("decision_reasons") or []
    if isinstance(decision_reasons, str):
        try:
            decision_reasons = json.loads(decision_reasons)
        except Exception:
            decision_reasons = []

    full_response = r.get("full_response")
    if isinstance(full_response, str):
        try:
            full_response = json.loads(full_response)
        except Exception:
            full_response = None

    config = r.get("config") or {}
    if isinstance(config, str):
        try:
            config = json.loads(config)
        except Exception:
            config = {}

    review_actions = r.get("review_actions")
    if isinstance(review_actions, str):
        try:
            review_actions = json.loads(review_actions)
        except Exception:
            review_actions = None

    decision_raw = r.get("decision", "block")
    decision = "flag" if decision_raw == "review" else decision_raw
    ecr = float(r.get("ecr") or 0)
    vs = float(r.get("vs") or 0)
    tc = r.get("total_claims") or 0

    reviewed_at = r.get("reviewed_at")
    created_at = r.get("created_at")

    return {
        "id": r.get("request_id", ""),
        "inputText": (r.get("content") or "")[:500],
        "domain": r.get("domain") or "financial",
        "decision": decision,
        "decisionReasons": decision_reasons,
        "totalClaims": tc,
        "corroboratedCount": r.get("corroborated_count") or 0,
        "contradictedCount": r.get("contradicted_count") or 0,
        "unsupportedCount": r.get("unsupported_count") or 0,
        "outOfScopeCount": r.get("out_of_scope_count") or 0,
        "coverageRatio": ecr,
        "corroborationRate": vs,
        "fullResponse": full_response,
        "config": config if config else {
            "unsupported_policy": "flag",
            "out_of_scope_policy": "accept",
            "contradiction_policy": "flag",
            "flag_extrapolations": False,
            "require_acknowledgement_note": False,
            "domain": "financial",
            "policy_profile": "moderate",
        },
        "reviewStatus": r.get("review_status") or "not_required",
        "reviewedBy": r.get("reviewed_by"),
        "reviewedAt": reviewed_at.isoformat() if hasattr(reviewed_at, "isoformat") else reviewed_at,
        "reviewNote": r.get("review_note"),
        "reviewActions": review_actions,
        "correctedText": r.get("corrected_text"),
        "parentVerificationId": r.get("parent_request_id"),
        "latencyMs": int((r.get("elapsed_seconds") or 0) * 1000),
        "traceId": r.get("trace_id") or r.get("request_id", ""),
        "agentId": r.get("agent_id"),
        "agent": (agents or {}).get(r.get("agent_id")),
        "createdAt": created_at.isoformat() if hasattr(created_at, "isoformat") else (created_at or ""),
    }


@app.get("/api/review")
async def api_review(
    tab: str = Query("needs_review"),  # "needs_review" | "all"
    current_user: dict = Depends(get_current_user),
    mcp_pool: asyncpg.Pool = Depends(get_mcp_pool),
    dash_pool: asyncpg.Pool = Depends(get_dash_pool),
):
    prefixes = await _get_user_prefixes(current_user["id"], dash_pool)
    if not prefixes:
        return []
    try:
        async with mcp_pool.acquire() as conn:
            if tab == "all":
                rows = await conn.fetch(
                    """
                    SELECT request_id, content, decision, vs, ecr, sci,
                           total_claims, corroborated_count, contradicted_count,
                           unsupported_count, out_of_scope_count, elapsed_seconds,
                           created_at, review_status, reviewed_by, reviewed_at,
                           review_note, review_actions, corrected_text, agent_id,
                           parent_request_id, domain, decision_reasons, full_response,
                           config, trace_id
                    FROM requests
                    WHERE LEFT(api_key, 12) = ANY($1::text[])
                    ORDER BY created_at DESC
                    LIMIT 100
                    """,
                    prefixes,
                )
            else:
                rows = await conn.fetch(
                    """
                    SELECT request_id, content, decision, vs, ecr, sci,
                           total_claims, corroborated_count, contradicted_count,
                           unsupported_count, out_of_scope_count, elapsed_seconds,
                           created_at, review_status, reviewed_by, reviewed_at,
                           review_note, review_actions, corrected_text, agent_id,
                           parent_request_id, domain, decision_reasons, full_response,
                           config, trace_id
                    FROM requests
                    WHERE LEFT(api_key, 12) = ANY($1::text[])
                      AND review_status IN ('pending_review', 'in_review')
                    ORDER BY
                        CASE WHEN decision='block' THEN 0 ELSE 1 END,
                        created_at ASC
                    """,
                    prefixes,
                )
    except Exception as exc:
        raise HTTPException(status_code=500, detail={"error": str(exc)})
    agents = await _get_user_agents(current_user["id"], dash_pool)
    return [_request_to_verification(dict(r), agents=agents) for r in rows]


# ---------------------------------------------------------------------------
# GET /api/verify/:id — fetch a single verification
# ---------------------------------------------------------------------------

@app.get("/api/verify/{verification_id}")
async def api_get_verification(
    verification_id: str,
    current_user: dict = Depends(get_current_user),
    mcp_pool: asyncpg.Pool = Depends(get_mcp_pool),
    dash_pool: asyncpg.Pool = Depends(get_dash_pool),
):
    prefixes = await _get_user_prefixes(current_user["id"], dash_pool)
    try:
        async with mcp_pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT request_id, content, decision, vs, ecr, sci,
                       total_claims, corroborated_count, contradicted_count,
                       unsupported_count, out_of_scope_count, elapsed_seconds,
                       created_at, review_status, reviewed_by, reviewed_at,
                       review_note, review_actions, corrected_text, agent_id,
                       parent_request_id, domain, decision_reasons, full_response,
                       config, trace_id
                FROM requests
                WHERE request_id=$1 AND LEFT(api_key, 12) = ANY($2::text[])
                """,
                verification_id, prefixes,
            )
    except Exception as exc:
        raise HTTPException(status_code=500, detail={"error": str(exc)})
    if not row:
        raise HTTPException(status_code=404, detail={"error": "Verification not found"})
    agents = await _get_user_agents(current_user["id"], dash_pool)
    return _request_to_verification(dict(row), agents=agents)


# ---------------------------------------------------------------------------
# PATCH /api/verify/:id/claim — reviewer claims a verification
# ---------------------------------------------------------------------------

@app.patch("/api/verify/{verification_id}/claim")
async def api_claim_verification(
    verification_id: str,
    current_user: dict = Depends(get_current_user),
    mcp_pool: asyncpg.Pool = Depends(get_mcp_pool),
    dash_pool: asyncpg.Pool = Depends(get_dash_pool),
):
    prefixes = await _get_user_prefixes(current_user["id"], dash_pool)
    try:
        async with mcp_pool.acquire() as conn:
            existing = await conn.fetchrow(
                "SELECT review_status, reviewed_by FROM requests WHERE request_id=$1 AND LEFT(api_key, 12) = ANY($2::text[])",
                verification_id, prefixes,
            )
            if not existing:
                raise HTTPException(status_code=404, detail={"error": "Verification not found"})
            if existing["review_status"] == "in_review" and existing["reviewed_by"] != str(current_user["id"]):
                raise HTTPException(status_code=409, detail={"error": "Already claimed by another reviewer"})
            row = await conn.fetchrow(
                """
                UPDATE requests
                SET review_status='in_review', reviewed_by=$1
                WHERE request_id=$2
                RETURNING request_id, content, decision, vs, ecr, sci,
                          total_claims, corroborated_count, contradicted_count,
                          unsupported_count, out_of_scope_count, elapsed_seconds,
                          created_at, review_status, reviewed_by, reviewed_at,
                          review_note, review_actions, corrected_text, agent_id,
                          parent_request_id, domain, decision_reasons, full_response,
                          config, trace_id
                """,
                str(current_user["id"]), verification_id,
            )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail={"error": str(exc)})
    agents = await _get_user_agents(current_user["id"], dash_pool)
    return _request_to_verification(dict(row), agents=agents)


# ---------------------------------------------------------------------------
# PATCH /api/verify/:id/review — submit review outcome
# ---------------------------------------------------------------------------

class ReviewSubmitBody(BaseModel):
    outcome: str  # "approved" | "rejected"
    reviewActions: Optional[list] = None
    correctedText: Optional[str] = None
    reviewNote: Optional[str] = None


@app.patch("/api/verify/{verification_id}/review")
async def api_submit_review(
    verification_id: str,
    body: ReviewSubmitBody,
    current_user: dict = Depends(get_current_user),
    mcp_pool: asyncpg.Pool = Depends(get_mcp_pool),
    dash_pool: asyncpg.Pool = Depends(get_dash_pool),
):
    if body.outcome not in ("approved", "rejected"):
        raise HTTPException(status_code=400, detail={"error": 'outcome must be "approved" or "rejected"'})
    prefixes = await _get_user_prefixes(current_user["id"], dash_pool)
    try:
        async with mcp_pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                UPDATE requests
                SET review_status=$1,
                    reviewed_by=$2,
                    reviewed_at=NOW(),
                    review_note=$3,
                    review_actions=$4::jsonb,
                    corrected_text=$5
                WHERE request_id=$6 AND LEFT(api_key, 12) = ANY($7::text[])
                RETURNING request_id, content, decision, vs, ecr, sci,
                          total_claims, corroborated_count, contradicted_count,
                          unsupported_count, out_of_scope_count, elapsed_seconds,
                          created_at, review_status, reviewed_by, reviewed_at,
                          review_note, review_actions, corrected_text, agent_id,
                          parent_request_id, domain, decision_reasons, full_response,
                          config, trace_id
                """,
                body.outcome,
                str(current_user["id"]),
                body.reviewNote,
                json.dumps(body.reviewActions) if body.reviewActions else None,
                body.correctedText,
                verification_id,
                prefixes,
            )
    except Exception as exc:
        raise HTTPException(status_code=500, detail={"error": str(exc)})
    if not row:
        raise HTTPException(status_code=404, detail={"error": "Verification not found"})
    agents = await _get_user_agents(current_user["id"], dash_pool)
    return _request_to_verification(dict(row), agents=agents)


# ---------------------------------------------------------------------------
# Verify — proxy to the verification API
# ---------------------------------------------------------------------------

class VerifyBody(BaseModel):
    text: str
    config: Optional[dict] = None
    agentId: Optional[str] = None
    parentVerificationId: Optional[str] = None


@app.post("/api/verify")
async def api_verify(
    body: VerifyBody,
    current_user: dict = Depends(get_current_user),
    dash_pool: asyncpg.Pool = Depends(get_dash_pool),
):
    # Get a key prefix to tag the logged request — try API keys first, fall back to agent key
    api_key = None
    try:
        async with dash_pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT key_prefix FROM api_keys WHERE user_id=$1 AND is_active=TRUE ORDER BY created_at LIMIT 1",
                current_user["id"],
            )
            if row:
                api_key = row["key_prefix"]
            else:
                agent_row = await conn.fetchrow(
                    "SELECT api_key FROM agents WHERE user_id=$1 AND api_key IS NOT NULL ORDER BY created_at LIMIT 1",
                    current_user["id"],
                )
                if agent_row:
                    api_key = agent_row["api_key"]
    except Exception:
        pass

    # Only send the content — the frontend's PolicyConfig format is incompatible
    # with the verification API's PolicyConfig (different keys). The verification
    # API uses its own defaults which are sufficient.
    payload: dict = {"content": body.text}

    # Pass domain hint if provided in config
    if body.config and isinstance(body.config, dict):
        domain = body.config.get("domain")
        if domain:
            payload["domain"] = domain

    # Fetch active custom sources for this user and include in verification
    try:
        async with dash_pool.acquire() as conn:
            custom_rows = await conn.fetch(
                "SELECT name, domain, authority_level, extracted_text FROM custom_sources WHERE user_id=$1 AND status='active'",
                current_user["id"],
            )
            if custom_rows:
                payload["custom_sources"] = [dict(r) for r in custom_rows]
    except Exception:
        pass

    try:
        async with httpx.AsyncClient(timeout=300.0) as client:
            headers = {}
            if api_key:
                headers["X-API-Key"] = api_key
            resp = await client.post(
                f"{VERIFY_API_URL}/v1/verify",
                json=payload,
                headers=headers,
            )
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=exc.response.status_code, detail={"error": str(exc)})
    except httpx.RequestError as exc:
        import traceback
        print(f"[api_verify] RequestError: {type(exc).__name__}: {exc}", flush=True)
        traceback.print_exc()
        raise HTTPException(status_code=503, detail={"error": f"Verification service unavailable: {exc}"})

    # Transform the response to match the frontend's VerificationResponse type
    meta = data.get("meta", {})
    scores = data.get("scores", {})
    claims_raw = data.get("claims", [])
    decision_raw = data.get("decision", "block")
    decision = "flag" if decision_raw == "review" else decision_raw

    # Count verdict breakdowns from claims array
    corroborated = sum(1 for c in claims_raw if c.get("status") == "corroborated")
    contradicted  = sum(1 for c in claims_raw if c.get("status") == "contradicted")
    unsupported   = sum(1 for c in claims_raw if c.get("status") == "unsupported")
    out_of_scope  = sum(1 for c in claims_raw if c.get("status") == "out_of_scope")
    total_claims  = meta.get("total_claims", len(claims_raw))

    def _confidence_to_strength(confidence: float) -> Optional[str]:
        if confidence >= 0.8:
            return "strong"
        if confidence >= 0.5:
            return "moderate"
        if confidence > 0:
            return "weak"
        return None

    def _citation_to_source(citation: dict, idx: int) -> dict:
        source_name = citation.get("source", "Unknown")
        connector_id = source_name.lower() if source_name.lower() in ("fred", "edgar") else None
        return {
            "id": f"src-{idx}",
            "name": source_name,
            "source_type": "live_api",
            "connector_id": connector_id,
            "url": None,
            "authority_level": "primary",
            "freshness": "current",
            "detail": {
                "ai_asserted": "",
                "source_states": f"{citation.get('label', source_name)}: {citation.get('value', '')} ({citation.get('date', '')})",
                "discrepancy_type": None,
                "summary": citation.get("label", ""),
            },
        }

    def _claim_decision(status: str) -> str:
        if status == "contradicted":
            return decision  # inherits worst case
        if status == "unsupported":
            return "flag"
        if status == "out_of_scope":
            return "out_of_scope"
        return "pass"

    # Map claims → frontend ClaimResult format
    frontend_claims = []
    for claim in claims_raw:
        status = claim.get("status", "out_of_scope")
        confidence = float(claim.get("confidence") or 0)
        citations = claim.get("citations") or []
        frontend_claims.append({
            "text": claim.get("text", ""),
            "position": {"start": 0, "end": len(claim.get("text", ""))},
            "status": status,
            "confirmation_strength": _confidence_to_strength(confidence) if status == "corroborated" else None,
            "fix": _build_fix(status, claim.get("reasoning", "")),
            "sources": [_citation_to_source(c, i) for i, c in enumerate(citations)],
        })

    # Wrap all claims in a single sentence (the verification API doesn't segment)
    sentences = [{
        "text": body.text,
        "decision": decision,
        "claims": frontend_claims,
    }] if frontend_claims else []

    # Build decision_reasons from contradicted/unsupported claims
    decision_reasons = [
        {"claim": c.get("text", ""), "reason": c.get("reasoning", "")}
        for c in claims_raw
        if c.get("status") in ("contradicted", "unsupported") and c.get("reasoning")
    ]

    elapsed_ms = int((meta.get("elapsed_seconds", 0) or 0) * 1000)
    sources_consulted = sum(len(c.get("citations") or []) for c in claims_raw)

    return {
        "request_id": data.get("request_id", ""),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "input_text": body.text,
        "annotated_text": body.text,
        "sentences": sentences,
        "coverage": {
            "total_sentences": len(sentences),
            "total_claims": total_claims,
            "corroborated": corroborated,
            "contradicted": contradicted,
            "unsupported": unsupported,
            "out_of_scope": out_of_scope,
            "coverage_ratio": float(scores.get("ecr", 0) or 0),
        },
        "decision": decision,
        "decision_reasons": decision_reasons,
        "config": body.config or {},
        "audit": {
            "sources_consulted": sources_consulted,
            "processing_time_ms": elapsed_ms,
            "trace_id": data.get("request_id", ""),
        },
    }


# ---------------------------------------------------------------------------
# Agents
# ---------------------------------------------------------------------------

_DEFAULT_POLICY = {
    "unsupported_policy": "flag",
    "out_of_scope_policy": "accept",
    "contradiction_policy": "flag",
    "flag_extrapolations": False,
    "require_acknowledgement_note": False,
    "domain": "news_editorial",
    "policy_profile": "moderate",
}


def _agent_row_to_dict(row: dict, include_key: bool = False) -> dict:
    policy = row.get("policy") or {}
    if isinstance(policy, str):
        policy = json.loads(policy)
    notification_override = row.get("notification_override")
    if isinstance(notification_override, str) and notification_override:
        notification_override = json.loads(notification_override)
    result = {
        "id": str(row["id"]),
        "name": row["name"],
        "type": row["type"],
        "owner": row["owner"],
        "policy": policy,
        "notificationOverride": notification_override,
        "createdAt": row["created_at"].isoformat() if hasattr(row["created_at"], "isoformat") else row["created_at"],
        "apiKey": row.get("api_key") if include_key else (
            ("bx_agent_" + row["api_key"][:4] + "…") if row.get("api_key") else None
        ),
    }
    return result


class AgentCreateBody(BaseModel):
    name: str
    type: Optional[str] = "AI Agent"
    owner: Optional[str] = None
    domain: Optional[str] = "news_editorial"
    policy_profile: Optional[str] = "moderate"
    policy: Optional[dict] = None


class AgentUpdateBody(BaseModel):
    name: Optional[str] = None
    type: Optional[str] = None
    owner: Optional[str] = None
    policy: Optional[dict] = None
    notificationOverride: Optional[dict] = None


@app.get("/api/agents")
async def api_agents_list(
    current_user: dict = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_dash_pool),
):
    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM agents WHERE user_id=$1 ORDER BY created_at ASC",
                current_user["id"],
            )
        return [_agent_row_to_dict(dict(r)) for r in rows]
    except Exception as exc:
        raise HTTPException(status_code=500, detail={"error": str(exc)})


@app.post("/api/agents", status_code=201)
async def api_agents_create(
    body: AgentCreateBody,
    current_user: dict = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_dash_pool),
):
    policy = {**_DEFAULT_POLICY, "domain": body.domain or "news_editorial", "policy_profile": body.policy_profile or "moderate"}
    if body.policy:
        policy.update(body.policy)
    agent_id = str(uuid.uuid4())
    agent_api_key = "bx_agent_" + secrets.token_hex(20)
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO agents (id, user_id, name, type, owner, policy, api_key)
                VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7)
                RETURNING *
                """,
                agent_id,
                current_user["id"],
                body.name,
                body.type or "AI Agent",
                body.owner or current_user.get("email", ""),
                json.dumps(policy),
                agent_api_key,
            )
        # Return the full key only on creation — never shown again
        return _agent_row_to_dict(dict(row), include_key=True)
    except Exception as exc:
        raise HTTPException(status_code=500, detail={"error": str(exc)})


@app.put("/api/agents/{agent_id}")
async def api_agents_update(
    agent_id: str,
    body: AgentUpdateBody,
    current_user: dict = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_dash_pool),
):
    try:
        async with pool.acquire() as conn:
            existing = await conn.fetchrow(
                "SELECT * FROM agents WHERE id=$1 AND user_id=$2", agent_id, current_user["id"]
            )
            if not existing:
                raise HTTPException(status_code=404, detail={"error": "Agent not found"})

            current_policy = existing["policy"] or {}
            if isinstance(current_policy, str):
                current_policy = json.loads(current_policy)
            if body.policy:
                current_policy.update(body.policy)

            row = await conn.fetchrow(
                """
                UPDATE agents
                SET name=COALESCE($1, name),
                    type=COALESCE($2, type),
                    owner=COALESCE($3, owner),
                    policy=$4::jsonb,
                    notification_override=COALESCE($5::jsonb, notification_override)
                WHERE id=$6 AND user_id=$7
                RETURNING *
                """,
                body.name,
                body.type,
                body.owner,
                json.dumps(current_policy),
                json.dumps(body.notificationOverride) if body.notificationOverride else None,
                agent_id,
                current_user["id"],
            )
        return _agent_row_to_dict(dict(row))
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail={"error": str(exc)})


@app.delete("/api/agents/{agent_id}", status_code=204)
async def api_agents_delete(
    agent_id: str,
    current_user: dict = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_dash_pool),
):
    try:
        async with pool.acquire() as conn:
            result = await conn.execute(
                "DELETE FROM agents WHERE id=$1 AND user_id=$2", agent_id, current_user["id"]
            )
        if result == "DELETE 0":
            raise HTTPException(status_code=404, detail={"error": "Agent not found"})
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail={"error": str(exc)})


@app.post("/api/agents/{agent_id}/regenerate-key")
async def api_agents_regenerate_key(
    agent_id: str,
    current_user: dict = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_dash_pool),
):
    new_key = "bx_agent_" + secrets.token_hex(20)
    try:
        async with pool.acquire() as conn:
            result = await conn.execute(
                "UPDATE agents SET api_key=$1 WHERE id=$2 AND user_id=$3",
                new_key, agent_id, current_user["id"],
            )
        if result == "UPDATE 0":
            raise HTTPException(status_code=404, detail={"error": "Agent not found"})
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail={"error": str(exc)})
    return {"apiKey": new_key}


# ---------------------------------------------------------------------------
# Sources — full catalog + DB-backed connected sources
# ---------------------------------------------------------------------------

_SOURCE_CATALOG = [
    # Financial
    {"id": "edgar",     "name": "SEC EDGAR",             "domain": "financial", "authorityLevel": "primary",       "isFree": True,  "requiresKey": False, "description": "US company filings — 10-K, 10-Q, quarterly earnings, proxy statements.",                                                    "notes": "No key needed."},
    {"id": "fred",      "name": "FRED (Federal Reserve)", "domain": "financial", "authorityLevel": "primary",       "isFree": True,  "requiresKey": False, "description": "Interest rates, GDP, inflation, employment, and 800,000+ economic time series from the St. Louis Fed.",                    "notes": "Macro indicators. Optional free key."},
    {"id": "worldbank", "name": "World Bank Open Data",   "domain": "financial", "authorityLevel": "institutional", "isFree": True,  "requiresKey": False, "description": "Global GDP, trade statistics, development indicators, and country economic profiles.",                                      "notes": "No key needed."},
    # Pharma
    {"id": "pubmed",        "name": "PubMed / MEDLINE",   "domain": "pharma", "authorityLevel": "primary", "isFree": True, "requiresKey": False, "description": "Biomedical literature database from NCBI — peer-reviewed research, clinical studies, and reviews.", "notes": "Optional free NCBI key."},
    {"id": "clinicaltrials","name": "ClinicalTrials.gov", "domain": "pharma", "authorityLevel": "primary", "isFree": True, "requiresKey": False, "description": "Registry of clinical studies — trial phases, status, enrollment, and results.",                       "notes": "No key needed."},
    {"id": "openfda",       "name": "OpenFDA",            "domain": "pharma", "authorityLevel": "primary", "isFree": True, "requiresKey": False, "description": "FDA drug approvals, adverse event reports, drug labels, recalls, and enforcement actions.",           "notes": "No key needed."},
    # News & Editorial
    {"id": "guardian",       "name": "The Guardian",      "domain": "news_editorial", "authorityLevel": "institutional", "isFree": True, "requiresKey": False, "description": "British daily newspaper — full article archive with search.",                               "notes": "Free registration."},
    {"id": "nytimes",        "name": "New York Times",    "domain": "news_editorial", "authorityLevel": "institutional", "isFree": True, "requiresKey": True,  "description": "NYT article search API — headlines, abstracts, and metadata.",                              "notes": "Free registration (limited calls)."},
    {"id": "wikidata",       "name": "Wikidata",          "domain": "news_editorial", "authorityLevel": "secondary",     "isFree": True, "requiresKey": False, "description": "Structured knowledge base — entities, dates, relationships, and facts.",                    "notes": "No key needed."},
    {"id": "crossref",       "name": "CrossRef",          "domain": "news_editorial", "authorityLevel": "secondary",     "isFree": True, "requiresKey": False, "description": "Academic citation metadata and DOI resolution.",                                            "notes": "No key needed."},
    {"id": "semanticscholar","name": "Semantic Scholar",  "domain": "news_editorial", "authorityLevel": "secondary",     "isFree": True, "requiresKey": False, "description": "AI-powered academic paper search with citation graphs.",                                    "notes": "No key needed."},
    # Financial (new)
    {"id": "bls",            "name": "Bureau of Labor Statistics", "domain": "financial", "authorityLevel": "primary",       "isFree": True,  "requiresKey": False, "description": "US labor market data — unemployment, payrolls, wages, job openings, and CPI components.", "notes": "Optional free key (BLS_API_KEY) for higher rate limits."},
    {"id": "census",         "name": "US Census Bureau",           "domain": "financial", "authorityLevel": "primary",       "isFree": True,  "requiresKey": False, "description": "US population, income, poverty, housing, and demographic statistics by state and county.", "notes": "Optional free key (CENSUS_API_KEY)."},
    {"id": "oecd",           "name": "OECD Statistics",            "domain": "financial", "authorityLevel": "institutional", "isFree": True,  "requiresKey": False, "description": "Cross-country economic and social indicators — GDP, health, education, inequality, and more.", "notes": "No key needed."},
    # Pharma (new)
    {"id": "europepmc",      "name": "Europe PubMed Central",      "domain": "pharma",    "authorityLevel": "primary",       "isFree": True,  "requiresKey": False, "description": "Biomedical literature beyond PubMed — preprints, patents, clinical guidelines, and non-US sources.", "notes": "No key needed."},
    # Legal (new)
    {"id": "courtlistener",  "name": "CourtListener",              "domain": "legal",     "authorityLevel": "primary",       "isFree": True,  "requiresKey": False, "description": "US court opinions, dockets, and case law from federal and state courts.",               "notes": "No key needed."},
    {"id": "federalregister","name": "Federal Register",           "domain": "legal",     "authorityLevel": "primary",       "isFree": True,  "requiresKey": False, "description": "US federal regulations, proposed rules, executive orders, and agency notices.",            "notes": "No key needed."},
    # Academic (new)
    {"id": "arxiv",          "name": "arXiv",                      "domain": "academic",    "authorityLevel": "secondary", "isFree": True,  "requiresKey": False, "description": "Open-access preprints in CS, physics, math, biology, and economics.",                    "notes": "No key needed."},
    {"id": "openalex",       "name": "OpenAlex",                   "domain": "academic",    "authorityLevel": "secondary", "isFree": True,  "requiresKey": False, "description": "250M+ scholarly works with citation graphs across all disciplines.",                       "notes": "No key needed."},
    # Geography (new)
    {"id": "geonames",       "name": "GeoNames",                   "domain": "geography",   "authorityLevel": "tertiary",  "isFree": True,  "requiresKey": False, "description": "Geographic database — city populations, coordinates, elevation, and administrative divisions.", "notes": "Free registration required (GEONAMES_USERNAME)."},
    {"id": "openmeteo",      "name": "Open-Meteo",                 "domain": "geography",   "authorityLevel": "secondary", "isFree": True,  "requiresKey": False, "description": "Historical and forecast weather data for any location — temperature, precipitation, wind.", "notes": "No key needed."},
    {"id": "wikipedia",      "name": "Wikipedia",                  "domain": "geography",   "authorityLevel": "tertiary",  "isFree": True,  "requiresKey": False, "description": "Encyclopedic summaries for general knowledge claims — people, places, events, and concepts.", "notes": "No key needed."},
]

_CATALOG_BY_ID = {c["id"]: c for c in _SOURCE_CATALOG}
_FREE_CONNECTOR_IDS = {c["id"] for c in _SOURCE_CATALOG if c["isFree"]}

COMING_SOON_CATALOG = [
    {
        "id": "academic_scholarly_journals",
        "name": "Academic & Scholarly Journals",
        "domain": "pharma",
        "authorityLevel": "primary",
        "category": "Scientific & Medical",
        "description": "Peer-reviewed research from the world's most authoritative scientific and medical journals. The source layer for defensible claims in pharma, biotech, clinical, and technical AI workflows.",
        "examples": ["Nature", "Science", "Cell", "The Lancet", "NEJM", "JAMA", "PNAS", "IEEE Spectrum"],
        "partner": "Copyright Clearance Center",
    },
    {
        "id": "business_trade_press",
        "name": "Business & Trade Press",
        "domain": "financial",
        "authorityLevel": "primary",
        "category": "Financial & Industry",
        "description": "Authoritative business, technology, and industry editorial from the publications enterprise decision-makers cite by name. Covers strategy, markets, technology trends, and sector analysis.",
        "examples": ["Harvard Business Review", "MIT Technology Review", "The Economist", "Bloomberg Businessweek", "Fortune", "Forbes", "Wired", "Fast Company"],
        "partner": "Copyright Clearance Center",
    },
    {
        "id": "professional_reference",
        "name": "Professional Reference & Textbooks",
        "domain": "legal",
        "authorityLevel": "primary",
        "category": "Legal & Regulatory",
        "description": "The canonical reference works that legal, medical, and financial professionals treat as ground truth. Critical for AI workflows in regulated industries where outputs need to trace back to an accepted authoritative source.",
        "examples": ["UpToDate", "Merck Manual", "Black's Law Dictionary", "Restatements of Law", "Oxford Reference", "Moody's Credit Reference"],
        "partner": "Association of American Publishers",
    },
]

_SOURCE_TEST_URLS: dict[str, str] = {
    "edgar":           "https://efts.sec.gov/LATEST/search-index?q=test&dateRange=custom&startdt=2024-01-01&forms=10-K",
    "fred":            "https://api.stlouisfed.org/fred/series?series_id=GDP&api_key=abcdefghijklmnopqrstuvwxyz012345&file_type=json",
    "worldbank":       "https://api.worldbank.org/v2/country/US?format=json&per_page=1",
    "pubmed":          "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pubmed&term=test&retmax=1&retmode=json",
    "clinicaltrials":  "https://clinicaltrials.gov/api/v2/studies?pageSize=1",
    "openfda":         "https://api.fda.gov/drug/nda.json?limit=1",
    "guardian":        f"https://content.guardianapis.com/search?api-key={os.environ.get('GUARDIAN_API_KEY', 'test')}&page-size=1",
    "nytimes":         "https://api.nytimes.com/svc/search/v2/articlesearch.json?q=test&api-key=test",
    "wikidata":        "https://www.wikidata.org/w/api.php?action=wbsearchentities&search=test&language=en&format=json&limit=1",
    "crossref":        "https://api.crossref.org/works?query=test&rows=1",
    "semanticscholar": "https://api.semanticscholar.org/graph/v1/paper/search?query=test&limit=1",
    "bls":             "https://api.bls.gov/publicAPI/v1/timeseries/data/LNS14000000",
    "census":          "https://api.census.gov/data/2022/acs/acs5?get=B01001_001E&for=us:1",
    "oecd":            "https://sdmx.oecd.org/public/rest/dataflow/OECD.SDD.NAD/DSD_NAMAIN1@DF_TABLE1_EXPENDITURE_HCPC/1.0?format=json",
    "europepmc":       "https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=test&format=json&pageSize=1",
    "courtlistener":   "https://www.courtlistener.com/api/rest/v4/search/?q=test&type=o&page_size=1&format=json",
    "federalregister": "https://www.federalregister.gov/api/v1/documents.json?conditions[term]=test&per_page=1",
    "arxiv":           "http://export.arxiv.org/api/query?search_query=all:test&max_results=1",
    "openalex":        "https://api.openalex.org/works?search=test&per-page=1",
    "geonames":        "http://api.geonames.org/searchJSON?q=London&maxRows=1&username=demo",
    "openmeteo":       "https://api.open-meteo.com/v1/forecast?latitude=40.71&longitude=-74.01&daily=temperature_2m_max&timezone=auto&forecast_days=1",
    "wikipedia":       "https://en.wikipedia.org/api/rest_v1/page/summary/Test",
}


def _source_row_to_dict(row: dict) -> dict:
    last_tested = row.get("last_tested_at")
    created = row.get("created_at")
    api_key = row.get("api_key")
    return {
        "id": str(row["id"]),
        "connectorId": row["connector_id"],
        "name": row["name"],
        "domain": row["domain"],
        "authorityLevel": row["authority_level"],
        "apiKey": "••••••••" if api_key else None,
        "status": row["status"],
        "lastTestedAt": last_tested.isoformat() if hasattr(last_tested, "isoformat") else last_tested,
        "createdAt": created.isoformat() if hasattr(created, "isoformat") else created,
    }


class SourceConnectBody(BaseModel):
    connectorId: str
    name: Optional[str] = None
    domain: Optional[str] = None
    apiKey: Optional[str] = None


@app.get("/api/sources/catalog")
async def api_sources_catalog(
    current_user: dict = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_dash_pool),
):
    try:
        async with pool.acquire() as conn:
            count_rows = await conn.fetch(
                "SELECT connector_id, COUNT(*) AS cnt FROM source_interests GROUP BY connector_id"
            )
            count_map = {r["connector_id"]: int(r["cnt"]) for r in count_rows}
            vote_rows = await conn.fetch(
                "SELECT connector_id, notify_on_launch FROM source_interests WHERE user_id=$1",
                current_user["id"],
            )
            vote_map = {r["connector_id"]: dict(r) for r in vote_rows}
    except Exception:
        count_map = {}
        vote_map = {}

    coming_soon = [
        {
            **c,
            "interestCount": count_map.get(c["id"], 0),
            "orgHasVoted": c["id"] in vote_map,
            "orgNotifyOnLaunch": vote_map.get(c["id"], {}).get("notify_on_launch", False),
        }
        for c in COMING_SOON_CATALOG
    ]
    return {"sources": _SOURCE_CATALOG, "comingSoon": coming_soon}


@app.get("/api/sources")
async def api_sources_list(
    current_user: dict = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_dash_pool),
):
    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM connected_sources WHERE user_id=$1 ORDER BY created_at ASC",
                current_user["id"],
            )
        return [_source_row_to_dict(dict(r)) for r in rows]
    except Exception as exc:
        raise HTTPException(status_code=500, detail={"error": str(exc)})


@app.post("/api/sources", status_code=201)
async def api_sources_connect(
    body: SourceConnectBody,
    current_user: dict = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_dash_pool),
):
    catalog_entry = _CATALOG_BY_ID.get(body.connectorId)
    if not catalog_entry:
        raise HTTPException(status_code=400, detail={"error": "Unknown connector"})
    if not catalog_entry["isFree"] and not body.apiKey:
        raise HTTPException(status_code=400, detail={"error": "apiKey is required for paid connectors"})
    source_id = str(uuid.uuid4())
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO connected_sources
                    (id, user_id, connector_id, name, domain, authority_level, api_key, status)
                VALUES ($1, $2, $3, $4, $5, $6, $7, 'active')
                ON CONFLICT (user_id, connector_id) DO UPDATE
                    SET api_key=EXCLUDED.api_key, status='active'
                RETURNING *
                """,
                source_id,
                current_user["id"],
                body.connectorId,
                body.name or catalog_entry["name"],
                body.domain or catalog_entry["domain"],
                catalog_entry["authorityLevel"],
                body.apiKey,
            )
        return _source_row_to_dict(dict(row))
    except Exception as exc:
        raise HTTPException(status_code=500, detail={"error": str(exc)})


@app.delete("/api/sources/{source_id}", status_code=204)
async def api_sources_disconnect(
    source_id: str,
    current_user: dict = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_dash_pool),
):
    try:
        async with pool.acquire() as conn:
            existing = await conn.fetchrow(
                "SELECT connector_id FROM connected_sources WHERE id=$1 AND user_id=$2",
                source_id, current_user["id"],
            )
            if not existing:
                raise HTTPException(status_code=404, detail={"error": "Source not found"})
            if existing["connector_id"] in _FREE_CONNECTOR_IDS:
                raise HTTPException(status_code=400, detail={"error": "Cannot disconnect free connectors — they are always active"})
            await conn.execute(
                "DELETE FROM connected_sources WHERE id=$1 AND user_id=$2",
                source_id, current_user["id"],
            )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail={"error": str(exc)})


@app.post("/api/sources/{source_id}/test")
async def api_sources_test(
    source_id: str,
    current_user: dict = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_dash_pool),
):
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM connected_sources WHERE id=$1 AND user_id=$2",
                source_id, current_user["id"],
            )
        if not row:
            raise HTTPException(status_code=404, detail={"error": "Source not found"})

        connector_id = row["connector_id"]
        test_url = _SOURCE_TEST_URLS.get(connector_id)

        import time
        start = time.monotonic()
        ok = False
        message = ""
        if not test_url:
            ok = True
            message = "Connector registered — connectivity check not available for this source type."
        else:
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    await client.get(test_url)
                ok = True
            except Exception as exc:
                ok = False
                message = str(exc)
        latency_ms = int((time.monotonic() - start) * 1000)

        new_status = "active" if ok else "error"
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE connected_sources SET last_tested_at=NOW(), status=$1 WHERE id=$2",
                new_status, source_id,
            )

        return {"ok": ok, "latencyMs": latency_ms, "message": "Connection successful" if ok else message}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail={"error": str(exc)})


# ---------------------------------------------------------------------------
# Coming Soon — Interest / Demand Signals
# ---------------------------------------------------------------------------

_COMING_SOON_BY_ID = {c["id"]: c for c in COMING_SOON_CATALOG}


@app.post("/api/sources/interest/{connector_id}")
async def api_sources_toggle_interest(
    connector_id: str,
    body: dict = Body(default={}),
    current_user: dict = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_dash_pool),
):
    if connector_id not in _COMING_SOON_BY_ID:
        raise HTTPException(status_code=404, detail={"error": "Not found"})
    notify_on_launch = bool(body.get("notifyOnLaunch", False)) if body else False
    try:
        async with pool.acquire() as conn:
            existing = await conn.fetchrow(
                "SELECT id FROM source_interests WHERE connector_id=$1 AND user_id=$2",
                connector_id, current_user["id"],
            )
            if existing:
                await conn.execute(
                    "DELETE FROM source_interests WHERE connector_id=$1 AND user_id=$2",
                    connector_id, current_user["id"],
                )
                count = await conn.fetchval(
                    "SELECT COUNT(*) FROM source_interests WHERE connector_id=$1", connector_id
                )
                return {"voted": False, "notifyOnLaunch": False, "interestCount": int(count)}
            else:
                await conn.execute(
                    "INSERT INTO source_interests (id, connector_id, user_id, notify_on_launch) VALUES ($1,$2,$3,$4)",
                    str(uuid.uuid4()), connector_id, current_user["id"], notify_on_launch,
                )
                count = await conn.fetchval(
                    "SELECT COUNT(*) FROM source_interests WHERE connector_id=$1", connector_id
                )
                return {"voted": True, "notifyOnLaunch": notify_on_launch, "interestCount": int(count)}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail={"error": str(exc)})


@app.patch("/api/sources/interest/{connector_id}/notify")
async def api_sources_update_notify(
    connector_id: str,
    body: dict = Body(...),
    current_user: dict = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_dash_pool),
):
    if connector_id not in _COMING_SOON_BY_ID:
        raise HTTPException(status_code=404, detail={"error": "Not found"})
    notify_on_launch = bool(body.get("notifyOnLaunch", False))
    try:
        async with pool.acquire() as conn:
            updated = await conn.fetchrow(
                "UPDATE source_interests SET notify_on_launch=$1 WHERE connector_id=$2 AND user_id=$3 RETURNING notify_on_launch",
                notify_on_launch, connector_id, current_user["id"],
            )
        if not updated:
            raise HTTPException(status_code=404, detail={"error": "Vote first before updating notify preference"})
        return {"notifyOnLaunch": updated["notify_on_launch"]}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail={"error": str(exc)})


# ---------------------------------------------------------------------------
# Custom Sources
# ---------------------------------------------------------------------------

def _mask_headers(headers: dict) -> dict:
    return {k: "••••••••" + v[-4:] if len(v) > 4 else "••••••••" for k, v in headers.items()}


def _custom_source_to_dict(row: dict) -> dict:
    config = row.get("connection_config") or {}
    if isinstance(config, str):
        import json as _json
        config = _json.loads(config)
    source_type = row.get("source_type", "")
    if source_type == "api" and isinstance(config.get("headers"), dict):
        config = {**config, "headers": _mask_headers(config["headers"])}
    last_indexed = row.get("last_indexed_at")
    created = row.get("created_at")
    return {
        "id": str(row["id"]),
        "name": row["name"],
        "description": row.get("description"),
        "sourceType": source_type,
        "domain": row["domain"],
        "authorityLevel": row["authority_level"],
        "scope": row["scope"],
        "status": row["status"],
        "errorMessage": row.get("error_message"),
        "lastIndexedAt": last_indexed.isoformat() if hasattr(last_indexed, "isoformat") else last_indexed,
        "createdAt": created.isoformat() if hasattr(created, "isoformat") else created,
        "connectionConfig": config,
    }


async def _extract_text_from_bytes(data: bytes, mime_type: str) -> str:
    if mime_type == "text/plain":
        return data.decode("utf-8", errors="replace")
    if mime_type == "application/pdf":
        import fitz
        doc = fitz.open(stream=data, filetype="pdf")
        return "\n".join(page.get_text() for page in doc)
    if mime_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        import subprocess, tempfile, os
        with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tmp:
            tmp.write(data)
            tmp_path = tmp.name
        try:
            result = subprocess.run(
                ["pandoc", tmp_path, "-f", "docx", "-t", "markdown", "--wrap=none"],
                capture_output=True, text=True, timeout=30,
            )
            if result.returncode == 0:
                return result.stdout
            # fallback to python-docx if pandoc fails
            import docx as _docx, io as _io
            document = _docx.Document(_io.BytesIO(data))
            return "\n".join(p.text for p in document.paragraphs if p.text.strip())
        finally:
            os.unlink(tmp_path)
    return ""


async def _index_source(source_id: str, source_type: str, connection_config: dict, pool: asyncpg.Pool):
    try:
        if source_type == "url":
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(connection_config["url"], headers={"User-Agent": "BriaExchange/1.0"})
                resp.raise_for_status()
                import re
                text = re.sub(r"<[^>]+>", " ", resp.text)
                text = re.sub(r"\s+", " ", text).strip()
        elif source_type == "api":
            headers = connection_config.get("headers") or {}
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(connection_config["url"], headers={"User-Agent": "BriaExchange/1.0", **headers})
                resp.raise_for_status()
                try:
                    text = json.dumps(json.loads(resp.text), indent=2)
                except Exception:
                    text = resp.text
        else:
            return

        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE custom_sources SET extracted_text=$1, status='active', error_message=NULL, last_indexed_at=NOW(), updated_at=NOW() WHERE id=$2",
                text or None, source_id,
            )
    except Exception as exc:
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE custom_sources SET status='error', error_message=$1, last_indexed_at=NOW(), updated_at=NOW() WHERE id=$2",
                str(exc), source_id,
            )


@app.get("/api/sources/custom")
async def api_custom_sources_list(
    current_user: dict = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_dash_pool),
):
    try:
        async with pool.acquire() as conn:
            mine_rows = await conn.fetch(
                "SELECT * FROM custom_sources WHERE user_id=$1 ORDER BY created_at DESC",
                current_user["id"],
            )
            community_rows = await conn.fetch(
                "SELECT id, name, description, source_type, domain, authority_level, scope, status, last_indexed_at, created_at FROM custom_sources WHERE scope='public' AND user_id!=$1 ORDER BY created_at DESC",
                current_user["id"],
            )
        mine = [_custom_source_to_dict(dict(r)) for r in mine_rows]
        community = [
            {
                "id": str(r["id"]),
                "name": r["name"],
                "description": r.get("description"),
                "sourceType": r["source_type"],
                "domain": r["domain"],
                "authorityLevel": r["authority_level"],
                "scope": r["scope"],
                "status": r["status"],
                "lastIndexedAt": r["last_indexed_at"].isoformat() if hasattr(r.get("last_indexed_at"), "isoformat") else r.get("last_indexed_at"),
                "createdAt": r["created_at"].isoformat() if hasattr(r.get("created_at"), "isoformat") else r.get("created_at"),
                "connectionConfig": {},
            }
            for r in community_rows
        ]
        return {"mine": mine, "community": community}
    except Exception as exc:
        raise HTTPException(status_code=500, detail={"error": str(exc)})


class CustomSourceBody(BaseModel):
    name: str
    description: Optional[str] = None
    sourceType: str
    domain: str
    authorityLevel: str = "secondary"
    scope: str = "private"
    connectionConfig: dict


@app.post("/api/sources/custom", status_code=201)
async def api_custom_sources_create(
    body: CustomSourceBody,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_dash_pool),
):
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail={"error": "Admin required"})
    if body.sourceType not in ("url", "api"):
        raise HTTPException(status_code=400, detail={"error": "Use /upload for file sources"})
    source_id = str(uuid.uuid4())
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """INSERT INTO custom_sources (id, user_id, name, description, source_type, domain, authority_level, scope, connection_config, status)
                   VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,'pending') RETURNING *""",
                source_id, current_user["id"], body.name, body.description,
                body.sourceType, body.domain, body.authorityLevel, body.scope,
                json.dumps(body.connectionConfig),
            )
        background_tasks.add_task(_index_source, source_id, body.sourceType, body.connectionConfig, pool)
        return _custom_source_to_dict(dict(row))
    except Exception as exc:
        raise HTTPException(status_code=500, detail={"error": str(exc)})


@app.post("/api/sources/custom/upload", status_code=201)
async def api_custom_sources_upload(
    file: UploadFile = File(...),
    name: str = Form(...),
    description: Optional[str] = Form(None),
    domain: str = Form(...),
    authorityLevel: str = Form("secondary"),
    scope: str = Form("private"),
    current_user: dict = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_dash_pool),
):
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail={"error": "Admin required"})
    allowed_mimes = {
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "text/plain",
    }
    if file.content_type not in allowed_mimes:
        raise HTTPException(status_code=400, detail={"error": "Only PDF, DOCX, or TXT files are accepted"})

    data = await file.read()
    if len(data) > 20 * 1024 * 1024:
        raise HTTPException(status_code=400, detail={"error": "File exceeds 20 MB limit"})

    extracted_text = None
    status = "active"
    error_message = None
    try:
        extracted_text = await _extract_text_from_bytes(data, file.content_type)
    except Exception as exc:
        status = "error"
        error_message = str(exc)

    connection_config = {
        "filename": file.filename,
        "mimeType": file.content_type,
        "sizeBytes": len(data),
    }
    from datetime import datetime as _dt, timezone as _tz
    last_indexed_at = _dt.now(_tz.utc) if status == "active" else None
    source_id = str(uuid.uuid4())
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """INSERT INTO custom_sources (id, user_id, name, description, source_type, domain, authority_level, scope, connection_config, extracted_text, status, error_message, last_indexed_at)
                   VALUES ($1,$2,$3,$4,'file',$5,$6,$7,$8,$9,$10,$11,$12) RETURNING *""",
                source_id, current_user["id"], name, description,
                domain, authorityLevel, scope,
                json.dumps(connection_config), extracted_text, status, error_message, last_indexed_at,
            )
        return _custom_source_to_dict(dict(row))
    except Exception as exc:
        raise HTTPException(status_code=500, detail={"error": str(exc)})


class CustomSourceUpdateBody(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    scope: Optional[str] = None
    authorityLevel: Optional[str] = None


@app.patch("/api/sources/custom/{source_id}")
async def api_custom_sources_update(
    source_id: str,
    body: CustomSourceUpdateBody,
    current_user: dict = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_dash_pool),
):
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail={"error": "Admin required"})
    try:
        async with pool.acquire() as conn:
            existing = await conn.fetchrow(
                "SELECT id FROM custom_sources WHERE id=$1 AND user_id=$2",
                source_id, current_user["id"],
            )
            if not existing:
                raise HTTPException(status_code=404, detail={"error": "Not found"})
            updates = []
            values = []
            idx = 1
            if body.name is not None:
                updates.append(f"name=${idx}"); values.append(body.name); idx += 1
            if body.description is not None:
                updates.append(f"description=${idx}"); values.append(body.description); idx += 1
            if body.scope is not None:
                updates.append(f"scope=${idx}"); values.append(body.scope); idx += 1
            if body.authorityLevel is not None:
                updates.append(f"authority_level=${idx}"); values.append(body.authorityLevel); idx += 1
            if not updates:
                row = await conn.fetchrow("SELECT * FROM custom_sources WHERE id=$1", source_id)
            else:
                updates.append(f"updated_at=NOW()")
                row = await conn.fetchrow(
                    f"UPDATE custom_sources SET {', '.join(updates)} WHERE id=${idx} RETURNING *",
                    *values, source_id,
                )
        return _custom_source_to_dict(dict(row))
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail={"error": str(exc)})


@app.delete("/api/sources/custom/{source_id}", status_code=204)
async def api_custom_sources_delete(
    source_id: str,
    current_user: dict = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_dash_pool),
):
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail={"error": "Admin required"})
    try:
        async with pool.acquire() as conn:
            existing = await conn.fetchrow(
                "SELECT id FROM custom_sources WHERE id=$1 AND user_id=$2",
                source_id, current_user["id"],
            )
            if not existing:
                raise HTTPException(status_code=404, detail={"error": "Not found"})
            await conn.execute("DELETE FROM custom_sources WHERE id=$1", source_id)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail={"error": str(exc)})


@app.get("/api/sources/custom/{source_id}")
async def api_custom_sources_get(
    source_id: str,
    current_user: dict = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_dash_pool),
):
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM custom_sources WHERE id=$1 AND user_id=$2",
                source_id, current_user["id"],
            )
        if not row:
            raise HTTPException(status_code=404, detail={"error": "Not found"})
        return _custom_source_to_dict(dict(row))
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail={"error": str(exc)})


@app.post("/api/sources/custom/{source_id}/test")
async def api_custom_sources_test(
    source_id: str,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_dash_pool),
):
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail={"error": "Admin required"})
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT id, source_type, connection_config FROM custom_sources WHERE id=$1 AND user_id=$2",
                source_id, current_user["id"],
            )
        if not row:
            raise HTTPException(status_code=404, detail={"error": "Not found"})
        if row["source_type"] == "file":
            raise HTTPException(status_code=400, detail={"error": "File sources cannot be re-indexed — re-upload to refresh"})
        config = row["connection_config"]
        if isinstance(config, str):
            config = json.loads(config)
        background_tasks.add_task(_index_source, source_id, row["source_type"], config, pool)
        return {"status": "pending", "message": "Re-indexing started"}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail={"error": str(exc)})


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

@app.get("/api/settings")
async def api_settings_get(
    current_user: dict = Depends(get_current_user),
    dash_pool: asyncpg.Pool = Depends(get_dash_pool),
):
    user_id = current_user["id"]
    email = current_user.get("email", "")
    name = current_user.get("display_name") or email.split("@")[0]
    org_name = current_user.get("org_name") or "My Organisation"
    role = current_user.get("role") or "admin"

    # Get first active API key prefix
    api_key_display = ""
    try:
        async with dash_pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT key_prefix FROM api_keys WHERE user_id=$1 AND is_active=TRUE ORDER BY created_at LIMIT 1",
                user_id,
            )
        if row:
            api_key_display = row["key_prefix"] + "…"
    except Exception:
        pass

    return {
        "org": {
            "id": str(user_id),
            "name": org_name,
            "apiKey": api_key_display,
            "plan": "starter",
            "manualReviewMinutesPerClaim": 15,
            "notificationConfig": {
                "emailRecipients": [email] if email else [],
                "webhookUrl": None,
                "notifyOn": ["block"],
            },
            "createdAt": current_user.get("created_at", datetime.now(timezone.utc)).isoformat()
                         if hasattr(current_user.get("created_at"), "isoformat")
                         else datetime.now(timezone.utc).isoformat(),
        },
        "members": [
            {
                "id": str(user_id),
                "name": name,
                "email": email,
                "role": role,
                "createdAt": datetime.now(timezone.utc).isoformat(),
                "reviewsCompleted": 0,
                "avgReviewTimeMs": 0,
                "approvalRate": 0.0,
                "avgFixesApplied": 0.0,
            }
        ],
    }


class UpdateSettingsBody(BaseModel):
    name: Optional[str] = None
    notificationConfig: Optional[dict] = None


@app.put("/api/settings")
async def api_settings_update(
    body: UpdateSettingsBody,
    current_user: dict = Depends(get_current_user),
    dash_pool: asyncpg.Pool = Depends(get_dash_pool),
):
    if body.name:
        try:
            async with dash_pool.acquire() as conn:
                await conn.execute(
                    "UPDATE users SET org_name=$1 WHERE id=$2",
                    body.name, current_user["id"],
                )
        except Exception as exc:
            raise HTTPException(status_code=500, detail={"error": str(exc)})
    return {"ok": True}


@app.post("/api/settings/regenerate-key")
async def api_settings_regenerate_key(
    current_user: dict = Depends(get_current_user),
    dash_pool: asyncpg.Pool = Depends(get_dash_pool),
):
    raw_key  = "bx_" + secrets.token_hex(20)
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    key_prefix = raw_key[:12]
    try:
        async with dash_pool.acquire() as conn:
            # Deactivate old keys and create a new one
            await conn.execute(
                "UPDATE api_keys SET is_active=FALSE WHERE user_id=$1", current_user["id"]
            )
            await conn.execute(
                "INSERT INTO api_keys (user_id, key_hash, key_prefix, label) VALUES ($1,$2,$3,'default')",
                current_user["id"], key_hash, key_prefix,
            )
    except Exception as exc:
        raise HTTPException(status_code=500, detail={"error": str(exc)})
    return {"apiKey": raw_key}


@app.post("/api/settings/invite")
async def api_settings_invite(body: dict, current_user: dict = Depends(get_current_user)):
    raise HTTPException(status_code=501, detail={"error": "Team invites not yet implemented"})


@app.put("/api/settings/members/{user_id}/role")
async def api_settings_update_role(
    user_id: str,
    body: dict,
    current_user: dict = Depends(get_current_user),
):
    raise HTTPException(status_code=501, detail={"error": "Role management not yet implemented"})


# ---------------------------------------------------------------------------
# Public verify — no auth, rate-limited
# ---------------------------------------------------------------------------

# Try Redis for distributed rate limiting; fall back to in-process memory.
try:
    import redis.asyncio as _aioredis
    _redis_client = _aioredis.from_url(os.environ.get("REDIS_URL", "redis://localhost:6379"))
    _USE_REDIS = True
except Exception:
    _USE_REDIS = False

_rate_store: dict[str, list[float]] = {}  # ip → [unix timestamps]
_RATE_LIMIT_MAX    = 10
_RATE_LIMIT_WINDOW = 60  # 1 minute in seconds

_PUBLIC_CONFIG = {
    "domain":                       "auto",
    "policy_profile":               "permissive",
    "unsupported_policy":           "accept",
    "out_of_scope_policy":          "accept",
    "contradiction_policy":         "flag",
    "flag_extrapolations":          False,
    "require_acknowledgement_note": False,
}

# Maps "permissive" profile → verification API's PolicyConfig kwargs
_PERMISSIVE_POLICY = {
    "min_ecr_for_pass": 0.20,
    "min_vs_for_pass":  0.65,
    "max_vs_for_block": 0.30,
}


async def _rl_check_redis(ip: str) -> bool:
    """Sliding-window rate check via Redis sorted set. Fails open on errors."""
    key    = f"bria:rl:{ip}"
    now    = time.time()
    cutoff = now - _RATE_LIMIT_WINDOW
    try:
        async with _redis_client.pipeline(transaction=True) as pipe:
            pipe.zremrangebyscore(key, 0, cutoff)
            pipe.zadd(key, {str(now): now})
            pipe.zcard(key)
            pipe.expire(key, _RATE_LIMIT_WINDOW)
            results = await pipe.execute()
        return results[2] <= _RATE_LIMIT_MAX  # zcard after add
    except Exception:
        return True  # fail open


def _rl_check_memory(ip: str) -> bool:
    """Sliding-window rate check using an in-process dict. Thread-safe via GIL."""
    now    = time.time()
    cutoff = now - _RATE_LIMIT_WINDOW
    ts     = [t for t in _rate_store.get(ip, []) if t > cutoff]
    if len(ts) >= _RATE_LIMIT_MAX:
        _rate_store[ip] = ts
        return False
    ts.append(now)
    _rate_store[ip] = ts
    return True


class PublicVerifyBody(BaseModel):
    text: Optional[str] = None
    input: Optional[str] = None


def _pub_confidence_to_strength(confidence: float) -> Optional[str]:
    if confidence >= 0.8:
        return "strong"
    if confidence >= 0.5:
        return "moderate"
    if confidence > 0:
        return "weak"
    return None


def _pub_citation_to_source(citation: dict, idx: int) -> dict:
    source_name  = citation.get("source", "Unknown")
    connector_id = source_name.lower() if source_name.lower() in ("fred", "edgar") else None
    return {
        "id":              f"src-{idx}",
        "name":            source_name,
        "source_type":     "live_api",
        "connector_id":    connector_id,
        "url":             None,
        "authority_level": "primary",
        "freshness":       "current",
        "detail": {
            "ai_asserted":      "",
            "source_states":    f"{citation.get('label', source_name)}: {citation.get('value', '')} ({citation.get('date', '')})",
            "discrepancy_type": None,
            "summary":          citation.get("label", ""),
        },
    }


@app.post("/api/public/verify")
async def api_public_verify(
    request: Request,
    body: PublicVerifyBody,
    dash_pool: asyncpg.Pool = Depends(get_dash_pool),
):
    # Accept both "text" and "input" fields for backward compat
    raw_text = body.text or body.input or ""
    if not raw_text.strip():
        raise HTTPException(status_code=400, detail={"error": "Text or input is required"})

    # ── Rate limit (IP-based) ──────────────────────────────────────────────
    client_ip = request.headers.get("X-Real-IP") or (request.client.host if request.client else None) or "unknown"
    if _USE_REDIS:
        allowed = await _rl_check_redis(client_ip)
    else:
        allowed = _rl_check_memory(client_ip)

    if not allowed:
        raise HTTPException(
            status_code=429,
            detail={"error": "rate_limit", "message": "Too many requests. Try again later."},
        )

    # ── URL detection & fetch ──────────────────────────────────────────────
    source_url: str | None = None
    publication: str | None = None
    text = raw_text.strip()

    if text.startswith("http://") or text.startswith("https://"):
        try:
            from url_fetch import fetch_url_content
            fetched = await fetch_url_content(text)
            text = fetched["text"]
            source_url = fetched["url"]
            publication = fetched["publication"]
        except (TimeoutError, ValueError) as exc:
            raise HTTPException(status_code=422, detail={"error": str(exc), "fallback": True})

    # ── Word cap ───────────────────────────────────────────────────────────
    # URL-fetched content is already trimmed by url_fetch (25K chars max).
    # Only apply the 300-word limit to raw pasted text.
    word_limit = 5000 if source_url else 300
    if len(text.split()) > word_limit:
        raise HTTPException(
            status_code=400,
            detail={"error": "too_long", "message": f"Text exceeds {word_limit} word limit."},
        )

    # ── Proxy to verification API with permissive policy ───────────────────
    payload: dict = {
        "content": text,
        "domain":  "auto",
        "policy":  _PERMISSIVE_POLICY,
    }

    started = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=300.0) as client:
            resp = await client.post(f"{VERIFY_API_URL}/v1/verify", json=payload)
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=exc.response.status_code,
            detail={"error": str(exc)},
        )
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=503,
            detail={"error": f"Verification service unavailable: {exc}"},
        )
    elapsed = time.perf_counter() - started

    # ── Log (fire-and-forget to mcp_db) ───────────────────────────────────
    import logging_middleware as _logger
    await _logger.log_verify_document(None, text, data, elapsed)

    # ── Transform response to frontend shape ──────────────────────────────
    meta         = data.get("meta", {})
    scores       = data.get("scores", {})
    claims_raw   = data.get("claims", [])
    decision_raw = data.get("decision", "block")
    decision     = "flag" if decision_raw == "review" else decision_raw

    corroborated = sum(1 for c in claims_raw if c.get("status") == "corroborated")
    contradicted  = sum(1 for c in claims_raw if c.get("status") == "contradicted")
    unsupported   = sum(1 for c in claims_raw if c.get("status") == "unsupported")
    out_of_scope  = sum(1 for c in claims_raw if c.get("status") == "out_of_scope")
    total_claims  = meta.get("total_claims", len(claims_raw))

    frontend_claims = []
    for claim in claims_raw:
        status     = claim.get("status", "out_of_scope")
        confidence = float(claim.get("confidence") or 0)
        citations  = claim.get("citations") or []
        frontend_claims.append({
            "text":                  claim.get("text", ""),
            "position":              {"start": 0, "end": len(claim.get("text", ""))},
            "status":                status,
            "confirmation_strength": _pub_confidence_to_strength(confidence) if status == "corroborated" else None,
            "fix":                   _build_fix(status, claim.get("reasoning", "")),
            "sources":               [_pub_citation_to_source(c, i) for i, c in enumerate(citations)],
        })

    sentences = [{"text": text, "decision": decision, "claims": frontend_claims}] if frontend_claims else []
    decision_reasons = [
        {"claim": c.get("text", ""), "reason": c.get("reasoning", "")}
        for c in claims_raw
        if c.get("status") in ("contradicted", "unsupported") and c.get("reasoning")
    ]
    elapsed_ms        = int((meta.get("elapsed_seconds", 0) or 0) * 1000)
    sources_consulted = sum(len(c.get("citations") or []) for c in claims_raw)

    pipeline_result = {
        "request_id":     data.get("request_id", ""),
        "timestamp":      datetime.now(timezone.utc).isoformat(),
        "input_text":     text,
        "annotated_text": text,
        "sentences":      sentences,
        "coverage": {
            "total_sentences": len(sentences),
            "total_claims":    total_claims,
            "corroborated":    corroborated,
            "contradicted":    contradicted,
            "unsupported":     unsupported,
            "out_of_scope":    out_of_scope,
            "coverage_ratio":  float(scores.get("ecr", 0) or 0),
        },
        "decision":          decision,
        "decision_reasons":  decision_reasons,
        "config":            _PUBLIC_CONFIG,
        "audit": {
            "sources_consulted":  sources_consulted,
            "processing_time_ms": elapsed_ms,
            "trace_id":           data.get("request_id", ""),
        },
    }

    # ── Exchange: billing, persistence, result_id ──────────────────────────
    from exchange_billing import count_verified_claims, check_and_increment_usage

    verified_count = await count_verified_claims(pipeline_result)

    # Determine user_id from optional auth header
    user_id: str | None = None
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        try:
            user_id = str(decode_jwt(auth_header.split(" ", 1)[1]))
        except Exception:
            pass

    usage = await check_and_increment_usage(dash_pool, user_id, client_ip, verified_count)
    if not usage["allowed"]:
        raise HTTPException(status_code=429, detail={
            "error": "Monthly limit reached",
            "used": usage["used"],
            "limit": usage["limit"],
        })

    # Determine overall verdict
    if contradicted > 0:
        verdict = "contradicted"
    elif unsupported > 0:
        verdict = "unsupported"
    elif corroborated > 0:
        verdict = "corroborated"
    else:
        verdict = "out_of_scope"

    result_id = "ex_" + secrets.token_urlsafe(6)
    async with dash_pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO exchange_results
               (id, user_id, source_url, publication, input_text, full_response, verified_claim_count, verdict)
               VALUES ($1, $2, $3, $4, $5, $6, $7, $8)""",
            result_id, user_id, source_url, publication, text, json.dumps(pipeline_result), verified_count, verdict,
        )

    return {
        "result_id": result_id,
        "source_url": source_url,
        "publication": publication,
        "verified_claim_count": verified_count,
        "verdict": verdict,
        "usage": usage,
        "result": pipeline_result,
    }



# ---------------------------------------------------------------------------
# Exchange — Streaming Verify (SSE)
# ---------------------------------------------------------------------------

import asyncio as _asyncio
import re as _re
from starlette.responses import StreamingResponse


def _split_sentences(text: str) -> list[str]:
    """Split text into sentences for the claim preview phase."""
    # Split on sentence-ending punctuation followed by whitespace
    raw = _re.split(r'(?<=[.!?])\s+', text.strip())
    # Filter out very short fragments (< 20 chars) that aren't real sentences
    return [s.strip() for s in raw if len(s.strip()) >= 20]


@app.post("/api/public/verify/stream")
async def api_public_verify_stream(
    request: Request,
    body: PublicVerifyBody,
    dash_pool: asyncpg.Pool = Depends(get_dash_pool),
):
    """SSE endpoint that streams claim extraction then verification results.

    Events:
      - "status"           : { "phase": "fetching_url" }
      - "claims_extracted"  : [ { "text": "...", "status": "checking" }, ... ]
      - "result"           : full verify response (same shape as POST /api/public/verify)
      - "error"            : { "error": "...", ... }
    """
    raw_text = body.text or body.input or ""
    if not raw_text.strip():
        raise HTTPException(status_code=400, detail={"error": "Text or input is required"})

    # Rate limit check (must happen before streaming starts)
    client_ip = request.headers.get("X-Real-IP") or (request.client.host if request.client else None) or "unknown"
    if _USE_REDIS:
        allowed = await _rl_check_redis(client_ip)
    else:
        allowed = _rl_check_memory(client_ip)
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail={"error": "rate_limit", "message": "Too many requests. Try again later."},
        )

    # Check usage before streaming (pre-check, can't raise inside generator)
    user_id: str | None = None
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        try:
            user_id = str(decode_jwt(auth_header.split(" ", 1)[1]))
        except Exception:
            pass

    async def event_stream():
        def sse(event: str, data: dict) -> str:
            return f"event: {event}\ndata: {json.dumps(data)}\n\n"

        source_url: str | None = None
        publication: str | None = None
        text = raw_text.strip()

        # ── Phase 0: URL fetch (if needed) ────────────────────────────────
        if text.startswith("http://") or text.startswith("https://"):
            yield sse("status", {"phase": "fetching_url", "url": text})
            try:
                from url_fetch import fetch_url_content
                fetched = await fetch_url_content(text)
                text = fetched["text"]
                source_url = fetched["url"]
                publication = fetched["publication"]
                yield sse("status", {"phase": "url_fetched", "publication": publication, "source_url": source_url})
            except (TimeoutError, ValueError) as exc:
                yield sse("error", {"error": str(exc), "fallback": True})
                return

        # Word cap
        word_limit = 5000 if source_url else 300
        if len(text.split()) > word_limit:
            yield sse("error", {"error": "too_long", "message": f"Text exceeds {word_limit} word limit."})
            return

        # ── Phase 1: Extract sentences → show as pending claims ───────────
        sentences = _split_sentences(text)
        preview_claims = [
            {"text": s, "status": "checking"}
            for s in sentences
        ]
        yield sse("claims_extracted", {"claims": preview_claims, "count": len(preview_claims)})

        # ── Phase 2: Run full verification ────────────────────────────────
        yield sse("status", {"phase": "verifying", "claim_count": len(preview_claims)})

        payload: dict = {
            "content": text,
            "domain":  "auto",
            "policy":  _PERMISSIVE_POLICY,
        }

        started = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=300.0) as client:
                resp = await client.post(f"{VERIFY_API_URL}/v1/verify", json=payload)
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPStatusError as exc:
            yield sse("error", {"error": f"Verification failed: {exc.response.status_code}"})
            return
        except httpx.RequestError as exc:
            yield sse("error", {"error": f"Verification service unavailable: {exc}"})
            return
        elapsed = time.perf_counter() - started

        # Log
        import logging_middleware as _logger
        await _logger.log_verify_document(None, text, data, elapsed)

        # Transform to frontend shape (same logic as non-streaming endpoint)
        meta         = data.get("meta", {})
        scores       = data.get("scores", {})
        claims_raw   = data.get("claims", [])
        decision_raw = data.get("decision", "block")
        decision     = "flag" if decision_raw == "review" else decision_raw

        n_corroborated = sum(1 for c in claims_raw if c.get("status") == "corroborated")
        n_contradicted = sum(1 for c in claims_raw if c.get("status") == "contradicted")
        n_unsupported  = sum(1 for c in claims_raw if c.get("status") == "unsupported")
        n_out_of_scope = sum(1 for c in claims_raw if c.get("status") == "out_of_scope")
        total_claims   = meta.get("total_claims", len(claims_raw))

        frontend_claims = []
        for claim in claims_raw:
            status     = claim.get("status", "out_of_scope")
            confidence = float(claim.get("confidence") or 0)
            citations  = claim.get("citations") or []
            fc = {
                "text":                  claim.get("text", ""),
                "position":              {"start": 0, "end": len(claim.get("text", ""))},
                "status":                status,
                "confirmation_strength": _pub_confidence_to_strength(confidence) if status == "corroborated" else None,
                "fix":                   _build_fix(status, claim.get("reasoning", "")),
                "sources":               [_pub_citation_to_source(c, i) for i, c in enumerate(citations)],
            }
            frontend_claims.append(fc)

            # ── Stream each claim verdict individually ─────────────────────
            yield sse("claim_verified", fc)
            await _asyncio.sleep(0)  # yield control so SSE flushes

        fe_sentences = [{"text": text, "decision": decision, "claims": frontend_claims}] if frontend_claims else []
        decision_reasons = [
            {"claim": c.get("text", ""), "reason": c.get("reasoning", "")}
            for c in claims_raw
            if c.get("status") in ("contradicted", "unsupported") and c.get("reasoning")
        ]
        elapsed_ms        = int((meta.get("elapsed_seconds", 0) or 0) * 1000)
        sources_consulted = sum(len(c.get("citations") or []) for c in claims_raw)

        pipeline_result = {
            "request_id":     data.get("request_id", ""),
            "timestamp":      datetime.now(timezone.utc).isoformat(),
            "input_text":     text,
            "annotated_text": text,
            "sentences":      fe_sentences,
            "coverage": {
                "total_sentences": len(fe_sentences),
                "total_claims":    total_claims,
                "corroborated":    n_corroborated,
                "contradicted":    n_contradicted,
                "unsupported":     n_unsupported,
                "out_of_scope":    n_out_of_scope,
                "coverage_ratio":  float(scores.get("ecr", 0) or 0),
            },
            "decision":          decision,
            "decision_reasons":  decision_reasons,
            "config":            _PUBLIC_CONFIG,
            "audit": {
                "sources_consulted":  sources_consulted,
                "processing_time_ms": elapsed_ms,
                "trace_id":           data.get("request_id", ""),
            },
        }

        # ── Billing & persistence ─────────────────────────────────────────
        try:
            from exchange_billing import count_verified_claims, check_and_increment_usage

            verified_count = await count_verified_claims(pipeline_result)
            usage = await check_and_increment_usage(dash_pool, user_id, client_ip, verified_count)
            if not usage["allowed"]:
                yield sse("error", {"error": "Monthly limit reached", "used": usage["used"], "limit": usage["limit"]})
                return

            if n_contradicted > 0:
                verdict = "contradicted"
            elif n_unsupported > 0:
                verdict = "unsupported"
            elif n_corroborated > 0:
                verdict = "corroborated"
            else:
                verdict = "out_of_scope"

            result_id = "ex_" + secrets.token_urlsafe(6)
            async with dash_pool.acquire() as conn:
                await conn.execute(
                    """INSERT INTO exchange_results
                       (id, user_id, source_url, publication, input_text, full_response, verified_claim_count, verdict)
                       VALUES ($1, $2, $3, $4, $5, $6, $7, $8)""",
                    result_id, user_id, source_url, publication, text, json.dumps(pipeline_result), verified_count, verdict,
                )

            # ── Final event: complete result ──────────────────────────────────
            yield sse("result", {
                "result_id": result_id,
                "source_url": source_url,
                "publication": publication,
                "verified_claim_count": verified_count,
                "verdict": verdict,
                "usage": usage,
                "result": pipeline_result,
            })
        except Exception as exc:
            import traceback
            traceback.print_exc()
            yield sse("error", {"error": f"Something went wrong. Please try again."})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ---------------------------------------------------------------------------
# Exchange — Additional Endpoints (results, usage)
# ---------------------------------------------------------------------------

@app.post("/api/results")
async def claim_exchange_result(
    request: Request,
    body: dict = Body(...),
    user: dict = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_dash_pool),
):
    result_id = body.get("result_id")
    if not result_id:
        raise HTTPException(status_code=400, detail={"error": "result_id is required"})

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """UPDATE exchange_results
               SET user_id = $1
               WHERE id = $2 AND user_id IS NULL
               RETURNING id, user_id, source_url, publication, input_text, full_response,
                         verified_claim_count, verdict, created_at""",
            str(user["id"]), result_id,
        )
    if not row:
        # Maybe already claimed or doesn't exist — try to fetch it
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT id, user_id, source_url, publication, input_text, full_response, verified_claim_count, verdict, created_at FROM exchange_results WHERE id = $1",
                result_id,
            )
        if not row:
            raise HTTPException(status_code=404, detail={"error": "Result not found"})

    return {
        "result_id": row["id"],
        "user_id": row["user_id"],
        "source_url": row["source_url"],
        "publication": row["publication"],
        "input_text": row["input_text"],
        "result": json.loads(row["full_response"]) if isinstance(row["full_response"], str) else row["full_response"],
        "verified_claim_count": row["verified_claim_count"],
        "verdict": row["verdict"],
        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
    }


@app.get("/api/results/{result_id}")
async def get_exchange_result(
    result_id: str,
    pool: asyncpg.Pool = Depends(get_dash_pool),
):
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """SELECT id, source_url, publication, created_at, verified_claim_count,
                      verdict, full_response
               FROM exchange_results WHERE id = $1""",
            result_id,
        )
    if not row:
        raise HTTPException(status_code=404, detail={"error": "Result not found"})

    return {
        "result_id": row["id"],
        "source_url": row["source_url"],
        "publication": row["publication"],
        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
        "verified_claim_count": row["verified_claim_count"],
        "verdict": row["verdict"],
        "result": json.loads(row["full_response"]) if isinstance(row["full_response"], str) else row["full_response"],
    }


@app.get("/api/results")
async def list_exchange_results(
    user: dict = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_dash_pool),
    verdict: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    conditions = ["user_id = $1"]
    params: list[Any] = [str(user["id"])]
    idx = 2

    if verdict:
        conditions.append(f"verdict = ${idx}")
        params.append(verdict)
        idx += 1

    if date_from:
        conditions.append(f"created_at >= ${idx}::timestamptz")
        params.append(date_from)
        idx += 1

    where = " AND ".join(conditions)

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            f"""SELECT id, source_url, publication, created_at, verified_claim_count,
                       verdict, input_text
                FROM exchange_results
                WHERE {where}
                ORDER BY created_at DESC
                LIMIT ${idx} OFFSET ${idx + 1}""",
            *params, limit, offset,
        )
        total_row = await conn.fetchrow(
            f"SELECT COUNT(*) as total FROM exchange_results WHERE {where}",
            *params,
        )

    return {
        "results": [
            {
                "result_id": r["id"],
                "source_url": r["source_url"],
                "publication": r["publication"],
                "created_at": r["created_at"].isoformat() if r["created_at"] else None,
                "verified_claim_count": r["verified_claim_count"],
                "verdict": r["verdict"],
                "input_text": r["input_text"][:200],
            }
            for r in rows
        ],
        "total": total_row["total"] if total_row else 0,
        "limit": limit,
        "offset": offset,
    }


@app.get("/api/usage")
async def get_exchange_usage(
    user: dict = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_dash_pool),
):
    month = datetime.now(timezone.utc).strftime("%Y-%m")
    user_id = str(user["id"])

    # Determine plan and limit
    plan = "free"
    limit = 50
    async with pool.acquire() as conn:
        try:
            col_check = await conn.fetchval(
                "SELECT COUNT(*) FROM information_schema.columns "
                "WHERE table_name = 'users' AND column_name = 'plan'"
            )
            if col_check:
                row = await conn.fetchrow("SELECT plan FROM users WHERE id = $1", user["id"])
                if row and row["plan"] == "pro":
                    plan = "pro"
                    limit = 500
        except Exception:
            pass

        usage_row = await conn.fetchrow(
            "SELECT verified_claims FROM exchange_usage WHERE user_id = $1 AND month = $2",
            user_id, month,
        )

    used = usage_row["verified_claims"] if usage_row else 0

    return {
        "month": month,
        "used": used,
        "limit": limit,
        "remaining": max(0, limit - used),
        "plan": plan,
    }
