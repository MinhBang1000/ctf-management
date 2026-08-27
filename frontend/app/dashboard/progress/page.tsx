"use client";

import { useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import type { Challenge, Member, Progress, ProgressStatus, Semester } from "@/lib/types";
import { useMember } from "@/lib/member-context";
import { Select } from "@/components/ui/select";
import { Card, CardContent } from "@/components/ui/card";
import { StatusBadge } from "@/components/status-badge";

const STATUSES: ProgressStatus[] = ["early", "done", "late", "missing"];

export default function ProgressPage() {
  const me = useMember();
  const canEdit = me.role === "lab_leader" || me.role === "presenter";

  const [semesters, setSemesters] = useState<Semester[]>([]);
  const [semesterId, setSemesterId] = useState("");
  const [members, setMembers] = useState<Member[]>([]);
  const [challenges, setChallenges] = useState<Challenge[]>([]);
  const [progress, setProgress] = useState<Progress[]>([]);
  const [savingKey, setSavingKey] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      const [s, m] = await Promise.all([
        api.get<Semester[]>("/api/v1/semesters"),
        api.get<Member[]>("/api/v1/members"),
      ]);
      setSemesters(s);
      setMembers(m.filter((x) => x.active));
      setSemesterId(s.find((x) => x.is_current)?.id ?? s[0]?.id ?? "");
    })();
  }, []);

  useEffect(() => {
    if (!semesterId) return;
    (async () => {
      const c = await api.get<Challenge[]>(`/api/v1/challenges?semester_id=${semesterId}`);
      setChallenges(c);
      const all = await Promise.all(c.map((ch) => api.get<Progress[]>(`/api/v1/progress?challenge_id=${ch.id}`)));
      setProgress(all.flat());
    })();
  }, [semesterId]);

  const progressMap = useMemo(() => {
    const map = new Map<string, Progress>();
    for (const p of progress) map.set(`${p.member_id}:${p.challenge_id}`, p);
    return map;
  }, [progress]);

  async function setStatus(memberId: string, challengeId: string, status: ProgressStatus) {
    const key = `${memberId}:${challengeId}`;
    setSavingKey(key);
    try {
      const updated = await api.put<Progress>("/api/v1/progress", {
        member_id: memberId,
        challenge_id: challengeId,
        status,
      });
      setProgress((prev) => [...prev.filter((p) => !(p.member_id === memberId && p.challenge_id === challengeId)), updated]);
    } finally {
      setSavingKey(null);
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-xl font-semibold">Progress</h1>
        <Select className="w-64" value={semesterId} onChange={(e) => setSemesterId(e.target.value)}>
          {semesters.map((s) => (
            <option key={s.id} value={s.id}>
              {s.name}
            </option>
          ))}
        </Select>
      </div>

      <Card>
        <CardContent className="overflow-x-auto p-0">
          <table className="hs-table">
            <thead>
              <tr>
                <th className="sticky left-0 bg-background pr-4">Member</th>
                {challenges.map((c) => (
                  <th key={c.id} className="whitespace-nowrap">
                    W{c.week_number} · {c.title}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {members.map((m) => (
                <tr key={m.id}>
                  <td className="sticky left-0 bg-surface pr-4 font-semibold">{m.full_name}</td>
                  {challenges.map((c) => {
                    const key = `${m.id}:${c.id}`;
                    const p = progressMap.get(key);
                    return (
                      <td key={c.id} className="py-2 px-3">
                        {canEdit ? (
                          <select
                            disabled={savingKey === key}
                            value={p?.status ?? ""}
                            onChange={(e) => setStatus(m.id, c.id, e.target.value as ProgressStatus)}
                            className="rounded-md border border-[var(--border)] bg-[var(--surface)] px-2 py-1 text-xs"
                          >
                            <option value="" disabled>
                              set…
                            </option>
                            {STATUSES.map((s) => (
                              <option key={s} value={s}>
                                {s}
                              </option>
                            ))}
                          </select>
                        ) : p ? (
                          <StatusBadge status={p.status} />
                        ) : (
                          <span className="text-muted">—</span>
                        )}
                      </td>
                    );
                  })}
                </tr>
              ))}
              {members.length === 0 && (
                <tr>
                  <td colSpan={challenges.length + 1} className="py-6 text-center text-muted">
                    No active members.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
          {challenges.length === 0 && semesterId && (
            <p className="py-6 text-center text-muted">No challenges in this semester yet.</p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
