import type { TaskState } from "./types";

export const STATE_BADGE: Record<TaskState, string> = {
  backlog: "bg-slate-200 text-slate-800",
  active: "bg-emerald-200 text-emerald-900",
  waiting: "bg-amber-200 text-amber-900",
  done: "bg-blue-200 text-blue-900",
};
