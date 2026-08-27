"use client";

import { useEffect, useState, type FormEvent } from "react";
import { api, ApiError } from "@/lib/api";
import type { Member, MemberRole, Platform, ResolveUserResult } from "@/lib/types";
import { useMember } from "@/lib/member-context";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { useToast } from "@/lib/toast-context";

function initialsOf(fullName: string) {
  return fullName.split(" ").slice(-2).map((w) => w[0]).join("").toUpperCase();
}

interface PlatformAccountDraft {
  platform_id: string;
  external_username: string;
  external_user_id: string;
}

function emptyAccount(defaultPlatformId: string): PlatformAccountDraft {
  return { platform_id: defaultPlatformId, external_username: "", external_user_id: "" };
}

export default function MembersPage() {
  const me = useMember();
  const canManage = me.role === "lab_leader";
  const { push: pushToast } = useToast();

  const [members, setMembers] = useState<Member[]>([]);
  const [platforms, setPlatforms] = useState<Platform[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState<MemberRole>("member");
  const [accounts, setAccounts] = useState<PlatformAccountDraft[]>([]);
  const [lookupStatus, setLookupStatus] = useState<Record<number, string>>({});
  const [lookingUp, setLookingUp] = useState<number | null>(null);

  async function load() {
    const [m, p] = await Promise.all([
      api.get<Member[]>("/api/v1/members"),
      api.get<Platform[]>("/api/v1/platforms"),
    ]);
    setMembers(m);
    setPlatforms(p);
  }

  useEffect(() => {
    load();
  }, []);

  async function lookupId(idx: number) {
    const acc = accounts[idx];
    if (!acc.platform_id || !acc.external_username.trim()) {
      setLookupStatus((prev) => ({ ...prev, [idx]: "Pick a platform and enter a username first" }));
      return;
    }
    setLookingUp(idx);
    setLookupStatus((prev) => ({ ...prev, [idx]: "" }));
    try {
      const result = await api.get<ResolveUserResult>(
        `/api/v1/platforms/${acc.platform_id}/resolve-user?username=${encodeURIComponent(acc.external_username)}`
      );
      if (result.matched && result.external_user_id) {
        // Fills the field for the Admin to review — does not save anything
        // by itself (PRD §6.3: never silently auto-fill without the Admin seeing it).
        setAccounts((prev) => prev.map((a, i) => (i === idx ? { ...a, external_user_id: result.external_user_id! } : a)));
        setLookupStatus((prev) => ({ ...prev, [idx]: `Found: id_auteur ${result.external_user_id} — please confirm` }));
      } else {
        setLookupStatus((prev) => ({ ...prev, [idx]: "No exact username match found — enter the ID manually" }));
      }
    } catch (err) {
      setLookupStatus((prev) => ({
        ...prev,
        [idx]: err instanceof ApiError ? err.message : "Lookup failed",
      }));
    } finally {
      setLookingUp(null);
    }
  }

  function resetForm() {
    setFullName("");
    setEmail("");
    setPassword("");
    setRole("member");
    setAccounts([]);
    setError(null);
  }

  async function onCreate(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await api.post("/api/v1/members", {
        full_name: fullName,
        email,
        password,
        role,
        platform_accounts: accounts.filter((a) => a.external_username && a.external_user_id),
      });
      resetForm();
      setShowForm(false);
      await load();
      pushToast("success", `${fullName} added`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to create member");
    } finally {
      setSubmitting(false);
    }
  }

  async function toggleActive(member: Member) {
    await api.patch(`/api/v1/members/${member.id}`, { active: !member.active });
    await load();
    pushToast("success", member.active ? `${member.full_name} deactivated` : `${member.full_name} activated`);
  }

  async function removeMember(member: Member) {
    if (!confirm(`Remove ${member.full_name}? This cannot be undone.`)) return;
    await api.delete(`/api/v1/members/${member.id}`);
    await load();
    pushToast("success", `${member.full_name} removed`);
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-xl font-semibold">Members</h1>
        {canManage && <Button onClick={() => setShowForm((v) => !v)}>{showForm ? "Cancel" : "New Member"}</Button>}
      </div>

      {canManage && showForm && (
        <Card>
          <CardHeader>
            <CardTitle>New Member</CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={onCreate} className="space-y-4">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <Label htmlFor="fullName">Full name</Label>
                  <Input id="fullName" required value={fullName} onChange={(e) => setFullName(e.target.value)} />
                </div>
                <div>
                  <Label htmlFor="email">Email</Label>
                  <Input id="email" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
                </div>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <Label htmlFor="password">Temporary password</Label>
                  <Input
                    id="password"
                    required
                    minLength={8}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                  />
                </div>
                <div>
                  <Label htmlFor="role">Role</Label>
                  <Select id="role" value={role} onChange={(e) => setRole(e.target.value as MemberRole)}>
                    <option value="member">member</option>
                    <option value="presenter">presenter</option>
                    <option value="lab_leader">lab_leader</option>
                  </Select>
                </div>
              </div>

              <div>
                <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                  <Label className="mb-0">Platform accounts</Label>
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => setAccounts((prev) => [...prev, emptyAccount(platforms[0]?.id ?? "")])}
                  >
                    + Add account
                  </Button>
                </div>
                <div className="space-y-3">
                  {accounts.map((acc, idx) => (
                    <div key={idx} className="grid grid-cols-1 gap-2 rounded-md border border-[var(--border)] p-3 sm:grid-cols-[1fr_1fr_1fr_auto]">
                      <div>
                        <Label className="text-xs">Platform</Label>
                        <Select
                          value={acc.platform_id}
                          onChange={(e) =>
                            setAccounts((prev) => prev.map((a, i) => (i === idx ? { ...a, platform_id: e.target.value } : a)))
                          }
                        >
                          {platforms.map((p) => (
                            <option key={p.id} value={p.id}>
                              {p.name}
                            </option>
                          ))}
                        </Select>
                      </div>
                      <div>
                        <Label className="text-xs">Root Me username</Label>
                        <Input
                          value={acc.external_username}
                          onChange={(e) =>
                            setAccounts((prev) =>
                              prev.map((a, i) => (i === idx ? { ...a, external_username: e.target.value } : a))
                            )
                          }
                        />
                      </div>
                      <div>
                        <Label className="text-xs">Root Me ID (id_auteur) *</Label>
                        <Input
                          required
                          placeholder="e.g. 1119850"
                          value={acc.external_user_id}
                          onChange={(e) =>
                            setAccounts((prev) =>
                              prev.map((a, i) => (i === idx ? { ...a, external_user_id: e.target.value } : a))
                            )
                          }
                        />
                      </div>
                      <div className="flex items-end gap-2">
                        <Button type="button" variant="outline" disabled={lookingUp === idx} onClick={() => lookupId(idx)}>
                          {lookingUp === idx ? "Looking up…" : "Tra cứu ID"}
                        </Button>
                        <Button
                          type="button"
                          variant="ghost"
                          onClick={() => setAccounts((prev) => prev.filter((_, i) => i !== idx))}
                        >
                          Remove
                        </Button>
                      </div>
                      {lookupStatus[idx] && (
                        <p className="col-span-4 text-xs text-muted">{lookupStatus[idx]}</p>
                      )}
                    </div>
                  ))}
                </div>
                <p className="mt-2 text-xs text-muted">
                  Root Me ID is required for every linked account — it is what sync calls use, not the username
                  (PRD §6.3).
                </p>
              </div>

              {error && <p className="text-sm text-[var(--status-missing)]">{error}</p>}
              <Button type="submit" disabled={submitting}>
                {submitting ? "Creating…" : "Create Member"}
              </Button>
            </form>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardContent className="overflow-x-auto p-0">
          <table className="hs-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Email</th>
                <th>Role</th>
                <th>Platform accounts</th>
                <th>Status</th>
                {canManage && <th />}
              </tr>
            </thead>
            <tbody>
              {members.map((m) => (
                <tr key={m.id} className="align-top">
                  <td>
                    <div className="flex items-center gap-2.5">
                      <span className="flex h-[26px] w-[26px] flex-shrink-0 items-center justify-center rounded-[7px] border border-[var(--border)] bg-background font-mono text-[11px] font-bold text-accent">
                        {initialsOf(m.full_name)}
                      </span>
                      <span className="font-semibold">{m.full_name}</span>
                    </div>
                  </td>
                  <td className="text-muted">{m.email}</td>
                  <td>
                    <Badge>{m.role}</Badge>
                  </td>
                  <td className="font-data text-xs text-muted">
                    {m.platform_accounts.length === 0
                      ? "—"
                      : m.platform_accounts.map((a) => `${a.external_username} (#${a.external_user_id})`).join(", ")}
                  </td>
                  <td>
                    <Badge className={m.active ? "text-[var(--status-done)]" : "text-[var(--status-missing)]"}>
                      {m.active ? "active" : "inactive"}
                    </Badge>
                  </td>
                  {canManage && (
                    <td className="text-right whitespace-nowrap">
                      <Button variant="outline" onClick={() => toggleActive(m)}>
                        {m.active ? "Deactivate" : "Activate"}
                      </Button>{" "}
                      <Button variant="destructive" onClick={() => removeMember(m)}>
                        Delete
                      </Button>
                    </td>
                  )}
                </tr>
              ))}
              {members.length === 0 && (
                <tr>
                  <td colSpan={canManage ? 6 : 5} className="py-6 text-center text-muted">
                    No members yet.
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
