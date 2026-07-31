"use client";

import { useState } from "react";
import { Session } from "next-auth";
import { Verification, verifyApi } from "@/lib/api";
import { TopBar } from "@/components/layout/TopBar";
import { DecisionBadge } from "@/components/shared/DecisionBadge";
import { DomainBadge } from "@/components/shared/DomainBadge";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { AlertCircle, Clock, CheckCircle, User, ChevronDown, ChevronRight } from "lucide-react";
import { toast } from "sonner";
import { useRouter } from "next/navigation";
import { VerificationDetail } from "./VerificationDetail";
import { ClaimRow, extractClaims } from "@/components/shared/ClaimRow";

interface ReviewPageClientProps {
  initialVerifications: Verification[];
  activeTab: string;
  error: string | null;
  userSession: Session;
}

function timeAgo(dateStr: string): string {
  const diff = Date.now() - new Date(dateStr).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}


export function ReviewPageClient({ initialVerifications, activeTab, error, userSession }: ReviewPageClientProps) {
  const router = useRouter();
  const [verifications, setVerifications] = useState(initialVerifications);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [claiming, setClaiming] = useState<string | null>(null);
  const [expandedRows, setExpandedRows] = useState<Set<string>>(new Set());
  const [claimedByMe, setClaimedByMe] = useState<Set<string>>(new Set());

  const token = userSession.accessToken;
  const userId = userSession.user.id;

  const selected = verifications.find(v => v.id === selectedId);

  function toggleRow(id: string) {
    setExpandedRows(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  async function handleClaim(v: Verification) {
    if (v.reviewStatus === "in_review" && v.reviewedBy !== userId) return;
    setClaiming(v.id);
    try {
      const updated = await verifyApi.claim(token, v.id);
      setVerifications(prev => prev.map(x => x.id === v.id ? { ...x, ...(updated as Partial<Verification>) } : x));
      setClaimedByMe(prev => new Set(prev).add(v.id));
      setSelectedId(v.id);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to claim");
    } finally {
      setClaiming(null);
    }
  }

  async function handleReviewComplete(id: string, outcome: "approved" | "rejected") {
    setVerifications(prev => prev.filter(v => v.id !== id));
    setSelectedId(null);
    toast.success(`Verification ${outcome}`);
    router.refresh();
  }

  function switchTab(tab: string) {
    router.push(`/review${tab === "all" ? "?tab=all" : ""}`);
  }

  if (error) {
    return (
      <>
        <TopBar title="Review Queue" subtitle="Verifications pending human review" />
        <div className="flex-1 flex items-center justify-center">
          <div className="text-center space-y-2">
            <AlertCircle className="h-8 w-8 text-destructive mx-auto" />
            <p className="text-sm text-muted-foreground">{error}</p>
          </div>
        </div>
      </>
    );
  }

  const isAllTab = activeTab === "all";
  const pendingCount = isAllTab ? null : verifications.length;

  return (
    <>
      <TopBar
        title="Review Queue"
        subtitle={pendingCount !== null
          ? `${pendingCount} item${pendingCount !== 1 ? "s" : ""} pending`
          : `${verifications.length} recent request${verifications.length !== 1 ? "s" : ""}`
        }
      />

      {/* Tab bar */}
      <div className="border-b border-border px-6">
        <div className="flex gap-0">
          {[
            { id: "needs_review", label: "Needs Review" },
            { id: "all", label: "All Activity" },
          ].map(tab => (
            <button
              key={tab.id}
              onClick={() => switchTab(tab.id)}
              className={`px-4 py-2.5 text-xs font-medium border-b-2 transition-colors ${
                activeTab === tab.id
                  ? "border-primary text-primary"
                  : "border-transparent text-muted-foreground hover:text-foreground"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      <div className="flex-1 p-6">
        {verifications.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-64 gap-3 text-center">
            <CheckCircle className="h-12 w-12 text-emerald-400" />
            <p className="text-base font-medium">
              {isAllTab ? "No requests yet" : "Queue is clear"}
            </p>
            <p className="text-sm text-muted-foreground">
              {isAllTab
                ? "No MCP verification requests have been recorded yet."
                : "No verifications pending review. Your AI agents are publishing clean content."}
            </p>
          </div>
        ) : (
          <div className="bg-card border border-border rounded-lg overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border">
                  {["", "Elapsed", "Agent", "Input preview", "Decision", "Claims", "Status", ""].map((h, i) => (
                    <th
                      key={i}
                      className="text-left px-4 py-3 text-muted-foreground"
                      style={{
                        fontFamily: "var(--font-sora, 'Sora', sans-serif)",
                        fontSize: 10,
                        letterSpacing: "0.08em",
                        textTransform: "uppercase",
                        fontWeight: 400,
                      }}
                    >
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {verifications.map(v => {
                  const isClaimed = v.reviewStatus === "in_review";
                  // All visible verifications belong to the current user's org —
                  // never block access to in_review items
                  const isMyReview = isClaimed;
                  const otherReviewer = false;
                  const elapsed = timeAgo(v.createdAt);
                  const isOld = !isAllTab && Date.now() - new Date(v.createdAt).getTime() > 4 * 60 * 60 * 1000;
                  const isExpanded = expandedRows.has(v.id);
                  const claims = extractClaims(v.fullResponse);

                  return (
                    <>
                      <tr
                        key={v.id}
                        className={`border-b border-border transition-colors ${isExpanded ? "bg-secondary/40" : "hover:bg-secondary/50"} ${selectedId === v.id ? "bg-secondary/80" : ""}`}
                      >
                        {/* Expand toggle */}
                        <td className="px-3 py-3 w-8">
                          <button
                            onClick={() => toggleRow(v.id)}
                            className="text-muted-foreground hover:text-foreground transition-colors"
                          >
                            {isExpanded
                              ? <ChevronDown className="h-3.5 w-3.5" />
                              : <ChevronRight className="h-3.5 w-3.5" />
                            }
                          </button>
                        </td>

                        <td className="px-4 py-3">
                          <span className={`text-xs font-mono ${isOld ? "text-red-400" : "text-muted-foreground"}`}>
                            {elapsed}
                          </span>
                        </td>

                        <td className="px-4 py-3">
                          <div className="space-y-0.5">
                            <p className="text-xs font-medium truncate max-w-[140px]">{v.agent || "API Direct"}</p>
                            <DomainBadge domain={v.domain} />
                          </div>
                        </td>

                        <td className="px-4 py-3">
                          <p className="text-xs text-muted-foreground truncate max-w-[240px]">{v.inputText.slice(0, 80)}</p>
                        </td>

                        <td className="px-4 py-3">
                          <DecisionBadge decision={v.decision} size="md" />
                        </td>

                        {/* Claims mini-summary */}
                        <td className="px-4 py-3">
                          <div className="flex items-center gap-2 text-xs font-mono">
                            {v.corroboratedCount > 0 && (
                              <span className="text-emerald-400">{v.corroboratedCount}✓</span>
                            )}
                            {v.contradictedCount > 0 && (
                              <span className="text-red-400">{v.contradictedCount}✗</span>
                            )}
                            {v.unsupportedCount > 0 && (
                              <span className="text-amber-400">{v.unsupportedCount}?</span>
                            )}
                            {v.totalClaims === 0 && (
                              <span className="text-muted-foreground">—</span>
                            )}
                          </div>
                        </td>

                        <td className="px-4 py-3">
                          {isAllTab && !isClaimed ? (
                            <Badge variant="outline" className="text-[10px] text-muted-foreground border-border">
                              {v.reviewStatus === "not_required" ? "Pass" : v.reviewStatus === "reviewed" ? "Reviewed" : "Pending"}
                            </Badge>
                          ) : otherReviewer ? (
                            <div className="flex items-center gap-1 text-xs text-muted-foreground">
                              <User className="h-3 w-3" />
                              In Review
                            </div>
                          ) : isClaimed ? (
                            <div className="flex items-center gap-1 text-xs text-blue-400">
                              <User className="h-3 w-3" />
                              Claimed by you
                            </div>
                          ) : (
                            <Badge variant="outline" className="text-[10px] text-amber-400 border-amber-400/40 bg-amber-400/10">
                              <Clock className="h-2.5 w-2.5 mr-1" />
                              Pending
                            </Badge>
                          )}
                        </td>

                        <td className="px-4 py-3">
                          <Button
                            size="sm"
                            variant={isMyReview || (!isAllTab && v.reviewStatus === "pending_review") ? "default" : "outline"}
                            className="h-7 text-xs"
                            disabled={otherReviewer || claiming === v.id}
                            onClick={() => {
                              if (isMyReview || isClaimed || isAllTab) {
                                setSelectedId(v.id);
                              } else {
                                handleClaim(v);
                              }
                            }}
                          >
                            {claiming === v.id
                              ? "Claiming..."
                              : isAllTab
                                ? "View"
                                : isMyReview
                                  ? "Review"
                                  : otherReviewer
                                    ? "In Review"
                                    : "Claim"}
                          </Button>
                        </td>
                      </tr>

                      {/* Expanded claims row */}
                      {isExpanded && (
                        <tr key={`${v.id}-claims`} className="border-b border-border bg-secondary/20">
                          <td colSpan={8} className="px-6 py-4">
                            {claims.length === 0 ? (
                              <p className="text-xs text-muted-foreground italic">No claim details available.</p>
                            ) : (
                              <div className="space-y-1.5">
                                {claims.map((claim, i) => (
                                  <ClaimRow key={i} claim={claim} />
                                ))}
                              </div>
                            )}
                          </td>
                        </tr>
                      )}
                    </>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Slide-over detail panel — approving step unchanged */}
      <Sheet open={!!selectedId} onOpenChange={(open) => !open && setSelectedId(null)}>
        <SheetContent side="right" className="w-[640px] max-w-full bg-card border-border overflow-y-auto p-0">
          {selected && (
            <>
              <SheetHeader className="p-6 border-b border-border">
                <SheetTitle className="flex items-center gap-2 text-sm">
                  <DecisionBadge decision={selected.decision} size="md" />
                  <span className="font-medium">{selected.agent || "Verification"}</span>
                  <span className="text-muted-foreground font-normal text-xs">· {timeAgo(selected.createdAt)}</span>
                </SheetTitle>
              </SheetHeader>
              <VerificationDetail
                verification={selected}
                token={token}
                userId={userId}
                onComplete={handleReviewComplete}
              />
            </>
          )}
        </SheetContent>
      </Sheet>
    </>
  );
}
