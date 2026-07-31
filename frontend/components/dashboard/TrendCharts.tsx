"use client";

import {
  AreaChart, Area, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  Legend, ResponsiveContainer, LineChart, Line
} from "recharts";
import { DashboardData } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

interface TrendChartsProps {
  data: DashboardData;
}

const TOOLTIP_STYLE = {
  backgroundColor: "#1A1A1A",  // --bria-surface
  border: "1px solid #2A2A2A", // --bria-border
  borderRadius: "8px",
  fontSize: "11px",
  color: "#FFFFFF",            // --foreground
};

export function TrendCharts({ data }: TrendChartsProps) {
  // Merge corroboration + coverage by date
  const corrobByDate: Record<string, number> = {};
  const coverageByDate: Record<string, number> = {};
  data.corroborationRateByDay.forEach(d => corrobByDate[d.date] = d.value);
  data.coverageRatioByDay.forEach(d => coverageByDate[d.date] = d.value);

  const trendLineData = data.corroborationRateByDay.map(d => ({
    date: d.date.slice(5), // MM-DD
    corroboration: d.value,
    coverage: coverageByDate[d.date] || 0,
  }));

  const decisionData = data.decisionByDay.map(d => ({
    date: d.date.slice(5),
    pass: d.pass,
    flag: d.flag,
    block: d.block,
  }));

  return (
    <div className="grid grid-cols-3 gap-4">
      {/* Left 2/3: Decision distribution stacked bar */}
      <Card className="col-span-2 bg-card border-border" style={{ borderRadius: 12 }}>
        <CardHeader className="pb-2 pt-4 px-4">
          <CardTitle
            className="text-muted-foreground"
            style={{
              fontFamily: "var(--font-sora, 'Sora', sans-serif)",
              fontSize: 10,
              letterSpacing: "0.08em",
              textTransform: "uppercase",
              fontWeight: 400,
            }}
          >
            Decision Distribution
          </CardTitle>
        </CardHeader>
        <CardContent className="px-4 pb-4">
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={decisionData} margin={{ top: 0, right: 0, left: -20, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#2A2A2A" vertical={false} />
              <XAxis dataKey="date" tick={{ fontSize: 10, fill: "#9E9E9E" }} tickLine={false} axisLine={false} />
              <YAxis tick={{ fontSize: 10, fill: "#9E9E9E" }} tickLine={false} axisLine={false} />
              <Tooltip contentStyle={TOOLTIP_STYLE} />
              <Legend iconSize={8} wrapperStyle={{ fontSize: "11px" }} />
              <Bar dataKey="pass" stackId="a" fill="#5BC29E" name="Pass" radius={[0,0,0,0]} />
              <Bar dataKey="flag" stackId="a" fill="#F2BC1B" name="Flag" radius={[0,0,0,0]} />
              <Bar dataKey="block" stackId="a" fill="#D70067" name="Block" radius={[2,2,0,0]} />
            </BarChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>

      {/* Right 1/3: Corroboration Rate + Coverage Ratio trend lines */}
      <Card className="col-span-1 bg-card border-border" style={{ borderRadius: 12 }}>
        <CardHeader className="pb-2 pt-4 px-4">
          <CardTitle
            className="text-muted-foreground"
            style={{
              fontFamily: "var(--font-sora, 'Sora', sans-serif)",
              fontSize: 10,
              letterSpacing: "0.08em",
              textTransform: "uppercase",
              fontWeight: 400,
            }}
          >
            Quality Trends
          </CardTitle>
        </CardHeader>
        <CardContent className="px-4 pb-4">
          <ResponsiveContainer width="100%" height={200}>
            <LineChart data={trendLineData} margin={{ top: 0, right: 0, left: -20, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#2A2A2A" vertical={false} />
              <XAxis dataKey="date" tick={{ fontSize: 9, fill: "#9E9E9E" }} tickLine={false} axisLine={false} interval="preserveStartEnd" />
              <YAxis tick={{ fontSize: 9, fill: "#9E9E9E" }} tickLine={false} axisLine={false} domain={[0, 100]} unit="%" />
              <Tooltip contentStyle={TOOLTIP_STYLE} formatter={(v) => typeof v === 'number' ? `${v.toFixed(1)}%` : String(v)} />
              <Legend iconSize={8} wrapperStyle={{ fontSize: "10px" }} />
              <Line type="monotone" dataKey="corroboration" stroke="#5BC29E" strokeWidth={2} dot={false} name="Corroboration" />
              <Line type="monotone" dataKey="coverage" stroke="#9D5FF5" strokeWidth={1.5} strokeDasharray="4 2" dot={false} name="Coverage" />
            </LineChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>
    </div>
  );
}
