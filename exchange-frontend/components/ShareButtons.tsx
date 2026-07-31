"use client";

import { useState } from "react";
import { Check, Copy, Link, Share2 } from "lucide-react";
import type { Coverage } from "@/lib/api";

interface ShareButtonsProps {
  resultId: string;
  verdict: string;
  coverage: Coverage;
}

const APP_URL =
  typeof window !== "undefined"
    ? window.location.origin
    : process.env.NEXT_PUBLIC_APP_URL || "https://verify.briaexchange.com";

export default function ShareButtons({
  resultId,
  coverage,
}: ShareButtonsProps) {
  const [copiedLink, setCopiedLink] = useState(false);
  const [copiedCard, setCopiedCard] = useState(false);

  const shareUrl = `${APP_URL}/check/${resultId}`;
  const hasContradictions = coverage.contradicted > 0;

  const shareText = hasContradictions
    ? `Checked this. Sources disagree on ${coverage.contradicted} claim${coverage.contradicted !== 1 ? "s" : ""}. ${shareUrl}`
    : coverage.unsupported > 0
      ? `Checked this. ${coverage.corroborated} claim${coverage.corroborated !== 1 ? "s" : ""} corroborated, ${coverage.unsupported} unsupported. ${shareUrl}`
      : `Checked this. Sources hold up. ${coverage.corroborated} claim${coverage.corroborated !== 1 ? "s" : ""} corroborated. ${shareUrl}`;

  const cardText = [
    "EXCHANGE CHECK",
    "",
    hasContradictions
      ? `Sources disagree on ${coverage.contradicted} claims.`
      : coverage.unsupported > 0
        ? `${coverage.corroborated} claims corroborated, ${coverage.unsupported} unsupported.`
        : "Sources hold up.",
    `${coverage.total_claims} claims — ${coverage.corroborated} corroborated, ${coverage.contradicted} contradicted, ${coverage.unsupported} unsupported`,
    "",
    shareUrl,
  ].join("\n");

  function handleCopyLink() {
    navigator.clipboard.writeText(shareUrl);
    setCopiedLink(true);
    setTimeout(() => setCopiedLink(false), 2000);
  }

  function handleCopyCard() {
    navigator.clipboard.writeText(cardText);
    setCopiedCard(true);
    setTimeout(() => setCopiedCard(false), 2000);
  }

  function handleShareX() {
    window.open(
      `https://twitter.com/intent/tweet?text=${encodeURIComponent(shareText)}`,
      "_blank",
      "noopener,noreferrer"
    );
  }

  function handleShareLinkedIn() {
    window.open(
      `https://www.linkedin.com/sharing/share-offsite/?url=${encodeURIComponent(shareUrl)}`,
      "_blank",
      "noopener,noreferrer"
    );
  }

  const btnClass =
    "inline-flex items-center gap-2 rounded-full border border-border px-4 py-2 font-body text-sm font-semibold text-text-secondary transition-colors hover:border-bria-purple hover:text-bria-purple-2 hover:bg-bria-purple/10";

  return (
    <div className="flex flex-wrap gap-2 max-sm:fixed max-sm:bottom-0 max-sm:left-0 max-sm:right-0 max-sm:bg-background max-sm:border-t max-sm:border-border max-sm:p-3 max-sm:z-50">
      <button onClick={handleShareX} className={btnClass}>
        <Share2 className="h-4 w-4" /> Share on X
      </button>
      <button onClick={handleShareLinkedIn} className={btnClass}>
        <Share2 className="h-4 w-4" /> Share on LinkedIn
      </button>
      <button onClick={handleCopyLink} className={btnClass}>
        {copiedLink ? <Check className="h-4 w-4" /> : <Link className="h-4 w-4" />}
        {copiedLink ? "Copied!" : "Copy link"}
      </button>
      <button onClick={handleCopyCard} className={btnClass}>
        {copiedCard ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
        {copiedCard ? "Copied!" : "Copy card text"}
      </button>
    </div>
  );
}
