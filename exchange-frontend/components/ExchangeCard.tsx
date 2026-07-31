"use client";

import type { ClaimResult, Coverage } from "@/lib/api";

const VERDICT_DOTS: Record<string, string> = {
  corroborated: "bg-[#5BC29E]",
  contradicted: "bg-[#E8354A]",
  unsupported: "bg-[#F59E0B]",
  out_of_scope: "bg-text-muted",
};

interface ExchangeCardProps {
  verdict: string;
  coverage: Coverage;
  claims: ClaimResult[];
  sourceUrl?: string | null;
  publication?: string | null;
  date?: string | null;
}

export default function ExchangeCard({
  coverage,
  claims,
  publication,
  date,
}: ExchangeCardProps) {
  const hasContradictions = coverage.contradicted > 0;
  const headline = hasContradictions
    ? `Sources disagree on ${coverage.contradicted} claim${coverage.contradicted !== 1 ? "s" : ""}.`
    : coverage.unsupported > 0
      ? `${coverage.corroborated} claim${coverage.corroborated !== 1 ? "s" : ""} corroborated, ${coverage.unsupported} unsupported.`
      : "Sources hold up.";

  const sortedClaims = [...claims].sort((a, b) => {
    const order = { contradicted: 0, unsupported: 1, corroborated: 2, out_of_scope: 3 };
    return (order[a.status] ?? 3) - (order[b.status] ?? 3);
  });
  const topClaims = sortedClaims.slice(0, 3);

  const dateStr = date
    ? new Date(date).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })
    : new Date().toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });

  return (
    <div className="card-elevated overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between bg-muted px-4 py-2.5">
        <span className="font-heading text-[13px] font-bold tracking-wider text-text-primary">
          EXCHANGE CHECK
        </span>
        <span className="font-heading text-[13px] font-bold text-text-secondary">
          {dateStr}
        </span>
      </div>

      {/* Body */}
      <div className="space-y-3 p-4">
        <h3 className="font-heading text-lg font-bold tracking-tight text-text-primary">
          {headline}
        </h3>

        {publication && (
          <p className="font-body text-sm text-text-secondary">
            Source: {publication}
          </p>
        )}

        <div className="space-y-2">
          {topClaims.map((claim, i) => (
            <div key={i} className="flex items-start gap-2">
              <span
                className={`mt-1.5 h-2 w-2 flex-shrink-0 rounded-full ${VERDICT_DOTS[claim.status] ?? VERDICT_DOTS.out_of_scope}`}
              />
              <span className="font-body text-sm text-text-primary line-clamp-2">
                {claim.text}
              </span>
            </div>
          ))}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between border-t border-border pt-3">
          <span className="font-body text-xs text-text-muted">
            verify.briaexchange.com
          </span>
          <span className="font-body text-xs text-text-muted">
            {coverage.total_claims} claims &middot; {coverage.corroborated}{" "}
            corroborated &middot; {coverage.contradicted} contradicted
            {coverage.unsupported > 0 && <> &middot; {coverage.unsupported} unsupported</>}
          </span>
        </div>
      </div>
    </div>
  );
}
