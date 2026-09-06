"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Activity,
  Calendar,
  ChevronLeft,
  ChevronRight,
  ClipboardList,
  FileText,
  History,
  LayoutGrid,
  Link2,
  LogOut,
  Settings as SettingsIcon,
  Target,
  Users,
} from "lucide-react";
import type { MemberMe, MemberRole } from "@/lib/types";

// §6 — `roles: undefined` means every role can see it; otherwise only the
// listed roles. Kept alongside the nav definition itself (not a separate
// lookup table) so a new page's visibility is defined in exactly one
// place. The backend's own role checks (require_roles(...) on each
// endpoint) are the real security boundary — this only controls what's
// offered in the UI, per §6's "keep backend authorization checks in
// place even when a page is hidden."
export const NAV_ITEMS: { href: string; label: string; icon: typeof LayoutGrid; roles?: MemberRole[] }[] = [
  { href: "/dashboard", label: "Overview", icon: LayoutGrid },
  { href: "/dashboard/members", label: "Members", icon: Users },
  { href: "/dashboard/semesters", label: "Semesters", icon: Calendar },
  { href: "/dashboard/challenges", label: "Challenges", icon: Target },
  { href: "/dashboard/progress", label: "Progress", icon: Activity },
  { href: "/dashboard/platforms", label: "Platforms", icon: Link2 },
  { href: "/dashboard/reports", label: "Reports", icon: FileText, roles: ["lab_leader"] },
  { href: "/dashboard/automation", label: "Automation", icon: History, roles: ["lab_leader"] },
  { href: "/dashboard/audit-log", label: "Audit Log", icon: ClipboardList, roles: ["lab_leader"] },
  { href: "/dashboard/settings", label: "Settings", icon: SettingsIcon, roles: ["lab_leader"] },
];

export function visibleNavItems(role: MemberRole) {
  return NAV_ITEMS.filter((item) => !item.roles || item.roles.includes(role));
}

function initialsOf(fullName: string) {
  return fullName.split(" ").slice(-2).map((w) => w[0]).join("").toUpperCase();
}

interface SidebarProps {
  member: MemberMe;
  collapsed: boolean;
  onToggleCollapse: () => void;
  isMobile: boolean;
  mobileOpen: boolean;
  onCloseMobile: () => void;
  onSignOut: () => void;
}

export function Sidebar({ member, collapsed, onToggleCollapse, isMobile, mobileOpen, onCloseMobile, onSignOut }: SidebarProps) {
  const pathname = usePathname();
  const effectiveCollapsed = collapsed && !isMobile;
  const showLabel = !effectiveCollapsed;
  const width = isMobile ? 240 : effectiveCollapsed ? 68 : 232;

  return (
    <>
      {isMobile && mobileOpen && (
        <div onClick={onCloseMobile} className="fixed inset-0 z-30 animate-fade-up bg-black/50" />
      )}
      <aside
        style={{
          width,
          minWidth: width,
          left: isMobile ? (mobileOpen ? 0 : -260) : undefined,
        }}
        className={`z-[31] flex h-screen flex-shrink-0 flex-col border-r border-[var(--border)] bg-[var(--sidebar-bg)] transition-[width,left] duration-200 ${
          isMobile ? "fixed top-0" : "relative"
        }`}
      >
        <div
          className={`flex h-[60px] flex-shrink-0 items-center gap-2.5 border-b border-[var(--border)] ${
            effectiveCollapsed ? "justify-center px-0" : "px-4"
          }`}
        >
          <div className="flex h-[30px] w-[30px] min-w-[30px] items-center justify-center rounded-[7px] bg-accent font-mono text-sm font-bold text-accent-foreground">
            &gt;_
          </div>
          {showLabel && (
            <div className="overflow-hidden whitespace-nowrap">
              <div className="text-[14.5px] font-extrabold leading-tight tracking-tight">HSLab CTF</div>
              <div className="font-data text-[11px] text-muted">lab: {member.tenant_name}</div>
            </div>
          )}
        </div>

        <nav className="flex flex-1 flex-col gap-0.5 overflow-y-auto p-2.5">
          {visibleNavItems(member.role).map((item) => {
            const active = pathname === item.href;
            const Icon = item.icon;
            return (
              <Link
                key={item.href}
                href={item.href}
                onClick={onCloseMobile}
                title={effectiveCollapsed ? item.label : undefined}
                className={`flex w-full items-center gap-3 rounded-[9px] px-2.5 py-2 text-[13.5px] font-semibold transition-colors ${
                  active ? "bg-[var(--surface-hover)] text-accent" : "text-foreground hover:bg-[var(--surface-hover)]"
                } ${effectiveCollapsed ? "justify-center" : ""}`}
              >
                <Icon size={20} strokeWidth={1.75} className="flex-shrink-0" />
                {showLabel && <span className="flex-1 truncate text-left">{item.label}</span>}
              </Link>
            );
          })}
        </nav>

        <div className={`flex flex-shrink-0 items-center gap-2.5 border-t border-[var(--border)] p-3 ${effectiveCollapsed ? "justify-center" : ""}`}>
          <Link
            href="/dashboard/profile"
            onClick={onCloseMobile}
            title="My profile"
            className="flex h-[30px] w-[30px] min-w-[30px] items-center justify-center rounded-lg bg-[var(--surface-hover)] font-mono text-xs font-bold text-accent"
          >
            {initialsOf(member.full_name)}
          </Link>
          {showLabel && (
            <>
              <Link href="/dashboard/profile" onClick={onCloseMobile} className="flex-1 overflow-hidden">
                <div className="truncate text-[12.5px] font-semibold">{member.full_name}</div>
                <div className="truncate text-[11px] text-muted capitalize">{member.role.replace("_", " ")}</div>
              </Link>
              <button
                onClick={onSignOut}
                title="Sign out"
                className="flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-lg text-muted hover:bg-[var(--surface-hover)] hover:text-foreground"
              >
                <LogOut size={16} strokeWidth={1.75} />
              </button>
            </>
          )}
        </div>

        {!isMobile && (
          <button
            onClick={onToggleCollapse}
            title={effectiveCollapsed ? "Expand sidebar" : "Collapse sidebar"}
            className="absolute right-[-11px] top-[52px] flex h-[22px] w-[22px] items-center justify-center rounded-full border border-[var(--border)] bg-[var(--surface)] text-muted shadow-[0_2px_6px_rgba(0,0,0,0.15)]"
          >
            {effectiveCollapsed ? <ChevronRight size={13} /> : <ChevronLeft size={13} />}
          </button>
        )}
      </aside>
    </>
  );
}
