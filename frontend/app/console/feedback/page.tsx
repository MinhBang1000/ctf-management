"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { api, ApiError } from "@/lib/api";
import type { PlatformFeedbackEntry, SuperAdminMe } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Topbar } from "@/components/layout/topbar";

const PAGE_SIZE = 50;

export default function ConsoleFeedbackPage() {
  const router = useRouter();
  const [me, setMe] = useState<SuperAdminMe | null>(null);
  const [entries, setEntries] = useState<PlatformFeedbackEntry[]>([]);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(false);

  async function load(nextOffset: number) {
    setLoading(true);
    try {
      const rows = await api.get<PlatformFeedbackEntry[]>(
        `/admin/feedback?limit=${PAGE_SIZE}&offset=${nextOffset}`
      );
      setEntries(rows);
      setOffset(nextOffset);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    (async () => {
      try {
        const m = await api.get<SuperAdminMe>("/admin/auth/me");
        setMe(m);
        await load(0);
      } catch (err) {
        if (err instanceof ApiError && (err.status === 401 || err.status === 403)) {
          router.replace("/console/login");
          return;
        }
        throw err;
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function logout() {
    await api.post("/admin/auth/logout");
    router.replace("/console/login");
  }

  if (!me) return null;

  return (
    <div className="flex min-h-screen flex-col">
      <Topbar
        title="Platform Feedback"
        badge="SYSTEM SCOPE"
        rightExtra={
          <div className="flex items-center gap-2">
            <Link href="/console" className="text-sm font-semibold text-muted hover:text-foreground">
              ← Labs
            </Link>
            <Button variant="outline" onClick={logout}>
              Sign out
            </Button>
          </div>
        }
      />
      <main className="flex-1 px-4 pb-16 pt-5 sm:px-8 sm:pt-7">
        <div className="mx-auto max-w-4xl animate-fade-up space-y-6">
          <p className="text-sm text-muted">
            Free-text feedback from every role, across every Lab — sent from the Feedback link in each Lab&apos;s
            sidebar.
          </p>

          <Card>
            <CardContent className="overflow-x-auto p-0">
              <table className="hs-table">
                <thead>
                  <tr>
                    <th>When</th>
                    <th>Lab</th>
                    <th>From</th>
                    <th>Message</th>
                  </tr>
                </thead>
                <tbody>
                  {entries.map((e) => (
                    <tr key={e.id}>
                      <td className="whitespace-nowrap font-data text-muted">{new Date(e.created_at).toLocaleString()}</td>
                      <td className="whitespace-nowrap">{e.tenant_name}</td>
                      <td className="whitespace-nowrap">
                        <Badge className="mr-1.5 capitalize">{e.member_role.replace("_", " ")}</Badge>
                        {e.member_email}
                      </td>
                      <td className="whitespace-pre-wrap">{e.message}</td>
                    </tr>
                  ))}
                  {entries.length === 0 && (
                    <tr>
                      <td colSpan={4} className="py-6 text-center text-muted">
                        {loading ? "Loading…" : "No feedback yet."}
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </CardContent>
          </Card>

          <div className="flex justify-between">
            <Button variant="outline" disabled={offset === 0 || loading} onClick={() => load(Math.max(0, offset - PAGE_SIZE))}>
              Newer
            </Button>
            <Button variant="outline" disabled={entries.length < PAGE_SIZE || loading} onClick={() => load(offset + PAGE_SIZE)}>
              Older
            </Button>
          </div>
        </div>
      </main>
    </div>
  );
}
