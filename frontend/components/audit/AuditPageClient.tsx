"use client";

import React, { useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Verification, Agent, auditApi } from "@/lib/api";
import { TopBar } from "@/components/layout/TopBar";
import { DecisionBadge, ReviewStatusBadge } from "@/components/shared/DecisionBadge";
import { DomainBadge } from "@/components/shared/DomainBadge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Download, ChevronDown, ChevronUp, AlertCircle, Bot } from "lucide-react";
import { ClaimRow, extractClaims } from "@/components/shared/ClaimRow";

interface AuditPageClientProps {
  initialData: { verifications: Verification[]; total: number; page: number; limit: number } | null;
  error: string | null;
  token: string;
  apiBase: string;
  agents?: Agent[];
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

export function AuditPageClient({ initialData, error, token, apiBase, agents = [] }: AuditPageClientProps) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [expandedRows, setExpandedRows] = useState<Set<string>>(new Set());
  const [exporting, setExporting] = useState(false);

  const verifications = initialData?.verifications || [];
  const total = initialData?.total || 0;

  // Filter state derived from URL params
  const decision = searchParams.get("decision") || "";
  const domain = searchParams.get("domain") || "";
  const reviewStatus = searchParams.get("reviewStatus") || "";
  const agentId = searchParams.get("agentId") || "";

  function updateFilter(key: string, value: string) {
    const params = new URLSearchParams(searchParams.toString());
    if (value && value !== "all") params.set(key, value);
    else params.delete(key);
    params.delete("page"); // reset page on filter change
    router.push(`/audit?${params.toString()}`);
  }

  function toggleRow(id: string) {
    setExpandedRows(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  async function handleExport() {
    setExporting(true);
    try {
      const params: Record<string, string> = {};
      if (decision) params.decision = decision;
      if (domain) params.domain = domain;
      if (reviewStatus) params.reviewStatus = reviewStatus;

      const url = auditApi.exportUrl(token, params);
      const res = await fetch(url, { headers: { Authorization: `Bearer ${token}` } });
      const blob = await res.blob();
      const link = document.createElement("a");
      link.href = URL.createObjectURL(blob);
      link.download = "bria-audit-export.csv";
      link.click();
    } catch {
      // silent fail
    } finally {
      setExporting(false);
    }
  }

  const ExportButton = (
    <Button variant="outline" size="sm" onClick={handleExport} disabled={exporting} className="gap-1.5 text-xs">
      <Download className="h-3.5 w-3.5" />
      {exporting ? "Exporting..." : "Export CSV"}
    </Button>
  );

  if (error) {
    return (
      <>
        <TopBar title="Audit Log" actions={ExportButton} />
        <div className="flex-1 flex items-center justify-center">
          <div className="text-center space-y-2">
            <AlertCircle className="h-8 w-8 text-destructive mx-auto" />
            <p className="text-sm text-muted-foreground">{error}</p>
          </div>
        </div>
      </>
    );
  }

  return (
    <>
      <TopBar title="Audit Log" subtitle={`${total.toLocaleString()} records`} actions={ExportButton} />

      <div className="flex-1 p-6 space-y-4">
        {/* Filters */}
        <div className="flex items-center gap-3 flex-wrap">
          <Select value={decision || "all"} onValueChange={v => v && updateFilter("decision", v)}>
            <SelectTrigger className="h-8 w-32 text-xs bg-card border-border">
              <SelectValue placeholder="Decision" />
            </SelectTrigger>
            <SelectContent className="bg-card border-border">
              <SelectItem value="all" className="text-xs">All decisions</SelectItem>
              <SelectItem value="pass" className="text-xs">Pass</SelectItem>
              <SelectItem value="flag" className="text-xs">Flag</SelectItem>
              <SelectItem value="block" className="text-xs">Block</SelectItem>
            </SelectContent>
          </Select>

          <Select value={domain || "all"} onValueChange={v => v && updateFilter("domain", v)}>
            <SelectTrigger className="h-8 w-40 text-xs bg-card border-border">
              <SelectValue placeholder="Domain" />
            </SelectTrigger>
            <SelectContent className="bg-card border-border">
              <SelectItem value="all" className="text-xs">All domains</SelectItem>
              <SelectItem value="pharma" className="text-xs">Pharma</SelectItem>
              <SelectItem value="legal" className="text-xs">Legal</SelectItem>
              <SelectItem value="financial" className="text-xs">Financial</SelectItem>
              <SelectItem value="news_editorial" className="text-xs">News &amp; Editorial</SelectItem>
            </SelectContent>
          </Select>

          <Select value={reviewStatus || "all"} onValueChange={v => v && updateFilter("reviewStatus", v)}>
            <SelectTrigger className="h-8 w-40 text-xs bg-card border-border">
              <SelectValue placeholder="Review status" />
            </SelectTrigger>
            <SelectContent className="bg-card border-border">
              <SelectItem value="all" className="text-xs">All statuses</SelectItem>
              <SelectItem value="not_required" className="text-xs">Not Required</SelectItem>
              <SelectItem value="pending_review" className="text-xs">Pending</SelectItem>
              <SelectItem value="in_review" className="text-xs">In Review</SelectItem>
              <SelectItem value="approved" className="text-xs">Approved</SelectItem>
              <SelectItem value="rejected" className="text-xs">Rejected</SelectItem>
            </SelectContent>
          </Select>

          {agents.length > 0 && (
            <Select value={agentId || "all"} onValueChange={v => v && updateFilter("agentId", v)}>
              <SelectTrigger className="h-8 w-44 text-xs bg-card border-border">
                <SelectValue placeholder="All agents" />
              </SelectTrigger>
              <SelectContent className="bg-card border-border">
                <SelectItem value="all" className="text-xs">All agents</SelectItem>
                {agents.map(a => (
                  <SelectItem key={a.id} value={a.id} className="text-xs">{a.name}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          )}

          {(decision || domain || reviewStatus || agentId) && (
            <Button variant="ghost" size="sm" className="h-8 text-xs text-muted-foreground" onClick={() => router.push("/audit")}>
              Clear filters
            </Button>
          )}
        </div>

        {/* Table */}
        <div className="bg-card border border-border rounded-lg overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border">
                {["", "Timestamp", "Input", "Agent", "Decision", "Corroboration", "Coverage", "Domain", "Review", "Latency"].map(h => (
                  <th
                    key={h}
                    className="text-left px-3 py-2.5 text-muted-foreground"
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
              {verifications.length === 0 ? (
                <tr>
                  <td colSpan={10} className="text-center text-xs text-muted-foreground py-8">No records found</td>
                </tr>
              ) : (
                verifications.map(v => {
                  const isExpanded = expandedRows.has(v.id);
                  return (
                    <React.Fragment key={v.id}>
                      <tr
                        className="border-b border-border/50 hover:bg-secondary/40 transition-colors cursor-pointer"
                        onClick={() => toggleRow(v.id)}
                      >
                        <td className="px-3 py-2.5">
                          {isExpanded ? <ChevronUp className="h-3.5 w-3.5 text-muted-foreground" /> : <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />}
                        </td>
                        <td className="px-3 py-2.5">
                          <p className="text-[11px] text-muted-foreground">{timeAgo(v.createdAt)}</p>
                          {(v.iterationCount || 0) > 0 && (
                            <span className="text-[9px] text-[var(--bria-blue)]">+{v.iterationCount} itr.</span>
                          )}
                        </td>
                        <td className="px-3 py-2.5 max-w-[200px]">
                          <p className="text-xs truncate">{v.inputText.slice(0, 70)}</p>
                        </td>
                        <td className="px-3 py-2.5">
                          {v.agent ? (
                            <div className="flex items-center gap-1.5">
                              <Bot className="h-3 w-3 text-primary shrink-0" />
                              <p className="text-[11px] truncate max-w-[100px]">{v.agent}</p>
                            </div>
                          ) : (
                            <p className="text-[11px] text-muted-foreground">—</p>
                          )}
                        </td>
                        <td className="px-3 py-2.5">
                          <DecisionBadge decision={v.decision} />
                        </td>
                        <td className="px-3 py-2.5">
                          <span className="font-mono text-[var(--bria-green)]" style={{ fontSize: 12 }}>{Math.round(v.corroborationRate * 100)}%</span>
                        </td>
                        <td className="px-3 py-2.5">
                          <span className="font-mono text-muted-foreground" style={{ fontSize: 12 }}>{Math.round(v.coverageRatio * 100)}%</span>
                        </td>
                        <td className="px-3 py-2.5">
                          <DomainBadge domain={v.domain} />
                        </td>
                        <td className="px-3 py-2.5">
                          {v.reviewStatus !== "not_required" && <ReviewStatusBadge status={v.reviewStatus} />}
                        </td>
                        <td className="px-3 py-2.5">
                          <span className="text-[10px] text-muted-foreground font-mono">{v.latencyMs}ms</span>
                        </td>
                      </tr>

                      {isExpanded && (
                        <tr className="border-b border-border/50 bg-secondary/20">
                          <td colSpan={10} className="px-4 py-4">
                            <div className="space-y-4">
                              {/* Full text + word/claim ratio */}
                              <div>
                                <div className="flex items-baseline justify-between mb-1">
                                  <p className="text-[10px] text-muted-foreground uppercase tracking-wider">Input text</p>
                                  {v.totalClaims > 0 && (() => {
                                    const wordCount = v.inputText ? v.inputText.trim().split(/\s+/).length : 0;
                                    return (
                                      <span className="text-[10px] text-muted-foreground font-mono">
                                        {wordCount} words · {v.totalClaims} claims · <span className="text-foreground">{Math.round(wordCount / v.totalClaims)} words/claim</span>
                                      </span>
                                    );
                                  })()}
                                </div>
                                <p className="text-xs text-foreground leading-relaxed">{v.inputText}</p>
                              </div>

                              {/* Claims */}
                              {(() => {
                                const claims = extractClaims(v.fullResponse);
                                return claims.length > 0 ? (
                                  <div>
                                    <p className="text-[10px] text-muted-foreground uppercase tracking-wider mb-2">
                                      Claims ({v.corroboratedCount}✓ {v.contradictedCount}✗ {v.unsupportedCount}? {v.outOfScopeCount} oos)
                                    </p>
                                    <div className="space-y-1.5">
                                      {claims.map((claim, i) => <ClaimRow key={i} claim={claim} />)}
                                    </div>
                                  </div>
                                ) : null;
                              })()}

                              {/* Review actions if reviewed */}
                              {v.reviewActions && (v.reviewActions as ReviewAction[]).length > 0 && (
                                <div>
                                  <p className="text-[10px] text-muted-foreground uppercase tracking-wider mb-1">Review Actions</p>
                                  <ul className="space-y-1">
                                    {(v.reviewActions as ReviewAction[]).map((a, i) => (
                                      <li key={i} className="text-[11px]">
                                        <span className="text-[var(--bria-blue)]">{a.action}</span>{" "}
                                        <span className="text-muted-foreground">on &quot;{a.claimText?.slice(0, 60)}&quot;</span>
                                        {a.note && <span className="text-muted-foreground"> — {a.note}</span>}
                                      </li>
                                    ))}
                                  </ul>
                                </div>
                              )}

                              <p className="text-[10px] text-muted-foreground font-mono">
                                Trace ID: {v.traceId}
                              </p>
                            </div>
                          </td>
                        </tr>
                      )}
                    </React.Fragment>
                  );
                })
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        {total > 50 && (
          <div className="flex items-center justify-between text-xs text-muted-foreground">
            <span>Showing {verifications.length} of {total.toLocaleString()} records</span>
            <div className="flex gap-2">
              <Button variant="outline" size="sm" className="h-7 text-xs" disabled>Previous</Button>
              <Button variant="outline" size="sm" className="h-7 text-xs" disabled>Next</Button>
            </div>
          </div>
        )}
      </div>
    </>
  );
}

interface ReviewAction {
  claimText: string;
  action: string;
  note?: string;
}
