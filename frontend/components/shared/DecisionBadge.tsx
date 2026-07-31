import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

// All badges use Sora + 4px border-radius
const BADGE_BASE = "font-mono rounded-[4px] border tracking-wide";

interface DecisionBadgeProps {
  decision: "pass" | "flag" | "block" | string;
  size?: "sm" | "md";
}

const DECISION_STYLES: Record<string, string> = {
  pass:  "text-[var(--bria-green)]  border-[rgba(16,185,129,0.2)]  hover:bg-[var(--bria-green-dim)]",
  flag:  "text-[var(--bria-amber)]  border-[rgba(245,158,11,0.2)]  hover:bg-[var(--bria-amber-dim)]",
  block: "text-[var(--bria-red)]    border-[rgba(239,68,68,0.2)]   hover:bg-[var(--bria-red-dim)]",
};

const DECISION_BG: Record<string, string> = {
  pass:  "bg-[var(--bria-green-dim)]",
  flag:  "bg-[var(--bria-amber-dim)]",
  block: "bg-[var(--bria-red-dim)]",
};

export function DecisionBadge({ decision, size = "sm" }: DecisionBadgeProps) {
  const colorStyle = DECISION_STYLES[decision] || "text-muted-foreground border-border";
  const bgStyle    = DECISION_BG[decision]    || "bg-secondary";
  return (
    <Badge
      variant="outline"
      className={cn(
        BADGE_BASE,
        bgStyle,
        colorStyle,
        "uppercase",
        size === "sm" ? "text-[10px] px-1.5 py-0" : "text-[11px] px-2 py-0.5"
      )}
    >
      {decision}
    </Badge>
  );
}

interface StatusBadgeProps {
  status: "corroborated" | "contradicted" | "unsupported" | "out_of_scope" | string;
  size?: "sm" | "md";
}

const STATUS_STYLES: Record<string, { bg: string; text: string; border: string }> = {
  corroborated: {
    bg:     "bg-[var(--bria-green-dim)]",
    text:   "text-[var(--bria-green)]",
    border: "border-[rgba(16,185,129,0.2)]",
  },
  contradicted: {
    bg:     "bg-[var(--bria-red-dim)]",
    text:   "text-[var(--bria-red)]",
    border: "border-[rgba(239,68,68,0.2)]",
  },
  unsupported: {
    bg:     "bg-[var(--bria-amber-dim)]",
    text:   "text-[var(--bria-amber)]",
    border: "border-[rgba(245,158,11,0.2)]",
  },
  out_of_scope: {
    bg:     "bg-secondary",
    text:   "text-muted-foreground",
    border: "border-border",
  },
};

const STATUS_LABELS: Record<string, string> = {
  corroborated: "Corroborated",
  contradicted: "Contradicted",
  unsupported:  "Unsupported",
  out_of_scope: "Out of Scope",
};

export function StatusBadge({ status, size = "sm" }: StatusBadgeProps) {
  const s = STATUS_STYLES[status] || STATUS_STYLES.out_of_scope;
  return (
    <Badge
      variant="outline"
      className={cn(
        BADGE_BASE,
        s.bg, s.text, s.border,
        size === "sm" ? "text-[10px] px-1.5 py-0" : "text-[11px] px-2 py-0.5"
      )}
    >
      {STATUS_LABELS[status] || status}
    </Badge>
  );
}

interface ReviewStatusBadgeProps {
  status: string;
}

const REVIEW_STATUS_STYLES: Record<string, { bg: string; text: string; border: string }> = {
  not_required:   { bg: "bg-secondary",                   text: "text-muted-foreground",       border: "border-border" },
  pending_review: { bg: "bg-[var(--bria-amber-dim)]",     text: "text-[var(--bria-amber)]",    border: "border-[rgba(245,158,11,0.2)]" },
  in_review:      { bg: "bg-[var(--bria-blue-dim)]",      text: "text-[var(--bria-blue)]",     border: "border-[rgba(125,41,242,0.2)]" },
  approved:       { bg: "bg-[var(--bria-green-dim)]",     text: "text-[var(--bria-green)]",    border: "border-[rgba(16,185,129,0.2)]" },
  rejected:       { bg: "bg-[var(--bria-red-dim)]",       text: "text-[var(--bria-red)]",      border: "border-[rgba(239,68,68,0.2)]" },
};

const REVIEW_STATUS_LABELS: Record<string, string> = {
  not_required:   "N/A",
  pending_review: "Pending",
  in_review:      "In Review",
  approved:       "Approved",
  rejected:       "Rejected",
};

export function ReviewStatusBadge({ status }: ReviewStatusBadgeProps) {
  const s = REVIEW_STATUS_STYLES[status] || REVIEW_STATUS_STYLES.not_required;
  return (
    <Badge
      variant="outline"
      className={cn("text-[10px] px-1.5 py-0", BADGE_BASE, s.bg, s.text, s.border)}
    >
      {REVIEW_STATUS_LABELS[status] || status}
    </Badge>
  );
}
