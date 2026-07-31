"use client";

import { useState, useRef, useEffect } from "react";
import { useSession, signOut } from "next-auth/react";
import { useRouter } from "next/navigation";
import { User, LogOut, History } from "lucide-react";

export default function UserMenu() {
  const { data: session } = useSession();
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  if (!session) {
    return (
      <button
        onClick={() => router.push("/login")}
        className="inline-flex items-center gap-2 rounded-full border border-border px-3 py-1.5 font-body text-sm font-semibold text-text-secondary transition-colors hover:border-bria-purple hover:text-bria-purple"
      >
        <User className="h-4 w-4" />
        Sign in
      </button>
    );
  }

  const initials = (session.user?.name || session.user?.email || "U")
    .split(" ")
    .map((w) => w[0])
    .join("")
    .toUpperCase()
    .slice(0, 2);

  return (
    <div ref={menuRef} className="relative">
      <button
        onClick={() => setOpen(!open)}
        className="flex h-8 w-8 items-center justify-center rounded-full bg-bria-purple text-xs font-bold text-white transition-colors hover:bg-bria-purple-2"
        title={session.user?.email || "Account"}
      >
        {initials}
      </button>

      {open && (
        <div className="absolute right-0 top-10 z-50 w-56 rounded-lg bg-card p-1 shadow-lg" style={{boxShadow: '0 4px 24px rgba(0,0,0,0.10), 0 0 0 1px rgba(0,0,0,0.04)'}}>
          <div className="px-3 py-2 border-b border-border/50">
            <p className="font-body text-sm font-semibold text-text-primary truncate">
              {session.user?.name}
            </p>
            <p className="font-body text-xs text-text-muted truncate">
              {session.user?.email}
            </p>
          </div>

          <button
            onClick={() => { setOpen(false); router.push("/history"); }}
            className="flex w-full items-center gap-2 rounded-lg px-3 py-2 font-body text-sm text-text-secondary transition-colors hover:bg-surface-2 hover:text-text-primary"
          >
            <History className="h-4 w-4" />
            Your checks
          </button>

          <button
            onClick={() => { setOpen(false); signOut({ callbackUrl: "/" }); }}
            className="flex w-full items-center gap-2 rounded-lg px-3 py-2 font-body text-sm text-text-secondary transition-colors hover:bg-surface-2 hover:text-text-primary"
          >
            <LogOut className="h-4 w-4" />
            Sign out
          </button>
        </div>
      )}
    </div>
  );
}
