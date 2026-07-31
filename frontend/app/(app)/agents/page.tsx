import { auth } from "@/lib/auth";
import { agentsApi, Agent } from "@/lib/api";
import { AgentsPageClient } from "@/components/agents/AgentsPageClient";

export const dynamic = "force-dynamic";

export default async function AgentsPage() {
  const session = await auth();

  let agents: Agent[] = [];
  let error: string | null = null;

  try {
    agents = await agentsApi.list(session!.accessToken);
  } catch (err) {
    error = err instanceof Error ? err.message : "Failed to load agents";
  }

  return (
    <AgentsPageClient
      initialAgents={agents}
      error={error}
      token={session!.accessToken}
    />
  );
}
