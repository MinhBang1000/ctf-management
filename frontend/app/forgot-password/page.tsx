"use client";

import { useState, type FormEvent } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent } from "@/components/ui/card";
import { AuthShell, BrandMark } from "@/components/layout/auth-shell";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [done, setDone] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    try {
      // §2 — always the same response regardless of whether the email
      // exists (see password_reset_service.request_password_reset).
      await api.post("/api/v1/auth/forgot-password", { email });
    } finally {
      setSubmitting(false);
      setDone(true);
    }
  }

  return (
    <AuthShell>
      <Card className="animate-scale-in p-9">
        <BrandMark />
        <p className="mb-6 text-sm text-muted">Reset your password</p>
        <CardContent className="p-0">
          {done ? (
            <p className="text-sm text-foreground">
              If that email exists, a password reset link has been sent — check your inbox (and spam folder). The
              link expires in 30 minutes.
            </p>
          ) : (
            <form onSubmit={onSubmit} className="space-y-4">
              <div>
                <Label htmlFor="email">Email</Label>
                <Input id="email" type="email" required autoFocus value={email} onChange={(e) => setEmail(e.target.value)} />
              </div>
              <Button type="submit" disabled={submitting} className="w-full">
                {submitting ? "Sending…" : "Send reset link"}
              </Button>
            </form>
          )}
          <p className="mt-4 text-center text-xs text-muted">
            <Link href="/login" className="underline">
              Back to sign in
            </Link>
          </p>
        </CardContent>
      </Card>
    </AuthShell>
  );
}
