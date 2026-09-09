"use client";

import { useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import type { Report, ReportSendAttempt, TenantSettings } from "@/lib/types";
import { useMember } from "@/lib/member-context";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { useToast } from "@/lib/toast-context";
import { Download, FileText } from "lucide-react";

export default function ReportsPage() {
  const me = useMember();
  const canManage = me.role === "lab_leader";
  const { push: pushToast } = useToast();

  const [reports, setReports] = useState<Report[]>([]);
  const [professorEmail, setProfessorEmail] = useState("");
  const [openId, setOpenId] = useState<string | null>(null);
  const [draftContent, setDraftContent] = useState("");
  const [toAddress, setToAddress] = useState("");
  const [saving, setSaving] = useState(false);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [generating, setGenerating] = useState(false);
  const [attempts, setAttempts] = useState<ReportSendAttempt[]>([]);
  const [resending, setResending] = useState(false);

  async function load() {
    const [r, s] = await Promise.all([
      api.get<Report[]>("/api/v1/reports"),
      canManage ? api.get<TenantSettings>("/api/v1/settings") : Promise.resolve(null),
    ]);
    setReports(r);
    if (s) setProfessorEmail(s.professor_email ?? "");
  }

  useEffect(() => {
    if (canManage) load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function openReport(report: Report) {
    const opening = report.id !== openId;
    setOpenId(opening ? report.id : null);
    setDraftContent(report.content ?? "");
    setToAddress(report.recipient_email ?? professorEmail);
    setError(null);
    setAttempts([]);
    if (opening) {
      api.get<ReportSendAttempt[]>(`/api/v1/reports/${report.id}/send-attempts`).then(setAttempts);
    }
  }

  async function saveDraft(report: Report) {
    setSaving(true);
    setError(null);
    try {
      await api.patch(`/api/v1/reports/${report.id}`, { content: draftContent });
      await load();
      pushToast("success", "Draft saved");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to save");
    } finally {
      setSaving(false);
    }
  }

  async function approve(report: Report) {
    if (!toAddress) {
      setError("Enter a recipient email");
      return;
    }
    const isRetry = attempts.length > 0;
    if (!confirm(`${isRetry ? "Retry sending" : "Send"} this report to ${toAddress}? This cannot be undone.`)) return;
    setSending(true);
    setError(null);
    try {
      await api.post(`/api/v1/reports/${report.id}/approve`, { to_address: toAddress });
      setOpenId(null);
      await load();
      pushToast("success", `Sent to ${toAddress}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to send");
      pushToast("error", "Failed to send");
      const fresh = await api.get<ReportSendAttempt[]>(`/api/v1/reports/${report.id}/send-attempts`);
      setAttempts(fresh);
    } finally {
      setSending(false);
    }
  }

  async function resend(report: Report) {
    if (!toAddress) {
      setError("Enter a recipient email");
      return;
    }
    if (!confirm(`Resend this already-sent report to ${toAddress}?`)) return;
    setResending(true);
    setError(null);
    try {
      await api.post(`/api/v1/reports/${report.id}/resend`, { to_address: toAddress, confirm: true });
      await load();
      const fresh = await api.get<ReportSendAttempt[]>(`/api/v1/reports/${report.id}/send-attempts`);
      setAttempts(fresh);
      pushToast("success", `Resent to ${toAddress}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to resend");
      pushToast("error", "Failed to resend");
    } finally {
      setResending(false);
    }
  }

  async function deleteReport(report: Report) {
    if (!confirm(`Delete this draft ${report.type} report (${report.period_start} – ${report.period_end})?`)) return;
    try {
      await api.delete(`/api/v1/reports/${report.id}`);
      if (openId === report.id) setOpenId(null);
      await load();
      pushToast("success", "Report deleted");
    } catch (err) {
      pushToast("error", err instanceof ApiError ? err.message : "Failed to delete report");
    }
  }

  async function generateNow() {
    setGenerating(true);
    setError(null);
    try {
      const report = await api.post<Report>("/api/v1/reports/generate-now");
      await load();
      openReport(report);
      pushToast("success", "Weekly report generated");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to generate report");
    } finally {
      setGenerating(false);
    }
  }

  if (!canManage) {
    return <p className="text-muted">Only the Lab Leader can view Reports.</p>;
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h1 className="text-xl font-semibold">Reports</h1>
          <p className="text-sm text-muted">
            Weekly reports generate automatically every Monday. Semester reports are generated manually from
            Semesters. Review and edit before sending to your professor.
          </p>
        </div>
        {canManage && (
          <Button variant="outline" disabled={generating} onClick={generateNow}>
            {generating ? "Generating…" : "Generate weekly now"}
          </Button>
        )}
      </div>

      {error && <p className="text-sm text-[var(--status-missing)]">{error}</p>}

      <div className="space-y-4">
        {reports.map((r) => {
          const isOpen = openId === r.id;
          return (
            <Card key={r.id} className={r.status === "draft" ? "border-[var(--status-late)]" : undefined}>
              <CardHeader className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex flex-wrap items-center gap-2.5">
                  <span className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-lg border border-[var(--border)] bg-background">
                    <FileText size={17} strokeWidth={1.75} />
                  </span>
                  <CardTitle>
                    {r.type === "semester" ? "Semester Report" : "Weekly Report"} ({r.period_start} – {r.period_end})
                  </CardTitle>
                  <Badge>{r.type}</Badge>
                  <Badge className={r.status === "draft" ? "text-[var(--status-late)]" : "text-[var(--status-done)]"}>
                    {r.status}
                  </Badge>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  {r.type === "semester" && (
                    <>
                      <a
                        href={`/api/v1/reports/${r.id}/export.pdf`}
                        onClick={() => pushToast("info", "Preparing PDF export…")}
                        className="inline-flex items-center gap-1.5 rounded-[9px] border border-[var(--border)] px-3.5 py-2 text-[13px] font-semibold hover:border-accent hover:text-accent"
                      >
                        <Download size={13} /> Export PDF
                      </a>
                      <a
                        href={`/api/v1/reports/${r.id}/export.xlsx`}
                        onClick={() => pushToast("info", "Preparing Excel export…")}
                        className="inline-flex items-center gap-1.5 rounded-[9px] border border-[var(--border)] px-3.5 py-2 text-[13px] font-semibold hover:border-accent hover:text-accent"
                      >
                        <Download size={13} /> Export Excel
                      </a>
                    </>
                  )}
                  <Button variant="outline" onClick={() => openReport(r)}>
                    {isOpen ? "Close" : r.status === "draft" ? "Review" : "View"}
                  </Button>
                  {canManage && r.status === "draft" && (
                    <Button variant="destructive" onClick={() => deleteReport(r)}>
                      Delete
                    </Button>
                  )}
                </div>
              </CardHeader>
              {isOpen && (
                <CardContent className="space-y-4">
                  {r.status === "draft" && canManage ? (
                    <>
                      <textarea
                        className="h-64 w-full rounded-md border border-[var(--border)] bg-[var(--surface)] p-3 font-data text-sm"
                        value={draftContent}
                        onChange={(e) => setDraftContent(e.target.value)}
                      />
                      <div className="flex gap-2">
                        <Button variant="outline" disabled={saving} onClick={() => saveDraft(r)}>
                          {saving ? "Saving…" : "Save draft"}
                        </Button>
                      </div>
                      <div className="border-t border-[var(--border)] pt-4">
                        <Label htmlFor="toAddress">Send to</Label>
                        <div className="flex gap-2">
                          <Input
                            id="toAddress"
                            type="email"
                            value={toAddress}
                            onChange={(e) => setToAddress(e.target.value)}
                            placeholder="professor@university.edu"
                          />
                          <Button disabled={sending} onClick={() => approve(r)}>
                            {sending ? "Sending…" : attempts.length > 0 ? "Retry & Send" : "Approve & Send"}
                          </Button>
                        </div>
                      </div>
                    </>
                  ) : (
                    <>
                      <pre className="whitespace-pre-wrap font-data text-sm text-foreground">{r.content}</pre>
                      {r.status === "sent" && (
                        <p className="text-xs text-muted">
                          Sent {r.sent_at ? new Date(r.sent_at).toLocaleString() : "—"} by {r.approved_by} to{" "}
                          {r.recipient_email ?? "—"}
                        </p>
                      )}
                      {r.status === "sent" && canManage && (
                        <div className="border-t border-[var(--border)] pt-4">
                          <Label htmlFor="resendAddress">Resend to</Label>
                          <div className="flex gap-2">
                            <Input
                              id="resendAddress"
                              type="email"
                              value={toAddress}
                              onChange={(e) => setToAddress(e.target.value)}
                              placeholder="professor@university.edu"
                            />
                            <Button variant="outline" disabled={resending} onClick={() => resend(r)}>
                              {resending ? "Resending…" : "Resend"}
                            </Button>
                          </div>
                        </div>
                      )}
                    </>
                  )}

                  {attempts.length > 0 && (
                    <div className="border-t border-[var(--border)] pt-4">
                      <p className="mb-2 text-xs font-semibold text-muted">Send attempts</p>
                      <div className="space-y-1.5">
                        {attempts.map((a) => (
                          <div key={a.id} className="flex flex-wrap items-center justify-between gap-2 text-xs">
                            <span>
                              <Badge className="mr-1.5 capitalize">{a.kind}</Badge>
                              <span
                                className={a.status === "success" ? "text-[var(--status-done)]" : "text-[var(--status-missing)]"}
                              >
                                {a.status}
                              </span>{" "}
                              → {a.recipient_email} by {a.attempted_by_email}
                            </span>
                            <span className="font-data text-muted">{new Date(a.attempted_at).toLocaleString()}</span>
                            {a.error_detail && (
                              <span className="w-full text-[var(--status-missing)]">{a.error_detail}</span>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </CardContent>
              )}
            </Card>
          );
        })}
        {reports.length === 0 && <p className="text-muted">No reports yet.</p>}
      </div>
    </div>
  );
}
