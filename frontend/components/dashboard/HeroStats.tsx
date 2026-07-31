"use client";

import { DashboardData } from "@/lib/api";
import { TrendingUp, TrendingDown, Minus } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";

interface HeroStatsProps {
  data: DashboardData;
}

interface StatCardProps {
  label: string;
  value: string | number;
  delta?: number;
  accent?: string;
  suffix?: string;
  note?: string;
}

function StatCard({ label, value, delta, accent = "text-foreground", suffix = "", note }: StatCardProps) {
  const deltaDisplay = delta !== undefined ? (
    <span className={`flex items-center gap-0.5 text-[10px] ${
      delta > 0 ? "text-[#5BC29E]" : delta < 0 ? "text-[#D70067]" : "text-muted-foreground"
    }`}>
      {delta > 0 ? <TrendingUp className="h-3 w-3" /> : delta < 0 ? <TrendingDown className="h-3 w-3" /> : <Minus className="h-3 w-3" />}
      {delta > 0 ? "+" : ""}{delta}
    </span>
  ) : null;

  return (
    <Card className="bg-card border-border" style={{ borderRadius: 12 }}>
      <CardContent className="p-4">
        {/* Label — Sora Regular, 10px, uppercase */}
        <p
          className="text-muted-foreground mb-2.5"
          style={{
            fontFamily: "var(--font-sora, 'Sora', sans-serif)",
            fontSize: 10,
            letterSpacing: "0.08em",
            textTransform: "uppercase",
          }}
        >
          {label}
        </p>
        <div className="flex items-end justify-between gap-1">
          {/* Number — Space Grotesk Bold, 32px */}
          <p
            className={`leading-none ${accent}`}
            style={{
              fontFamily: "var(--font-space-grotesk, 'Space Grotesk', sans-serif)",
              fontSize: 32,
              fontWeight: 700,
            }}
          >
            {value}{suffix}
          </p>
          {deltaDisplay}
        </div>
        {note && (
          <p className="text-muted-foreground mt-1.5" style={{ fontSize: 11 }}>{note}</p>
        )}
      </CardContent>
    </Card>
  );
}

export function HeroStats({ data }: HeroStatsProps) {
  const d = data.deltas;

  return (
    <div className="grid grid-cols-6 gap-4">
      <StatCard
        label="Total Verifications"
        value={data.totalVerifications.toLocaleString()}
        delta={d.totalVerifications}
      />
      <StatCard
        label="Claims Prevented"
        value={data.claimsPreventedFromPublication.toLocaleString()}
        delta={d.claimsPreventedFromPublication}
        accent="text-[#D70067]"
        note="Contradicted in flagged/blocked outputs"
      />
      <StatCard
        label="Outputs Flagged"
        value={data.flagCount.toLocaleString()}
        accent="text-[#F2BC1B]"
      />
      <StatCard
        label="Outputs Blocked"
        value={data.blockCount.toLocaleString()}
        accent="text-[#D70067]"
      />
      <StatCard
        label="Corroboration Rate"
        value={data.avgCorroborationRate.toFixed(1)}
        suffix="%"
        delta={d.avgCorroborationRate}
        accent="text-[#5BC29E]"
        note="Of in-scope claims"
      />
      <StatCard
        label="Est. Hours Saved"
        value={data.estimatedHoursSaved.toLocaleString()}
        suffix="h"
        delta={d.estimatedHoursSaved}
        accent="text-[#9D5FF5]"
        note="Based on org review baseline"
      />
    </div>
  );
}
