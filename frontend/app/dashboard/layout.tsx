"use client";

import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { api, ApiError } from "@/lib/api";
import type { MemberMe, Notification } from "@/lib/types";
import { MemberContext } from "@/lib/member-context";
import { Sidebar } from "@/components/layout/sidebar";
import { Topbar, type TopbarNotification } from "@/components/layout/topbar";
import { CommandPalette } from "@/components/layout/command-palette";

const SIDEBAR_COLLAPSED_KEY = "hslab-sidebar-collapsed";
const MOBILE_BREAKPOINT = 900;

const PAGE_TITLES: Record<string, string> = {
  "/dashboard": "Overview",
  "/dashboard/members": "Members",
  "/dashboard/semesters": "Semesters",
  "/dashboard/challenges": "Challenges",
  "/dashboard/progress": "Progress",
  "/dashboard/platforms": "Platforms",
  "/dashboard/reports": "Reports",
  "/dashboard/automation": "Automation",
  "/dashboard/audit-log": "Audit Log",
  "/dashboard/settings": "Settings",
  "/dashboard/profile": "My Profile",
};

function toTopbarNotification(n: Notification): TopbarNotification {
  return {
    id: n.id,
    title: n.title,
    detail: n.body ?? "",
    read: n.read_at !== null,
    dotColor: n.type === "sync_error" ? "var(--status-missing)" : n.type === "semester_report_nudge" ? "var(--status-late)" : "var(--accent)",
  };
}

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const [member, setMember] = useState<MemberMe | null>(null);
  const [notifications, setNotifications] = useState<TopbarNotification[]>([]);
  const [collapsed, setCollapsed] = useState(false);
  const [isMobile, setIsMobile] = useState(false);
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const [commandOpen, setCommandOpen] = useState(false);
  const pathname = usePathname();

  useEffect(() => {
    (async () => {
      try {
        const m = await api.get<MemberMe>("/api/v1/auth/me");
        setMember(m);
      } catch (err) {
        if (err instanceof ApiError && (err.status === 401 || err.status === 403)) {
          router.replace("/login");
          return;
        }
        throw err;
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function loadNotifications() {
    // §12 — real persisted notifications, not the dashboard's own
    // computed-live nudges (those still exist on the Overview page's own
    // banners, unrelated to this bell — see notification_service.py).
    const rows = await api.get<Notification[]>("/api/v1/notifications");
    setNotifications(rows.map(toTopbarNotification));
  }

  useEffect(() => {
    if (!member) return;
    loadNotifications();
  }, [member]);

  async function markRead(id: string) {
    setNotifications((prev) => prev.map((n) => (n.id === id ? { ...n, read: true } : n)));
    await api.post(`/api/v1/notifications/${id}/read`);
  }

  async function dismiss(id: string) {
    setNotifications((prev) => prev.filter((n) => n.id !== id));
    await api.post(`/api/v1/notifications/${id}/dismiss`);
  }

  async function markAllRead() {
    setNotifications((prev) => prev.map((n) => ({ ...n, read: true })));
    await api.post("/api/v1/notifications/read-all");
  }

  useEffect(() => {
    function onResize() {
      setIsMobile(window.innerWidth < MOBILE_BREAKPOINT);
    }
    onResize();
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);

  useEffect(() => {
    const stored = window.localStorage.getItem(SIDEBAR_COLLAPSED_KEY);
    // eslint-disable-next-line react-hooks/set-state-in-effect -- localStorage is client-only, same as theme-context.tsx
    if (stored === "true") setCollapsed(true);
  }, []);

  function toggleCollapse() {
    setCollapsed((v) => {
      window.localStorage.setItem(SIDEBAR_COLLAPSED_KEY, String(!v));
      return !v;
    });
  }

  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setCommandOpen(true);
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  async function logout() {
    await api.post("/api/v1/auth/logout");
    router.replace("/login");
  }

  if (!member) return null;

  return (
    <MemberContext.Provider value={member}>
      <div className="flex min-h-screen bg-background text-foreground">
        <Sidebar
          member={member}
          collapsed={collapsed}
          onToggleCollapse={toggleCollapse}
          isMobile={isMobile}
          mobileOpen={mobileNavOpen}
          onCloseMobile={() => setMobileNavOpen(false)}
          onSignOut={logout}
        />

        <div className="flex h-screen min-w-0 flex-1 flex-col overflow-hidden">
          <Topbar
            title={PAGE_TITLES[pathname] ?? "Dashboard"}
            showHamburger={isMobile}
            onOpenMobileNav={() => setMobileNavOpen(true)}
            onOpenCommand={() => setCommandOpen(true)}
            notifications={notifications}
            onMarkRead={markRead}
            onDismiss={dismiss}
            onMarkAllRead={markAllRead}
          />
          <main className="flex-1 overflow-y-auto px-4 pb-[60px] pt-5 sm:px-8 sm:pt-7">
            <div className="mx-auto max-w-[1560px] animate-fade-up">{children}</div>
          </main>
        </div>

        <CommandPalette open={commandOpen} onClose={() => setCommandOpen(false)} role={member.role} />
      </div>
    </MemberContext.Provider>
  );
}
