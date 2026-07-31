import { notFound } from "next/navigation";
import CheckResultClient from "./client";

const API_URL =
  process.env.API_URL ||
  process.env.NEXT_PUBLIC_API_URL ||
  "http://localhost:8001";

interface PageProps {
  params: Promise<{ id: string }>;
}

async function fetchResult(id: string) {
  const res = await fetch(`${API_URL}/api/results/${id}`, {
    cache: "no-store",
  });
  if (!res.ok) return null;
  return res.json();
}

export default async function CheckPage({ params }: PageProps) {
  const { id } = await params;
  const data = await fetchResult(id);

  if (!data) {
    return (
      <main className="flex min-h-screen flex-col items-center justify-center bg-background px-4">
        <div className="max-w-[480px] text-center space-y-4">
          <h1 className="font-heading text-2xl font-bold tracking-tight text-text-primary">
            This Exchange Check was not found.
          </h1>
          <a
            href="/"
            className="inline-block rounded-full bg-bria-purple px-6 py-2.5 font-body text-sm font-semibold text-white hover:bg-bria-purple-2"
          >
            Go to verify.briaexchange.com
          </a>
        </div>
      </main>
    );
  }

  return <CheckResultClient data={data} />;
}
