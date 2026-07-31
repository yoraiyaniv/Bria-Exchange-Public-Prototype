"use client";

import type { VerifyResponse, ExchangeResult, ClaimResult } from "@/lib/api";
import ShareButtons from "./ShareButtons";
import ExchangeCard from "./ExchangeCard";
import ClaimRow from "./ClaimRow";

interface ResultViewProps {
  data: VerifyResponse | ExchangeResult;
  onReset?: () => void;
  resetLabel?: string;
}

export default function ResultView({ data, onReset, resetLabel }: ResultViewProps) {
  const result = data.result;
  const coverage = result.coverage;
  const resultId = "result_id" in data ? data.result_id : "";
  const hasContradictions = coverage.contradicted > 0;

  const allClaims: ClaimResult[] = result.sentences.flatMap((s) => s.claims);

  const sortedClaims = [...allClaims].sort((a, b) => {
    const order: Record<string, number> = {
      contradicted: 0,
      unsupported: 1,
      corroborated: 2,
      out_of_scope: 3,
    };
    return (order[a.status] ?? 3) - (order[b.status] ?? 3);
  });

  const summaryParts: string[] = [];
  if (coverage.corroborated > 0)
    summaryParts.push(`${coverage.corroborated} corroborated`);
  if (coverage.contradicted > 0)
    summaryParts.push(`${coverage.contradicted} contradicted`);
  if (coverage.unsupported > 0)
    summaryParts.push(`${coverage.unsupported} unsupported`);

  const verdictCounts: Array<{
    label: string;
    count: number;
    dot: string;
  }> = [
    { label: "corroborated", count: coverage.corroborated, dot: "bg-[#5BC29E]" },
    { label: "contradicted", count: coverage.contradicted, dot: "bg-[#E8354A]" },
    { label: "unsupported", count: coverage.unsupported, dot: "bg-[#F59E0B]" },
    { label: "out of scope", count: coverage.out_of_scope, dot: "bg-text-muted" },
  ].filter((v) => v.count > 0);

  return (
    <div className="w-full space-y-6">
      {/* Top bar */}
      <div className="flex items-center justify-between">
        {onReset && (
          <button
            onClick={onReset}
            className="font-body text-sm font-semibold text-bria-purple-2 hover:text-bria-purple"
          >
            &larr; {resetLabel ?? "Check something else"}
          </button>
        )}
        {data.source_url && data.publication && (
          <span className="rounded-full border border-border px-3 py-1 font-body text-xs text-text-secondary truncate max-w-[300px]">
            Checked: {data.publication} — {data.source_url}
          </span>
        )}
      </div>

      {/* Verdict banner */}
      <div
        className={`rounded-lg p-5 ring-1 ${
          hasContradictions
            ? "ring-[#E8354A]/20 bg-[#E8354A]/8"
            : coverage.unsupported > 0
              ? "ring-[#F59E0B]/20 bg-[#F59E0B]/8"
              : "ring-[#5BC29E]/20 bg-[#5BC29E]/8"
        }`}
      >
        <h2 className="font-heading text-2xl font-bold tracking-tight text-text-primary">
          {hasContradictions
            ? `Sources disagree on ${coverage.contradicted} claim${coverage.contradicted !== 1 ? "s" : ""}.`
            : coverage.unsupported > 0
              ? `${coverage.corroborated} claim${coverage.corroborated !== 1 ? "s" : ""} corroborated, ${coverage.unsupported} unsupported.`
              : "Sources hold up."}
        </h2>
        <p className="mt-1 font-body text-sm text-text-secondary">
          {coverage.total_claims} claims — {summaryParts.join(", ")}
        </p>
        <div className="mt-3 flex flex-wrap gap-2">
          {verdictCounts.map((v) => (
            <span
              key={v.label}
              className="inline-flex items-center gap-1.5 rounded-full border border-border bg-card px-3 py-1 font-body text-xs font-semibold text-text-primary"
            >
              <span className={`h-2 w-2 rounded-full ${v.dot}`} />
              {v.count} {v.label}
            </span>
          ))}
        </div>
      </div>

      {/* Share buttons */}
      <ShareButtons
        resultId={resultId}
        verdict={data.verdict}
        coverage={coverage}
      />

      {/* Exchange Card */}
      <ExchangeCard
        verdict={data.verdict}
        coverage={coverage}
        claims={allClaims}
        sourceUrl={data.source_url}
        publication={data.publication}
        date={"created_at" in data ? data.created_at : undefined}
      />

      {/* Original text */}
      {result.input_text && (
        <details className="group card-elevated p-4">
          <summary className="cursor-pointer font-heading text-lg font-bold tracking-tight text-text-primary select-none">
            Original text
            <span className="ml-2 text-xs font-normal text-text-secondary group-open:hidden">
              (click to expand)
            </span>
          </summary>
          <p className="mt-3 whitespace-pre-wrap font-body text-sm leading-relaxed text-text-secondary">
            {result.input_text}
          </p>
        </details>
      )}

      {/* Full claim breakdown */}
      <div className="space-y-2">
        <h3 className="font-heading text-lg font-bold tracking-tight text-text-primary">
          All claims
        </h3>
        {sortedClaims.map((claim, i) => (
          <ClaimRow
            key={i}
            claim={claim}
            defaultOpen={claim.status === "contradicted"}
          />
        ))}
      </div>
    </div>
  );
}
