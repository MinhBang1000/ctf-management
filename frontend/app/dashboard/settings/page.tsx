"use client";

import { useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import type { AutomationSettings, TenantSettings, TestConnectionResult } from "@/lib/types";
import { useMember } from "@/lib/member-context";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { useToast } from "@/lib/toast-context";
import { Download } from "lucide-react";
import { RepeatScheduleEditor } from "@/components/automation/repeat-schedule-editor";

export default function SettingsPage() {
  const me = useMember();
  const { push: pushToast } = useToast();

  const [settings, setSettings] = useState<TenantSettings | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const [host, setHost] = useState("");
  const [port, setPort] = useState(587);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [fromAddress, setFromAddress] = useState("");
  const [useTls, setUseTls] = useState(true);

  const [professorEmail, setProfessorEmail] = useState("");
  const [savingProfessor, setSavingProfessor] = useState(false);

  const [testTo, setTestTo] = useState("");
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<TestConnectionResult | null>(null);

  const [automation, setAutomation] = useState<AutomationSettings | null>(null);
  const [savingAutomation, setSavingAutomation] = useState(false);

  async function load() {
    const [s, a] = await Promise.all([
      api.get<TenantSettings>("/api/v1/settings"),
      api.get<AutomationSettings>("/api/v1/settings/automation"),
    ]);
    setSettings(s);
    setHost(s.smtp.host ?? "");
    setPort(s.smtp.port ?? 587);
    setUsername(s.smtp.username ?? "");
    setFromAddress(s.smtp.from_address ?? "");
    setUseTls(s.smtp.use_tls ?? true);
    setProfessorEmail(s.professor_email ?? "");
    setAutomation(a);
  }

  async function saveAutomation() {
    if (!automation) return;
    setSavingAutomation(true);
    try {
      const updated = await api.patch<AutomationSettings>("/api/v1/settings/automation", automation);
      setAutomation(updated);
      pushToast("success", "Automation settings saved");
    } catch (err) {
      pushToast("error", err instanceof ApiError ? err.message : "Failed to save automation settings");
    } finally {
      setSavingAutomation(false);
    }
  }

  useEffect(() => {
    if (me.role === "lab_leader") load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function saveSmtp() {
    setSaving(true);
    setError(null);
    try {
      await api.patch("/api/v1/settings/smtp", {
        host,
        port,
        username: username || null,
        password,
        from_address: fromAddress || null,
        use_tls: useTls,
      });
      setPassword("");
      await load();
      pushToast("success", "SMTP settings saved");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to save SMTP settings");
    } finally {
      setSaving(false);
    }
  }

  async function saveProfessorEmail() {
    setSavingProfessor(true);
    setError(null);
    try {
      await api.patch("/api/v1/settings/professor-email", { professor_email: professorEmail || null });
      await load();
      pushToast("success", "Professor email saved");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to save");
    } finally {
      setSavingProfessor(false);
    }
  }

  async function sendTest() {
    setTesting(true);
    setTestResult(null);
    try {
      const result = await api.post<TestConnectionResult>("/api/v1/settings/smtp/test-email", {
        to_address: testTo,
      });
      setTestResult(result);
      pushToast(result.ok ? "success" : "error", result.detail);
    } finally {
      setTesting(false);
    }
  }

  if (me.role !== "lab_leader") {
    return <p className="text-muted">Only the Lab Leader can view Settings.</p>;
  }
  if (!settings) return null;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold">Settings</h1>
        <p className="text-sm text-muted">SMTP is used for reminders and the weekly report to your professor.</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex flex-wrap items-center gap-2">
            SMTP
            <Badge className={settings.smtp.has_credentials ? "text-[var(--status-done)]" : "text-[var(--status-missing)]"}>
              {settings.smtp.has_credentials ? "configured" : "using system default"}
            </Badge>
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <Label htmlFor="host">Host</Label>
              <Input id="host" value={host} onChange={(e) => setHost(e.target.value)} placeholder="smtp.gmail.com" />
            </div>
            <div>
              <Label htmlFor="port">Port</Label>
              <Input id="port" type="number" value={port} onChange={(e) => setPort(Number(e.target.value))} />
            </div>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <Label htmlFor="username">Username</Label>
              <Input id="username" value={username} onChange={(e) => setUsername(e.target.value)} />
            </div>
            <div>
              <Label htmlFor="password">Password</Label>
              <Input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder={settings.smtp.has_credentials ? "•••••••• (leave blank to keep current)" : ""}
              />
            </div>
          </div>
          <div>
            <Label htmlFor="fromAddress">From address</Label>
            <Input id="fromAddress" value={fromAddress} onChange={(e) => setFromAddress(e.target.value)} />
          </div>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={useTls} onChange={(e) => setUseTls(e.target.checked)} />
            Use TLS
          </label>
          {error && <p className="text-sm text-[var(--status-missing)]">{error}</p>}
          <Button disabled={saving} onClick={saveSmtp}>
            {saving ? "Saving…" : "Save SMTP settings"}
          </Button>

          <div className="border-t border-[var(--border)] pt-4">
            <Label htmlFor="testTo">Send a test email</Label>
            <div className="flex gap-2">
              <Input id="testTo" type="email" value={testTo} onChange={(e) => setTestTo(e.target.value)} placeholder="you@example.com" />
              <Button variant="outline" disabled={testing} onClick={sendTest}>
                {testing ? "Sending…" : "Send test"}
              </Button>
            </div>
            {testResult && (
              <p className={`mt-2 text-sm ${testResult.ok ? "text-[var(--status-done)]" : "text-[var(--status-missing)]"}`}>
                {testResult.ok ? "✓" : "✗"} {testResult.detail}
              </p>
            )}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Data export</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <p className="text-sm text-muted">
            Download every record for this Lab — Members and their platform associations, Semesters, Challenges,
            Progress, Reports, and automation history — as a single versioned JSON file. Encrypted credentials
            (Root Me API key, SMTP password) are never included.
          </p>
          <a
            href="/api/v1/export"
            onClick={() => pushToast("info", "Preparing export…")}
            className="inline-flex items-center gap-1.5 rounded-[9px] border border-[var(--border)] px-3.5 py-2 text-[13px] font-semibold hover:border-accent hover:text-accent"
          >
            <Download size={13} /> Export this Lab&apos;s data
          </a>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Professor email</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <p className="text-sm text-muted">
            Pre-fills the recipient when approving a report manually, and is also where automation sends a report
            directly when auto-send is turned on below.
          </p>
          <div className="flex gap-2">
            <Input
              type="email"
              value={professorEmail}
              onChange={(e) => setProfessorEmail(e.target.value)}
              placeholder="professor@university.edu"
            />
            <Button variant="outline" disabled={savingProfessor} onClick={saveProfessorEmail}>
              {savingProfessor ? "Saving…" : "Save"}
            </Button>
          </div>
        </CardContent>
      </Card>

      {automation && (
        <Card>
          <CardHeader>
            <CardTitle>Automation</CardTitle>
          </CardHeader>
          <CardContent className="space-y-6">
            <p className="text-sm text-muted">
              Each schedule runs on its own — turn one off without affecting the other. Semester report has its own
              trigger date instead, set per-Semester on the Semesters page.
            </p>

            <div className="space-y-2 border-b border-[var(--border)] pb-6">
              <Label className="mb-0 text-sm font-bold">Reminders (T-3 / T-1 emails to members)</Label>
              <RepeatScheduleEditor
                idPrefix="reminder"
                value={automation.reminder}
                onChange={(reminder) => setAutomation({ ...automation, reminder })}
              />
            </div>

            <div className="space-y-2">
              <Label className="mb-0 text-sm font-bold">Weekly report</Label>
              <RepeatScheduleEditor
                idPrefix="weekly-report"
                value={automation.weekly_report}
                onChange={(weekly_report) => setAutomation({ ...automation, weekly_report })}
              />
              <label className="flex items-center gap-2 pt-2 text-sm">
                <input
                  type="checkbox"
                  checked={automation.weekly_report_auto_send}
                  onChange={(e) => setAutomation({ ...automation, weekly_report_auto_send: e.target.checked })}
                />
                Auto-send to the professor email above (no review) instead of just notifying me to approve it
              </label>
            </div>

            <Button disabled={savingAutomation} onClick={saveAutomation}>
              {savingAutomation ? "Saving…" : "Save automation settings"}
            </Button>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
