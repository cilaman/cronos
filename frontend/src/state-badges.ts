import type { TaskState } from "./types";

// Re-toned for the operator-console `canvas`. Each semantic badge uses:
//   - surface: bright `-400` at 10% opacity — visible but understated
//   - text:    `-300` shade — AAA on the dim fill
//   - ring:    `-400` at 40% — saturated outline so the badge reads at a glance
// Backlog is the "untouched" state — it uses neutral surface/ink tokens so it
// recedes against the three semantic states.
export const STATE_BADGE: Record<TaskState, string> = {
  backlog: "bg-surface-2 text-ink-muted ring-1 ring-hairline",
  active: "bg-emerald-400/10 text-emerald-300 ring-1 ring-emerald-400/40",
  waiting: "bg-amber-400/10 text-amber-300 ring-1 ring-amber-400/40",
  done: "bg-sky-400/10 text-sky-300 ring-1 ring-sky-400/40",
};
