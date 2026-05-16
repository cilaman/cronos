import type { TaskState } from "./types";

// Light theme: solid `-100` fill, dark `-800` text, mid `-300` ring — crisp on
// a bone canvas.
// Dark theme: bright `-400` at 10% opacity, `-300` text, `-400/40` ring — sits
// on the canvas without washing out.
// Backlog is the "untouched" state — neutral surface/ink tokens recede against
// the three semantic states in both modes.
export const STATE_BADGE: Record<TaskState, string> = {
  backlog: "bg-surface-2 text-ink-muted ring-1 ring-hairline",
  active:
    "bg-emerald-100 text-emerald-800 ring-1 ring-emerald-300 dark:bg-emerald-400/10 dark:text-emerald-300 dark:ring-emerald-400/40",
  waiting:
    "bg-amber-100 text-amber-800 ring-1 ring-amber-300 dark:bg-amber-400/10 dark:text-amber-300 dark:ring-amber-400/40",
  done:
    "bg-sky-100 text-sky-800 ring-1 ring-sky-300 dark:bg-sky-400/10 dark:text-sky-300 dark:ring-sky-400/40",
};
