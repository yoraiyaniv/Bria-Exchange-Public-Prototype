"use client";

import { useState } from "react";
import { ChevronDown, ChevronRight, Copy, Check } from "lucide-react";
import type { ClaimResult, ContradictedFix, UnsupportedFix } from "@/lib/api";

const STATUS_STYLES: Record<
  string,
  { dot: string; badge: string; label: string }
> = {
  corroborated: {
    dot: "bg-[#5BC29E]",
    badge: "bg-[#5BC29E]/15 text-[#5BC29E]",
    label: "Corroborated",
  },
  contradicted: {
    dot: "bg-[#E8354A]",
    badge: "bg-[#E8354A]/15 text-[#E8354A]",
    label: "Contradicted",
  },
  unsupported: {
    dot: "bg-[#F59E0B]",
    badge: "bg-[#F59E0B]/15 text-[#F59E0B]",
    label: "Unsupported",
  },
  out_of_scope: {
    dot: "bg-text-muted",
    badge: "bg-surface-3 text-text-secondary",
    label: "Out of scope",
  },
};

interface ClaimRowProps {
  claim: ClaimResult;
  defaultOpen?: boolean;
}

export default function ClaimRow({ claim, defaultOpen = false }: ClaimRowProps) {
  const [open, setOpen] = useState(defaultOpen);
  const [copied, setCopied] = useState(false);

  const style = STATUS_STYLES[claim.status] ?? STATUS_STYLES.out_of_scope;

  const correctionText =
    claim.status === "contradicted"
      ? (claim.fix as ContradictedFix | null)?.suggested_text
      : claim.status === "unsupported"
        ? (claim.fix as UnsupportedFix | null)?.suggestion
        : null;

  function handleCopyCorrection() {
    if (!correctionText) return;
    navigator.clipboard.writeText(correctionText);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  return (
    <div className="card-elevated">
      <button
        onClick={() => setOpen(!open)}
        className="flex w-full items-center gap-3 px-4 py-3 text-left"
      >
        <span className={`h-2.5 w-2.5 flex-shrink-0 rounded-full ${style.dot}`} />
        <span className="flex-1 font-body text-sm text-text-primary">
          {claim.text}
        </span>
        <span
          className={`rounded-full px-2.5 py-0.5 font-body text-xs font-semibold ${style.badge}`}
        >
          {style.label}
        </span>
        {open ? (
          <ChevronDown className="h-4 w-4 text-text-muted" />
        ) : (
          <ChevronRight className="h-4 w-4 text-text-muted" />
        )}
      </button>

      {open && (
        <div className="border-t border-border px-4 py-3 space-y-3">
          {claim.sources.length > 0 && (
            <div className="space-y-1">
              {claim.sources.map((source, i) => (
                <div key={i} className="font-body text-sm text-text-secondary">
                  <span className="font-semibold text-text-primary">
                    {source.name}
                  </span>
                  {" — "}
                  {source.detail.summary}
                </div>
              ))}
            </div>
          )}

          {correctionText && (
            <div className="rounded-lg border border-bria-purple/30 bg-bria-purple/10 p-3 space-y-2">
              <span className="font-body text-[10px] font-semibold uppercase tracking-wider text-bria-purple-2">
                Suggested correction
              </span>
              <p className="font-body text-sm text-text-primary">
                {correctionText}
              </p>
              <button
                onClick={handleCopyCorrection}
                className="inline-flex items-center gap-1.5 rounded-full border border-bria-purple/30 bg-secondary px-3 py-1.5 font-body text-xs font-semibold text-bria-purple-2 transition-colors hover:bg-bria-purple/10"
              >
                {copied ? (
                  <Check className="h-3 w-3" />
                ) : (
                  <Copy className="h-3 w-3" />
                )}
                {copied ? "Copied!" : "Copy correction"}
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
