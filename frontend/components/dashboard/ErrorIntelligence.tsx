"use client";

import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Cell
} from "recharts";
import { DashboardData } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

interface ErrorIntelligenceProps {
  data: DashboardData;
}

const DISCREPANCY_LABELS: Record<string, string> = {
  factual_date: "Factual — Date",
  factual_quantity: "Factual — Quantity",
  factual_entity: "Factual — Entity",
  factual_status: "Factual — Status",
  factual_relationship: "Factual — Relationship",
  scope_overstatement: "Scope — Overstatement",
  scope_understatement: "Scope — Understatement",
  causal_fabrication: "Causal Fabrication",
  temporal_displacement: "Temporal Displacement",
  context_shift: "Context Shift",
};

const DISCREPANCY_COLORS: Record<string, string> = {
  factual_date:          "#F2BC1B",  // amber — factual errors
  factual_quantity:      "#F2BC1B",
  factual_entity:        "#F2BC1B",
  factual_status:        "#F2BC1B",
  factual_relationship:  "#F2BC1B",
  scope_overstatement:   "#D70067",  // red — scope/causal errors (higher severity)
  scope_understatement:  "#D70067",
  causal_fabrication:    "#D70067",
  temporal_displacement: "#D70067",
  context_shift:         "#D70067",
};

const TOOLTIP_STYLE = {
  backgroundColor: "#1A1A1A",  // --bria-surface
  border: "1px solid #2A2A2A", // --bria-border
  borderRadius: "8px",
  fontSize: "11px",
  color: "#FFFFFF",
};

export function ErrorIntelligence({ data }: ErrorIntelligenceProps) {
  const discrepancyData = Object.entries(data.discrepancyTypeBreakdown)
    .filter(([, v]) => v > 0)
    .sort(([, a], [, b]) => b - a)
    .map(([key, value]) => ({
      name: DISCREPANCY_LABELS[key] || key,
      value,
      key,
    }));

  const { strong, moderate, weak } = data.confirmationStrengthBreakdown;
  const total = strong + moderate + weak;

  const strengthData = [
    { name: "Strong",   value: strong,   pct: total > 0 ? Math.round(strong   / total * 100) : 0, color: "#5BC29E" },
    { name: "Moderate", value: moderate, pct: total > 0 ? Math.round(moderate / total * 100) : 0, color: "#F2BC1B" },
    { name: "Weak",     value: weak,     pct: total > 0 ? Math.round(weak     / total * 100) : 0, color: "#D70067" },
  ];

  return (
    <div className="grid grid-cols-2 gap-4">
      {/* Discrepancy Type Breakdown */}
      <Card className="bg-card border-border" style={{ borderRadius: 12 }}>
        <CardHeader className="pb-2 pt-4 px-4">
          <CardTitle className="card-label">Discrepancy Type Breakdown</CardTitle>
          <p className="text-[11px] text-muted-foreground mt-0.5">What kind of errors your AI makes</p>
        </CardHeader>
        <CardContent className="px-4 pb-4">
          {discrepancyData.length === 0 ? (
            <div className="h-[200px] flex items-center justify-center text-xs text-muted-foreground">
              No contradictions detected in this period
            </div>
          ) : (
            <ResponsiveContainer width="100%" height={220}>
              <BarChart layout="vertical" data={discrepancyData} margin={{ top: 0, right: 20, left: 0, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#2A2A2A" horizontal={false} />
                <XAxis type="number" tick={{ fontSize: 9, fill: "#6b7280" }} tickLine={false} axisLine={false} />
                <YAxis type="category" dataKey="name" width={140} tick={{ fontSize: 9, fill: "#6b7280" }} tickLine={false} axisLine={false} />
                <Tooltip contentStyle={TOOLTIP_STYLE} />
                <Bar dataKey="value" radius={[0, 2, 2, 0]} name="Count">
                  {discrepancyData.map((entry) => (
                    <Cell key={entry.key} fill={DISCREPANCY_COLORS[entry.key] || "#F2BC1B"} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          )}
        </CardContent>
      </Card>

      {/* Confirmation Strength Distribution */}
      <Card className="bg-card border-border" style={{ borderRadius: 12 }}>
        <CardHeader className="pb-2 pt-4 px-4">
          <CardTitle className="card-label">Confirmation Strength</CardTitle>
          <p className="text-[11px] text-muted-foreground mt-0.5">Quality of corroborating evidence</p>
        </CardHeader>
        <CardContent className="px-4 pb-4 space-y-4">
          {total === 0 ? (
            <div className="h-[200px] flex items-center justify-center text-xs text-muted-foreground">
              No corroborated claims in this period
            </div>
          ) : (
            <>
              {/* Stacked bar */}
              <div className="h-6 flex rounded-full overflow-hidden gap-0.5">
                {strengthData.filter(s => s.value > 0).map(s => (
                  <div
                    key={s.name}
                    style={{ width: `${s.pct}%`, backgroundColor: s.color }}
                    title={`${s.name}: ${s.pct}%`}
                  />
                ))}
              </div>

              {/* Legend */}
              <div className="grid grid-cols-3 gap-3">
                {strengthData.map(s => (
                  <div key={s.name} className="space-y-1">
                    <div className="flex items-center gap-1.5">
                      <div className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: s.color }} />
                      <span className="text-xs text-muted-foreground">{s.name}</span>
                    </div>
                    <p style={{ fontFamily: "var(--font-space-grotesk, 'Space Grotesk', sans-serif)", fontWeight: 700, fontSize: 22, color: s.color, lineHeight: 1 }}>{s.pct}%</p>
                    <p className="text-[10px] text-muted-foreground">{s.value.toLocaleString()} claims</p>
                  </div>
                ))}
              </div>

              <p className="text-[11px] text-muted-foreground pt-2 border-t border-border">
                {strengthData[0].pct < 30
                  ? "⚠ Low strong-source share — corroborated claims may lack primary source backing"
                  : "Corroboration quality is healthy"}
              </p>
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
