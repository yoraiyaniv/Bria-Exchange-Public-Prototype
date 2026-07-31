"use client";

import { useState } from "react";
import { DashboardData } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { DomainBadge } from "@/components/shared/DomainBadge";
import { formatDistanceToNow } from "@/lib/utils";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer
} from "recharts";
import { PieChart, Pie, Cell } from "recharts";

interface Props { data: DashboardData }

const TOOLTIP_STYLE = {
  backgroundColor: "var(--bria-surface)",
  border: "1px solid var(--bria-border)",
  borderRadius: "6px",
  fontSize: "11px",
  color: "var(--foreground)",
};

const DOMAIN_COLORS = {
  pharma:         "#9D5FF5",
  legal:          "#7D29F2",
  financial:      "#5BC29E",
  news_editorial: "#9E9E9E",
};

export function LeaderboardAndDomain({ data }: Props) {
  const [leaderboardTab, setLeaderboardTab] = useState("agents");

  const domainData = [
    { name: "News & Ed.", value: data.byDomain.news_editorial, color: DOMAIN_COLORS.news_editorial, key: "news_editorial" },
    { name: "Financial", value: data.byDomain.financial, color: DOMAIN_COLORS.financial, key: "financial" },
    { name: "Legal", value: data.byDomain.legal, color: DOMAIN_COLORS.legal, key: "legal" },
    { name: "Pharma", value: data.byDomain.pharma, color: DOMAIN_COLORS.pharma, key: "pharma" },
  ].filter(d => d.value > 0);

  const oosData = data.outOfScopeRateByDay.map(d => ({
    date: d.date.slice(5),
    oos: d.value,
  }));

  const reviewOps = data.reviewOperations;

  return (
    <div className="grid grid-cols-2 gap-4">
      {/* Left: Tabbed leaderboard */}
      <Card className="bg-card border-border" style={{ borderRadius: 12 }}>
        <CardHeader className="pb-2 pt-4 px-4">
          <CardTitle className="card-label">Leaderboard</CardTitle>
        </CardHeader>
        <CardContent className="px-4 pb-4">
          <Tabs value={leaderboardTab} onValueChange={setLeaderboardTab}>
            <TabsList className="bg-secondary h-7 mb-3">
              <TabsTrigger value="agents" className="text-xs h-6">AI Agents</TabsTrigger>
              <TabsTrigger value="reviewers" className="text-xs h-6">Reviewers</TabsTrigger>
            </TabsList>

            <TabsContent value="agents">
              {data.agentLeaderboard.length === 0 ? (
                <p className="text-xs text-muted-foreground py-4 text-center">No agent data yet</p>
              ) : (
                <div className="space-y-1">
                  <div
                    className="grid grid-cols-4 text-muted-foreground px-2 pb-1"
                    style={{
                      fontFamily: "var(--font-sora, 'Sora', sans-serif)",
                      fontSize: 10,
                      letterSpacing: "0.08em",
                      textTransform: "uppercase",
                    }}
                  >
                    <span>Agent</span>
                    <span className="text-center">Verifications</span>
                    <span className="text-center">Corroboration</span>
                    <span className="text-center">Contradiction</span>
                  </div>
                  {data.agentLeaderboard.slice(0, 6).map(agent => (
                    <div key={agent.id} className="grid grid-cols-4 text-xs px-2 py-1.5 rounded hover:bg-secondary transition-colors">
                      <div>
                        <p className="font-medium truncate text-[11px]">{agent.name}</p>
                        <DomainBadge domain={agent.domain} size="sm" />
                      </div>
                      <span className="text-center self-center text-muted-foreground">{agent.verifications}</span>
                      <div className="text-center self-center">
                        <span className="text-[var(--bria-green)] font-mono font-medium">{agent.corroborationRate}%</span>
                        <div className="w-full bg-secondary rounded-full h-0.5 mt-0.5">
                          <div className="h-0.5 rounded-full bg-[var(--bria-green)]" style={{ width: `${agent.corroborationRate}%` }} />
                        </div>
                      </div>
                      <div className="text-center self-center">
                        <span className={`font-mono font-medium`} style={{ color: agent.contradictionRate > 20 ? "#D70067" : "#F2BC1B" }}>
                          {agent.contradictionRate}%
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </TabsContent>

            <TabsContent value="reviewers">
              {data.reviewerLeaderboard.length === 0 ? (
                <p className="text-xs text-muted-foreground py-4 text-center">No reviewer data yet</p>
              ) : (
                <div className="space-y-1">
                  <div
                    className="grid grid-cols-4 text-muted-foreground px-2 pb-1"
                    style={{
                      fontFamily: "var(--font-sora, 'Sora', sans-serif)",
                      fontSize: 10,
                      letterSpacing: "0.08em",
                      textTransform: "uppercase",
                    }}
                  >
                    <span>Reviewer</span>
                    <span className="text-center">Reviews</span>
                    <span className="text-center">Approval</span>
                    <span className="text-center">Avg Fixes</span>
                  </div>
                  {data.reviewerLeaderboard.slice(0, 6).map(rev => {
                    const isRubberStamp = rev.approvalRate > 0.9 && rev.avgFixesApplied < 0.5;
                    return (
                      <div key={rev.userId} className="grid grid-cols-4 text-xs px-2 py-1.5 rounded hover:bg-secondary transition-colors">
                        <div>
                          <p className="font-medium truncate text-[11px]">{rev.name}</p>
                          {isRubberStamp && (
                            <span className="text-[9px] text-amber-400">⚠ Low fixes</span>
                          )}
                        </div>
                        <span className="text-center self-center text-muted-foreground">{rev.reviewsCompleted}</span>
                        <span
                          className="text-center self-center font-mono font-medium"
                          style={{ color: rev.approvalRate < 0.7 ? "#5BC29E" : "#9E9E9E" }}
                        >
                          {Math.round(rev.approvalRate * 100)}%
                        </span>
                        <span
                          className="text-center self-center font-mono"
                          style={{ color: rev.avgFixesApplied > 2 ? "#5BC29E" : "#9E9E9E" }}
                        >
                          {rev.avgFixesApplied.toFixed(1)}
                        </span>
                      </div>
                    );
                  })}
                </div>
              )}
            </TabsContent>
          </Tabs>
        </CardContent>
      </Card>

      {/* Right: Domain donut + OOS trend + Review ops */}
      <div className="space-y-4">
        {/* Domain donut */}
        <Card className="bg-card border-border" style={{ borderRadius: 12 }}>
          <CardHeader className="pb-1 pt-4 px-4">
            <CardTitle className="card-label">Verification by Domain</CardTitle>
          </CardHeader>
          <CardContent className="px-4 pb-4">
            <div className="flex items-center gap-4">
              <div className="h-[100px] w-[100px] shrink-0">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie data={domainData} cx="50%" cy="50%" innerRadius={30} outerRadius={48} dataKey="value" strokeWidth={0}>
                      {domainData.map((entry, index) => (
                        <Cell key={index} fill={entry.color} />
                      ))}
                    </Pie>
                  </PieChart>
                </ResponsiveContainer>
              </div>
              <div className="space-y-1.5">
                {domainData.map(d => {
                  const total = domainData.reduce((s, x) => s + x.value, 0);
                  return (
                    <div key={d.key} className="flex items-center gap-2 text-[11px]">
                      <div className="w-2 h-2 rounded-full shrink-0" style={{ backgroundColor: d.color }} />
                      <span className="text-muted-foreground">{d.name}</span>
                      <span className="font-mono font-medium">{d.value}</span>
                      <span className="text-muted-foreground">({total > 0 ? Math.round(d.value/total*100) : 0}%)</span>
                    </div>
                  );
                })}
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Out-of-scope trend */}
        <Card className="bg-card border-border" style={{ borderRadius: 12 }}>
          <CardHeader className="pb-1 pt-3 px-4">
            <CardTitle className="card-label">Out-of-Scope Rate</CardTitle>
          </CardHeader>
          <CardContent className="px-4 pb-3">
            <ResponsiveContainer width="100%" height={70}>
              <LineChart data={oosData} margin={{ top: 0, right: 0, left: -30, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#2A2A2A" vertical={false} />
                <XAxis dataKey="date" hide />
                <YAxis tick={{ fontSize: 9, fill: "#9E9E9E" }} tickLine={false} axisLine={false} unit="%" domain={[0, "auto"]} />
                <Tooltip contentStyle={TOOLTIP_STYLE} formatter={(v) => typeof v === 'number' ? `${v.toFixed(1)}%` : String(v)} />
                <Line type="monotone" dataKey="oos" stroke="#9D5FF5" strokeWidth={1.5} dot={false} name="OOS Rate" />
              </LineChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        {/* Review operations */}
        <Card className="bg-card border-border" style={{ borderRadius: 12 }}>
          <CardHeader className="pb-1 pt-3 px-4">
            <CardTitle className="card-label">Review Operations</CardTitle>
          </CardHeader>
          <CardContent className="px-4 pb-3">
            <div className="grid grid-cols-3 gap-3">
              <div>
                <p className="text-[10px] text-muted-foreground">Avg Review Time</p>
                <p className="font-mono text-foreground" style={{ fontFamily: "var(--font-space-grotesk, 'Space Grotesk', sans-serif)", fontSize: 20, lineHeight: 1.2 }}>
                  {reviewOps.avgReviewTimeMs > 0 ? `${Math.round(reviewOps.avgReviewTimeMs / 60000)}m` : "—"}
                </p>
              </div>
              <div>
                <p className="text-[10px] text-muted-foreground">Approved / Rejected</p>
                <p className="text-base font-mono" style={{ fontSize: 16 }}>
                  <span className="text-[var(--bria-green)]">{reviewOps.approvedCount}</span>
                  <span className="text-muted-foreground mx-1">/</span>
                  <span className="text-[var(--bria-red)]">{reviewOps.rejectedCount}</span>
                </p>
              </div>
              <div>
                <p className="text-[10px] text-muted-foreground">Re-verify Rate</p>
                <p className="text-[var(--bria-blue)] font-mono" style={{ fontFamily: "var(--font-space-grotesk, 'Space Grotesk', sans-serif)", fontSize: 20, lineHeight: 1.2 }}>
                  {Math.round(reviewOps.reVerificationRate * 100)}%
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

