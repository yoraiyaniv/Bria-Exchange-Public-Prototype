import { auth } from "@/lib/auth";
import { auditApi, agentsApi, Agent } from "@/lib/api";
import { AuditPageClient } from "@/components/audit/AuditPageClient";

export const dynamic = "force-dynamic";

export default async function AuditPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string>>;
}) {
  const session = await auth();
  const params = await searchParams;

  const queryParams: Record<string, string> = {};
  if (params.decision) queryParams.decision = params.decision;
  if (params.domain) queryParams.domain = params.domain;
  if (params.agentId) queryParams.agentId = params.agentId;
  if (params.reviewStatus) queryParams.reviewStatus = params.reviewStatus;
  if (params.from) queryParams.from = params.from;
  if (params.to) queryParams.to = params.to;
  if (params.page) queryParams.page = params.page;

  let result = null;
  let error = null;
  let agents: Agent[] = [];

  try {
    [result, agents] = await Promise.all([
      auditApi.list(session!.accessToken, queryParams),
      agentsApi.list(session!.accessToken),
    ]);
  } catch (err) {
    error = err instanceof Error ? err.message : "Failed to load audit log";
  }

  return (
    <AuditPageClient
      initialData={result}
      error={error}
      token={session!.accessToken}
      apiBase={process.env.NEXT_PUBLIC_API_URL || "http://localhost:3001"}
      agents={agents}
    />
  );
}
