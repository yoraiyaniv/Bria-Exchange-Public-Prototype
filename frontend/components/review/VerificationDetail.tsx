"use client";

import { useState } from "react";
import { Verification, verifyApi, ClaimResult, VerificationResponse } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { StatusBadge } from "@/components/shared/DecisionBadge";
import { Badge } from "@/components/ui/badge";
import { CheckCircle, XCircle, ExternalLink, ChevronDown, ChevronUp, RefreshCw } from "lucide-react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import { extractClaims, ClaimRow, NormalizedClaim } from "@/components/shared/ClaimRow";

interface VerificationDetailProps {
  verification: Verification;
  token: string;
  userId: string;
  onComplete: (id: string, outcome: "approved" | "rejected") => void;
}

interface ReviewAction {
  claimText: string;
  action: string;
  note?: string;
  reviewedBy?: string;
  reviewedAt?: string;
}

export function VerificationDetail({ verification, token, onComplete }: VerificationDetailProps) {
  const [reviewNote, setReviewNote] = useState("");
  const [submitting, setSubmitting] = useState<"approved" | "rejected" | null>(null);
  const [expandedClaims, setExpandedClaims] = useState<Set<number>>(new Set());
  const [reviewActions, setReviewActions] = useState<ReviewAction[]>([]);
  const [correctedText, setCorrectedText] = useState(verification.correctedText || "");
  const [reVerifying, setReVerifying] = useState(false);

  const fullResponse = verification.fullResponse as VerificationResponse;
  const policy = verification.config;
  const requireNote = policy?.require_acknowledgement_note;

  // Sentences shape (structured API response)
  const allClaims: ClaimResult[] = fullResponse?.sentences?.flatMap(s => s.claims) || [];
  const nonPassClaims = allClaims.filter(c => c.status !== "corroborated");

  // Flat shape fallback (MCP server response — has reasoning + citations)
  const flatClaims: NormalizedClaim[] = allClaims.length === 0
    ? extractClaims(fullResponse)
    : [];

  function toggleClaim(i: number) {
    setExpandedClaims(prev => {
      const next = new Set(prev);
      if (next.has(i)) next.delete(i);
      else next.add(i);
      return next;
    });
  }

  function addReviewAction(claimText: string, action: string, note?: string) {
    setReviewActions(prev => {
      const existing = prev.findIndex(a => a.claimText === claimText);
      const entry: ReviewAction = { claimText, action, note, reviewedBy: undefined, reviewedAt: new Date().toISOString() };
      if (existing >= 0) {
        const next = [...prev];
        next[existing] = entry;
        return next;
      }
      return [...prev, entry];
    });
  }

  async function handleSubmit(outcome: "approved" | "rejected") {
    // Note is only required when REJECTING (overriding ground truth needs justification).
    // Approval never requires a note — accepting the verification as-is is a valid one-click action.
    if (outcome === "rejected" && requireNote && !reviewNote.trim()) {
      toast.error("A justification note is required when rejecting this verification");
      return;
    }
    setSubmitting(outcome);
    try {
      await verifyApi.submitReview(token, verification.id, {
        reviewActions,
        correctedText,
        outcome,
        reviewNote: reviewNote || undefined,
      });
      onComplete(verification.id, outcome);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Submit failed");
      setSubmitting(null);
    }
  }

  async function handleReVerify() {
    setReVerifying(true);
    try {
      await verifyApi.run(token, {
        text: correctedText || verification.inputText,
        config: policy,
        agentId: verification.agentId || undefined,
        parentVerificationId: verification.id,
      });
      toast.success("Re-verification submitted — check the queue");
    } catch {
      toast.error("Re-verification failed");
    } finally {
      setReVerifying(false);
    }
  }

  return (
    <div className="p-6 space-y-6">
      {/* Coverage summary */}
      {(() => {
        const wordCount = verification.inputText ? verification.inputText.trim().split(/\s+/).length : 0;
        const wordsPerClaim = verification.totalClaims > 0 ? Math.round(wordCount / verification.totalClaims) : null;
        return (
          <div className="grid grid-cols-6 gap-2 text-center text-xs">
            {[
              { label: "Total", value: verification.totalClaims, color: "text-foreground" },
              { label: "Corroborated", value: verification.corroboratedCount, color: "text-emerald-400" },
              { label: "Contradicted", value: verification.contradictedCount, color: "text-red-400" },
              { label: "Unsupported", value: verification.unsupportedCount, color: "text-amber-400" },
              { label: "Out of Scope", value: verification.outOfScopeCount, color: "text-muted-foreground" },
            ].map(s => (
              <div key={s.label} className="bg-secondary rounded p-2">
                <p className={`text-base font-bold font-mono ${s.color}`}>{s.value}</p>
                <p className="text-[10px] text-muted-foreground">{s.label}</p>
              </div>
            ))}
            <div className="bg-secondary rounded p-2">
              <p className="text-base font-bold font-mono text-foreground">{wordsPerClaim ?? "—"}</p>
              <p className="text-[10px] text-muted-foreground">Words / Claim</p>
            </div>
          </div>
        );
      })()}

      {/* Flat claims (MCP shape) — shows reasoning + citations inline via ClaimRow */}
      {flatClaims.length > 0 && (
        <div className="space-y-2">
          <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
            Claims ({flatClaims.filter(c => c.status === "corroborated").length}✓{" "}
            {flatClaims.filter(c => c.status === "contradicted").length}✗{" "}
            {flatClaims.filter(c => c.status === "unsupported").length}?{" "}
            {flatClaims.filter(c => c.status === "out_of_scope").length} oos)
          </h3>
          <div className="space-y-1.5">
            {flatClaims.map((claim, i) => (
              <div key={i} className="space-y-1">
                <ClaimRow claim={claim} />
                {claim.status !== "corroborated" && (
                  <div className="flex flex-wrap gap-2 pl-6">
                    {claim.status === "contradicted" && (
                      <Button size="sm" variant="outline" className="h-6 text-[11px] text-emerald-400 border-emerald-400/40"
                        onClick={() => addReviewAction(claim.text, "applied_fix")}>
                        Apply Fix
                      </Button>
                    )}
                    {claim.status === "unsupported" && (
                      <>
                        <Button size="sm" variant="outline" className="h-6 text-[11px]"
                          onClick={() => addReviewAction(claim.text, "qualified")}>Qualify</Button>
                        <Button size="sm" variant="outline" className="h-6 text-[11px] text-red-400 border-red-400/40"
                          onClick={() => addReviewAction(claim.text, "removed")}>Remove</Button>
                      </>
                    )}
                    {claim.status === "out_of_scope" && (
                      <Button size="sm" variant="outline" className="h-6 text-[11px] text-amber-400 border-amber-400/40"
                        onClick={() => addReviewAction(claim.text, "escalated")}>Escalate</Button>
                    )}
                    <Button size="sm" variant="ghost" className="h-6 text-[11px] text-muted-foreground"
                      onClick={() => addReviewAction(claim.text, "acknowledged")}>
                      Acknowledge Risk
                    </Button>
                    {reviewActions.find(a => a.claimText === claim.text) && (
                      <Badge variant="outline" className="text-[10px] border-purple-400/40 text-purple-400 bg-purple-400/10">
                        {reviewActions.find(a => a.claimText === claim.text)?.action}
                      </Badge>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Claims that need attention */}
      {nonPassClaims.length > 0 && (
        <div className="space-y-2">
          <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Claims Requiring Review</h3>
          {allClaims.map((claim, i) => {
            if (claim.status === "corroborated") return null;
            const isExpanded = expandedClaims.has(i);
            const action = reviewActions.find(a => a.claimText === claim.text);

            return (
              <div key={i} className="border border-border rounded-lg overflow-hidden">
                <button
                  onClick={() => toggleClaim(i)}
                  className="w-full flex items-start gap-3 p-3 text-left hover:bg-secondary/50 transition-colors"
                >
                  <StatusBadge status={claim.status} size="sm" />
                  <p className="flex-1 text-xs text-foreground">{claim.text}</p>
                  {action && (
                    <Badge variant="outline" className="text-[10px] border-purple-400/40 text-purple-400 bg-purple-400/10">
                      {action.action}
                    </Badge>
                  )}
                  {isExpanded ? <ChevronUp className="h-3.5 w-3.5 text-muted-foreground shrink-0" /> : <ChevronDown className="h-3.5 w-3.5 text-muted-foreground shrink-0" />}
                </button>

                {isExpanded && (
                  <div className="border-t border-border p-3 space-y-3 bg-secondary/30">
                    {/* Source detail */}
                    {claim.sources.map((src, si) => (
                      <div key={si} className="space-y-1.5 p-2 bg-secondary rounded text-xs">
                        <div className="flex items-center gap-2">
                          <span className="font-medium text-foreground">{src.name}</span>
                          <Badge variant="outline" className="text-[10px] border-border">{src.authority_level}</Badge>
                          <Badge variant="outline" className={cn("text-[10px] border-border", {
                            "text-emerald-400": src.freshness === "current",
                            "text-amber-400": src.freshness === "aging",
                            "text-red-400": src.freshness === "stale" || src.freshness === "deprecated",
                          })}>{src.freshness}</Badge>
                          {src.url && (
                            <a href={src.url} target="_blank" rel="noreferrer" className="text-primary hover:underline flex items-center gap-0.5">
                              View source <ExternalLink className="h-2.5 w-2.5" />
                            </a>
                          )}
                        </div>
                        <div className="grid grid-cols-2 gap-2 text-[11px]">
                          <div>
                            <p className="text-muted-foreground">AI asserted:</p>
                            <p className="text-foreground">{src.detail.ai_asserted}</p>
                          </div>
                          <div>
                            <p className="text-muted-foreground">Source states:</p>
                            <p className="text-foreground">{src.detail.source_states}</p>
                          </div>
                        </div>
                        {src.detail.discrepancy_type && (
                          <p className="text-[10px] text-amber-400">Discrepancy: {src.detail.discrepancy_type.replace(/_/g, " ")}</p>
                        )}
                      </div>
                    ))}

                    {/* Fix suggestion */}
                    {claim.fix && (
                      <div className="bg-primary/10 border border-primary/30 rounded p-2 text-xs space-y-1">
                        <p className="text-primary font-medium text-[11px]">Suggested fix</p>
                        {"suggested_text" in claim.fix && claim.fix.suggested_text && (
                          <p className="text-foreground">{claim.fix.suggested_text}</p>
                        )}
                        {"suggestion" in claim.fix && claim.fix.suggestion && (
                          <p className="text-foreground">{claim.fix.suggestion}</p>
                        )}
                      </div>
                    )}

                    {/* Actions */}
                    <div className="flex flex-wrap gap-2">
                      {claim.status === "contradicted" && (
                        <Button size="sm" variant="outline" className="h-6 text-[11px] text-emerald-400 border-emerald-400/40"
                          onClick={() => addReviewAction(claim.text, "applied_fix")}>
                          Apply Fix
                        </Button>
                      )}
                      {claim.status === "unsupported" && (
                        <>
                          <Button size="sm" variant="outline" className="h-6 text-[11px]"
                            onClick={() => addReviewAction(claim.text, "qualified")}>Qualify</Button>
                          <Button size="sm" variant="outline" className="h-6 text-[11px] text-red-400 border-red-400/40"
                            onClick={() => addReviewAction(claim.text, "removed")}>Remove</Button>
                        </>
                      )}
                      {claim.status === "out_of_scope" && (
                        <Button size="sm" variant="outline" className="h-6 text-[11px] text-amber-400 border-amber-400/40"
                          onClick={() => addReviewAction(claim.text, "escalated")}>Escalate</Button>
                      )}
                      <Button size="sm" variant="ghost" className="h-6 text-[11px] text-muted-foreground"
                        onClick={() => addReviewAction(claim.text, "acknowledged")}>
                        Acknowledge Risk
                      </Button>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* Corrected text editor */}
      <div className="space-y-2">
        <label className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Corrected Text</label>
        <textarea
          className="w-full h-32 text-xs bg-input border border-border rounded p-2.5 text-foreground placeholder-muted-foreground resize-none focus:outline-none focus:ring-1 focus:ring-primary"
          value={correctedText || verification.inputText}
          onChange={e => setCorrectedText(e.target.value)}
          placeholder="Edit the corrected version of the text..."
        />
      </div>

      {/* Review note */}
      <div className="space-y-2">
        <label className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
          Review Note {requireNote && <span className="text-amber-400">*required when rejecting</span>}
        </label>
        <textarea
          className="w-full h-20 text-xs bg-input border border-border rounded p-2.5 text-foreground placeholder-muted-foreground resize-none focus:outline-none focus:ring-1 focus:ring-primary"
          value={reviewNote}
          onChange={e => setReviewNote(e.target.value)}
          placeholder={requireNote ? "Required when rejecting — explain why you're overriding the ground truth..." : "Optional: add a note about your review decision..."}
        />
      </div>

      {/* Actions */}
      <div className="flex items-center gap-3 pt-2 border-t border-border">
        <Button
          variant="outline"
          size="sm"
          disabled={reVerifying}
          onClick={handleReVerify}
          className="gap-1.5"
        >
          <RefreshCw className={cn("h-3.5 w-3.5", reVerifying && "animate-spin")} />
          {reVerifying ? "Re-verifying..." : "Re-verify"}
        </Button>
        <div className="flex-1" />
        <Button
          variant="outline"
          size="sm"
          disabled={!!submitting}
          onClick={() => handleSubmit("rejected")}
          className="gap-1.5 text-red-400 border-red-400/40 hover:bg-red-400/10"
        >
          <XCircle className="h-3.5 w-3.5" />
          {submitting === "rejected" ? "Rejecting..." : "Reject"}
        </Button>
        <Button
          size="sm"
          disabled={!!submitting}
          onClick={() => handleSubmit("approved")}
          className="gap-1.5"
        >
          <CheckCircle className="h-3.5 w-3.5" />
          {submitting === "approved" ? "Approving..." : "Approve"}
        </Button>
      </div>
    </div>
  );
}
