"use client";

import { useEffect, useState } from "react";
import { useSession } from "next-auth/react";
import { getUsage } from "@/lib/api";
import type { UsageResponse } from "@/lib/api";

export default function UsageMeter() {
  const { data: session } = useSession();
  const [usage, setUsage] = useState<UsageResponse | null>(null);

  useEffect(() => {
    if (!session?.accessToken) return;
    getUsage(session.accessToken).then(setUsage).catch(() => {});
  }, [session?.accessToken]);

  if (!session || !usage) return null;

  const percent = Math.min(100, (usage.used / usage.limit) * 100);

  return (
    <div className="w-full space-y-1">
      <div className="h-1.5 w-full overflow-hidden rounded-full bg-muted">
        <div
          className="h-full rounded-full bg-bria-purple transition-all duration-300"
          style={{ width: `${percent}%` }}
        />
      </div>
      <p className="font-body text-xs text-text-secondary">
        {usage.used} of {usage.limit} claims used this month
      </p>
    </div>
  );
}
