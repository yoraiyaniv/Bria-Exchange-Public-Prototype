import { auth } from "@/lib/auth";
import { reviewApi, Verification } from "@/lib/api";
import { ReviewPageClient } from "@/components/review/ReviewPageClient";

export const dynamic = "force-dynamic";

export default async function ReviewPage({
  searchParams,
}: {
  searchParams: Promise<{ tab?: string }>;
}) {
  const session = await auth();
  const { tab } = await searchParams;
  const activeTab = tab === "all" ? "all" : "needs_review";

  let verifications: Verification[] = [];
  let error: string | null = null;

  try {
    verifications = await reviewApi.list(session!.accessToken, activeTab);
  } catch (err) {
    error = err instanceof Error ? err.message : "Failed to load review queue";
  }

  return (
    <ReviewPageClient
      initialVerifications={verifications}
      activeTab={activeTab}
      error={error}
      userSession={session!}
    />
  );
}
