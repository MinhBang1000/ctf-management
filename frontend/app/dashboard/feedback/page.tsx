"use client";

import { useState, type FormEvent } from "react";
import { api, ApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useToast } from "@/lib/toast-context";

export default function FeedbackPage() {
  const { push: pushToast } = useToast();
  const [message, setMessage] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await api.post("/api/v1/feedback", { message });
      setMessage("");
      pushToast("success", "Thanks — your feedback was sent");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to send feedback");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="max-w-2xl space-y-6">
      <div>
        <h1 className="text-xl font-semibold">Feedback</h1>
        <p className="text-sm text-muted">
          Tell us what&apos;s missing, confusing, or broken about this platform — every role can send feedback, and
          it goes straight to the team running HSLab CTF Classroom, not to your Lab Leader.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Send feedback</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={onSubmit} className="space-y-4">
            <div>
              <Label htmlFor="message">What should we improve?</Label>
              <textarea
                id="message"
                required
                minLength={1}
                maxLength={4000}
                rows={6}
                placeholder="e.g. the Sync button is confusing, I wish Progress showed..."
                className="w-full rounded-md border border-[var(--border)] bg-[var(--surface)] p-3 text-sm"
                value={message}
                onChange={(e) => setMessage(e.target.value)}
              />
            </div>
            {error && <p className="text-sm text-[var(--status-missing)]">{error}</p>}
            <Button type="submit" disabled={submitting || !message.trim()}>
              {submitting ? "Sending…" : "Send feedback"}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
