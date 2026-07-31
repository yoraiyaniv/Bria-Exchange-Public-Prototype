import { redirect } from "next/navigation";
import { auth } from "@/lib/auth";
import { costApi, CostData } from "@/lib/api";
import { CostPageClient } from "@/components/cost/CostPageClient";

export const dynamic = "force-dynamic";

export default async function CostPage({
  searchParams,
}: {
  searchParams: Promise<{ period?: string }>;
}) {
  const session = await auth();
  if (session?.user?.role !== "admin") redirect("/dashboard");
  const params = await searchParams;
  const period = params.period || "30d";

  let data: CostData | null = null;
  let error: string | null = null;

  try {
    data = await costApi.get(session!.accessToken, period);
  } catch (err) {
    error = err instanceof Error ? err.message : "Failed to load cost data";
  }

  return <CostPageClient data={data} error={error} period={period} />;
}
