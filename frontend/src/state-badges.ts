import type { TaskState } from "./types";

// Re-toned for the dark `pitch` canvas. Each badge:
//   - surface: deep (-950) at 60% opacity so the pitch shows through
//   - text:    light shade (-300) for AA contrast on a dark fill
//   - ring:    one-step-darker border (-800) at 50% for definition without harshness
// Backlog is the "untouched" state — it uses neutral pitch/bone tokens so it
// recedes against the three semantic states.
export const STATE_BADGE: Record<TaskState, string> = {
  backlog: "bg-pitch-100 text-bone-muted ring-1 ring-hairline",
  active: "bg-emerald-950/60 text-emerald-300 ring-1 ring-emerald-800/50",
  waiting: "bg-amber-950/60 text-amber-300 ring-1 ring-amber-800/50",
  done: "bg-sky-950/60 text-sky-300 ring-1 ring-sky-800/50",
};
