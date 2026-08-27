"use client";

import { useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import type { LabDashboard, Platform } from "@/lib/types";
import Link from "next/link";
import { RefreshCw } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { StatusBadge } from "@/components/status-badge";
import { useToast } from "@/lib/toast-context";

const STATUS_META: Record<string, { label: string; color: string }> = {
  early: { label: "Early", color: "var(--status-early)" },
  done: { label: "Done", color: "var(--status-done)" },
  late: { label: "Late", color: "var(--status-late)" },
  missing: { label: "Missing", color: "var(--status-missing)" },
};

export default function DashboardPage() {
  const { push: pushToast } = useToast();
  const [data, setData] = useState<LabDashboard | null>(null);
  const [focusPlatform, setFocusPlatform] = useState<Platform | null>(null);
  const [syncing, setSyncing] = useState(false);

  async function load() {
    const [dashboard, platforms] = await Promise.all([
      api.get<LabDashboard>("/api/v1/dashboard"),
      api.get<Platform[]>("/api/v1/platforms"),
    ]);
    setData(dashboard);
    setFocusPlatform(platforms.find((p) => p.is_focus) ?? null);
  }

  useEffect(() => {
    load();
  }, []);

  async function syncNow() {
    if (!focusPlatform) return;
    setSyncing(true);
    try {
      const result = await api.post<{ updated: unknown[]; errors: string[] }>(
        `/api/v1/platforms/${focusPlatform.id}/sync-now`
      );
      await load();
      if (result.errors.length > 0) {
        pushToast("error", `Sync finished with ${result.errors.length} error(s)`);
      } else {
        pushToast("success", `Sync complete — ${result.updated.length} update(s) found`);
      }
    } catch (err) {
      pushToast("error", err instanceof ApiError ? err.message : "Sync failed");
    } finally {
      setSyncing(false);
    }
  }

  if (!data) return null;

  const statusEntries: [keyof LabDashboard["status_counts"], number][] = [
    ["early", data.status_counts.early ?? 0],
    ["done", data.status_counts.done ?? 0],
    ["late", data.status_counts.late ?? 0],
    ["missing", data.status_counts.missing ?? 0],
  ];
  const total = statusEntries.reduce((sum, [, count]) => sum + count, 0) || 1;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-[22px] font-extrabold tracking-tight">Overview</h1>
          <p className="text-[13.5px] text-muted">
            {data.current_semester_name ? `Current semester: ${data.current_semester_name}` : "No current semester set"}
            {data.focus_platform_name && ` · ${data.focus_platform_name} focus platform`}
          </p>
          {data.semester_report_nudge && (
            <p className="mt-1 text-sm text-muted">
              {data.semester_report_nudge.semester_name} ended {data.semester_report_nudge.end_date} with no semester
              report yet —{" "}
              <Link href="/dashboard/semesters" className="underline">
                generate one
              </Link>
              .
            </p>
          )}
        </div>
        <button
          onClick={syncNow}
          disabled={syncing || !focusPlatform}
          title={!focusPlatform ? "No focus platform configured" : undefined}
          className="flex items-center gap-2 rounded-[9px] border border-[var(--border)] bg-surface px-4 py-2.5 text-[13px] font-semibold transition-colors hover:border-accent hover:text-accent disabled:opacity-50"
        >
          <RefreshCw size={15} className={syncing ? "animate-spin-slow" : ""} />
          {syncing ? "Syncing…" : "Sync now"}
        </button>
      </div>

      {data.pending_report && (
        <Card className="border-2" style={{ borderColor: "var(--accent)", background: "color-mix(in oklch, var(--accent) 6%, var(--surface))" }}>
          <CardContent className="flex flex-wrap items-center justify-between gap-3 py-5">
            <div>
              <p className="text-sm font-semibold text-accent">📋 Weekly report awaiting your approval</p>
              <p className="text-sm text-muted">
                Week of {data.pending_report.period_start} – {data.pending_report.period_end}
              </p>
            </div>
            <Link href="/dashboard/reports">
              <span className="inline-flex items-center rounded-[9px] bg-accent px-3.5 py-2 text-sm font-semibold text-accent-foreground hover:brightness-110">
                Review &amp; send
              </span>
            </Link>
          </CardContent>
        </Card>
      )}

      {!data.focus_platform_configured && (
        <Card style={{ borderColor: "var(--status-missing)" }}>
          <CardContent className="flex flex-wrap items-center justify-between gap-2 py-4">
            <p className="text-sm text-[var(--status-missing)]">
              ⚠ Focus platform has no credentials configured — automatic sync will not run.
            </p>
            <Link href="/dashboard/platforms" className="text-sm font-medium underline">
              Configure now
            </Link>
          </CardContent>
        </Card>
      )}

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3.5">
        <Card className="hs-hover-card">
          <CardContent className="py-4">
            <p className="mb-2 text-xs font-semibold text-muted">Members</p>
            <p className="font-data text-[26px] font-bold">
              {data.active_member_count}
              <span className="text-base font-normal text-muted"> / {data.member_count}</span>
            </p>
          </CardContent>
        </Card>
        <Card className="hs-hover-card">
          <CardContent className="py-4">
            <p className="mb-2 text-xs font-semibold text-muted">Semesters</p>
            <p className="font-data text-[26px] font-bold">{data.semester_count}</p>
          </CardContent>
        </Card>
        <Card className="hs-hover-card">
          <CardContent className="py-4">
            <p className="mb-2 text-xs font-semibold text-muted">Challenges</p>
            <p className="font-data text-[26px] font-bold">{data.challenge_count}</p>
          </CardContent>
        </Card>
        <Card className="hs-hover-card">
          <CardContent className="py-4">
            <p className="mb-2 text-xs font-semibold text-muted">Reminders sent (7d)</p>
            <p className="font-data text-[26px] font-bold">{data.reminders_sent_this_week}</p>
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-1 items-start gap-3.5 lg:grid-cols-[1.4fr_1fr]">
        <Card>
          <CardContent className="py-5">
            <p className="mb-3.5 text-sm font-bold">Status breakdown — this semester</p>
            <div className="flex h-3.5 overflow-hidden rounded-[7px] bg-background">
              {statusEntries.map(([status, count]) => (
                <div
                  key={status}
                  style={{ width: `${(count / total) * 100}%`, background: STATUS_META[status].color }}
                />
              ))}
            </div>
            <div className="mt-3.5 flex flex-wrap gap-[18px]">
              {statusEntries.map(([status, count]) => (
                <div key={status} className="flex items-center gap-1.5 text-[12.5px] text-muted">
                  <span className="h-2 w-2 rounded-sm" style={{ background: STATUS_META[status].color }} />
                  {STATUS_META[status].label}{" "}
                  <span className="font-data font-semibold text-foreground">
                    {Math.round((count / total) * 100)}%
                  </span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        <div className="flex flex-col gap-3">
          {data.status_counts.missing > 0 || data.status_counts.late > 0 ? (
            <Card style={{ borderColor: "var(--status-late)" }}>
              <CardContent className="py-3.5">
                <p className="mb-1 text-[13px] font-bold">⚠ Members need a nudge</p>
                <p className="text-xs text-muted">
                  {data.status_counts.missing} missing, {data.status_counts.late} late right now
                </p>
              </CardContent>
            </Card>
          ) : null}
          <Card>
            <CardContent className="py-3.5">
              <p className="mb-1 text-[13px] font-bold">Reports</p>
              <p className="mb-2.5 text-xs text-muted">Review weekly and semester reports</p>
              <Link href="/dashboard/reports" className="text-xs font-bold text-accent">
                Go to Reports →
              </Link>
            </CardContent>
          </Card>
        </div>
      </div>

      <div>
        <h2 className="mb-3 text-sm font-semibold text-muted">Progress status breakdown</h2>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3.5">
          {statusEntries.map(([status, count]) => (
            <Card key={status} className="hs-hover-card">
              <CardContent className="flex items-center justify-between py-4">
                <StatusBadge status={status} />
                <span className="font-data text-2xl font-bold">{count}</span>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    </div>
  );
}
