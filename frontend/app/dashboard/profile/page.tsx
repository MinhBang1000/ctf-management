"use client";

import { useEffect, useState, type FormEvent } from "react";
import { api, ApiError } from "@/lib/api";
import type { Member, Platform, PlatformAccount } from "@/lib/types";
import { useMember } from "@/lib/member-context";
import { useToast } from "@/lib/toast-context";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

interface PlatformAccountDraft {
  platform_id: string;
  external_username: string;
  external_user_id: string;
}

export default function ProfilePage() {
  const me = useMember();
  const { push: pushToast } = useToast();

  const [platforms, setPlatforms] = useState<Platform[]>([]);
  const [accounts, setAccounts] = useState<PlatformAccountDraft[]>([]);
  const [savingAccounts, setSavingAccounts] = useState(false);

  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [changingPassword, setChangingPassword] = useState(false);
  const [passwordError, setPasswordError] = useState<string | null>(null);

  async function load() {
    const [p, self] = await Promise.all([
      api.get<Platform[]>("/api/v1/platforms"),
      api.get<Member>(`/api/v1/members/${me.id}`),
    ]);
    setPlatforms(p);
    setAccounts(
      self.platform_accounts.map((a: PlatformAccount) => ({
        platform_id: a.platform_id,
        external_username: a.external_username,
        external_user_id: a.external_user_id,
      }))
    );
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function saveAccounts(e: FormEvent) {
    e.preventDefault();
    setSavingAccounts(true);
    try {
      await api.put("/api/v1/me/platform-accounts", accounts);
      pushToast("success", "Platform accounts updated");
      await load();
    } catch (err) {
      pushToast("error", err instanceof ApiError ? err.message : "Failed to save");
    } finally {
      setSavingAccounts(false);
    }
  }

  async function changePassword(e: FormEvent) {
    e.preventDefault();
    setPasswordError(null);
    setChangingPassword(true);
    try {
      await api.post("/api/v1/auth/change-password", {
        current_password: currentPassword,
        new_password: newPassword,
      });
      setCurrentPassword("");
      setNewPassword("");
      pushToast("success", "Password changed");
    } catch (err) {
      setPasswordError(err instanceof ApiError ? err.message : "Failed to change password");
    } finally {
      setChangingPassword(false);
    }
  }

  return (
    <div className="max-w-2xl space-y-6">
      <div>
        <h1 className="text-xl font-semibold">My Profile</h1>
        <p className="text-sm text-muted">
          Manage your own account — for changes to your role, active status, or Lab, contact your Lab Leader.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Account information</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 text-sm">
          <div className="flex justify-between">
            <span className="text-muted">Name</span>
            <span>{me.full_name}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-muted">Email</span>
            <span>{me.email}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-muted">Role</span>
            <Badge className="capitalize">{me.role.replace("_", " ")}</Badge>
          </div>
          <div className="flex justify-between">
            <span className="text-muted">Lab</span>
            <span>{me.tenant_name}</span>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Change password</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={changePassword} className="space-y-4">
            <div>
              <Label htmlFor="currentPassword">Current password</Label>
              <Input
                id="currentPassword"
                type="password"
                required
                value={currentPassword}
                onChange={(e) => setCurrentPassword(e.target.value)}
              />
            </div>
            <div>
              <Label htmlFor="newPassword">New password</Label>
              <Input
                id="newPassword"
                type="password"
                required
                minLength={8}
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
              />
            </div>
            {passwordError && <p className="text-sm text-[var(--status-missing)]">{passwordError}</p>}
            <Button type="submit" disabled={changingPassword}>
              {changingPassword ? "Changing…" : "Change password"}
            </Button>
          </form>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>My platform accounts</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={saveAccounts} className="space-y-4">
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
                        setAccounts((prev) => prev.map((a, i) => (i === idx ? { ...a, external_username: e.target.value } : a)))
                      }
                    />
                  </div>
                  <div>
                    <Label className="text-xs">Root Me ID (id_auteur) *</Label>
                    <Input
                      required
                      value={acc.external_user_id}
                      onChange={(e) =>
                        setAccounts((prev) => prev.map((a, i) => (i === idx ? { ...a, external_user_id: e.target.value } : a)))
                      }
                    />
                  </div>
                  <div className="flex items-end">
                    <Button type="button" variant="ghost" onClick={() => setAccounts((prev) => prev.filter((_, i) => i !== idx))}>
                      Remove
                    </Button>
                  </div>
                </div>
              ))}
            </div>
            <div className="flex gap-2">
              <Button
                type="button"
                variant="outline"
                onClick={() => setAccounts((prev) => [...prev, { platform_id: platforms[0]?.id ?? "", external_username: "", external_user_id: "" }])}
              >
                + Add account
              </Button>
              <Button type="submit" disabled={savingAccounts}>
                {savingAccounts ? "Saving…" : "Save"}
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
