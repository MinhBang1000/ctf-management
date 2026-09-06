"use client";

import { Fragment, useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import type { JobRun, SyncRun } from "@/lib/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useToast } from "@/lib/toast-context";

function statusTone(status: string) {
  if (status === "ok" || status === "success" || status === "done") return "text-[var(--status-done)]";
  if (status === "error" || status === "failed") return "text-[var(--status-missing)]";
  if (status === "partial") return "text-[var(--status-late)]";
  if (status === "running") return "text-accent";
  return "text-muted";
}

export default function AutomationPage() {
  const { push: pushToast } = useToast();
  const [syncRuns, setSyncRuns] = useState<SyncRun[]>([]);
  const [jobRuns, setJobRuns] = useState<JobRun[]>([]);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [retrying, setRetrying] = useState<string | null>(null);

  async function load() {
    const [s, j] = await Promise.all([
      api.get<SyncRun[]>("/api/v1/automation/sync-runs"),
      api.get<JobRun[]>("/api/v1/automation/job-runs"),
    ]);
    setSyncRuns(s);
    setJobRuns(j);
  }

  useEffect(() => {
    load();
  }, []);

  async function retry(jobType: string) {
    setRetrying(jobType);
    try {
      const result = await api.post<{ ok: boolean; detail: string }>("/api/v1/automation/retry", { job_type: jobType });
      pushToast(result.ok ? "success" : "error", result.detail);
      await load();
    } catch (err) {
      pushToast("error", err instanceof ApiError ? err.message : "Retry failed");
    } finally {
      setRetrying(null);
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold">Automation History</h1>
        <p className="text-sm text-muted">
          Operational history for this Lab — Root Me synchronization, reminders, and weekly report generation.
          Backup history for this Lab is managed by the Super Admin.
        </p>
      </div>

      <Card>
        <CardHeader className="flex flex-wrap items-center justify-between gap-2">
          <CardTitle>Synchronization runs</CardTitle>
          <Button variant="outline" disabled={retrying === "sync"} onClick={() => retry("sync")}>
            {retrying === "sync" ? "Retrying…" : "Retry sync"}
          </Button>
        </CardHeader>
        <CardContent className="overflow-x-auto p-0">
          <table className="hs-table">
            <thead>
              <tr>
                <th>Run at</th>
                <th>Platform</th>
                <th>Status</th>
                <th>Checked</th>
                <th>Updated</th>
                <th>Conflicts</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {syncRuns.map((r) => (
                <Fragment key={r.id}>
                  <tr>
                    <td className="font-data text-muted">{new Date(r.run_at).toLocaleString()}</td>
                    <td>{r.platform_name}</td>
                    <td>
                      <Badge className={statusTone(r.status)}>{r.status}</Badge>
                    </td>
                    <td className="font-data">{r.members_checked}</td>
                    <td className="font-data">{r.updated_count}</td>
                    <td className="font-data">{r.conflicts_count}</td>
                    <td>
                      {r.errors && (
                        <button
                          className="text-xs font-semibold text-accent underline"
                          onClick={() => setExpanded(expanded === r.id ? null : r.id)}
                        >
                          {expanded === r.id ? "Hide errors" : "View errors"}
                        </button>
                      )}
                    </td>
                  </tr>
                  {expanded === r.id && r.errors && (
                    <tr>
                      <td colSpan={7} className="whitespace-pre-wrap bg-[var(--surface-hover)] font-data text-xs text-[var(--status-missing)]">
                        {r.errors}
                      </td>
                    </tr>
                  )}
                </Fragment>
              ))}
              {syncRuns.length === 0 && (
                <tr>
                  <td colSpan={7} className="py-6 text-center text-muted">
                    No synchronization runs yet.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex flex-wrap items-center justify-between gap-2">
          <CardTitle>Reminder &amp; weekly-report runs</CardTitle>
          <div className="flex gap-2">
            <Button variant="outline" disabled={retrying === "reminder"} onClick={() => retry("reminder")}>
              {retrying === "reminder" ? "Retrying…" : "Retry reminders"}
            </Button>
            <Button variant="outline" disabled={retrying === "weekly_report"} onClick={() => retry("weekly_report")}>
              {retrying === "weekly_report" ? "Retrying…" : "Retry weekly report"}
            </Button>
          </div>
        </CardHeader>
        <CardContent className="overflow-x-auto p-0">
          <table className="hs-table">
            <thead>
              <tr>
                <th>Run at</th>
                <th>Job</th>
                <th>Status</th>
                <th>Detail</th>
              </tr>
            </thead>
            <tbody>
              {jobRuns.map((j) => (
                <tr key={j.id}>
                  <td className="font-data text-muted">{new Date(j.run_at).toLocaleString()}</td>
                  <td className="capitalize">{j.job_type.replace("_", " ")}</td>
                  <td>
                    <Badge className={statusTone(j.status)}>{j.status}</Badge>
                  </td>
                  <td className="text-muted">{j.detail ?? "—"}</td>
                </tr>
              ))}
              {jobRuns.length === 0 && (
                <tr>
                  <td colSpan={4} className="py-6 text-center text-muted">
                    No reminder or weekly-report runs yet.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </CardContent>
      </Card>
    </div>
  );
}
