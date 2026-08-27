"use client";

import { useEffect, useState, type FormEvent } from "react";
import { api, ApiError } from "@/lib/api";
import type { Challenge, ChallengeLookupResult, Member, Platform, Semester } from "@/lib/types";
import { useMember } from "@/lib/member-context";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useToast } from "@/lib/toast-context";

function toLocalInputValue(iso: string) {
  const d = new Date(iso);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

export default function ChallengesPage() {
  const me = useMember();
  const canManage = me.role === "lab_leader";
  const { push: pushToast } = useToast();

  const [challenges, setChallenges] = useState<Challenge[]>([]);
  const [semesters, setSemesters] = useState<Semester[]>([]);
  const [platforms, setPlatforms] = useState<Platform[]>([]);
  const [members, setMembers] = useState<Member[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const [semesterId, setSemesterId] = useState("");
  const [platformId, setPlatformId] = useState("");
  const [weekNumber, setWeekNumber] = useState(1);
  const [title, setTitle] = useState("");
  const [category, setCategory] = useState("");
  const [difficulty, setDifficulty] = useState("");
  const [presenterId, setPresenterId] = useState("");
  const [deadline, setDeadline] = useState("");
  const [points, setPoints] = useState<number | "">("");
  const [externalChallengeId, setExternalChallengeId] = useState("");
  const [lookingUp, setLookingUp] = useState(false);
  const [lookupStatus, setLookupStatus] = useState("");

  async function load() {
    const [c, s, p, m] = await Promise.all([
      api.get<Challenge[]>("/api/v1/challenges"),
      api.get<Semester[]>("/api/v1/semesters"),
      api.get<Platform[]>("/api/v1/platforms"),
      api.get<Member[]>("/api/v1/members"),
    ]);
    setChallenges(c);
    setSemesters(s);
    setPlatforms(p);
    setMembers(m);
    if (!semesterId && s.length > 0) setSemesterId(s.find((x) => x.is_current)?.id ?? s[0].id);
    if (!platformId && p.length > 0) setPlatformId(p[0].id);
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function semesterName(id: string) {
    return semesters.find((s) => s.id === id)?.name ?? "—";
  }
  function presenterName(id: string | null) {
    if (!id) return "—";
    return members.find((m) => m.id === id)?.full_name ?? "—";
  }

  async function lookupFromRootMe() {
    if (!platformId || !externalChallengeId.trim()) {
      setLookupStatus("Pick a platform and enter a Root Me challenge ID first");
      return;
    }
    setLookingUp(true);
    setLookupStatus("");
    try {
      const result = await api.get<ChallengeLookupResult>(
        `/api/v1/platforms/${platformId}/challenge-lookup?external_challenge_id=${encodeURIComponent(externalChallengeId)}`
      );
      if (result.title) setTitle(result.title);
      if (result.category) setCategory(result.category);
      if (result.score !== null) setPoints(result.score);
      setLookupStatus("Prefilled from Root Me — review before saving");
    } catch (err) {
      setLookupStatus(err instanceof ApiError ? err.message : "Lookup failed");
    } finally {
      setLookingUp(false);
    }
  }

  async function onCreate(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await api.post("/api/v1/challenges", {
        semester_id: semesterId,
        platform_id: platformId,
        week_number: weekNumber,
        title,
        category: category || null,
        difficulty: difficulty || null,
        external_challenge_id: externalChallengeId || null,
        presenter_id: presenterId || null,
        deadline_at: new Date(deadline).toISOString(),
        points: points === "" ? null : points,
      });
      setTitle("");
      setCategory("");
      setDifficulty("");
      setExternalChallengeId("");
      setLookupStatus("");
      setPresenterId("");
      setDeadline("");
      setPoints("");
      setShowForm(false);
      await load();
      pushToast("success", `${title} added`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to create challenge");
    } finally {
      setSubmitting(false);
    }
  }

  async function remove(challenge: Challenge) {
    if (!confirm(`Delete challenge "${challenge.title}"?`)) return;
    await api.delete(`/api/v1/challenges/${challenge.id}`);
    await load();
    pushToast("success", `${challenge.title} deleted`);
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-xl font-semibold">Challenges</h1>
        {canManage && semesters.length > 0 && (
          <Button onClick={() => setShowForm((v) => !v)}>{showForm ? "Cancel" : "New Challenge"}</Button>
        )}
      </div>

      {canManage && semesters.length === 0 && (
        <p className="text-sm text-muted">Create a Semester first before adding Challenges.</p>
      )}

      {canManage && showForm && (
        <Card>
          <CardHeader>
            <CardTitle>New Challenge</CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={onCreate} className="space-y-4">
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                <div>
                  <Label htmlFor="semester">Semester</Label>
                  <Select id="semester" value={semesterId} onChange={(e) => setSemesterId(e.target.value)}>
                    {semesters.map((s) => (
                      <option key={s.id} value={s.id}>
                        {s.name}
                      </option>
                    ))}
                  </Select>
                </div>
                <div>
                  <Label htmlFor="platform">Platform</Label>
                  <Select id="platform" value={platformId} onChange={(e) => setPlatformId(e.target.value)}>
                    {platforms.map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.name}
                      </option>
                    ))}
                  </Select>
                </div>
                <div>
                  <Label htmlFor="week">Week #</Label>
                  <Input
                    id="week"
                    type="number"
                    min={1}
                    required
                    value={weekNumber}
                    onChange={(e) => setWeekNumber(Number(e.target.value))}
                  />
                </div>
              </div>

              <div>
                <Label htmlFor="extId">Root Me challenge ID (optional)</Label>
                <div className="flex gap-2">
                  <Input
                    id="extId"
                    placeholder="e.g. 42"
                    value={externalChallengeId}
                    onChange={(e) => setExternalChallengeId(e.target.value)}
                  />
                  <Button type="button" variant="outline" disabled={lookingUp} onClick={lookupFromRootMe}>
                    {lookingUp ? "Fetching…" : "Fetch from Root Me"}
                  </Button>
                </div>
                {lookupStatus && <p className="mt-1 text-xs text-muted">{lookupStatus}</p>}
                <p className="mt-1 text-xs text-muted">
                  Required for auto-sync (Phase 3) to match this Challenge against a member&apos;s solved challenges.
                </p>
              </div>

              <div>
                <Label htmlFor="title">Title</Label>
                <Input id="title" required value={title} onChange={(e) => setTitle(e.target.value)} />
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                <div>
                  <Label htmlFor="category">Category</Label>
                  <Input id="category" value={category} onChange={(e) => setCategory(e.target.value)} />
                </div>
                <div>
                  <Label htmlFor="difficulty">Difficulty</Label>
                  <Input id="difficulty" value={difficulty} onChange={(e) => setDifficulty(e.target.value)} />
                </div>
                <div>
                  <Label htmlFor="points">Points</Label>
                  <Input
                    id="points"
                    type="number"
                    value={points}
                    onChange={(e) => setPoints(e.target.value === "" ? "" : Number(e.target.value))}
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <Label htmlFor="presenter">Presenter</Label>
                  <Select id="presenter" value={presenterId} onChange={(e) => setPresenterId(e.target.value)}>
                    <option value="">— none —</option>
                    {members.map((m) => (
                      <option key={m.id} value={m.id}>
                        {m.full_name}
                      </option>
                    ))}
                  </Select>
                </div>
                <div>
                  <Label htmlFor="deadline">Deadline</Label>
                  <Input
                    id="deadline"
                    type="datetime-local"
                    required
                    value={deadline}
                    onChange={(e) => setDeadline(e.target.value)}
                  />
                </div>
              </div>

              {error && <p className="text-sm text-[var(--status-missing)]">{error}</p>}
              <Button type="submit" disabled={submitting}>
                {submitting ? "Creating…" : "Create Challenge"}
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
                <th>Wk</th>
                <th>Title</th>
                <th>Semester</th>
                <th>Presenter</th>
                <th>Deadline</th>
                {canManage && <th />}
              </tr>
            </thead>
            <tbody>
              {challenges.map((c) => (
                <tr key={c.id}>
                  <td className="font-data text-muted">W{c.week_number}</td>
                  <td className="font-semibold">{c.title}</td>
                  <td className="text-muted">{semesterName(c.semester_id)}</td>
                  <td className="text-muted">{presenterName(c.presenter_id)}</td>
                  <td className="font-data text-muted">{toLocalInputValue(c.deadline_at).replace("T", " ")}</td>
                  {canManage && (
                    <td className="text-right">
                      <Button variant="destructive" onClick={() => remove(c)}>
                        Delete
                      </Button>
                    </td>
                  )}
                </tr>
              ))}
              {challenges.length === 0 && (
                <tr>
                  <td colSpan={canManage ? 6 : 5} className="py-6 text-center text-muted">
                    No challenges yet.
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
