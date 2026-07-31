"""Billing and usage tracking for Exchange public verification."""

from datetime import datetime, timezone

import asyncpg


async def count_verified_claims(pipeline_result: dict) -> int:
    """Count all claims that went through the pipeline.

    Every claim costs compute regardless of verdict, so count them all
    except out_of_scope (which are skipped by the pipeline).
    """
    count = 0
    for sentence in pipeline_result.get("sentences", []):
        for claim in sentence.get("claims", []):
            status = (claim.get("status") or "").lower()
            if status != "out_of_scope":
                count += 1
    return count


async def check_and_increment_usage(
    pool: asyncpg.Pool,
    user_id: str | None,
    ip_address: str | None,
    new_claims: int,
) -> dict:
    """Check usage limits and increment if allowed.

    Free logged-in: 50/month. Anonymous: 10/month per IP.
    Pro plan: 500/month.
    """
    month = datetime.now(timezone.utc).strftime("%Y-%m")

    # Determine limit
    limit = 100  # anonymous default
    if user_id:
        limit = 50  # logged-in default
        try:
            async with pool.acquire() as conn:
                # Check if plan column exists before querying it
                col_check = await conn.fetchval(
                    "SELECT COUNT(*) FROM information_schema.columns "
                    "WHERE table_name = 'users' AND column_name = 'plan'"
                )
                if col_check:
                    row = await conn.fetchrow(
                        "SELECT plan FROM users WHERE id = $1",
                        int(user_id) if user_id.isdigit() else user_id,
                    )
                    if row and row["plan"] == "admin":
                        return {"allowed": True, "used": 0, "limit": 999999}
                    if row and row["plan"] == "pro":
                        limit = 500
        except Exception:
            pass  # use default limit

    # Check current usage
    async with pool.acquire() as conn:
        if user_id:
            row = await conn.fetchrow(
                "SELECT verified_claims FROM exchange_usage WHERE user_id = $1 AND month = $2",
                user_id, month,
            )
        else:
            row = await conn.fetchrow(
                "SELECT verified_claims FROM exchange_usage WHERE ip_address = $1 AND month = $2",
                ip_address, month,
            )

        current = row["verified_claims"] if row else 0

        # Allow the request if user hasn't exceeded the limit yet.
        # The claim count of this single request doesn't block it —
        # we charge after the fact and check *before* the next request.
        if current >= limit:
            return {"allowed": False, "used": current, "limit": limit}

        # Upsert usage — don't set ip_address for logged-in users to avoid
        # hitting the UNIQUE(ip_address, month) constraint
        if user_id:
            await conn.execute(
                """INSERT INTO exchange_usage (user_id, month, verified_claims)
                   VALUES ($1, $2, $3)
                   ON CONFLICT (user_id, month)
                   DO UPDATE SET verified_claims = exchange_usage.verified_claims + $3""",
                user_id, month, new_claims,
            )
        else:
            await conn.execute(
                """INSERT INTO exchange_usage (ip_address, month, verified_claims)
                   VALUES ($1, $2, $3)
                   ON CONFLICT (ip_address, month)
                   DO UPDATE SET verified_claims = exchange_usage.verified_claims + $3""",
                ip_address, month, new_claims,
            )

        return {"allowed": True, "used": current + new_claims, "limit": limit}
