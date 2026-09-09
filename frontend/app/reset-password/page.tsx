"use client";

import { Suspense, useState, type FormEvent } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { api, ApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent } from "@/components/ui/card";
import { AuthShell, BrandMark } from "@/components/layout/auth-shell";

function ResetPasswordForm() {
  const router = useRouter();
  const token = useSearchParams().get("token") ?? "";
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [done, setDone] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await api.post("/api/v1/auth/reset-password", { token, new_password: password });
      setDone(true);
      setTimeout(() => router.replace("/login"), 2000);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Reset failed");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <AuthShell>
      <Card className="animate-scale-in p-9">
        <BrandMark />
        <p className="mb-6 text-sm text-muted">Choose a new password</p>
        <CardContent className="p-0">
          {!token ? (
            <p className="text-sm text-[var(--status-missing)]">
              This link is missing its reset token. Request a new one from{" "}
              <Link href="/forgot-password" className="underline">
                forgot password
              </Link>
              .
            </p>
          ) : done ? (
            <p className="text-sm text-[var(--status-done)]">Password reset — redirecting to sign in…</p>
          ) : (
            <form onSubmit={onSubmit} className="space-y-4">
              <div>
                <Label htmlFor="password">New password</Label>
                <Input
                  id="password"
                  type="password"
                  required
                  minLength={8}
                  autoFocus
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                />
              </div>
              {error && <p className="text-sm text-[var(--status-missing)]">{error}</p>}
              <Button type="submit" disabled={submitting} className="w-full">
                {submitting ? "Resetting…" : "Reset password"}
              </Button>
            </form>
          )}
        </CardContent>
      </Card>
    </AuthShell>
  );
}

export default function ResetPasswordPage() {
  return (
    <Suspense fallback={null}>
      <ResetPasswordForm />
    </Suspense>
  );
}
