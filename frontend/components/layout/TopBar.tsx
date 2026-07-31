"use client";

interface TopBarProps {
  title: string;
  subtitle?: string;
  actions?: React.ReactNode;
  periodSelector?: React.ReactNode;
}

export function TopBar({ title, subtitle, actions, periodSelector }: TopBarProps) {
  return (
    <div className="h-14 flex items-center justify-between px-6 border-b border-[var(--bria-border)] bg-[var(--bria-surface)] sticky top-0 z-30">
      <div>
        <h1
          className="text-foreground leading-none"
          style={{
            fontFamily: "var(--font-space-grotesk, 'Space Grotesk', sans-serif)",
            fontSize: 20,
            letterSpacing: "-0.02em",
          }}
        >
          {title}
        </h1>
        {subtitle && <p className="text-xs text-muted-foreground mt-0.5">{subtitle}</p>}
      </div>
      <div className="flex items-center gap-3">
        {periodSelector}
        {actions}
      </div>
    </div>
  );
}
