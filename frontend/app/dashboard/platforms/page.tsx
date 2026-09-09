"use client";

import { useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import type { Platform, SyncNowResult, TestConnectionResult } from "@/lib/types";
import { useMember } from "@/lib/member-context";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { useToast } from "@/lib/toast-context";
import { Link2 } from "lucide-react";

interface DraftState {
  name: string;
  baseUrl: string;
  apiKey: string;
}

function emptyDraft(p: Platform): DraftState {
  return { name: p.name, baseUrl: p.base_url ?? "", apiKey: "" };
}

function toLocalString(iso: string) {
  return new Date(iso).toLocaleString();
}

// §7 — persisted states are "not configured" / "unverified" / "verified"
// (credentials_verified_at is cleared server-side whenever the API key or
// base URL changes — see update_platform). "Verification failed" isn't a
// column the backend stores (a failed Test Connection just leaves
// verified_at unset); it's surfaced transiently below from the most
// recent test-connection response instead — a judgment call since the
// doc doesn't specify a persisted failure record.
function verificationBadge(p: Platform) {
  if (!p.has_credentials) return { label: "not configured", tone: "text-muted" };
  if (p.credentials_verified_at) return { label: `verified ${toLocalString(p.credentials_verified_at)}`, tone: "text-[var(--status-done)]" };
  return { label: "unverified", tone: "text-[var(--status-missing)]" };
}

export default function PlatformsPage() {
  const me = useMember();
  const canManage = me.role === "lab_leader";
  const { push: pushToast } = useToast();

  const [platforms, setPlatforms] = useState<Platform[]>([]);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [draft, setDraft] = useState<DraftState | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [testResults, setTestResults] = useState<Record<string, TestConnectionResult>>({});
  const [testing, setTesting] = useState<string | null>(null);

  const [syncing, setSyncing] = useState<string | null>(null);
  const [syncResults, setSyncResults] = useState<Record<string, SyncNowResult>>({});
  const [syncErrors, setSyncErrors] = useState<Record<string, string>>({});

  async function load() {
    setPlatforms(await api.get<Platform[]>("/api/v1/platforms"));
  }

  useEffect(() => {
    load();
  }, []);

  function startEdit(p: Platform) {
    setEditingId(p.id);
    setDraft(emptyDraft(p));
    setError(null);
  }

  async function saveEdit(p: Platform) {
    if (!draft) return;
    setSaving(true);
    setError(null);
    try {
      const body: Record<string, unknown> = { name: draft.name, base_url: draft.baseUrl || null };
      if (draft.apiKey.trim()) {
        body.auth_config = { api_key: draft.apiKey.trim() };
      }
      await api.patch(`/api/v1/platforms/${p.id}`, body);
      setEditingId(null);
      setDraft(null);
      await load();
      pushToast("success", `${draft.name} saved`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to save");
    } finally {
      setSaving(false);
    }
  }

  async function testConnection(p: Platform) {
    setTesting(p.id);
    try {
      const result = await api.post<TestConnectionResult>(`/api/v1/platforms/${p.id}/test-connection`);
      setTestResults((prev) => ({ ...prev, [p.id]: result }));
      pushToast(result.ok ? "success" : "error", result.detail);
      await load(); // refresh credentials_verified_at from the server
    } finally {
      setTesting(null);
    }
  }

  async function makeFocus(p: Platform) {
    if (
      !confirm(
        `Switch focus platform to "${p.name}"? This changes which platform Progress sync will run against for this Lab.`
      )
    )
      return;
    await api.post(`/api/v1/platforms/${p.id}/focus`);
    await load();
    pushToast("success", `${p.name} is now the focus platform`);
  }

  async function syncNow(p: Platform) {
    setSyncing(p.id);
    setSyncErrors((prev) => ({ ...prev, [p.id]: "" }));
    try {
      const result = await api.post<SyncNowResult>(`/api/v1/platforms/${p.id}/sync-now`);
      setSyncResults((prev) => ({ ...prev, [p.id]: result }));
      pushToast(
        result.errors.length > 0 ? "error" : "success",
        result.errors.length > 0
          ? `Sync finished with ${result.errors.length} error(s)`
          : `Sync complete — ${result.updated.length} update(s) found`
      );
    } catch (err) {
      const message = err instanceof ApiError ? err.message : "Sync failed";
      setSyncErrors((prev) => ({ ...prev, [p.id]: message }));
      pushToast("error", message);
    } finally {
      setSyncing(null);
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold">Platforms</h1>
        <p className="text-sm text-muted">
          Every Lab is seeded with a Root Me platform on creation — configure its API key below rather than
          creating a new one.
        </p>
      </div>

      <div className="space-y-4">
        {platforms.map((p) => {
          const isEditing = editingId === p.id;
          const testResult = testResults[p.id];
          const syncResult = syncResults[p.id];
          const syncError = syncErrors[p.id];
          return (
            <Card key={p.id}>
              <CardHeader className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex flex-wrap items-center gap-2.5">
                  <span className="flex h-[34px] w-[34px] flex-shrink-0 items-center justify-center rounded-lg border border-[var(--border)] bg-background">
                    <Link2 size={16} strokeWidth={1.75} />
                  </span>
                  <CardTitle>{p.name}</CardTitle>
                  <Badge>{p.adapter_type}</Badge>
                  {p.is_focus && <Badge className="text-[var(--status-done)]">focus</Badge>}
                  {!p.is_active && <Badge className="text-[var(--status-missing)]">inactive</Badge>}
                  <Badge className={verificationBadge(p).tone}>{verificationBadge(p).label}</Badge>
                </div>
                {canManage && !isEditing && (
                  <Button variant="outline" onClick={() => startEdit(p)}>
                    Edit
                  </Button>
                )}
              </CardHeader>
              <CardContent className="space-y-4">
                {isEditing && draft ? (
                  <div className="space-y-4">
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                      <div>
                        <Label>Name</Label>
                        <Input value={draft.name} onChange={(e) => setDraft({ ...draft, name: e.target.value })} />
                      </div>
                      <div>
                        <Label>Base URL</Label>
                        <Input
                          value={draft.baseUrl}
                          onChange={(e) => setDraft({ ...draft, baseUrl: e.target.value })}
                        />
                      </div>
                    </div>
                    <div>
                      <Label>Root Me API key</Label>
                      <Input
                        type="password"
                        placeholder={p.has_credentials ? "•••••••• (leave blank to keep current key)" : "paste api_key"}
                        value={draft.apiKey}
                        onChange={(e) => setDraft({ ...draft, apiKey: e.target.value })}
                      />
                      <p className="mt-1 text-xs text-muted">
                        Stored encrypted — never shown again after saving. Get one from your Lab&apos;s Root Me
                        account at root-me.org/?page=preferences.
                      </p>
                    </div>
                    {error && <p className="text-sm text-[var(--status-missing)]">{error}</p>}
                    <div className="flex gap-2">
                      <Button disabled={saving} onClick={() => saveEdit(p)}>
                        {saving ? "Saving…" : "Save"}
                      </Button>
                      <Button
                        variant="outline"
                        onClick={() => {
                          setEditingId(null);
                          setDraft(null);
                        }}
                      >
                        Cancel
                      </Button>
                    </div>
                  </div>
                ) : (
                  <p className="text-sm text-muted">{p.base_url ?? "—"}</p>
                )}

                {canManage && !isEditing && (
                  <div className="space-y-2 border-t border-[var(--border)] pt-4">
                    <div className="flex flex-wrap items-center gap-2">
                      <Button variant="outline" disabled={testing === p.id} onClick={() => testConnection(p)}>
                        {testing === p.id ? "Testing…" : "Test connection"}
                      </Button>
                      <Button
                        variant="outline"
                        disabled={p.is_focus || !p.is_active || !p.credentials_verified_at}
                        title={
                          !p.is_active
                            ? "Inactive platforms cannot become the focus"
                            : !p.credentials_verified_at
                              ? "Run a successful Test connection first"
                              : undefined
                        }
                        onClick={() => makeFocus(p)}
                      >
                        {p.is_focus ? "Current focus" : "Make focus"}
                      </Button>
                      <Button
                        variant="outline"
                        disabled={syncing === p.id || !p.has_credentials}
                        onClick={() => syncNow(p)}
                      >
                        {syncing === p.id ? "Syncing…" : "Sync now"}
                      </Button>
                    </div>

                    {testResult && (
                      <p className={`text-sm ${testResult.ok ? "text-[var(--status-done)]" : "text-[var(--status-missing)]"}`}>
                        {testResult.ok ? "✓" : "✗"} {testResult.detail}
                      </p>
                    )}
                    {syncResult && (
                      <p className="text-sm text-muted">
                        Sync checked {syncResult.members_checked} member(s) — {syncResult.updated.length} updated,{" "}
                        {syncResult.conflicts.length} manual-override conflicts skipped
                        {syncResult.errors.length > 0 && `, ${syncResult.errors.length} error(s)`}
                        {syncResult.errors.length > 0 && (
                          <span className="block text-[var(--status-missing)]">{syncResult.errors.join("; ")}</span>
                        )}
                      </p>
                    )}
                    {syncError && <p className="text-sm text-[var(--status-missing)]">{syncError}</p>}
                  </div>
                )}
              </CardContent>
            </Card>
          );
        })}
        {platforms.length === 0 && <p className="text-muted">No platforms yet.</p>}
      </div>
    </div>
  );
}
