"use client";

import { useRouter, useSearchParams } from "next/navigation";
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from "recharts";
import { TopBar } from "@/components/layout/TopBar";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { type CostData } from "@/lib/api";
import { AlertCircle, TrendingUp, TrendingDown, Minus } from "lucide-react";

interface CostPageClientProps {
  data: CostData | null;
  error: string | null;
  period: string;
}

const TOOLTIP_STYLE = {
  backgroundColor: "#1A1A1A",
  border: "1px solid #2A2A2A",
  borderRadius: "8px",
  fontSize: "11px",
  color: "#FFFFFF",
};

const LABEL_STYLE = {
  fontFamily: "var(--font-sora, 'Sora', sans-serif)",
  fontSize: 10,
  letterSpacing: "0.08em",
  textTransform: "uppercase" as const,
  fontWeight: 400,
};

const VALUE_STYLE = {
  fontFamily: "var(--font-space-grotesk, 'Space Grotesk', sans-serif)",
  fontSize: 32,
  fontWeight: 700,
};

function fmt(n: number, decimals = 4) {
  if (n >= 1) return `$${n.toFixed(2)}`;
  if (n === 0) return "$0.00";
  return `$${n.toFixed(decimals)}`;
}

function fmtTokens(n: number) {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(0)}K`;
  return String(n);
}

function StatCard({
  label,
  value,
  delta,
  note,
}: {
  label: string;
  value: string;
  delta?: number;
  note?: string;
}) {
  return (
    <Card className="bg-card border-border" style={{ borderRadius: 12 }}>
      <CardContent className="p-4">
        <p className="text-muted-foreground mb-2.5" style={LABEL_STYLE}>{label}</p>
        <div className="flex items-end justify-between gap-1">
          <p className="leading-none text-foreground" style={VALUE_STYLE}>{value}</p>
          {delta !== undefined && (
            <span className={`flex items-center gap-0.5 text-[10px] ${
              delta > 0 ? "text-[#D70067]" : delta < 0 ? "text-[#5BC29E]" : "text-muted-foreground"
            }`}>
              {delta > 0 ? <TrendingUp className="h-3 w-3" /> : delta < 0 ? <TrendingDown className="h-3 w-3" /> : <Minus className="h-3 w-3" />}
              {delta > 0 ? "+" : ""}{delta}%
            </span>
          )}
        </div>
        {note && <p className="text-muted-foreground mt-1.5" style={{ fontSize: 11 }}>{note}</p>}
      </CardContent>
    </Card>
  );
}

export function CostPageClient({ data, error, period }: CostPageClientProps) {
  const router = useRouter();
  const searchParams = useSearchParams();

  function setPeriod(p: string) {
    const params = new URLSearchParams(searchParams.toString());
    params.set("period", p);
    router.push(`/cost?${params.toString()}`);
  }

  const PeriodSelector = (
    <div className="flex items-center gap-1">
      {["7d", "30d", "90d"].map(p => (
        <Button
          key={p}
          variant={period === p ? "default" : "ghost"}
          size="sm"
          className="h-7 px-2.5 text-xs"
          onClick={() => setPeriod(p)}
        >
          {p === "7d" ? "7 days" : p === "30d" ? "30 days" : "90 days"}
        </Button>
      ))}
    </div>
  );

  if (error) {
    return (
      <>
        <TopBar title="Cost Estimation" periodSelector={PeriodSelector} />
        <div className="flex-1 flex items-center justify-center p-8">
          <div className="text-center space-y-3">
            <AlertCircle className="h-10 w-10 text-destructive mx-auto" />
            <p className="text-sm text-muted-foreground">{error}</p>
            <Button variant="outline" size="sm" onClick={() => router.refresh()}>Retry</Button>
          </div>
        </div>
      </>
    );
  }

  if (!data) return null;

  const chartData = data.costByDay.map(d => ({
    date: d.date.slice(5),
    costUsd: d.costUsd,
  }));

  const totalTokens = data.totalInputTokensEst + data.totalOutputTokensEst;

  return (
    <>
      <TopBar
        title="Cost Estimation"
        subtitle="Estimated API usage costs based on token consumption"
        periodSelector={PeriodSelector}
      />

      <div className="flex-1 pt-8 px-6 pb-6 space-y-6">

        {/* Hero stats */}
        <div className="grid grid-cols-4 gap-4">
          <StatCard
            label="Total Cost"
            value={fmt(data.totalCostUsd)}
            delta={Math.abs(data.deltaPercent) <= 999 && data.deltaPercent !== 0 ? data.deltaPercent : undefined}
            note={`vs previous ${period}`}
          />
          <StatCard
            label="Projected Monthly"
            value={fmt(data.projectedMonthlyCost)}
            note="at current rate"
          />
          <StatCard
            label="Avg Cost / Verification"
            value={fmt(data.avgCostPerVerification)}
            note={`${data.totalVerifications} verifications`}
          />
          <StatCard
            label="Total Tokens Est."
            value={fmtTokens(totalTokens)}
            note={`${fmtTokens(data.totalInputTokensEst)} in · ${fmtTokens(data.totalOutputTokensEst)} out`}
          />
        </div>

        {/* Cost over time */}
        <Card className="bg-card border-border" style={{ borderRadius: 12 }}>
          <CardHeader className="pb-2 pt-4 px-4">
            <CardTitle className="text-muted-foreground" style={LABEL_STYLE}>
              Cost Over Time
            </CardTitle>
          </CardHeader>
          <CardContent className="px-4 pb-4">
            {chartData.length === 0 ? (
              <div className="h-40 flex items-center justify-center text-muted-foreground text-sm">
                No data for this period
              </div>
            ) : (
              <ResponsiveContainer width="100%" height={180}>
                <AreaChart data={chartData}>
                  <defs>
                    <linearGradient id="costGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#9B59B6" stopOpacity={0.3} />
                      <stop offset="95%" stopColor="#9B59B6" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#2A2A2A" />
                  <XAxis dataKey="date" tick={{ fontSize: 10, fill: "#888" }} />
                  <YAxis
                    tick={{ fontSize: 10, fill: "#888" }}
                    tickFormatter={v => `$${v}`}
                    width={48}
                  />
                  <Tooltip
                    contentStyle={TOOLTIP_STYLE}
                    formatter={(v) => [`$${Number(v).toFixed(4)}`, "Cost"]}
                  />
                  <Area
                    type="monotone"
                    dataKey="costUsd"
                    stroke="#9B59B6"
                    strokeWidth={2}
                    fill="url(#costGrad)"
                  />
                </AreaChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>

        {/* By agent + by model */}
        <div className="grid grid-cols-3 gap-4">

          {/* Agent breakdown — 2/3 width */}
          <Card className="col-span-2 bg-card border-border" style={{ borderRadius: 12 }}>
            <CardHeader className="pb-2 pt-4 px-4">
              <CardTitle className="text-muted-foreground" style={LABEL_STYLE}>
                Cost by Agent
              </CardTitle>
            </CardHeader>
            <CardContent className="px-4 pb-4">
              {data.byAgent.length === 0 ? (
                <p className="text-muted-foreground text-sm text-center py-6">No agent data</p>
              ) : (
                <table className="w-full text-xs">
                  <thead>
                    <tr className="text-muted-foreground border-b border-border">
                      <th className="text-left pb-2 font-normal">Agent</th>
                      <th className="text-right pb-2 font-normal">Verifications</th>
                      <th className="text-right pb-2 font-normal">Input tokens</th>
                      <th className="text-right pb-2 font-normal">Output tokens</th>
                      <th className="text-right pb-2 font-normal">Cost</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.byAgent.map(a => (
                      <tr key={a.agentId} className="border-b border-border/50 last:border-0">
                        <td className="py-2 pr-4 font-medium truncate max-w-[160px]">{a.agentName}</td>
                        <td className="py-2 text-right text-muted-foreground">{a.verifications.toLocaleString()}</td>
                        <td className="py-2 text-right text-muted-foreground">{fmtTokens(a.inputTokensEst)}</td>
                        <td className="py-2 text-right text-muted-foreground">{fmtTokens(a.outputTokensEst)}</td>
                        <td className="py-2 text-right font-medium text-foreground">{fmt(a.costUsd)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </CardContent>
          </Card>

          {/* Model breakdown — 1/3 width */}
          <Card className="bg-card border-border" style={{ borderRadius: 12 }}>
            <CardHeader className="pb-2 pt-4 px-4">
              <CardTitle className="text-muted-foreground" style={LABEL_STYLE}>
                Cost by Model
              </CardTitle>
            </CardHeader>
            <CardContent className="px-4 pb-4 space-y-3">
              {data.byModel.length === 0 ? (
                <p className="text-muted-foreground text-sm text-center py-6">No model data</p>
              ) : (
                data.byModel.map(m => {
                  const pct = data.totalCostUsd > 0
                    ? Math.round((m.costUsd / data.totalCostUsd) * 100)
                    : 0;
                  return (
                    <div key={m.model}>
                      <div className="flex justify-between text-xs mb-1">
                        <span className="text-muted-foreground truncate">{m.model}</span>
                        <span className="font-medium ml-2 shrink-0">{fmt(m.costUsd)}</span>
                      </div>
                      <div className="h-1.5 bg-secondary rounded-full overflow-hidden">
                        <div
                          className="h-full bg-primary rounded-full"
                          style={{ width: `${pct}%` }}
                        />
                      </div>
                      <p className="text-[10px] text-muted-foreground mt-0.5">
                        {m.verifications} verifications · {pct}%
                      </p>
                    </div>
                  );
                })
              )}

              <div className="border-t border-border pt-3 mt-3">
                <p className="text-[10px] text-muted-foreground leading-relaxed">
                  Estimates based on ~4 chars per input token and ~300 tokens per claim for output.
                  Actual billed usage may vary.
                </p>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </>
  );
}
