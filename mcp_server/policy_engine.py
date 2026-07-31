"""
Bria Exchange — Policy Engine
Produces a Pass / Review / Block decision from VS, ECR, and SCI scores.

Design principles:
- Contradictions always surface — a contradiction can never produce Pass
- Low coverage → Review, not Pass (absence of evidence ≠ evidence of absence)
- High coverage + low VS → Block
- Thresholds are customer-configurable; defaults are conservative
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from scoring import Scores


# ── Types ──────────────────────────────────────────────────────────────────────

class Decision(str, Enum):
    PASS   = "pass"
    REVIEW = "review"
    BLOCK  = "block"


@dataclass
class PolicyConfig:
    """
    Customer-configurable thresholds.
    All values are between 0.0 and 1.0.
    """
    # Minimum ECR required before a Pass is possible
    min_ecr_for_pass:      float = 0.40

    # Minimum VS required for Pass (given sufficient ECR)
    min_vs_for_pass:       float = 0.80

    # VS below this threshold → Block (given sufficient ECR)
    max_vs_for_block:      float = 0.40

    # Any contradiction above this confidence forces at least Review
    contradiction_review_threshold: float = 0.70

    # Contradiction above this confidence + ECR above min → Block
    contradiction_block_threshold:  float = 0.90

    # Minimum SCI required to trust a Block decision
    # If sources are low quality, downgrade Block → Review
    min_sci_for_block:     float = 0.70

    def to_dict(self) -> dict:
        return {
            "min_ecr_for_pass":              self.min_ecr_for_pass,
            "min_vs_for_pass":               self.min_vs_for_pass,
            "max_vs_for_block":              self.max_vs_for_block,
            "contradiction_review_threshold": self.contradiction_review_threshold,
            "contradiction_block_threshold":  self.contradiction_block_threshold,
            "min_sci_for_block":             self.min_sci_for_block,
        }


@dataclass
class PolicyResult:
    decision:   Decision
    reason:     str
    scores:     Scores
    config:     PolicyConfig
    flags:      list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "decision": self.decision.value,
            "reason":   self.reason,
            "flags":    self.flags,
            "scores":   self.scores.to_dict(),
            "config":   self.config.to_dict(),
        }

    def pretty(self) -> str:
        lines = [
            f"Decision:  {self.decision.value.upper()}",
            f"Reason:    {self.reason}",
        ]
        if self.flags:
            lines.append(f"Flags:")
            for flag in self.flags:
                lines.append(f"  • {flag}")
        return "\n".join(lines)


# ── Policy engine ──────────────────────────────────────────────────────────────

class PolicyEngine:

    def __init__(self, config: Optional[PolicyConfig] = None):
        self.config = config or PolicyConfig()

    def decide(self, scores: Scores) -> PolicyResult:
        """
        Evaluate scores against policy thresholds and return a decision.

        Evaluation order matters — more severe conditions checked first.
        """
        cfg   = self.config
        flags = []

        # ── Flag conditions (informational, always evaluated) ──────────────────
        if scores.contradicted > 0:
            flags.append(
                f"{scores.contradicted} contradicted claim(s) found"
            )
        if scores.ecr < cfg.min_ecr_for_pass:
            flags.append(
                f"Low evidence coverage ({scores.ecr:.0%} — "
                f"min {cfg.min_ecr_for_pass:.0%} required for Pass)"
            )
        if scores.sci < cfg.min_sci_for_block and scores.contradicted > 0:
            flags.append(
                f"Low source confidence ({scores.sci:.0%}) — "
                f"contradictions may be unreliable"
            )

        # ── Rule 1: No evidence at all → Review ───────────────────────────────
        if scores.evidenced_claims == 0:
            return PolicyResult(
                decision=Decision.REVIEW,
                reason="No verifiable evidence found — cannot assess document accuracy.",
                scores=scores,
                config=cfg,
                flags=flags,
            )

        # ── Rule 2: High-confidence contradiction + sufficient coverage → Block ─
        if (
            scores.contradicted > 0
            and scores.ecr >= cfg.min_ecr_for_pass
            and scores.sci  >= cfg.min_sci_for_block
        ):
            # Only block if the contradiction confidence is high enough
            # (checked by VS being below block threshold)
            if scores.vs <= cfg.max_vs_for_block:
                return PolicyResult(
                    decision=Decision.BLOCK,
                    reason=(
                        f"VS {scores.vs:.0%} is below block threshold "
                        f"({cfg.max_vs_for_block:.0%}) with {scores.ecr:.0%} evidence coverage."
                    ),
                    scores=scores,
                    config=cfg,
                    flags=flags,
                )

        # ── Rule 3: Any contradiction → at least Review ───────────────────────
        if scores.contradicted > 0:
            return PolicyResult(
                decision=Decision.REVIEW,
                reason=(
                    f"{scores.contradicted} contradicted claim(s) require human review. "
                    f"VS {scores.vs:.0%}, ECR {scores.ecr:.0%}."
                ),
                scores=scores,
                config=cfg,
                flags=flags,
            )

        # ── Rule 4: Insufficient coverage → Review ────────────────────────────
        if scores.ecr < cfg.min_ecr_for_pass:
            return PolicyResult(
                decision=Decision.REVIEW,
                reason=(
                    f"Insufficient evidence coverage ({scores.ecr:.0%}) "
                    f"to issue a Pass — {cfg.min_ecr_for_pass:.0%} required."
                ),
                scores=scores,
                config=cfg,
                flags=flags,
            )

        # ── Rule 5: High VS + sufficient coverage → Pass ──────────────────────
        if scores.vs >= cfg.min_vs_for_pass:
            return PolicyResult(
                decision=Decision.PASS,
                reason=(
                    f"VS {scores.vs:.0%} exceeds pass threshold "
                    f"({cfg.min_vs_for_pass:.0%}) with {scores.ecr:.0%} evidence coverage."
                ),
                scores=scores,
                config=cfg,
                flags=flags,
            )

        # ── Rule 6: Everything else → Review ──────────────────────────────────
        return PolicyResult(
            decision=Decision.REVIEW,
            reason=(
                f"VS {scores.vs:.0%} is below pass threshold "
                f"({cfg.min_vs_for_pass:.0%}) — manual review required."
            ),
            scores=scores,
            config=cfg,
            flags=flags,
        )