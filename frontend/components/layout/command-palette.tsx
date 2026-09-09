"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { Search } from "lucide-react";
import type { MemberRole } from "@/lib/types";
import { visibleNavItems } from "./sidebar";

interface CommandPaletteProps {
  open: boolean;
  onClose: () => void;
  role: MemberRole;
}

export function CommandPalette({ open, onClose, role }: CommandPaletteProps) {
  const router = useRouter();
  const [query, setQuery] = useState("");

  // §6 — same role filter as the sidebar, so the palette never offers a
  // page this role can't actually use.
  const items = visibleNavItems(role);
  const results = useMemo(() => {
    const q = query.trim().toLowerCase();
    return q ? items.filter((item) => item.label.toLowerCase().includes(q)) : items;
  }, [query, items]);

  useEffect(() => {
    if (!open) return;
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [open, onClose]);

  if (!open) return null;

  function go(href: string) {
    router.push(href);
    setQuery("");
    onClose();
  }

  return (
    <div
      onClick={onClose}
      className="fixed inset-0 z-50 flex animate-fade-up items-start justify-center bg-black/50 pt-[14vh]"
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="w-[560px] max-w-[90vw] animate-scale-in overflow-hidden rounded-[14px] border border-[var(--border)] bg-surface shadow-[0_30px_80px_rgba(0,0,0,0.4)]"
      >
        <div className="flex items-center gap-2.5 border-b border-[var(--border)] px-4 py-3.5">
          <Search size={16} className="text-muted" />
          <input
            autoFocus
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Jump to a page…"
            className="flex-1 border-none bg-transparent text-[14.5px] outline-none"
          />
          <span className="rounded border border-[var(--border)] px-1 font-mono text-[10px] text-muted">ESC</span>
        </div>
        <div className="max-h-80 overflow-y-auto p-2">
          {results.map((item) => {
            const Icon = item.icon;
            return (
              <button
                key={item.href}
                onClick={() => go(item.href)}
                className="flex w-full items-center gap-3 rounded-[9px] px-3 py-2.5 text-left text-[13.5px] font-semibold hover:bg-[var(--surface-hover)]"
              >
                <Icon size={18} className="text-muted" />
                {item.label}
              </button>
            );
          })}
          {results.length === 0 && <p className="px-3 py-6 text-center text-sm text-muted">No matches.</p>}
        </div>
      </div>
    </div>
  );
}
