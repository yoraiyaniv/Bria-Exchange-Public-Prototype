"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { signOut, useSession } from "next-auth/react";
import {
  LayoutDashboard, ClipboardList, FileText, Settings2, Database,
  Settings, ChevronDown, LogOut, User, Bot, DollarSign
} from "lucide-react";
import { cn } from "@/lib/utils";
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem,
  DropdownMenuSeparator, DropdownMenuTrigger
} from "@/components/ui/dropdown-menu";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";

interface SidebarProps {
  pendingReviewCount?: number;
  pendingHasBlock?: boolean;
  isAdmin?: boolean;
}

const NAV_ITEMS = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/review", label: "Review", icon: ClipboardList, hasBadge: true },
  { href: "/audit", label: "Audit Log", icon: FileText },
  { href: "/cost", label: "Cost", icon: DollarSign, adminOnly: true },
  { href: "/policy", label: "Policy Manager", icon: Settings2 },
  { href: "/agents", label: "Agents", icon: Bot },
  { href: "/sources", label: "Sources", icon: Database },
];

export function Sidebar({ pendingReviewCount = 0, pendingHasBlock = false, isAdmin = false }: SidebarProps) {
  const pathname = usePathname();
  const router = useRouter();
  const { data: session } = useSession();
  // Defer client-only components (base-ui DropdownMenu) to avoid SSR ID mismatch
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  const userName = session?.user?.name || "User";
  const orgName = session?.user?.orgName || "Organisation";
  const initials = userName.split(" ").map((n: string) => n[0]).join("").slice(0, 2).toUpperCase();

  return (
    <aside className="fixed left-0 top-0 h-screen w-[220px] flex flex-col bg-[var(--bria-surface)] border-r border-[var(--bria-border)] z-50">
      {/* Logo */}
      <div className="px-4 py-4 border-b border-[var(--bria-border)]">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src="/bria-exchange-logo.png"
          alt="Bria Exchange"
          className="w-full h-auto object-contain"
        />
        <p className="text-[10px] text-muted-foreground mt-1 truncate">{orgName}</p>
      </div>

      {/* Nav */}
      <nav className="flex-1 px-2 py-3 space-y-0.5 overflow-y-auto">
        {NAV_ITEMS.filter(({ adminOnly }) => !adminOnly || isAdmin).map(({ href, label, icon: Icon, hasBadge }) => {
          const isActive = pathname.startsWith(href);
          const showBadge = hasBadge && pendingReviewCount > 0;

          return (
            <Link
              key={href}
              href={href}
              className={cn(
                "flex items-center gap-2.5 px-3 py-2 rounded-md text-sm transition-colors group",
                isActive
                  ? "bg-primary/15 text-primary font-medium"
                  : "text-muted-foreground hover:text-foreground hover:bg-secondary"
              )}
            >
              <Icon className={cn("h-4 w-4 shrink-0", isActive ? "text-primary" : "text-muted-foreground group-hover:text-foreground")} />
              <span className="flex-1">{label}</span>
              {showBadge && (
                <Badge
                  className={cn(
                    "h-5 min-w-5 flex items-center justify-center text-[10px] px-1",
                    pendingHasBlock
                      ? "bg-red-500 text-white hover:bg-red-500"
                      : "bg-amber-500 text-black hover:bg-amber-500"
                  )}
                >
                  {pendingReviewCount > 99 ? "99+" : pendingReviewCount}
                </Badge>
              )}
            </Link>
          );
        })}

        {/* Divider */}
        <div className="border-t border-[var(--bria-border)] my-2" />

        <Link
          href="/settings"
          className={cn(
            "flex items-center gap-2.5 px-3 py-2 rounded-md text-sm transition-colors group",
            pathname.startsWith("/settings")
              ? "bg-primary/15 text-primary font-medium"
              : "text-muted-foreground hover:text-foreground hover:bg-secondary"
          )}
        >
          <Settings className={cn("h-4 w-4 shrink-0", pathname.startsWith("/settings") ? "text-primary" : "text-muted-foreground group-hover:text-foreground")} />
          Settings
        </Link>
      </nav>

      {/* User menu — rendered client-only to avoid base-ui SSR ID mismatch */}
      <div className="border-t border-[var(--bria-border)] p-2">
        {mounted ? (
          <DropdownMenu>
            <DropdownMenuTrigger className="w-full flex items-center gap-2.5 px-2 py-2 rounded-md hover:bg-secondary transition-colors text-left bg-transparent border-none cursor-pointer">
              <Avatar className="h-7 w-7">
                <AvatarFallback className="bg-primary/20 text-primary text-[10px] font-bold">{initials}</AvatarFallback>
              </Avatar>
              <div className="flex-1 min-w-0">
                <p className="text-xs font-medium truncate">{userName}</p>
                <p className="text-[10px] text-muted-foreground truncate">{session?.user?.email}</p>
              </div>
              <ChevronDown className="h-3 w-3 text-muted-foreground shrink-0" />
            </DropdownMenuTrigger>
            <DropdownMenuContent side="top" align="start" className="w-48 bg-card border-border">
              <DropdownMenuItem
                onClick={() => router.push("/settings")}
                className="flex items-center gap-2 cursor-pointer"
              >
                <User className="h-4 w-4" />
                Profile &amp; Settings
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem
                onClick={() => signOut({ callbackUrl: "/login" })}
                className="text-red-400 focus:text-red-400 flex items-center gap-2 cursor-pointer"
              >
                <LogOut className="h-4 w-4" />
                Sign out
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        ) : (
          /* Skeleton placeholder during SSR to match layout */
          <div className="flex items-center gap-2.5 px-2 py-2">
            <div className="h-7 w-7 rounded-full bg-primary/20 shrink-0" />
            <div className="flex-1 min-w-0 space-y-1">
              <div className="h-2.5 w-20 bg-secondary rounded" />
              <div className="h-2 w-28 bg-secondary rounded" />
            </div>
          </div>
        )}
      </div>
    </aside>
  );
}
