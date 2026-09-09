"use client";

import { useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import type { PendingReminder } from "@/lib/types";
import { useMember } from "@/lib/member-context";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { useToast } from "@/lib/toast-context";

export default function RemindersPage() {
  const me = useMember();
  const canManage = me.role === "lab_leader";
  const { push: pushToast } = useToast();

  const [reminders, setReminders] = useState<PendingReminder[]>([]);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  const [busyId, setBusyId] = useState<string | null>(null);

  async function load() {
    setReminders(await api.get<PendingReminder[]>("/api/v1/reminders/pending"));
  }

  useEffect(() => {
    if (canManage) load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function startEdit(r: PendingReminder) {
    setEditingId(r.id);
    setSubject(r.subject ?? "");
    setBody(r.body ?? "");
  }

  async function saveEdit(r: PendingReminder) {
    setBusyId(r.id);
    try {
      await api.patch(`/api/v1/reminders/${r.id}`, { subject, body });
      setEditingId(null);
      await load();
      pushToast("success", "Reminder updated");
    } catch (err) {
      pushToast("error", err instanceof ApiError ? err.message : "Failed to save");
    } finally {
      setBusyId(null);
    }
  }

  async function sendNow(r: PendingReminder) {
    if (!confirm(`Send this reminder to ${r.member_email} now?`)) return;
    setBusyId(r.id);
    try {
      await api.post(`/api/v1/reminders/${r.id}/send`);
      await load();
      pushToast("success", `Sent to ${r.member_email}`);
    } catch (err) {
      pushToast("error", err instanceof ApiError ? err.message : "Failed to send");
      await load(); // pick up the "failed" status + error_detail
    } finally {
      setBusyId(null);
    }
  }

  async function discard(r: PendingReminder) {
    if (!confirm(`Discard this reminder for ${r.member_email}? It won't be sent.`)) return;
    setBusyId(r.id);
    try {
      await api.delete(`/api/v1/reminders/${r.id}`);
      await load();
      pushToast("success", "Reminder discarded");
    } catch (err) {
      pushToast("error", err instanceof ApiError ? err.message : "Failed to discard");
    } finally {
      setBusyId(null);
    }
  }

  if (!canManage) {
    return <p className="text-muted">Only the Lab Leader can view Reminders.</p>;
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold">Reminders</h1>
        <p className="text-sm text-muted">
          Reminders generated while auto-send is off, waiting for you to review, edit, or send — see Settings to
          turn auto-send back on.
        </p>
      </div>

      <div className="space-y-4">
        {reminders.map((r) => {
          const isEditing = editingId === r.id;
          return (
            <Card key={r.id} className={r.status === "failed" ? "border-[var(--status-missing)]" : undefined}>
              <CardContent className="space-y-3 py-4">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-semibold">{r.member_name}</span>
                    <span className="text-sm text-muted">{r.member_email}</span>
                    <Badge>{r.milestone}</Badge>
                    <Badge className={r.status === "failed" ? "text-[var(--status-missing)]" : "text-[var(--status-late)]"}>
                      {r.status}
                    </Badge>
                  </div>
                  <div className="flex gap-2">
                    {!isEditing && (
                      <Button variant="outline" onClick={() => startEdit(r)}>
                        Edit
                      </Button>
                    )}
                    <Button disabled={busyId === r.id} onClick={() => sendNow(r)}>
                      {busyId === r.id ? "Working…" : "Send"}
                    </Button>
                    <Button variant="destructive" disabled={busyId === r.id} onClick={() => discard(r)}>
                      Discard
                    </Button>
                  </div>
                </div>
                <p className="text-sm text-muted">
                  Challenge: <span className="font-semibold text-foreground">{r.challenge_title}</span>
                </p>
                {r.status === "failed" && r.error_detail && (
                  <p className="text-sm text-[var(--status-missing)]">Error: {r.error_detail}</p>
                )}

                {isEditing ? (
                  <div className="space-y-2">
                    <input
                      className="w-full rounded-md border border-[var(--border)] bg-[var(--background)] px-3 py-2 text-sm"
                      value={subject}
                      onChange={(e) => setSubject(e.target.value)}
                    />
                    <textarea
                      rows={5}
                      className="w-full rounded-md border border-[var(--border)] bg-[var(--background)] p-3 font-data text-xs"
                      value={body}
                      onChange={(e) => setBody(e.target.value)}
                    />
                    <div className="flex gap-2">
                      <Button disabled={busyId === r.id} onClick={() => saveEdit(r)}>
                        Save
                      </Button>
                      <Button variant="outline" onClick={() => setEditingId(null)}>
                        Cancel
                      </Button>
                    </div>
                  </div>
                ) : (
                  <div className="rounded-md border border-[var(--border)] bg-[var(--background)] p-3">
                    <p className="text-sm font-semibold">{r.subject}</p>
                    <pre className="mt-1 whitespace-pre-wrap font-data text-xs text-muted">{r.body}</pre>
                  </div>
                )}
              </CardContent>
            </Card>
          );
        })}
        {reminders.length === 0 && <p className="text-muted">No reminders waiting for review.</p>}
      </div>
    </div>
  );
}
