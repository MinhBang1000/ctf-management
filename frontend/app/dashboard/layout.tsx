"use client";

import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { api, ApiError } from "@/lib/api";
import type { LabDashboard, MemberMe } from "@/lib/types";
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
  "/dashboard/settings": "Settings",
};

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

  useEffect(() => {
    if (!member) return;
    api.get<LabDashboard>("/api/v1/dashboard").then((data) => {
      const items: TopbarNotification[] = [];
      if (data.pending_report) {
        items.push({
          id: "pending-report",
          title: "Weekly report ready to review",
          detail: `Week of ${data.pending_report.period_start} – ${data.pending_report.period_end}`,
          dotColor: "var(--accent)",
        });
      }
      if (data.semester_report_nudge) {
        items.push({
          id: "semester-nudge",
          title: `${data.semester_report_nudge.semester_name} ended with no report yet`,
          detail: `Ended ${data.semester_report_nudge.end_date} — generate one from Semesters`,
          dotColor: "var(--status-late)",
        });
      }
      setNotifications(items);
    });
  }, [member]);

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
          />
          <main className="flex-1 overflow-y-auto px-4 pb-[60px] pt-5 sm:px-8 sm:pt-7">
            <div className="mx-auto max-w-[1560px] animate-fade-up">{children}</div>
          </main>
        </div>

        <CommandPalette open={commandOpen} onClose={() => setCommandOpen(false)} />
      </div>
    </MemberContext.Provider>
  );
}
