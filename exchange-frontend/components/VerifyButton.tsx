"use client";

import { Loader2 } from "lucide-react";

interface VerifyButtonProps {
  onClick: () => void;
  loading: boolean;
  disabled?: boolean;
}

export default function VerifyButton({
  onClick,
  loading,
  disabled,
}: VerifyButtonProps) {
  return (
    <button
      onClick={onClick}
      disabled={disabled || loading}
      className="inline-flex items-center gap-2 rounded-full bg-bria-purple px-5 py-2 font-body text-sm font-semibold text-white transition-colors hover:bg-bria-purple-2 disabled:opacity-50 disabled:cursor-not-allowed"
    >
      {loading && <Loader2 className="h-4 w-4 animate-spin" />}
      {loading ? "Checking..." : "Verify"}
    </button>
  );
}
