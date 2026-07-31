"use client";

import { Check } from "lucide-react";

export default function Logo() {
  return (
    <div className="flex items-center gap-2">
      <div className="flex h-7 w-7 items-center justify-center rounded-[6px] bg-bria-purple">
        <Check className="h-4 w-4 text-white" strokeWidth={3} />
      </div>
      <span className="font-heading text-xl font-bold tracking-tight">
        <span className="text-text-primary">Bria</span>{" "}
        <span className="text-bria-purple">Exchange</span>
      </span>
    </div>
  );
}
