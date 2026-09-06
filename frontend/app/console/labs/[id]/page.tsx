"use client";

import { useEffect, useState, type ChangeEvent, type FormEvent } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { api, ApiError } from "@/lib/api";
import type { DeletionPreview, SuperAdminMe, Tenant, TenantDataJob } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Topbar } from "@/components/layout/topbar";
import { useToast } from "@/lib/toast-context";
import { Download } from "lucide-react";

export default function LabDetailPage() {
  const params = useParams<{ id: string }>();
  const labId = params.id;
  const router = useRouter();
  const { push: pushToast } = useToast();

  const [me, setMe] = useState<SuperAdminMe | null>(null);
  const [lab, setLab] = useState<Tenant | null>(null);
  const [preview, setPreview] = useState<DeletionPreview | null>(null);
  const [backups, setBackups] = useState<TenantDataJob[]>([]);

  const [confirmName, setConfirmName] = useState("");
  const [deleting, setDeleting] = useState(false);
  const [backingUp, setBackingUp] = useState(false);

  const [leaderName, setLeaderName] = useState("");
  const [leaderEmail, setLeaderEmail] = useState("");
  const [leaderPassword, setLeaderPassword] = useState("");
  const [assigning, setAssigning] = useState(false);
  const [assignError, setAssignError] = useState<string | null>(null);

  const [restoreMode, setRestoreMode] = useState<"new_lab" | "overwrite_existing">("new_lab");
  const [restoreBundle, setRestoreBundle] = useState<Record<string, unknown> | null>(null);
  const [restoreFileName, setRestoreFileName] = useState("");
  const [restoring, setRestoring] = useState(false);
  const [restoreWarnings, setRestoreWarnings] = useState<string[]>([]);

  async function load() {
    const [labs, p, b] = await Promise.all([
      api.get<Tenant[]>("/admin/labs"),
      api.get<DeletionPreview>(`/admin/labs/${labId}/deletion-preview`),
      api.get<TenantDataJob[]>(`/admin/labs/${labId}/backups`),
    ]);
    setLab(labs.find((l) => l.id === labId) ?? null);
    setPreview(p);
    setBackups(b);
  }

  useEffect(() => {
    (async () => {
      try {
        const m = await api.get<SuperAdminMe>("/admin/auth/me");
        setMe(m);
        await load();
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

  async function deleteLab() {
    if (!lab) return;
    if (confirmName !== lab.name) {
      pushToast("error", "Type the Lab's exact name to confirm");
      return;
    }
    if (!confirm(`This permanently deletes "${lab.name}" and all its data right now. Continue?`)) return;
    setDeleting(true);
    try {
      await api.delete(`/admin/labs/${labId}`);
      pushToast("success", `${lab.name} deleted`);
      router.replace("/console");
    } catch (err) {
      pushToast("error", err instanceof ApiError ? err.message : "Failed to delete Lab");
    } finally {
      setDeleting(false);
    }
  }

  async function backupNow() {
    setBackingUp(true);
    try {
      await api.post(`/admin/labs/${labId}/backup`);
      await load();
      pushToast("success", "Backup created");
    } catch (err) {
      pushToast("error", err instanceof ApiError ? err.message : "Backup failed");
    } finally {
      setBackingUp(false);
    }
  }

  async function assignLeader(e: FormEvent) {
    e.preventDefault();
    setAssignError(null);
    setAssigning(true);
    try {
      await api.post(`/admin/labs/${labId}/assign-leader`, {
        full_name: leaderName,
        email: leaderEmail,
        password: leaderPassword,
      });
      setLeaderName("");
      setLeaderEmail("");
      setLeaderPassword("");
      pushToast("success", `${leaderEmail} assigned as Lab Leader`);
    } catch (err) {
      setAssignError(err instanceof ApiError ? err.message : "Failed to assign Lab Leader");
    } finally {
      setAssigning(false);
    }
  }

  function onBundleFileChange(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setRestoreFileName(file.name);
    const reader = new FileReader();
    reader.onload = () => {
      try {
        setRestoreBundle(JSON.parse(String(reader.result)));
      } catch {
        pushToast("error", "That file isn't valid JSON");
        setRestoreBundle(null);
      }
    };
    reader.readAsText(file);
  }

  async function doRestore() {
    if (!restoreBundle) {
      pushToast("error", "Choose a bundle file first");
      return;
    }
    if (
      !confirm(
        restoreMode === "overwrite_existing"
          ? `This replaces ALL current data in "${lab?.name}" with the bundle's contents. Continue?`
          : "This creates a brand-new Lab from the bundle's contents. Continue?"
      )
    )
      return;
    setRestoring(true);
    setRestoreWarnings([]);
    try {
      const result = await api.post<{ tenant_id: string; warnings: string[] }>("/admin/labs/restore", {
        bundle: restoreBundle,
        mode: restoreMode,
        target_tenant_id: restoreMode === "overwrite_existing" ? labId : undefined,
      });
      setRestoreWarnings(result.warnings);
      pushToast("success", "Restore complete");
      if (restoreMode === "new_lab") {
        router.push(`/console/labs/${result.tenant_id}`);
      } else {
        await load();
      }
    } catch (err) {
      pushToast("error", err instanceof ApiError ? err.message : "Restore failed");
    } finally {
      setRestoring(false);
    }
  }

  if (!me || !lab) return null;

  return (
    <div className="flex min-h-screen flex-col">
      <Topbar
        title={lab.name}
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
        <div className="mx-auto max-w-3xl animate-fade-up space-y-6">
          <div className="flex flex-wrap items-center gap-2">
            <Badge className={lab.is_active ? "text-[var(--status-done)]" : "text-[var(--status-missing)]"}>
              {lab.is_active ? "active" : "inactive"}
            </Badge>
            <span className="font-data text-sm text-muted">{lab.slug}</span>
          </div>

          <Card>
            <CardHeader>
              <CardTitle>Data overview</CardTitle>
            </CardHeader>
            <CardContent>
              {preview && (
                <div className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-3">
                  <div>
                    <span className="text-muted">Members</span> <b>{preview.member_count}</b>
                  </div>
                  <div>
                    <span className="text-muted">Semesters</span> <b>{preview.semester_count}</b>
                  </div>
                  <div>
                    <span className="text-muted">Challenges</span> <b>{preview.challenge_count}</b>
                  </div>
                  <div>
                    <span className="text-muted">Progress</span> <b>{preview.progress_count}</b>
                  </div>
                  <div>
                    <span className="text-muted">Reports</span> <b>{preview.report_count}</b>
                  </div>
                  <div>
                    <span className="text-muted">Platforms</span> <b>{preview.platform_count}</b>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Assign Lab Leader</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <p className="text-sm text-muted">
                Only usable when this Lab currently has no active Lab Leader — otherwise use that Lab Leader&apos;s
                own ownership transfer from inside the Lab.
              </p>
              <form onSubmit={assignLeader} className="grid grid-cols-1 gap-3 sm:grid-cols-3">
                <div>
                  <Label htmlFor="leaderName">Full name</Label>
                  <Input id="leaderName" required value={leaderName} onChange={(e) => setLeaderName(e.target.value)} />
                </div>
                <div>
                  <Label htmlFor="leaderEmail">Email</Label>
                  <Input
                    id="leaderEmail"
                    type="email"
                    required
                    value={leaderEmail}
                    onChange={(e) => setLeaderEmail(e.target.value)}
                  />
                </div>
                <div>
                  <Label htmlFor="leaderPassword">Temporary password</Label>
                  <Input
                    id="leaderPassword"
                    minLength={8}
                    required
                    value={leaderPassword}
                    onChange={(e) => setLeaderPassword(e.target.value)}
                  />
                </div>
                <div className="sm:col-span-3">
                  {assignError && <p className="mb-2 text-sm text-[var(--status-missing)]">{assignError}</p>}
                  <Button type="submit" disabled={assigning}>
                    {assigning ? "Assigning…" : "Assign Lab Leader"}
                  </Button>
                </div>
              </form>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-wrap items-center justify-between gap-2">
              <CardTitle>Export &amp; backup</CardTitle>
              <div className="flex gap-2">
                <a
                  href={`/admin/labs/${labId}/export`}
                  className="inline-flex items-center gap-1.5 rounded-[9px] border border-[var(--border)] px-3.5 py-2 text-[13px] font-semibold hover:border-accent hover:text-accent"
                >
                  <Download size={13} /> Export JSON
                </a>
                <Button variant="outline" disabled={backingUp} onClick={backupNow}>
                  {backingUp ? "Backing up…" : "Backup now"}
                </Button>
              </div>
            </CardHeader>
            <CardContent className="overflow-x-auto p-0">
              <table className="hs-table">
                <thead>
                  <tr>
                    <th>Created</th>
                    <th>Status</th>
                    <th>Downloaded</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {backups.map((b) => (
                    <tr key={b.id}>
                      <td className="font-data text-muted">{new Date(b.created_at).toLocaleString()}</td>
                      <td>
                        <Badge className={b.status === "done" ? "text-[var(--status-done)]" : "text-[var(--status-missing)]"}>
                          {b.status}
                        </Badge>
                      </td>
                      <td className="text-muted">{b.downloaded_at ? new Date(b.downloaded_at).toLocaleString() : "—"}</td>
                      <td className="text-right">
                        <a
                          href={`/admin/labs/backups/${b.id}/download`}
                          className="text-xs font-semibold text-accent underline"
                        >
                          Download
                        </a>
                      </td>
                    </tr>
                  ))}
                  {backups.length === 0 && (
                    <tr>
                      <td colSpan={4} className="py-6 text-center text-muted">
                        No backups yet.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Restore from bundle</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="flex flex-wrap items-center gap-3">
                <Label className="mb-0">Mode</Label>
                <label className="flex items-center gap-1.5 text-sm">
                  <input
                    type="radio"
                    checked={restoreMode === "new_lab"}
                    onChange={() => setRestoreMode("new_lab")}
                  />
                  Restore as a new Lab
                </label>
                <label className="flex items-center gap-1.5 text-sm">
                  <input
                    type="radio"
                    checked={restoreMode === "overwrite_existing"}
                    onChange={() => setRestoreMode("overwrite_existing")}
                  />
                  Overwrite this Lab&apos;s data
                </label>
              </div>
              <Input type="file" accept="application/json" onChange={onBundleFileChange} />
              {restoreFileName && <p className="text-xs text-muted">Selected: {restoreFileName}</p>}
              <Button variant="outline" disabled={restoring || !restoreBundle} onClick={doRestore}>
                {restoring ? "Restoring…" : "Restore"}
              </Button>
              {restoreWarnings.length > 0 && (
                <div className="text-xs text-[var(--status-late)]">
                  {restoreWarnings.map((w, i) => (
                    <p key={i}>⚠ {w}</p>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>

          <Card style={{ borderColor: "var(--status-missing)" }}>
            <CardHeader>
              <CardTitle>Delete this Lab</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <p className="text-sm text-muted">
                This is immediate and cannot be undone — the Lab and all its data (except this audit trail and any
                existing backups) are deleted the moment you confirm. Type the Lab&apos;s exact name below to enable
                the button.
              </p>
              <Input
                placeholder={lab.name}
                value={confirmName}
                onChange={(e) => setConfirmName(e.target.value)}
              />
              <Button variant="destructive" disabled={deleting || confirmName !== lab.name} onClick={deleteLab}>
                {deleting ? "Deleting…" : `Delete "${lab.name}"`}
              </Button>
            </CardContent>
          </Card>
        </div>
      </main>
    </div>
  );
}
