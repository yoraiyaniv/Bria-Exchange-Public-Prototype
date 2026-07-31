"use client";

import type { PreviewClaim, VerifiedClaim } from "@/lib/api";
import { Loader2 } from "lucide-react";

interface ProcessingViewProps {
  phase: string;
  previewClaims: PreviewClaim[];
  verifiedClaims: VerifiedClaim[];
  publication?: string | null;
}

const VERDICT_COLORS: Record<string, string> = {
  corroborated: "bg-[#5BC29E]",
  contradicted: "bg-[#E8354A]",
  unsupported: "bg-[#F59E0B]",
  out_of_scope: "bg-text-muted",
};

const VERDICT_BADGE: Record<string, string> = {
  corroborated: "bg-[#5BC29E]/15 text-[#5BC29E]",
  contradicted: "bg-[#E8354A]/15 text-[#E8354A]",
  unsupported: "bg-[#F59E0B]/15 text-[#F59E0B]",
  out_of_scope: "bg-surface-3 text-text-secondary",
};

const PHASE_LABELS: Record<string, string> = {
  fetching_url: "Fetching page content...",
  url_fetched: "Page fetched. Extracting claims...",
  verifying: "Checking claims against sources...",
};

export default function ProcessingView({
  phase,
  previewClaims,
  verifiedClaims,
  publication,
}: ProcessingViewProps) {
  const verifiedTexts = new Set(
    verifiedClaims.map((c) => c.text.toLowerCase().trim())
  );

  const totalExpected = previewClaims.length || verifiedClaims.length;
  const doneCount = verifiedClaims.length;
  const progress = totalExpected > 0 ? (doneCount / totalExpected) * 100 : 0;
  const isVerifying = phase === "verifying" && verifiedClaims.length > 0;

  return (
    <div className="w-full space-y-6">
      <div>
        <h2 className="font-heading text-2xl font-bold tracking-tight text-text-primary">
          {PHASE_LABELS[phase] || "Checking against sources..."}
        </h2>
        {publication && (
          <p className="mt-1 font-body text-sm text-text-secondary">
            Source: {publication}
          </p>
        )}
        <div className="mt-3 h-1.5 w-full overflow-hidden rounded-full bg-muted">
          <div
            className="h-full rounded-full bg-bria-purple transition-all duration-500 ease-out"
            style={{
              width: isVerifying ? `${Math.max(5, progress)}%` : undefined,
              animation: !isVerifying
                ? "indeterminate 1.5s ease-in-out infinite"
                : "none",
            }}
          />
        </div>
        {isVerifying && (
          <p className="mt-1 font-body text-xs text-text-secondary">
            {doneCount} of {totalExpected} claims verified
          </p>
        )}
      </div>

      <style jsx>{`
        @keyframes indeterminate {
          0% { width: 0%; margin-left: 0%; }
          50% { width: 40%; margin-left: 30%; }
          100% { width: 0%; margin-left: 100%; }
        }
      `}</style>

      <div className="space-y-2">
        {verifiedClaims.map((claim, i) => (
          <div
            key={`verified-${i}`}
            className="flex items-center gap-3 card-elevated px-4 py-3 animate-in fade-in duration-300"
          >
            <span
              className={`h-2.5 w-2.5 flex-shrink-0 rounded-full ${VERDICT_COLORS[claim.status]}`}
            />
            <span className="flex-1 truncate font-body text-sm text-text-primary">
              {claim.text}
            </span>
            <span
              className={`rounded-full px-2.5 py-0.5 font-body text-xs font-semibold capitalize ${VERDICT_BADGE[claim.status]}`}
            >
              {claim.status.replace("_", " ")}
            </span>
          </div>
        ))}

        {previewClaims
          .filter((pc) => !verifiedTexts.has(pc.text.toLowerCase().trim()))
          .map((claim, i) => (
            <div
              key={`preview-${i}`}
              className="flex items-center gap-3 card-elevated px-4 py-3"
            >
              <Loader2 className="h-3.5 w-3.5 flex-shrink-0 animate-spin text-bria-purple" />
              <span className="flex-1 truncate font-body text-sm text-text-secondary">
                {claim.text}
              </span>
              <span className="rounded-full bg-bria-purple/15 px-2.5 py-0.5 font-body text-xs font-semibold text-bria-purple-2">
                checking...
              </span>
            </div>
          ))}

        {previewClaims.length === 0 &&
          verifiedClaims.length === 0 &&
          Array.from({ length: 4 }).map((_, i) => (
            <div
              key={`skeleton-${i}`}
              className="flex items-center gap-3 card-elevated px-4 py-3"
            >
              <span className="h-2.5 w-2.5 flex-shrink-0 rounded-full bg-muted animate-pulse" />
              <span className="h-4 flex-1 rounded bg-muted animate-pulse" />
            </div>
          ))}
      </div>
    </div>
  );
}
