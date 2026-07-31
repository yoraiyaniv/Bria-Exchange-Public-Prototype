"use client";

import { useEffect, useState } from "react";
import { useSession } from "next-auth/react";
import { useRouter } from "next/navigation";
import Logo from "@/components/Logo";
import { getResults } from "@/lib/api";
import type { ExchangeResultSummary, PaginatedResults } from "@/lib/api";

const VERDICT_DOTS: Record<string, string> = {
  corroborated: "bg-[#5BC29E]",
  contradicted: "bg-[#E8354A]",
  unsupported: "bg-[#F59E0B]",
  out_of_scope: "bg-text-muted",
};

export default function HistoryPage() {
  const { data: session, status } = useSession();
  const router = useRouter();
  const [results, setResults] = useState<ExchangeResultSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [verdictFilter, setVerdictFilter] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const limit = 20;

  useEffect(() => {
    if (status === "unauthenticated") { router.push("/login"); return; }
    if (!session?.accessToken) return;
    setLoading(true);
    getResults(session.accessToken, { verdict: verdictFilter || undefined, limit, offset })
      .then((data: PaginatedResults) => { setResults(data.results); setTotal(data.total); })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [session?.accessToken, status, router, verdictFilter, offset]);

  if (status === "loading") {
    return (
      <main className="flex min-h-screen items-center justify-center">
        <p className="font-body text-text-secondary">Loading...</p>
      </main>
    );
  }

  return (
    <main className="flex min-h-screen flex-col items-center bg-background px-4 py-12">
      <div className="w-full max-w-[680px] space-y-6">
        <Logo />
        <div className="flex items-center justify-between">
          <h1 className="font-heading text-2xl font-bold tracking-tight text-text-primary">
            Your Exchange Checks
          </h1>
          <a href="/" className="font-body text-sm font-semibold text-bria-purple-2 hover:text-bria-purple">
            &larr; New check
          </a>
        </div>

        <div className="flex gap-2">
          {["", "contradicted", "corroborated", "unsupported"].map((v) => (
            <button
              key={v}
              onClick={() => { setVerdictFilter(v); setOffset(0); }}
              className={`rounded-full px-3 py-1.5 font-body text-xs font-semibold transition-colors ${
                verdictFilter === v
                  ? "bg-bria-purple text-white"
                  : "border border-border text-text-secondary hover:border-bria-purple hover:text-bria-purple-2"
              }`}
            >
              {v || "All"}
            </button>
          ))}
        </div>

        {loading ? (
          <div className="space-y-3">
            {Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="h-16 animate-pulse rounded-lg bg-muted" />
            ))}
          </div>
        ) : results.length === 0 ? (
          <p className="py-12 text-center font-body text-text-secondary">No results found.</p>
        ) : (
          <div className="space-y-2">
            {results.map((r) => (
              <a
                key={r.result_id}
                href={`/check/${r.result_id}`}
                className="flex items-center gap-3 card-elevated px-4 py-3 transition-shadow hover:shadow-[0_2px_8px_rgba(125,41,242,0.10),0_0_0_1px_rgba(125,41,242,0.15)]"
              >
                <span className={`h-2.5 w-2.5 flex-shrink-0 rounded-full ${VERDICT_DOTS[r.verdict] ?? VERDICT_DOTS.out_of_scope}`} />
                <span className="flex-1 truncate font-body text-sm text-text-primary">
                  {r.publication || r.input_text}
                </span>
                <span className="font-body text-xs text-text-muted">{r.verified_claim_count} claims</span>
                <span className="font-body text-xs text-text-muted">
                  {r.created_at ? new Date(r.created_at).toLocaleDateString("en-US", { month: "short", day: "numeric" }) : ""}
                </span>
              </a>
            ))}
          </div>
        )}

        {total > limit && (
          <div className="flex items-center justify-center gap-4">
            <button
              onClick={() => setOffset(Math.max(0, offset - limit))}
              disabled={offset === 0}
              className="rounded-full border border-border px-4 py-2 font-body text-sm font-semibold text-text-secondary disabled:opacity-50 hover:border-bria-purple hover:text-bria-purple-2"
            >
              Previous
            </button>
            <span className="font-body text-xs text-text-muted">
              {offset + 1}–{Math.min(offset + limit, total)} of {total}
            </span>
            <button
              onClick={() => setOffset(offset + limit)}
              disabled={offset + limit >= total}
              className="rounded-full border border-border px-4 py-2 font-body text-sm font-semibold text-text-secondary disabled:opacity-50 hover:border-bria-purple hover:text-bria-purple-2"
            >
              Next
            </button>
          </div>
        )}
      </div>
    </main>
  );
}
