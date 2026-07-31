"""
Bria Exchange — Scoring Module
Computes VS (Verification Score), ECR (Evidence Coverage Ratio),
and SCI (Source Confidence Index) from a PipelineResult.
"""

from dataclasses import dataclass
from typing import Optional

from verification_agent import Verdict
from verification_pipeline import PipelineResult


# ── Source authority weights ───────────────────────────────────────────────────
# Higher = more authoritative. Used to compute SCI.

SOURCE_WEIGHTS = {
    "edgar_10k":  1.00,   # audited annual filing
    "edgar_10q":  0.95,   # quarterly filing
    "fred":       0.95,   # official government data
    "edgar":      0.95,   # generic EDGAR (form unknown)
    "wikidata":   0.85,   # structured, sourced knowledge base
    "pubmed":     0.90,   # peer-reviewed medical literature
    "guardian":   0.65,   # major newspaper
    "nytimes":    0.65,   # major newspaper
    "news":       0.60,   # generic news source
    "wikipedia":  0.45,   # encyclopedic — not authoritative, last resort
    "unknown":    0.50,   # fallback
}


# ── Types ──────────────────────────────────────────────────────────────────────

@dataclass
class Scores:
    vs:  float   # Verification Score      0.0 – 1.0
    ecr: float   # Evidence Coverage Ratio 0.0 – 1.0
    sci: float   # Source Confidence Index 0.0 – 1.0

    # supporting counts for transparency
    total_claims:       int
    evidenced_claims:   int   # corroborated + contradicted + unsupported
    corroborated:       int
    contradicted:       int
    unsupported:        int
    out_of_scope:       int

    def to_dict(self) -> dict:
        return {
            "vs":  round(self.vs,  4),
            "ecr": round(self.ecr, 4),
            "sci": round(self.sci, 4),
            "breakdown": {
                "total_claims":     self.total_claims,
                "evidenced_claims": self.evidenced_claims,
                "corroborated":     self.corroborated,
                "contradicted":     self.contradicted,
                "unsupported":      self.unsupported,
                "out_of_scope":     self.out_of_scope,
            }
        }

    def pretty(self) -> str:
        lines = [
            f"VS  (Verification Score):      {self.vs:.2%}",
            f"ECR (Evidence Coverage Ratio): {self.ecr:.2%}",
            f"SCI (Source Confidence Index): {self.sci:.2%}",
            f"",
            f"Breakdown:",
            f"  Total claims:     {self.total_claims}",
            f"  Evidenced:        {self.evidenced_claims}",
            f"  Corroborated:     {self.corroborated}",
            f"  Contradicted:     {self.contradicted}",
            f"  Unsupported:      {self.unsupported}",
            f"  Out of scope:     {self.out_of_scope}",
        ]
        return "\n".join(lines)


# ── Scorer ─────────────────────────────────────────────────────────────────────

class Scorer:

    def score(self, result: PipelineResult) -> Scores:
        verifications = result.verifications
        total         = result.total_claims

        # ── Partition by verdict ───────────────────────────────────────────────
        corroborated = [v for v in verifications if v.result.verdict == Verdict.CORROBORATED]
        contradicted = [v for v in verifications if v.result.verdict == Verdict.CONTRADICTED]
        unsupported  = [v for v in verifications if v.result.verdict == Verdict.UNSUPPORTED]
        out_of_scope = [v for v in verifications if v.result.verdict == Verdict.OUT_OF_SCOPE]

        evidenced    = corroborated + contradicted + unsupported

        # ── VS: accuracy over evidenced claims only ────────────────────────────
        corr_weight = sum(v.result.confidence for v in corroborated)
        cont_weight = sum(v.result.confidence for v in contradicted)
        total_weight = corr_weight + cont_weight

        if total_weight == 0:
            # No evidence either way — VS is undefined, default to 0
            vs = 0.0
        else:
            vs = corr_weight / total_weight

        # ── ECR: coverage over all verifiable claims ───────────────────────────
        # skipped (subjective) claims don't count toward denominator
        verifiable = total - result.skipped_claims
        ecr        = len(evidenced) / verifiable if verifiable > 0 else 0.0

        # ── SCI: source authority of all citations ─────────────────────────────
        sci = self._compute_sci(verifications)

        return Scores(
            vs=vs,
            ecr=ecr,
            sci=sci,
            total_claims=total,
            evidenced_claims=len(evidenced),
            corroborated=len(corroborated),
            contradicted=len(contradicted),
            unsupported=len(unsupported),
            out_of_scope=len(out_of_scope),
        )

    def _compute_sci(self, verifications) -> float:
        """
        Weighted average source authority across all citations.
        Each citation contributes its source weight.
        If no citations exist, SCI is 0.
        """
        weights = []

        for cv in verifications:
            for citation in cv.result.citations:
                weight = self._citation_weight(citation)
                weights.append(weight)

        return sum(weights) / len(weights) if weights else 0.0

    def _citation_weight(self, citation: dict) -> float:
        """Resolve a citation to its source authority weight."""
        source = citation.get("source", "unknown").lower()
        form   = citation.get("form", "").upper()

        # EDGAR citations carry the filing form — use it for precision
        if source == "edgar":
            if form == "10-K":
                return SOURCE_WEIGHTS["edgar_10k"]
            if form == "10-Q":
                return SOURCE_WEIGHTS["edgar_10q"]
            return SOURCE_WEIGHTS["edgar"]

        return SOURCE_WEIGHTS.get(source, SOURCE_WEIGHTS["unknown"])