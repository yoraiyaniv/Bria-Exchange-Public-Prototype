import { auth } from "@/lib/auth";
import { settingsApi } from "@/lib/api";
import { SettingsPageClient } from "@/components/settings/SettingsPageClient";

export const dynamic = "force-dynamic";

export default async function SettingsPage() {
  const session = await auth();
  const token = session?.accessToken ?? "";

  let settings = null;
  let error: string | null = null;

  try {
    settings = await settingsApi.get(token);
  } catch {
    error = "Failed to load settings. Please try again.";
  }

  return (
    <SettingsPageClient
      initialSettings={settings}
      error={error}
      token={token}
      currentUserId={session?.user?.id ?? ""}
      currentUserRole={session?.user?.role ?? "member"}
    />
  );
}
