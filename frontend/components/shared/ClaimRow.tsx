"use client";

import { useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";

export interface NormalizedClaim {
  text: string;
  status: "corroborated" | "contradicted" | "unsupported" | "out_of_scope";
  confidence?: number;
  reasoning?: string;
  citations?: Array<{ source?: string; label?: string; value?: unknown; date?: string; identifier?: string }>;
}

const STATUS_COLORS: Record<string, string> = {
  corroborated: "text-emerald-400",
  contradicted:  "text-red-400",
  unsupported:   "text-amber-400",
  out_of_scope:  "text-muted-foreground",
};

const STATUS_DOT: Record<string, string> = {
  corroborated: "bg-emerald-400",
  contradicted:  "bg-red-400",
  unsupported:   "bg-amber-400",
  out_of_scope:  "bg-muted-foreground",
};

export function extractClaims(fullResponse: unknown): NormalizedClaim[] {
  if (!fullResponse || typeof fullResponse !== "object") return [];
  const resp = fullResponse as Record<string, unknown>;

  // MCP shape: flat claims array with confidence + reasoning + citations
  if (Array.isArray(resp.claims)) {
    return resp.claims as NormalizedClaim[];
  }

  // Dashboard shape: sentences[].claims[]
  if (Array.isArray(resp.sentences)) {
    return (resp.sentences as Array<{ claims?: NormalizedClaim[] }>)
      .flatMap(s => s.claims ?? []);
  }

  return [];
}

export function ClaimRow({ claim }: { claim: NormalizedClaim }) {
  const [open, setOpen] = useState(false);
  const hasDetail = !!claim.reasoning || (claim.citations && claim.citations.length > 0);
  const color = STATUS_COLORS[claim.status] ?? "text-muted-foreground";
  const dot   = STATUS_DOT[claim.status]   ?? "bg-muted-foreground";

  return (
    <div className="rounded border border-border overflow-hidden">
      <button
        className="w-full flex items-start gap-3 px-3 py-2 text-left hover:bg-secondary/50 transition-colors disabled:cursor-default"
        onClick={() => hasDetail && setOpen(o => !o)}
        disabled={!hasDetail}
      >
        <span className={`mt-1.5 h-1.5 w-1.5 rounded-full shrink-0 ${dot}`} />
        <span className="flex-1 text-xs text-foreground">{claim.text}</span>
        {claim.confidence !== undefined && (
          <span className={`text-[10px] font-mono shrink-0 ${color}`}>
            {Math.round(claim.confidence * 100)}%
          </span>
        )}
        <span className={`text-[10px] font-mono shrink-0 w-20 text-right ${color}`}>
          {claim.status.replace(/_/g, " ")}
        </span>
        {hasDetail && (
          open
            ? <ChevronDown className="h-3 w-3 text-muted-foreground shrink-0 mt-0.5" />
            : <ChevronRight className="h-3 w-3 text-muted-foreground shrink-0 mt-0.5" />
        )}
      </button>

      {open && hasDetail && (
        <div className="border-t border-border px-3 py-2.5 bg-secondary/30 space-y-2">
          {claim.reasoning && (
            <p className="text-xs text-muted-foreground leading-relaxed">{claim.reasoning}</p>
          )}
          {claim.citations && claim.citations.length > 0 && (
            <div className="space-y-1">
              {claim.citations.map((c, i) => (
                <div key={i} className="flex items-baseline gap-2 text-[11px]">
                  <span className="text-muted-foreground font-medium shrink-0">{c.source}</span>
                  {c.label && <span className="text-foreground">{c.label}</span>}
                  {c.value !== null && c.value !== undefined && (
                    <span className="font-mono text-primary">{String(c.value)}</span>
                  )}
                  {c.date && <span className="text-muted-foreground">({c.date})</span>}
                  {c.identifier && <span className="text-muted-foreground font-mono text-[10px]">{c.identifier}</span>}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
