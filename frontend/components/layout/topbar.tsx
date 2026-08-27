"use client";

import { useState, type ReactNode } from "react";
import { Bell, Menu, Moon, Search, Sun } from "lucide-react";
import { useTheme } from "@/lib/theme-context";

export interface TopbarNotification {
  id: string;
  title: string;
  detail: string;
  dotColor?: string;
}

interface TopbarProps {
  title: string;
  badge?: string;
  showHamburger?: boolean;
  onOpenMobileNav?: () => void;
  onOpenCommand?: () => void;
  notifications?: TopbarNotification[];
  rightExtra?: ReactNode;
}

export function Topbar({ title, badge, showHamburger, onOpenMobileNav, onOpenCommand, notifications, rightExtra }: TopbarProps) {
  const { theme, toggleTheme } = useTheme();
  const [bellOpen, setBellOpen] = useState(false);
  const hasNotifications = (notifications?.length ?? 0) > 0;

  return (
    <header className="flex h-[60px] flex-shrink-0 items-center gap-3.5 border-b border-[var(--border)] bg-surface px-5">
      {showHamburger && (
        <button
          onClick={onOpenMobileNav}
          className="flex h-[34px] w-[34px] flex-shrink-0 items-center justify-center rounded-lg border border-[var(--border)] text-foreground"
        >
          <Menu size={18} />
        </button>
      )}

      <div className="flex min-w-0 items-center gap-2 truncate text-[15px] font-bold">
        <span className="truncate">{title}</span>
        {badge && (
          <span
            className="flex-shrink-0 rounded-[5px] px-1.5 py-0.5 font-mono text-[9px] font-bold"
            style={{ background: "var(--root-badge-bg)", color: "var(--root-badge-fg)" }}
          >
            {badge}
          </span>
        )}
      </div>

      {onOpenCommand && (
        <>
          {/* Full search pill — hidden below md, where there's no room for it */}
          <button
            onClick={onOpenCommand}
            className="ml-auto hidden w-[220px] items-center gap-2 rounded-[9px] border border-[var(--border)] bg-background px-3 py-2 text-[13px] text-muted transition-colors hover:border-accent md:flex"
          >
            <Search size={16} className="flex-shrink-0" />
            <span className="flex-1 text-left">Search or jump to…</span>
            <span className="rounded border border-[var(--border)] px-1 font-mono text-[10px]">⌘K</span>
          </button>
          {/* Icon-only search trigger for narrow screens — same command palette */}
          <button
            onClick={onOpenCommand}
            title="Search"
            className="ml-auto flex h-[34px] w-[34px] flex-shrink-0 items-center justify-center rounded-lg border border-[var(--border)] text-foreground hover:bg-[var(--surface-hover)] md:hidden"
          >
            <Search size={17} />
          </button>
        </>
      )}

      <button
        onClick={toggleTheme}
        title="Toggle theme"
        className={`flex h-[34px] w-[34px] flex-shrink-0 items-center justify-center rounded-lg border border-[var(--border)] text-foreground hover:bg-[var(--surface-hover)] ${onOpenCommand ? "" : "ml-auto"}`}
      >
        {theme === "dark" ? <Sun size={17} /> : <Moon size={17} />}
      </button>

      {notifications !== undefined && (
        <div className="relative flex-shrink-0">
          <button
            onClick={() => setBellOpen((v) => !v)}
            title="Notifications"
            className="relative flex h-[34px] w-[34px] items-center justify-center rounded-lg border border-[var(--border)] text-foreground hover:bg-[var(--surface-hover)]"
          >
            <Bell size={17} />
            {hasNotifications && (
              <span className="absolute right-1.5 top-1.5 h-[7px] w-[7px] rounded-full border-[1.5px] border-surface bg-[var(--status-late)]" />
            )}
          </button>
          {bellOpen && (
            <div className="absolute right-0 top-[42px] z-40 w-[calc(100vw-2.5rem)] max-w-[300px] animate-fade-up overflow-hidden rounded-xl border border-[var(--border)] bg-surface shadow-[0_16px_40px_rgba(0,0,0,0.2)]">
              <div className="border-b border-[var(--border)] px-3.5 py-3 text-[12.5px] font-bold">Notifications</div>
              {hasNotifications ? (
                notifications!.map((n) => (
                  <div key={n.id} className="flex gap-2.5 border-b border-[var(--border)] px-3.5 py-3 last:border-b-0">
                    <span
                      className="mt-[5px] h-[7px] w-[7px] flex-shrink-0 rounded-full"
                      style={{ background: n.dotColor ?? "var(--accent)" }}
                    />
                    <div>
                      <div className="text-[12.5px] font-semibold">{n.title}</div>
                      <div className="mt-0.5 text-[11.5px] text-muted">{n.detail}</div>
                    </div>
                  </div>
                ))
              ) : (
                <div className="px-3.5 py-4 text-center text-[12.5px] text-muted">Nothing new right now.</div>
              )}
            </div>
          )}
        </div>
      )}

      {rightExtra}
    </header>
  );
}
