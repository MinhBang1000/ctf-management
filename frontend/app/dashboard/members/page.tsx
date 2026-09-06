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

function toDraft(accounts: Member["platform_accounts"]): PlatformAccountDraft[] {
  return accounts.map((a) => ({ platform_id: a.platform_id, external_username: a.external_username, external_user_id: a.external_user_id }));
}

export default function MembersPage() {
  const me = useMember();
  const canManage = me.role === "lab_leader";
  const { push: pushToast } = useToast();

  const [members, setMembers] = useState<Member[]>([]);
  const [platforms, setPlatforms] = useState<Platform[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null); // §3 — null = "New Member" form, else editing that Member
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState<MemberRole>("member");
  const [active, setActive] = useState(true);
  const [accounts, setAccounts] = useState<PlatformAccountDraft[]>([]);
  const [lookupStatus, setLookupStatus] = useState<Record<number, string>>({});
  const [lookingUp, setLookingUp] = useState<number | null>(null);

  const [resetTargetId, setResetTargetId] = useState<string | null>(null);
  const [resetPassword, setResetPassword] = useState("");
  const [transferTargetId, setTransferTargetId] = useState<string | null>(null);
  const [demoteSelfTo, setDemoteSelfTo] = useState("");

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
    setActive(true);
    setAccounts([]);
    setError(null);
  }

  function openCreateForm() {
    resetForm();
    setEditingId(null);
    setShowForm((v) => (v && editingId === null ? false : true));
  }

  function openEditForm(member: Member) {
    setFullName(member.full_name);
    setEmail(member.email);
    setPassword("");
    setRole(member.role);
    setActive(member.active);
    setAccounts(toDraft(member.platform_accounts));
    setError(null);
    setEditingId(member.id);
    setShowForm(true);
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      if (editingId) {
        // §3 — profile fields via PATCH, platform accounts via their own
        // dedicated endpoint (same one the create flow already uses the
        // shape of), same split the backend itself keeps.
        await api.patch(`/api/v1/members/${editingId}`, { full_name: fullName, email, role, active });
        await api.put(
          `/api/v1/members/${editingId}/platform-accounts`,
          accounts.filter((a) => a.external_username && a.external_user_id)
        );
        pushToast("success", `${fullName} updated`);
      } else {
        await api.post("/api/v1/members", {
          full_name: fullName,
          email,
          password,
          role,
          platform_accounts: accounts.filter((a) => a.external_username && a.external_user_id),
        });
        pushToast("success", `${fullName} added`);
      }
      resetForm();
      setShowForm(false);
      setEditingId(null);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to save member");
    } finally {
      setSubmitting(false);
    }
  }

  // §14 — client-side mirror of assert_not_last_lab_leader, purely to
  // disable the button proactively with an explanatory tooltip; the
  // backend's own transactional check (see member_service.py) remains
  // the actual enforcement, since this count can race in the UI.
  function isLastActiveLeader(member: Member): boolean {
    if (member.role !== "lab_leader" || !member.active) return false;
    return members.filter((m) => m.role === "lab_leader" && m.active).length <= 1;
  }

  async function toggleActive(member: Member) {
    try {
      await api.patch(`/api/v1/members/${member.id}`, { active: !member.active });
      await load();
      pushToast("success", member.active ? `${member.full_name} deactivated` : `${member.full_name} activated`);
    } catch (err) {
      pushToast("error", err instanceof ApiError ? err.message : "Failed to update");
    }
  }

  async function removeMember(member: Member) {
    if (!confirm(`Remove ${member.full_name}? This cannot be undone.`)) return;
    try {
      await api.delete(`/api/v1/members/${member.id}`);
      await load();
      pushToast("success", `${member.full_name} removed`);
    } catch (err) {
      pushToast("error", err instanceof ApiError ? err.message : "Failed to delete");
    }
  }

  async function submitResetPassword(e: FormEvent) {
    e.preventDefault();
    if (!resetTargetId) return;
    try {
      await api.post(`/api/v1/members/${resetTargetId}/reset-password`, { new_password: resetPassword });
      pushToast("success", "Password reset — share the new password with them directly");
      setResetTargetId(null);
      setResetPassword("");
    } catch (err) {
      pushToast("error", err instanceof ApiError ? err.message : "Failed to reset password");
    }
  }

  async function submitTransferOwnership(e: FormEvent) {
    e.preventDefault();
    if (!transferTargetId) return;
    const target = members.find((m) => m.id === transferTargetId);
    if (!confirm(`Transfer Lab Leader ownership to ${target?.full_name}?`)) return;
    try {
      await api.post(`/api/v1/members/${transferTargetId}/transfer-ownership`, {
        confirm: true,
        demote_self_to: demoteSelfTo || null,
      });
      pushToast("success", `Ownership transferred to ${target?.full_name}`);
      setTransferTargetId(null);
      setDemoteSelfTo("");
      await load();
    } catch (err) {
      pushToast("error", err instanceof ApiError ? err.message : "Failed to transfer ownership");
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-xl font-semibold">Members</h1>
        {canManage && <Button onClick={openCreateForm}>{showForm ? "Cancel" : "New Member"}</Button>}
      </div>

      {canManage && showForm && (
        <Card>
          <CardHeader>
            <CardTitle>{editingId ? "Edit Member" : "New Member"}</CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={onSubmit} className="space-y-4">
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
                {!editingId && (
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
                )}
                <div>
                  <Label htmlFor="role">Role</Label>
                  <Select id="role" value={role} onChange={(e) => setRole(e.target.value as MemberRole)}>
                    <option value="member">member</option>
                    <option value="presenter">presenter</option>
                    <option value="lab_leader">lab_leader</option>
                  </Select>
                </div>
                {editingId && (
                  <div>
                    <Label htmlFor="active">Status</Label>
                    <Select id="active" value={active ? "active" : "inactive"} onChange={(e) => setActive(e.target.value === "active")}>
                      <option value="active">active</option>
                      <option value="inactive">inactive</option>
                    </Select>
                  </div>
                )}
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
                {submitting ? "Saving…" : editingId ? "Save changes" : "Create Member"}
              </Button>
            </form>
          </CardContent>
        </Card>
      )}

      {canManage && resetTargetId && (
        <Card>
          <CardHeader>
            <CardTitle>Reset password for {members.find((m) => m.id === resetTargetId)?.full_name}</CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={submitResetPassword} className="flex flex-wrap items-end gap-2">
              <div className="flex-1 min-w-[200px]">
                <Label htmlFor="resetPassword">New temporary password</Label>
                <Input id="resetPassword" required minLength={8} value={resetPassword} onChange={(e) => setResetPassword(e.target.value)} />
              </div>
              <Button type="submit">Reset</Button>
              <Button type="button" variant="outline" onClick={() => setResetTargetId(null)}>Cancel</Button>
            </form>
          </CardContent>
        </Card>
      )}

      {canManage && transferTargetId && (
        <Card>
          <CardHeader>
            <CardTitle>Transfer ownership to {members.find((m) => m.id === transferTargetId)?.full_name}</CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={submitTransferOwnership} className="flex flex-wrap items-end gap-2">
              <div className="flex-1 min-w-[200px]">
                <Label htmlFor="demoteSelfTo">Your new role (optional — leave blank to stay a co-Leader)</Label>
                <Select id="demoteSelfTo" value={demoteSelfTo} onChange={(e) => setDemoteSelfTo(e.target.value)}>
                  <option value="">Stay Lab Leader</option>
                  <option value="presenter">Step down to Presenter</option>
                  <option value="member">Step down to Member</option>
                </Select>
              </div>
              <Button type="submit">Confirm transfer</Button>
              <Button type="button" variant="outline" onClick={() => setTransferTargetId(null)}>Cancel</Button>
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
                    <td className="text-right whitespace-nowrap space-x-1.5">
                      <Button variant="outline" onClick={() => openEditForm(m)}>
                        Edit
                      </Button>
                      <Button variant="outline" onClick={() => setResetTargetId(m.id)}>
                        Reset password
                      </Button>
                      {m.role !== "lab_leader" && m.id !== me.id && (
                        <Button variant="outline" onClick={() => setTransferTargetId(m.id)}>
                          Make owner
                        </Button>
                      )}
                      <Button
                        variant="outline"
                        disabled={isLastActiveLeader(m)}
                        title={isLastActiveLeader(m) ? "This is the Lab's last active Lab Leader — promote another Member first" : undefined}
                        onClick={() => toggleActive(m)}
                      >
                        {m.active ? "Deactivate" : "Activate"}
                      </Button>
                      <Button
                        variant="destructive"
                        disabled={isLastActiveLeader(m)}
                        title={isLastActiveLeader(m) ? "This is the Lab's last active Lab Leader — promote another Member first" : undefined}
                        onClick={() => removeMember(m)}
                      >
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
