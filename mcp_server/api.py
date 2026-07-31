"""
Bria Exchange — API
POST /v1/verify  →  VerificationResponse
"""

import asyncio
import time
import uuid
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException, Header, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from verification_pipeline import PipelineRunner
from assembler import ResponseAssembler
from policy_engine import PolicyConfig
import logging_middleware as logger


# ── Request / response models ──────────────────────────────────────────────────

class VerifyRequest(BaseModel):
    content:      str  = Field(..., description="Text to verify", min_length=10)
    request_id:   Optional[str]   = Field(None, description="Idempotency key")
    policy:       Optional[dict]  = Field(None, description="Custom policy thresholds")
    domain:       Optional[str]   = Field("auto", description="Domain hint: financial, pharma, legal, news_editorial, or auto")
    enabled_connector_ids: Optional[list[str]] = Field(None, description="Restrict verification to these connector IDs")
    custom_sources: Optional[list[dict]] = Field(None, description="Org custom sources to include in verification corpus")

    class Config:
        json_schema_extra = {
            "example": {
                "content": "Apple reported revenue of $124.3 billion for Q1 2026.",
                "request_id": "req_abc123",
                "policy": {
                    "min_ecr_for_pass": 0.40,
                    "min_vs_for_pass":  0.80,
                }
            }
        }


# ── App state ──────────────────────────────────────────────────────────────────

runner    = None
assembler = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global runner, assembler
    if runner is None:
        runner    = PipelineRunner(concurrency=3)
    if assembler is None:
        assembler = ResponseAssembler()
    yield
    runner    = None
    assembler = None


# ── App ────────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Bria Exchange",
    description="AI output verification infrastructure. Verify claims against licensed, authoritative sources.",
    version="1.0.0",
    lifespan=lifespan,
)


# ── Error schema ───────────────────────────────────────────────────────────────

def error_response(code: str, message: str, status_code: int) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": {"code": code, "message": message}},
    )


# ── Routes ─────────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "version": "1.0.0"}


@app.post("/v1/verify")
async def verify(
    request:    VerifyRequest,
    x_request_id: Optional[str] = Header(None),
    x_api_key:    Optional[str] = Header(None),
):
    """
    Verify AI-generated text against authoritative data sources.

    Extracts claims, verifies each against FRED and EDGAR,
    scores the document, and returns a Pass/Review/Block decision.
    """
    if runner is None:
        return error_response("service_unavailable", "Service not ready.", 503)

    # Request ID: header > body > generated
    request_id = x_request_id or request.request_id or str(uuid.uuid4())

    # Build optional policy config from request body
    policy_config = None
    if request.policy:
        try:
            policy_config = PolicyConfig(**request.policy)
        except Exception as e:
            return error_response(
                "invalid_policy_config",
                f"Invalid policy configuration: {e}",
                400,
            )

    try:
        started = time.perf_counter()

        pipeline_result = await runner.run(
            request.content,
            domain=request.domain or "auto",
            enabled_connector_ids=request.enabled_connector_ids,
            custom_sources=request.custom_sources,
        )
        response        = assembler.assemble(
            pipeline_result,
            request_id=request_id,
            policy_config=policy_config,
        )

        elapsed = time.perf_counter() - started

        result = response.to_dict()
        result["meta"]["elapsed_seconds"] = round(elapsed, 2)

        await logger.log_verify_document(x_api_key, request.content, result, elapsed)

        return result

    except Exception as e:
        return error_response(
            "verification_failed",
            f"Verification failed: {str(e)}",
            500,
        )


@app.post("/v1/verify/batch")
async def verify_batch(requests: list[VerifyRequest]):
    """
    Verify multiple documents concurrently.
    Returns a list of verification responses in the same order as the input.
    Max 10 documents per batch.
    """
    if len(requests) > 10:
        return error_response(
            "batch_too_large",
            "Maximum 10 documents per batch request.",
            400,
        )

    if runner is None:
        return error_response("service_unavailable", "Service not ready.", 503)

    async def run_one(req: VerifyRequest) -> dict:
        request_id    = req.request_id or str(uuid.uuid4())
        policy_config = PolicyConfig(**req.policy) if req.policy else None
        pipeline      = await runner.run(req.content, domain=req.domain or "auto", enabled_connector_ids=req.enabled_connector_ids)
        response      = assembler.assemble(pipeline,
                            request_id=request_id,
                            policy_config=policy_config)
        return response.to_dict()

    results = await asyncio.gather(
        *[run_one(req) for req in requests],
        return_exceptions=True,
    )

    return [
        r if not isinstance(r, Exception)
        else {"error": {"code": "verification_failed", "message": str(r)}}
        for r in results
    ]

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)