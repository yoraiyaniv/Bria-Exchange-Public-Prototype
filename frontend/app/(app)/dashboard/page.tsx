import { auth } from "@/lib/auth";
import { dashboardApi, DashboardData } from "@/lib/api";
import { DashboardClient } from "@/components/dashboard/DashboardClient";

export const dynamic = "force-dynamic";

export default async function DashboardPage({
  searchParams,
}: {
  searchParams: Promise<{ period?: string }>;
}) {
  const session = await auth();
  const params = await searchParams;
  const period = params.period || "30d";

  let data: DashboardData | null = null;
  let error: string | null = null;

  try {
    data = await dashboardApi.get(session!.accessToken, period);
  } catch (err) {
    error = err instanceof Error ? err.message : "Failed to load dashboard";
  }

  return <DashboardClient data={data} error={error} period={period} />;
}
