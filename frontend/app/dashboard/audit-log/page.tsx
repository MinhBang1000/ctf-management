"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { AuditLogEntry } from "@/lib/types";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

const PAGE_SIZE = 50;

export default function AuditLogPage() {
  const [entries, setEntries] = useState<AuditLogEntry[]>([]);
  const [actionFilter, setActionFilter] = useState("");
  const [targetTypeFilter, setTargetTypeFilter] = useState("");
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(false);

  async function load(nextOffset: number) {
    setLoading(true);
    try {
      const params = new URLSearchParams({ limit: String(PAGE_SIZE), offset: String(nextOffset) });
      if (actionFilter.trim()) params.set("action", actionFilter.trim());
      if (targetTypeFilter.trim()) params.set("target_type", targetTypeFilter.trim());
      const rows = await api.get<AuditLogEntry[]>(`/api/v1/audit-log?${params.toString()}`);
      setEntries(rows);
      setOffset(nextOffset);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load(0);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold">Audit Log</h1>
        <p className="text-sm text-muted">A record of significant actions taken within this Lab.</p>
      </div>

      <Card>
        <CardContent className="flex flex-wrap items-end gap-3 py-4">
          <div>
            <Label htmlFor="actionFilter">Action contains</Label>
            <Input
              id="actionFilter"
              placeholder="e.g. member.updated"
              value={actionFilter}
              onChange={(e) => setActionFilter(e.target.value)}
            />
          </div>
          <div>
            <Label htmlFor="targetTypeFilter">Target type</Label>
            <Input
              id="targetTypeFilter"
              placeholder="e.g. member"
              value={targetTypeFilter}
              onChange={(e) => setTargetTypeFilter(e.target.value)}
            />
          </div>
          <Button variant="outline" onClick={() => load(0)}>
            Filter
          </Button>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="overflow-x-auto p-0">
          <table className="hs-table">
            <thead>
              <tr>
                <th>When</th>
                <th>Actor</th>
                <th>Action</th>
                <th>Target</th>
                <th>Summary</th>
              </tr>
            </thead>
            <tbody>
              {entries.map((e) => (
                <tr key={e.id}>
                  <td className="whitespace-nowrap font-data text-muted">{new Date(e.created_at).toLocaleString()}</td>
                  <td className="whitespace-nowrap">
                    <Badge className="mr-1.5 capitalize">{e.actor_type.replace("_", " ")}</Badge>
                    {e.actor_label}
                  </td>
                  <td className="font-data text-xs">{e.action}</td>
                  <td className="text-muted">{e.target_type ?? "—"}</td>
                  <td>{e.summary}</td>
                </tr>
              ))}
              {entries.length === 0 && (
                <tr>
                  <td colSpan={5} className="py-6 text-center text-muted">
                    {loading ? "Loading…" : "No audit log entries."}
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
  );
}
