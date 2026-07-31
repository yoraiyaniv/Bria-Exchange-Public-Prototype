"""
Bria Exchange — Response Assembler
Packages PipelineResult, Scores, and PolicyResult into the final API response.
This is what the client receives from POST /verify.
"""

import hashlib
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from verification_pipeline import PipelineResult
from scoring import Scores, Scorer
from policy_engine import PolicyEngine, PolicyResult, PolicyConfig


# ── API response schema ────────────────────────────────────────────────────────

@dataclass
class ClaimVerdict:
    """Per-claim result in the API response."""
    claim_id:       str
    text:           str
    claim_type:     str
    status:         str        # corroborated | contradicted | unsupported | out_of_scope
    confidence:     float
    reasoning:      str
    citations:      list[dict]
    explanation:    Optional[str] = None
    corrected_fact: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "claim_id":       self.claim_id,
            "text":           self.text,
            "claim_type":     self.claim_type,
            "status":         self.status,
            "confidence":     self.confidence,
            "reasoning":      self.reasoning,
            "explanation":    self.explanation,
            "corrected_fact": self.corrected_fact,
            "citations":      self.citations,
        }


@dataclass
class AuditEntry:
    """Immutable audit log entry for compliance."""
    request_id:    str
    input_hash:    str
    document_type: str
    timestamp:     str
    model:         str
    total_claims:  int
    decision:      str
    vs:            float
    ecr:           float
    sci:           float
    flags:         list[str]

    def to_dict(self) -> dict:
        return {
            "request_id":    self.request_id,
            "input_hash":    self.input_hash,
            "document_type": self.document_type,
            "timestamp":     self.timestamp,
            "model":         self.model,
            "total_claims":  self.total_claims,
            "decision":      self.decision,
            "scores": {
                "vs":  self.vs,
                "ecr": self.ecr,
                "sci": self.sci,
            },
            "flags": self.flags,
        }


@dataclass
class VerificationResponse:
    """The complete API response returned to the client."""
    request_id:     str
    input_hash:     str
    document_type:  str

    # Top-level scores
    vs:             float
    ecr:            float
    sci:            float

    # Policy decision
    decision:       str
    decision_reason: str
    flags:          list[str]

    # Per-claim verdicts
    claims:         list[ClaimVerdict]

    # Audit
    audit:          AuditEntry

    # Metadata
    started_at:     str
    completed_at:   str
    total_claims:   int
    verified_claims: int
    skipped_claims: int
    error_claims:   int

    def to_dict(self) -> dict:
        return {
            "request_id":      self.request_id,
            "input_hash":      self.input_hash,
            "document_type":   self.document_type,
            "scores": {
                "vs":  round(self.vs,  4),
                "ecr": round(self.ecr, 4),
                "sci": round(self.sci, 4),
            },
            "decision":        self.decision,
            "decision_reason": self.decision_reason,
            "flags":           self.flags,
            "claims":          [c.to_dict() for c in self.claims],
            "audit":           self.audit.to_dict(),
            "meta": {
                "started_at":     self.started_at,
                "completed_at":   self.completed_at,
                "total_claims":   self.total_claims,
                "verified_claims": self.verified_claims,
                "skipped_claims": self.skipped_claims,
                "error_claims":   self.error_claims,
            }
        }

    def pretty(self) -> str:
        lines = [
            f"{'='*60}",
            f"Bria Exchange Verification Response",
            f"{'='*60}",
            f"Request ID:  {self.request_id}",
            f"Input hash:  {self.input_hash}",
            f"",
            f"Scores:",
            f"  VS  (Verification Score):      {self.vs:.2%}",
            f"  ECR (Evidence Coverage Ratio): {self.ecr:.2%}",
            f"  SCI (Source Confidence Index): {self.sci:.2%}",
            f"",
            f"Decision:    {self.decision.upper()}",
            f"Reason:      {self.decision_reason}",
        ]

        if self.flags:
            lines.append(f"Flags:")
            for flag in self.flags:
                lines.append(f"  • {flag}")

        lines += [
            f"",
            f"Claims ({self.total_claims} total):",
        ]

        for c in self.claims:
            status_label = {
                "corroborated": "✓",
                "contradicted": "✗",
                "unsupported":  "?",
                "out_of_scope": "–",
            }.get(c.status, " ")
            lines.append(
                f"  [{status_label}] [{c.confidence:.0%}] {c.text[:70]}"
            )
            if c.status == "contradicted":
                lines.append(f"        {c.reasoning[:100]}")

        lines.append(f"{'='*60}")
        return "\n".join(lines)


# ── Assembler ──────────────────────────────────────────────────────────────────

class ResponseAssembler:

    def __init__(
        self,
        scorer:        Optional[Scorer]        = None,
        policy_engine: Optional[PolicyEngine]  = None,
        model:         str = "claude-opus-4-5",
    ):
        self.scorer        = scorer        or Scorer()
        self.policy_engine = policy_engine or PolicyEngine()
        self.model         = model

    def assemble(
        self,
        pipeline_result: PipelineResult,
        request_id:      Optional[str] = None,
        policy_config:   Optional[PolicyConfig] = None,
    ) -> VerificationResponse:
        """
        Assemble the final API response from a completed PipelineResult.

        Args:
            pipeline_result: output from PipelineRunner.run()
            request_id:      optional client-provided idempotency key
            policy_config:   optional customer threshold overrides

        Returns:
            VerificationResponse ready to serialize and return to client
        """
        request_id = request_id or str(uuid.uuid4())

        # ── Score ──────────────────────────────────────────────────────────────
        if policy_config:
            engine = PolicyEngine(config=policy_config)
        else:
            engine = self.policy_engine

        scores: Scores           = self.scorer.score(pipeline_result)
        policy: PolicyResult     = engine.decide(scores)

        # ── Build per-claim verdicts ───────────────────────────────────────────
        claims = self._build_claim_verdicts(pipeline_result)

        # ── Build audit entry ──────────────────────────────────────────────────
        audit = AuditEntry(
            request_id=request_id,
            input_hash=pipeline_result.input_hash,
            document_type=pipeline_result.document_type,
            timestamp=datetime.now(timezone.utc).isoformat(),
            model=self.model,
            total_claims=pipeline_result.total_claims,
            decision=policy.decision.value,
            vs=round(scores.vs,  4),
            ecr=round(scores.ecr, 4),
            sci=round(scores.sci, 4),
            flags=policy.flags,
        )

        return VerificationResponse(
            request_id=request_id,
            input_hash=pipeline_result.input_hash,
            document_type=pipeline_result.document_type,
            vs=scores.vs,
            ecr=scores.ecr,
            sci=scores.sci,
            decision=policy.decision.value,
            decision_reason=policy.reason,
            flags=policy.flags,
            claims=claims,
            audit=audit,
            started_at=pipeline_result.started_at,
            completed_at=pipeline_result.completed_at,
            total_claims=pipeline_result.total_claims,
            verified_claims=pipeline_result.verified_claims,
            skipped_claims=pipeline_result.skipped_claims,
            error_claims=pipeline_result.error_claims,
        )

    def _build_claim_verdicts(
        self, pipeline_result: PipelineResult
    ) -> list[ClaimVerdict]:
        verdicts = []

        for cv in pipeline_result.verifications:
            verdicts.append(ClaimVerdict(
                claim_id=cv.claim.id,
                text=cv.claim.text,
                claim_type=cv.claim.claim_type.value,
                status=cv.result.verdict.value,
                confidence=cv.result.confidence,
                reasoning=cv.result.reasoning,
                explanation=cv.result.explanation,
                corrected_fact=cv.result.corrected_fact,
                citations=cv.result.citations,
            ))

        # Skipped claims included with status = out_of_scope
        for claim in pipeline_result.skipped:
            verdicts.append(ClaimVerdict(
                claim_id=claim.id,
                text=claim.text,
                claim_type=claim.claim_type.value,
                status="out_of_scope",
                confidence=0.0,
                reasoning="Skipped — subjective claim, not verifiable.",
                citations=[],
            ))

        # Error claims included with status = out_of_scope
        for error in pipeline_result.errors:
            verdicts.append(ClaimVerdict(
                claim_id=error.get("claim_id", "unknown"),
                text=error.get("claim", ""),
                claim_type="unknown",
                status="out_of_scope",
                confidence=0.0,
                reasoning=f"Verification error: {error.get('error', 'unknown error')}",
                citations=[],
            ))

        return verdicts