import type { ProgressStatus } from "@/lib/types";

const STYLES: Record<ProgressStatus, string> = {
  early: "text-[var(--status-early)] bg-[var(--status-early-bg)]",
  done: "text-[var(--status-done)] bg-[var(--status-done-bg)]",
  late: "text-[var(--status-late)] bg-[var(--status-late-bg)]",
  missing: "text-[var(--status-missing)] bg-[var(--status-missing-bg)]",
};

const LABELS: Record<ProgressStatus, string> = {
  early: "Early",
  done: "Done",
  late: "Late",
  missing: "Missing",
};

export function StatusBadge({ status }: { status: ProgressStatus }) {
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-1 text-[11.5px] font-bold ${STYLES[status]}`}>
      {LABELS[status]}
    </span>
  );
}
