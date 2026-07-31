"use client";

import { DashboardData } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { DecisionBadge, ReviewStatusBadge } from "@/components/shared/DecisionBadge";
import { DomainBadge } from "@/components/shared/DomainBadge";
import { useRouter } from "next/navigation";

interface Props { data: DashboardData }

function timeAgo(dateStr: string): string {
  const diff = Date.now() - new Date(dateStr).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

export function SourcesAndActivity({ data }: Props) {
  const router = useRouter();

  const { sourceAuthorityBreakdown: auth, sourceFreshnessBreakdown: fresh } = data;
  const authTotal = auth.primary + auth.institutional + auth.secondary + auth.tertiary;
  const freshTotal = fresh.current + fresh.aging + fresh.stale + fresh.deprecated;

  const authBars = [
    { label: "Primary",       value: auth.primary,       pct: authTotal > 0 ? auth.primary/authTotal : 0,       hex: "#5BC29E" },
    { label: "Institutional", value: auth.institutional, pct: authTotal > 0 ? auth.institutional/authTotal : 0, hex: "#7D29F2" },
    { label: "Secondary",     value: auth.secondary,     pct: authTotal > 0 ? auth.secondary/authTotal : 0,     hex: "#9D5FF5" },
    { label: "Tertiary",      value: auth.tertiary,      pct: authTotal > 0 ? auth.tertiary/authTotal : 0,      hex: "#9E9E9E" },
  ];

  const freshBars = [
    { label: "Current",    value: fresh.current,    pct: freshTotal > 0 ? fresh.current/freshTotal : 0,    hex: "#5BC29E" },
    { label: "Aging",      value: fresh.aging,      pct: freshTotal > 0 ? fresh.aging/freshTotal : 0,      hex: "#F2BC1B" },
    { label: "Stale",      value: fresh.stale,      pct: freshTotal > 0 ? fresh.stale/freshTotal : 0,      hex: "#D70067" },
    { label: "Deprecated", value: fresh.deprecated, pct: freshTotal > 0 ? fresh.deprecated/freshTotal : 0, hex: "#991b1b" },
  ];

  const hasStaleWarning = fresh.stale > 0 || fresh.deprecated > 0;

  return (
    <div className="grid grid-cols-3 gap-4">
      {/* Left 2/3: Activity feed */}
      <Card className="col-span-2 bg-card border-border" style={{ borderRadius: 12 }}>
        <CardHeader className="pb-2 pt-4 px-4">
          <CardTitle className="card-label">Recent Activity</CardTitle>
        </CardHeader>
        <CardContent className="px-4 pb-4">
          {data.recentActivity.length === 0 ? (
            <p className="text-xs text-muted-foreground py-4 text-center">No activity yet</p>
          ) : (
            <div className="space-y-1">
              {data.recentActivity.map(item => (
                <div
                  key={item.id}
                  className="flex items-center gap-3 px-2 py-2 rounded hover:bg-secondary transition-colors cursor-pointer text-xs"
                  onClick={() => router.push(`/audit?id=${item.id}`)}
                >
                  <span className="text-[10px] text-muted-foreground w-16 shrink-0">{timeAgo(item.createdAt)}</span>
                  <span className="flex-1 truncate text-foreground">{item.inputPreview}</span>
                  <DomainBadge domain={item.domain} />
                  <DecisionBadge decision={item.decision} />
                  {item.reviewStatus !== "not_required" && (
                    <ReviewStatusBadge status={item.reviewStatus} />
                  )}
                  {item.contradictedCount > 0 && (
                    <span className="text-[10px] text-[var(--bria-red)] font-mono shrink-0">{item.contradictedCount} ✗</span>
                  )}
                  <span className="text-[10px] text-[var(--bria-green)] font-mono shrink-0">
                    {Math.round(item.corroborationRate * 100)}%
                  </span>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Right 1/3: Source authority + freshness */}
      <div className="space-y-4">
        {/* Source authority */}
        <Card className="bg-card border-border" style={{ borderRadius: 12 }}>
          <CardHeader className="pb-2 pt-4 px-4">
            <CardTitle className="card-label">Source Authority</CardTitle>
          </CardHeader>
          <CardContent className="px-4 pb-4 space-y-2">
            {authBars.map(bar => (
              <div key={bar.label} className="space-y-0.5">
                <div className="flex justify-between text-[10px]">
                  <span className="text-muted-foreground">{bar.label}</span>
                  <span className="font-mono">{Math.round(bar.pct * 100)}%</span>
                </div>
                <div className="w-full bg-secondary rounded-full h-1.5">
                  <div className="h-1.5 rounded-full" style={{ width: `${bar.pct * 100}%`, backgroundColor: bar.hex }} />
                </div>
              </div>
            ))}
          </CardContent>
        </Card>

        {/* Source freshness */}
        <Card className="bg-card border-border" style={{ borderRadius: 12 }}>
          <CardHeader className="pb-2 pt-4 px-4">
            <CardTitle className="card-label flex items-center gap-1.5">
              Source Freshness
              {hasStaleWarning && <span className="text-[var(--bria-amber)]">⚠</span>}
            </CardTitle>
          </CardHeader>
          <CardContent className="px-4 pb-4 space-y-2">
            {freshBars.map(bar => (
              <div key={bar.label} className="space-y-0.5">
                <div className="flex justify-between text-[10px]">
                  <span style={{ color: bar.label === "Stale" || bar.label === "Deprecated" ? "#D70067" : "#9E9E9E" }}>{bar.label}</span>
                  <span className="font-mono">{Math.round(bar.pct * 100)}%</span>
                </div>
                <div className="w-full bg-secondary rounded-full h-1.5">
                  <div className="h-1.5 rounded-full" style={{ width: `${bar.pct * 100}%`, backgroundColor: bar.hex }} />
                </div>
              </div>
            ))}
            {hasStaleWarning && (
              <p className="text-[10px] text-amber-400 pt-1">
                Stale/deprecated sources reduce corroboration reliability
              </p>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
