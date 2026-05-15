export type TaskState = "backlog" | "active" | "waiting" | "done";

export const LANES: { state: TaskState; label: string }[] = [
  { state: "backlog", label: "Backlog" },
  { state: "active", label: "Active" },
  { state: "waiting", label: "Waiting" },
  { state: "done", label: "Done" },
];

// User-initiated transitions allowed via drag-and-drop. Mirrors
// USER_TRANSITIONS on the backend (storage.py).
const USER_TRANSITIONS_SET = new Set<string>([
  "backlog->active",
  "active->backlog",
  "waiting->backlog",
  "done->backlog",
]);

export function canUserTransition(from: TaskState, to: TaskState): boolean {
  if (from === to) return false;
  return USER_TRANSITIONS_SET.has(`${from}->${to}`);
}

export interface TaskSummary {
  id: string;
  title: string;
  state: TaskState;
  created_at: string;
  updated_at: string;
  waiting_question: string | null;
  brief_preview: string;
}

export interface Task {
  id: string;
  title: string;
  state: TaskState;
  created_at: string;
  updated_at: string;
  claude_session_id: string | null;
  waiting_question: string | null;
  brief: string;
  history: string;
}

export interface Board {
  backlog: TaskSummary[];
  active: TaskSummary[];
  waiting: TaskSummary[];
  done: TaskSummary[];
}
