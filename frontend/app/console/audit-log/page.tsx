"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { api, ApiError } from "@/lib/api";
import type { AuditLogEntry, SuperAdminMe } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Topbar } from "@/components/layout/topbar";

const PAGE_SIZE = 50;

export default function AdminAuditLogPage() {
  const router = useRouter();
  const [me, setMe] = useState<SuperAdminMe | null>(null);
  const [entries, setEntries] = useState<AuditLogEntry[]>([]);
  const [tenantIdFilter, setTenantIdFilter] = useState("");
  const [actionFilter, setActionFilter] = useState("");
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(false);

  async function load(nextOffset: number) {
    setLoading(true);
    try {
      const params = new URLSearchParams({ limit: String(PAGE_SIZE), offset: String(nextOffset) });
      if (tenantIdFilter.trim()) params.set("tenant_id", tenantIdFilter.trim());
      if (actionFilter.trim()) params.set("action", actionFilter.trim());
      const rows = await api.get<AuditLogEntry[]>(`/admin/audit-log?${params.toString()}`);
      setEntries(rows);
      setOffset(nextOffset);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    (async () => {
      try {
        const m = await api.get<SuperAdminMe>("/admin/auth/me");
        setMe(m);
        await load(0);
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
        title="System-wide Audit Log"
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
        <div className="mx-auto max-w-5xl animate-fade-up space-y-6">
          <p className="text-sm text-muted">
            Every Lab&apos;s audit trail, including entries — like a deleted Lab&apos;s own history — that survive
            past the event they describe.
          </p>

          <Card>
            <CardContent className="flex flex-wrap items-end gap-3 py-4">
              <div>
                <Label htmlFor="tenantIdFilter">Lab (tenant) ID</Label>
                <Input
                  id="tenantIdFilter"
                  placeholder="uuid"
                  value={tenantIdFilter}
                  onChange={(e) => setTenantIdFilter(e.target.value)}
                />
              </div>
              <div>
                <Label htmlFor="actionFilter">Action</Label>
                <Input
                  id="actionFilter"
                  placeholder="e.g. lab.deleted"
                  value={actionFilter}
                  onChange={(e) => setActionFilter(e.target.value)}
                />
              </div>
              <Button variant="outline" onClick={() => load(0)}>
                Filter
              </Button>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="overflow-x-auto p-0">
              <table className="hs-table">
                <thead>
                  <tr>
                    <th>When</th>
                    <th>Lab</th>
                    <th>Actor</th>
                    <th>Action</th>
                    <th>Summary</th>
                  </tr>
                </thead>
                <tbody>
                  {entries.map((e) => (
                    <tr key={e.id}>
                      <td className="whitespace-nowrap font-data text-muted">{new Date(e.created_at).toLocaleString()}</td>
                      <td className="font-data text-xs text-muted">{e.tenant_id ?? "—"}</td>
                      <td className="whitespace-nowrap">
                        <Badge className="mr-1.5 capitalize">{e.actor_type.replace("_", " ")}</Badge>
                        {e.actor_label}
                      </td>
                      <td className="font-data text-xs">{e.action}</td>
                      <td>{e.summary}</td>
                    </tr>
                  ))}
                  {entries.length === 0 && (
                    <tr>
                      <td colSpan={5} className="py-6 text-center text-muted">
                        {loading ? "Loading…" : "No audit log entries."}
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </CardContent>
          </Card>

          <div className="flex justify-between">
            <Button variant="outline" disabled={offset === 0 || loading} onClick={() => load(Math.max(0, offset - PAGE_SIZE))}>
              Newer
            </Button>
            <Button variant="outline" disabled={entries.length < PAGE_SIZE || loading} onClick={() => load(offset + PAGE_SIZE)}>
              Older
            </Button>
          </div>
        </div>
      </main>
    </div>
  );
}
