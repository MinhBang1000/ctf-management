"use client";

import { useEffect, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { api, ApiError } from "@/lib/api";
import type { Report, Semester } from "@/lib/types";
import { useMember } from "@/lib/member-context";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { useToast } from "@/lib/toast-context";

export default function SemestersPage() {
  const me = useMember();
  const canManage = me.role === "lab_leader";
  const router = useRouter();
  const { push: pushToast } = useToast();

  const [semesters, setSemesters] = useState<Semester[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [generatingId, setGeneratingId] = useState<string | null>(null);

  const [name, setName] = useState("");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [isCurrent, setIsCurrent] = useState(false);

  async function load() {
    setSemesters(await api.get<Semester[]>("/api/v1/semesters"));
  }

  useEffect(() => {
    load();
  }, []);

  async function onCreate(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await api.post("/api/v1/semesters", {
        name,
        start_date: startDate,
        end_date: endDate,
        is_current: isCurrent,
      });
      setName("");
      setStartDate("");
      setEndDate("");
      setIsCurrent(false);
      setShowForm(false);
      await load();
      pushToast("success", `${name} created`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to create semester");
    } finally {
      setSubmitting(false);
    }
  }

  async function setCurrent(semester: Semester) {
    await api.patch(`/api/v1/semesters/${semester.id}`, { is_current: true });
    await load();
    pushToast("success", `${semester.name} set as current`);
  }

  async function remove(semester: Semester) {
    if (!confirm(`Delete semester "${semester.name}"? This also deletes its challenges.`)) return;
    await api.delete(`/api/v1/semesters/${semester.id}`);
    await load();
    pushToast("success", `${semester.name} deleted`);
  }

  async function generateReport(semester: Semester) {
    if (!confirm(`Generate a semester report for "${semester.name}"? You'll review it before sending.`)) return;
    setGeneratingId(semester.id);
    setError(null);
    try {
      await api.post<Report>(`/api/v1/semesters/${semester.id}/generate-report`);
      pushToast("success", "Semester report generated");
      router.push("/dashboard/reports");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to generate report");
      pushToast("error", "Failed to generate report");
    } finally {
      setGeneratingId(null);
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-xl font-semibold">Semesters</h1>
        {canManage && <Button onClick={() => setShowForm((v) => !v)}>{showForm ? "Cancel" : "New Semester"}</Button>}
      </div>

      {canManage && showForm && (
        <Card>
          <CardHeader>
            <CardTitle>New Semester</CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={onCreate} className="space-y-4">
              <div>
                <Label htmlFor="name">Name</Label>
                <Input id="name" required value={name} onChange={(e) => setName(e.target.value)} />
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <Label htmlFor="start">Start date</Label>
                  <Input
                    id="start"
                    type="date"
                    required
                    value={startDate}
                    onChange={(e) => setStartDate(e.target.value)}
                  />
                </div>
                <div>
                  <Label htmlFor="end">End date</Label>
                  <Input id="end" type="date" required value={endDate} onChange={(e) => setEndDate(e.target.value)} />
                </div>
              </div>
              <label className="flex items-center gap-2 text-sm">
                <input type="checkbox" checked={isCurrent} onChange={(e) => setIsCurrent(e.target.checked)} />
                Set as current semester
              </label>
              {error && <p className="text-sm text-[var(--status-missing)]">{error}</p>}
              <Button type="submit" disabled={submitting}>
                {submitting ? "Creating…" : "Create Semester"}
              </Button>
            </form>
          </CardContent>
        </Card>
      )}

      {!showForm && error && <p className="text-sm text-[var(--status-missing)]">{error}</p>}

      <Card>
        <CardContent className="overflow-x-auto p-0">
          <table className="hs-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Start</th>
                <th>End</th>
                <th>Current</th>
                {canManage && <th />}
              </tr>
            </thead>
            <tbody>
              {semesters.map((s) => (
                <tr key={s.id}>
                  <td className="font-semibold">{s.name}</td>
                  <td className="text-muted">{s.start_date}</td>
                  <td className="text-muted">{s.end_date}</td>
                  <td>{s.is_current ? <Badge className="text-[var(--status-done)]">current</Badge> : null}</td>
                  {canManage && (
                    <td className="text-right whitespace-nowrap">
                      {!s.is_current && (
                        <Button variant="outline" onClick={() => setCurrent(s)}>
                          Set current
                        </Button>
                      )}{" "}
                      <Button variant="outline" disabled={generatingId === s.id} onClick={() => generateReport(s)}>
                        {generatingId === s.id ? "Generating…" : "Generate Report"}
                      </Button>{" "}
                      <Button variant="destructive" onClick={() => remove(s)}>
                        Delete
                      </Button>
                    </td>
                  )}
                </tr>
              ))}
              {semesters.length === 0 && (
                <tr>
                  <td colSpan={canManage ? 5 : 4} className="py-6 text-center text-muted">
                    No semesters yet.
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
