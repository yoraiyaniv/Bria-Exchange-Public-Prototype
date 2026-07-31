import { auth } from "@/lib/auth";
import { sourcesApi, type ConnectedSource, type Connector, type ComingSoonSource, type CustomSource } from "@/lib/api";
import { SourcesPageClient } from "@/components/sources/SourcesPageClient";

export const dynamic = "force-dynamic";

export default async function SourcesPage() {
  const session = await auth();
  const token = session?.accessToken ?? "";
  const apiBase = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:3001";

  let catalog: Connector[] = [];
  let connectedSources: ConnectedSource[] = [];
  let comingSoon: ComingSoonSource[] = [];
  let customMine: CustomSource[] = [];
  let customCommunity: CustomSource[] = [];
  let error: string | null = null;

  try {
    const [catalogRes, connected, customRes] = await Promise.all([
      sourcesApi.getCatalog(token),
      sourcesApi.getConnected(token),
      sourcesApi.getCustomSources(token),
    ]);
    catalog = catalogRes.sources ?? [];
    comingSoon = catalogRes.comingSoon ?? [];
    connectedSources = connected;
    customMine = customRes.mine ?? [];
    customCommunity = customRes.community ?? [];
  } catch (e) {
    error = "Failed to load sources. Please try again.";
  }

  return (
    <SourcesPageClient
      catalog={catalog}
      connectedSources={connectedSources}
      comingSoon={comingSoon}
      customMine={customMine}
      customCommunity={customCommunity}
      error={error}
      token={token}
      apiBase={apiBase}
    />
  );
}
