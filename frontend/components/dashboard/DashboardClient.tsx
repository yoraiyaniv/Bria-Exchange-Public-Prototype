"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { TopBar } from "@/components/layout/TopBar";
import { DashboardData } from "@/lib/api";
import { HeroStats } from "./HeroStats";
import { PendingReviewBanner } from "./PendingReviewBanner";
import { TrendCharts } from "./TrendCharts";
import { ErrorIntelligence } from "./ErrorIntelligence";
import { LeaderboardAndDomain } from "./LeaderboardAndDomain";
import { SourcesAndActivity } from "./SourcesAndActivity";
import { Button } from "@/components/ui/button";
import { AlertCircle } from "lucide-react";

interface DashboardClientProps {
  data: DashboardData | null;
  error: string | null;
  period: string;
}

export function DashboardClient({ data, error, period }: DashboardClientProps) {
  const router = useRouter();
  const searchParams = useSearchParams();

  function setPeriod(p: string) {
    const params = new URLSearchParams(searchParams.toString());
    params.set("period", p);
    router.push(`/dashboard?${params.toString()}`);
  }

  const PeriodSelector = (
    <div className="flex items-center gap-1 bg-secondary rounded-md p-0.5">
      {(["7d", "30d", "90d"] as const).map((p) => (
        <button
          key={p}
          onClick={() => setPeriod(p)}
          className={`px-3 py-1 text-xs rounded font-medium transition-colors ${
            period === p
              ? "bg-primary text-primary-foreground"
              : "text-muted-foreground hover:text-foreground"
          }`}
        >
          {p}
        </button>
      ))}
    </div>
  );

  if (error) {
    return (
      <>
        <TopBar title="Dashboard" periodSelector={PeriodSelector} />
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

  return (
    <>
      <TopBar
        title="Dashboard"
        subtitle={`${period === "7d" ? "Last 7 days" : period === "30d" ? "Last 30 days" : "Last 90 days"}`}
        periodSelector={PeriodSelector}
      />

      <div className="flex-1 pt-8 px-6 pb-6 space-y-6">
        {/* Pending review alert */}
        {data.pendingReviewCount > 0 && (
          <PendingReviewBanner
            count={data.pendingReviewCount}
            hasBlock={data.pendingReviewHasBlock}
          />
        )}

        {/* Row 1: Hero stats */}
        <HeroStats data={data} />

        {/* Row 2: Trend charts */}
        <TrendCharts data={data} />

        {/* Row 3: Error intelligence */}
        <ErrorIntelligence data={data} />

        {/* Row 4: Leaderboard + Domain + Out-of-scope + Review ops */}
        <LeaderboardAndDomain data={data} />

        {/* Row 5: Source quality + Activity feed */}
        <SourcesAndActivity data={data} />
      </div>
    </>
  );
}
