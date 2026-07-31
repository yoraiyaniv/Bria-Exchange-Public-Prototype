"use client";

import Link from "next/link";
import { AlertCircle, ArrowRight } from "lucide-react";

interface PendingReviewBannerProps {
  count: number;
  hasBlock: boolean;
}

export function PendingReviewBanner({ count, hasBlock }: PendingReviewBannerProps) {
  return (
    <div
      className="flex items-center justify-between px-4 py-2.5 rounded-lg border text-sm"
      style={hasBlock
        ? { background: "var(--bria-red-dim)",   border: "1px solid rgba(239,68,68,0.3)",   color: "var(--bria-red)" }
        : { background: "var(--bria-amber-dim)", border: "1px solid rgba(245,158,11,0.3)", color: "var(--bria-amber)" }
      }
    >
      <div className="flex items-center gap-2">
        <AlertCircle className="h-4 w-4 shrink-0" />
        <span>
          <strong>{count}</strong> verification{count !== 1 ? "s" : ""} pending review
          {hasBlock && " — includes blocked content"}
        </span>
      </div>
      <Link
        href="/review"
        className="flex items-center gap-1 text-xs font-medium hover:underline"
      >
        View Queue <ArrowRight className="h-3 w-3" />
      </Link>
    </div>
  );
}
