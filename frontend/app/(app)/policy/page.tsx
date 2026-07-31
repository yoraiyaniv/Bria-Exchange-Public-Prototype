import { auth } from "@/lib/auth";
import { agentsApi, sourcesApi, Agent, ConnectedSource } from "@/lib/api";
import { PolicyPageClient } from "@/components/policy/PolicyPageClient";

export const dynamic = "force-dynamic";

export default async function PolicyPage() {
  const session = await auth();

  let agents: Agent[] = [];
  let sources: ConnectedSource[] = [];
  let error: string | null = null;

  try {
    [agents, sources] = await Promise.all([
      agentsApi.list(session!.accessToken),
      sourcesApi.list(session!.accessToken),
    ]);
  } catch (err) {
    error = err instanceof Error ? err.message : "Failed to load policy data";
  }

  return (
    <PolicyPageClient
      initialAgents={agents}
      connectedSources={sources}
      error={error}
      token={session!.accessToken}
    />
  );
}
