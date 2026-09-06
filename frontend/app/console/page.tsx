"use client";

import { useEffect, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { api, ApiError } from "@/lib/api";
import type { SuperAdminDashboard, SuperAdminMe, Tenant } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Topbar } from "@/components/layout/topbar";
import { useToast } from "@/lib/toast-context";

export default function ConsolePage() {
  const router = useRouter();
  const { push: pushToast } = useToast();
  const [me, setMe] = useState<SuperAdminMe | null>(null);
  const [dashboard, setDashboard] = useState<SuperAdminDashboard | null>(null);
  const [labs, setLabs] = useState<Tenant[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  const [leaderName, setLeaderName] = useState("");
  const [leaderEmail, setLeaderEmail] = useState("");
  const [leaderPassword, setLeaderPassword] = useState("");

  async function load() {
    const [d, l] = await Promise.all([
      api.get<SuperAdminDashboard>("/admin/labs/dashboard"),
      api.get<Tenant[]>("/admin/labs"),
    ]);
    setDashboard(d);
    setLabs(l);
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

  async function onCreateLab(e: FormEvent) {
    e.preventDefault();
    setFormError(null);
    setSubmitting(true);
    try {
      await api.post("/admin/labs", {
        name,
        slug,
        lab_leader_full_name: leaderName,
        lab_leader_email: leaderEmail,
        lab_leader_password: leaderPassword,
      });
      setName("");
      setSlug("");
      setLeaderName("");
      setLeaderEmail("");
      setLeaderPassword("");
      setShowForm(false);
      await load();
      pushToast("success", `Lab "${name}" created`);
    } catch (err) {
      setFormError(err instanceof ApiError ? err.message : "Failed to create Lab");
    } finally {
      setSubmitting(false);
    }
  }

  async function toggleActive(lab: Tenant) {
    await api.patch(`/admin/labs/${lab.id}`, { is_active: !lab.is_active });
    await load();
    pushToast("success", lab.is_active ? `${lab.name} suspended` : `${lab.name} reactivated`);
  }

  async function logout() {
    await api.post("/admin/auth/logout");
    router.replace("/console/login");
  }

  if (!me) return null;

  return (
    <div className="flex min-h-screen flex-col">
      <Topbar
        title="System Console"
        badge="SYSTEM SCOPE"
        rightExtra={
          <div className="flex items-center gap-2">
            <Link href="/console/jobs" className="text-sm font-semibold text-muted hover:text-foreground">
              System Jobs
            </Link>
            <Link href="/console/audit-log" className="text-sm font-semibold text-muted hover:text-foreground">
              Audit Log
            </Link>
            <Button variant="outline" onClick={logout}>
              Sign out
            </Button>
          </div>
        }
      />
      <main className="flex-1 px-4 pb-16 pt-5 sm:px-8 sm:pt-7">
        <div className="mx-auto max-w-5xl animate-fade-up">
          <p className="mb-6 text-sm text-muted">Signed in as {me.email} — whole-system scope, every Lab</p>

          {dashboard && (
            <div className="mb-[18px] grid grid-cols-2 sm:grid-cols-3 gap-3.5">
              <Card className="hs-hover-card">
                <CardContent className="py-4">
                  <p className="mb-2 text-xs font-semibold text-muted">Total Labs</p>
                  <p className="font-data text-2xl font-bold">{dashboard.total_labs}</p>
                </CardContent>
              </Card>
              <Card className="hs-hover-card">
                <CardContent className="py-4">
                  <p className="mb-2 text-xs font-semibold text-muted">Active</p>
                  <p className="font-data text-2xl font-bold">{dashboard.active_labs}</p>
                </CardContent>
              </Card>
              <Card className="hs-hover-card">
                <CardContent className="py-4">
                  <p className="mb-2 text-xs font-semibold text-muted">Inactive</p>
                  <p className="font-data text-2xl font-bold">{dashboard.inactive_labs}</p>
                </CardContent>
              </Card>
            </div>
          )}

          {dashboard && dashboard.labs_needing_attention.length > 0 && (
            <Card className="mb-[18px]" style={{ borderColor: "var(--status-late)" }}>
              <CardContent className="py-3.5">
                <p className="mb-1 text-[13px] font-bold">⚠ Labs needing attention</p>
                <div className="space-y-1.5">
                  {dashboard.labs_needing_attention.map((lab) => (
                    <div key={lab.id} className="flex flex-wrap items-center justify-between gap-1 text-sm">
                      <span>{lab.name}</span>
                      <span className="text-[var(--status-late)]">
                        {lab.reason === "not_configured" ? "Focus platform not configured" : "Sync errors on last run"}
                      </span>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}

          <Card>
            <CardHeader className="flex flex-wrap items-center justify-between gap-2">
              <CardTitle>Labs</CardTitle>
              <Button onClick={() => setShowForm((v) => !v)}>{showForm ? "Cancel" : "New Lab"}</Button>
            </CardHeader>
            <CardContent>
          {showForm && (
            <form onSubmit={onCreateLab} className="mb-6 space-y-4 rounded-md border border-[var(--border)] p-4">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <Label htmlFor="name">Lab name</Label>
                  <Input id="name" required value={name} onChange={(e) => setName(e.target.value)} />
                </div>
                <div>
                  <Label htmlFor="slug">Slug</Label>
                  <Input
                    id="slug"
                    required
                    pattern="[a-z0-9-]+"
                    placeholder="e.g. hslab"
                    value={slug}
                    onChange={(e) => setSlug(e.target.value)}
                  />
                </div>
              </div>
              <p className="text-xs text-muted">First Lab Leader account for this Lab</p>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
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
              </div>
              <div>
                <Label htmlFor="leaderPassword">Temporary password</Label>
                <Input
                  id="leaderPassword"
                  type="text"
                  required
                  minLength={8}
                  value={leaderPassword}
                  onChange={(e) => setLeaderPassword(e.target.value)}
                />
              </div>
              {formError && <p className="text-sm text-[var(--status-missing)]">{formError}</p>}
              <Button type="submit" disabled={submitting}>
                {submitting ? "Creating…" : "Create Lab"}
              </Button>
            </form>
          )}

          <div className="overflow-x-auto">
          <table className="hs-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Slug</th>
                <th>Status</th>
                <th>Created</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {labs.map((lab) => (
                <tr key={lab.id}>
                  <td className="font-semibold">{lab.name}</td>
                  <td className="font-data text-muted">{lab.slug}</td>
                  <td>
                    <Badge className={lab.is_active ? "text-[var(--status-done)]" : "text-[var(--status-missing)]"}>
                      {lab.is_active ? "active" : "inactive"}
                    </Badge>
                  </td>
                  <td className="font-data text-muted">{new Date(lab.created_at).toLocaleDateString()}</td>
                  <td className="text-right whitespace-nowrap space-x-1.5">
                    <Link
                      href={`/console/labs/${lab.id}`}
                      className="inline-flex items-center rounded-[9px] border border-[var(--border)] px-3.5 py-2 text-[13px] font-semibold hover:border-accent hover:text-accent"
                    >
                      Manage
                    </Link>
                    <Button variant="outline" onClick={() => toggleActive(lab)}>
                      {lab.is_active ? "Suspend" : "Reactivate"}
                    </Button>
                  </td>
                </tr>
              ))}
              {labs.length === 0 && (
                <tr>
                  <td colSpan={5} className="py-6 text-center text-muted">
                    No Labs yet.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
          </div>
            </CardContent>
          </Card>
        </div>
      </main>
    </div>
  );
}
