import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

// Domain badges use Sora + 4px radius
const BADGE_BASE = "font-mono rounded-[4px] border tracking-wide";

const DOMAIN_STYLES: Record<string, { bg: string; text: string; border: string }> = {
  pharma:         { bg: "bg-purple-500/10",               text: "text-purple-400",             border: "border-purple-500/20" },
  legal:          { bg: "bg-[var(--bria-blue-dim)]",      text: "text-[var(--bria-blue)]",     border: "border-[rgba(125,41,242,0.2)]" },
  financial:      { bg: "bg-[var(--bria-green-dim)]",     text: "text-[var(--bria-green)]",    border: "border-[rgba(16,185,129,0.2)]" },
  news_editorial: { bg: "bg-secondary",                   text: "text-muted-foreground",       border: "border-border" },
};

const DOMAIN_LABELS: Record<string, string> = {
  pharma:         "Pharma",
  legal:          "Legal",
  financial:      "Financial",
  news_editorial: "News & Editorial",
};

interface DomainBadgeProps {
  domain: string;
  size?: "sm" | "md";
}

export function DomainBadge({ domain, size = "sm" }: DomainBadgeProps) {
  const s = DOMAIN_STYLES[domain] || { bg: "bg-secondary", text: "text-muted-foreground", border: "border-border" };
  return (
    <Badge
      variant="outline"
      className={cn(
        BADGE_BASE,
        s.bg, s.text, s.border,
        size === "sm" ? "text-[10px] px-1.5 py-0" : "text-[11px] px-2 py-0.5"
      )}
    >
      {DOMAIN_LABELS[domain] || domain}
    </Badge>
  );
}
