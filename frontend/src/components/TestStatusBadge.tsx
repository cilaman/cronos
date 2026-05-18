import type { TestCaseStatus } from "../types";

const STATUS_STYLE: Record<TestCaseStatus, { label: string; cls: string }> = {
  passed:  { label: "Passed",  cls: "text-accent-bright border-accent/30 bg-accent/10" },
  failed:  { label: "Failed",  cls: "text-danger border-danger/30 bg-danger/10" },
  error:   { label: "Error",   cls: "text-danger border-danger/30 bg-danger/10" },
  skipped: { label: "Skipped", cls: "text-ink-muted border-hairline bg-surface-2" },
};

interface Props {
  status: TestCaseStatus;
  size?: "sm" | "md";
}

export function TestStatusBadge({ status, size = "md" }: Props) {
  const style = STATUS_STYLE[status] ?? STATUS_STYLE.skipped;
  const sizeClass = size === "sm"
    ? "px-1.5 py-0.5 text-[9px]"
    : "px-2 py-0.5 text-[10px]";
  return (
    <span
      className={`inline-flex items-center rounded border font-display uppercase tracking-[0.14em] ${sizeClass} ${style.cls}`}
    >
      {style.label}
    </span>
  );
}
