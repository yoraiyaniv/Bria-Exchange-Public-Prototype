import { auth } from "@/lib/auth";
import { redirect } from "next/navigation";
import { Sidebar } from "@/components/layout/Sidebar";
import { dashboardApi } from "@/lib/api";

export default async function AppLayout({ children }: { children: React.ReactNode }) {
  const session = await auth();
  if (!session?.user) {
    redirect("/login");
  }

  // Fetch pending review count for sidebar badge
  let pendingCount = 0;
  let hasBlock = false;
  try {
    const data = await dashboardApi.get(session.accessToken, "7d");
    pendingCount = data.pendingReviewCount;
    hasBlock = data.pendingReviewHasBlock;
  } catch {
    // Non-critical — don't fail the layout
  }

  return (
    <div className="flex h-screen bg-background">
      <Sidebar pendingReviewCount={pendingCount} pendingHasBlock={hasBlock} isAdmin={session.user.role === "admin"} />
      <main className="flex-1 ml-[220px] flex flex-col min-h-screen overflow-y-auto">
        {children}
      </main>
    </div>
  );
}
