"""
Bria Exchange — Pipeline Runner
Connects ClaimExtractor and VerificationAgent.
Runs all claims concurrently with a semaphore to cap parallelism.
No claims are lost — errors are captured per-claim, not raised.
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from claim_extraction import (
    ClaimExtractor,
    Claim,
    ExtractionResult,
    Verifiability,
)
from verification_agent import (
    VerificationAgent,
    VerificationResult,
    Verdict,
)


# ── Types ──────────────────────────────────────────────────────────────────────

@dataclass
class ClaimVerification:
    """Pairs an extracted claim with its verification result."""
    claim:  Claim
    result: VerificationResult


@dataclass
class PipelineResult:
    document_type:   str
    input_hash:      str
    started_at:      str
    completed_at:    str
    verifications:   list[ClaimVerification]     # verified claims + verdicts
    skipped:         list[Claim]                 # subjective claims, not sent to agent
    errors:          list[dict]                  # claims that failed with exception
    extraction_tokens: dict                      # token usage from extractor
    total_claims:    int
    verified_claims: int
    skipped_claims:  int
    error_claims:    int

    # ── Verdict breakdown ──────────────────────────────────────────────────────
    @property
    def corroborated(self) -> list[ClaimVerification]:
        return [v for v in self.verifications if v.result.verdict == Verdict.CORROBORATED]

    @property
    def contradicted(self) -> list[ClaimVerification]:
        return [v for v in self.verifications if v.result.verdict == Verdict.CONTRADICTED]

    @property
    def unsupported(self) -> list[ClaimVerification]:
        return [v for v in self.verifications if v.result.verdict == Verdict.UNSUPPORTED]

    @property
    def out_of_scope(self) -> list[ClaimVerification]:
        return [v for v in self.verifications if v.result.verdict == Verdict.OUT_OF_SCOPE]

    def summary(self) -> dict:
        return {
            "input_hash":      self.input_hash,
            "document_type":   self.document_type,
            "started_at":      self.started_at,
            "completed_at":    self.completed_at,
            "total_claims":    self.total_claims,
            "verified_claims": self.verified_claims,
            "skipped_claims":  self.skipped_claims,
            "error_claims":    self.error_claims,
            "verdicts": {
                "corroborated": len(self.corroborated),
                "contradicted": len(self.contradicted),
                "unsupported":  len(self.unsupported),
                "out_of_scope": len(self.out_of_scope),
            },
            "extraction_tokens": self.extraction_tokens,
            "errors": self.errors,
        }

    def print_report(self) -> None:
        print(f"\n{'='*60}")
        print(f"Pipeline report — {self.input_hash}")
        print(f"{'='*60}")
        print(f"Total claims:    {self.total_claims}")
        print(f"Verified:        {self.verified_claims}")
        print(f"Skipped:         {self.skipped_claims}  (subjective)")
        print(f"Errors:          {self.error_claims}")
        print(f"\nVerdicts:")
        print(f"  corroborated:  {len(self.corroborated)}")
        print(f"  contradicted:  {len(self.contradicted)}")
        print(f"  unsupported:   {len(self.unsupported)}")
        print(f"  out_of_scope:  {len(self.out_of_scope)}")

        if self.contradicted:
            print(f"\n⚠ Contradicted claims:")
            for cv in self.contradicted:
                print(f"  [{cv.result.confidence:.0%}] {cv.claim.text}")
                print(f"         {cv.result.reasoning}")

        if self.errors:
            print(f"\n✗ Errors:")
            for e in self.errors:
                print(f"  {e['claim'][:60]}...")
                print(f"  → {e['error']}")
        print(f"{'='*60}\n")


# ── Runner ─────────────────────────────────────────────────────────────────────

class PipelineRunner:
    def __init__(
        self,
        extractor:   Optional[ClaimExtractor]    = None,
        agent:       Optional[VerificationAgent] = None,
        concurrency: int = 10,
    ):
        self.extractor   = extractor or ClaimExtractor()
        self.agent       = agent     or VerificationAgent()
        self.sem         = asyncio.Semaphore(concurrency)

    async def run(
        self,
        source: str,
        domain: str = "auto",
        enabled_connector_ids: Optional[list[str]] = None,
        custom_sources: Optional[list[dict]] = None,
    ) -> PipelineResult:
        """
        Full pipeline: extract claims then verify all concurrently.

        Args:
            source: raw text, or a file path to a PDF/DOCX
            domain: 'financial', 'pharma', 'legal', 'news_editorial', or 'auto'
            enabled_connector_ids: list of connector IDs the org has activated;
                                   if None, all connectors for the domain are used

        Returns:
            PipelineResult with every claim accounted for
        """
        started_at = datetime.now(timezone.utc).isoformat()

        # ── Step 1: Extract claims (sync, single call) ─────────────────────────
        extraction: ExtractionResult = await asyncio.get_event_loop().run_in_executor(
            None, lambda: self.extractor.extract(source)
        )

        # ── Step 2: Partition claims ───────────────────────────────────────────
        to_verify = [
            c for c in extraction.claims
            if c.verifiability != Verifiability.SUBJECTIVE
        ]
        skipped = [
            c for c in extraction.claims
            if c.verifiability == Verifiability.SUBJECTIVE
        ]

        # ── Step 3: Verify all claims concurrently ─────────────────────────────
        raw_results = await asyncio.gather(
            *[self._verify_one(claim, domain, enabled_connector_ids, custom_sources) for claim in to_verify],
            return_exceptions=True,
        )

        # ── Step 4: Collect results — no claims dropped ────────────────────────
        verifications: list[ClaimVerification] = []
        errors:        list[dict]              = []

        for claim, result in zip(to_verify, raw_results):
            if isinstance(result, Exception):
                # Capture exception as structured error, don't raise
                errors.append({
                    "claim": claim.text,
                    "claim_id": claim.id,
                    "error": str(result),
                    "error_type": type(result).__name__,
                })
            else:
                verifications.append(ClaimVerification(claim=claim, result=result))

        completed_at = datetime.now(timezone.utc).isoformat()

        return PipelineResult(
            document_type=extraction.document_type,
            input_hash=extraction.input_hash,
            started_at=started_at,
            completed_at=completed_at,
            verifications=verifications,
            skipped=skipped,
            errors=errors,
            extraction_tokens=extraction.token_usage,
            total_claims=len(extraction.claims),
            verified_claims=len(verifications),
            skipped_claims=len(skipped),
            error_claims=len(errors),
        )

    async def _verify_one(
        self,
        claim: Claim,
        domain: str = "auto",
        enabled_connector_ids: Optional[list[str]] = None,
        custom_sources: Optional[list[dict]] = None,
    ) -> VerificationResult:
        """
        Verify a single claim under the semaphore.
        The semaphore caps concurrent agent loops to avoid rate limits.
        """
        async with self.sem:
            return await self.agent.verify(
                claim.text,
                domain=domain,
                enabled_connector_ids=enabled_connector_ids,
                custom_sources=custom_sources,
            )


if __name__ == "__main__":
    file = open("test.txt", "r")
    text = file.read()
    file.close()
    async def main():
        runner = PipelineRunner()
        result = await runner.run(text)
        result.print_report()

    asyncio.run(main())