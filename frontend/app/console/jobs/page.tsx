"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { api, ApiError } from "@/lib/api";
import type { SuperAdminMe, SystemJobRun } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Topbar } from "@/components/layout/topbar";

function statusTone(status: string) {
  if (status === "ok") return "text-[var(--status-done)]";
  if (status === "error") return "text-[var(--status-missing)]";
  return "text-muted";
}

export default function SystemJobsPage() {
  const router = useRouter();
  const [me, setMe] = useState<SuperAdminMe | null>(null);
  const [runs, setRuns] = useState<SystemJobRun[]>([]);

  useEffect(() => {
    (async () => {
      try {
        const m = await api.get<SuperAdminMe>("/admin/auth/me");
        setMe(m);
        setRuns(await api.get<SystemJobRun[]>("/admin/system/job-runs"));
      } catch (err) {
        if (err instanceof ApiError && (err.status === 401 || err.status === 403)) {
          router.replace("/console/login");
          return;
        }
        throw err;
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function logout() {
    await api.post("/admin/auth/logout");
    router.replace("/console/login");
  }

  if (!me) return null;

  return (
    <div className="flex min-h-screen flex-col">
      <Topbar
        title="System Job History"
        badge="SYSTEM SCOPE"
        rightExtra={
          <div className="flex items-center gap-2">
            <Link href="/console" className="text-sm font-semibold text-muted hover:text-foreground">
              ← Labs
            </Link>
            <Button variant="outline" onClick={logout}>
              Sign out
            </Button>
          </div>
        }
      />
      <main className="flex-1 px-4 pb-16 pt-5 sm:px-8 sm:pt-7">
        <div className="mx-auto max-w-4xl animate-fade-up space-y-6">
          <p className="text-sm text-muted">
            System-wide operational history — the one job class (backups) with no single-Tenant scope. Per-Lab sync
            and reminder/weekly-report history live inside each Lab&apos;s own Automation page.
          </p>
          <Card>
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
                  {runs.map((r) => (
                    <tr key={r.id}>
                      <td className="font-data text-muted">{new Date(r.run_at).toLocaleString()}</td>
                      <td className="capitalize">{r.job_type}</td>
                      <td>
                        <Badge className={statusTone(r.status)}>{r.status}</Badge>
                      </td>
                      <td className="text-muted">{r.detail ?? "—"}</td>
                    </tr>
                  ))}
                  {runs.length === 0 && (
                    <tr>
                      <td colSpan={4} className="py-6 text-center text-muted">
                        No system job runs yet.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </CardContent>
          </Card>
        </div>
      </main>
    </div>
  );
}
