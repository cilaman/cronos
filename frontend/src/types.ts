export type TaskState = "backlog" | "active" | "waiting" | "done" | "archived";

export const LANES: { state: TaskState; label: string }[] = [
  { state: "backlog", label: "To Do" },
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
  "done->archived",
  "waiting->archived",
  "archived->backlog",
]);

export function canUserTransition(from: TaskState, to: TaskState): boolean {
  if (from === to) return false;
  return USER_TRANSITIONS_SET.has(`${from}->${to}`);
}

export interface TaskSummary {
  id: string;
  space_id: string;
  title: string;
  state: TaskState;
  created_at: string;
  updated_at: string;
  waiting_question: string | null;
  brief_preview: string;
  space_name: string | null;
  space_color: string | null;
  space_icon: string | null;
}

export type AgentMode = "plan" | "auto" | "ask";

export const AGENT_MODES: { value: AgentMode; label: string }[] = [
  { value: "plan", label: "Planning" },
  { value: "auto", label: "Auto" },
  { value: "ask", label: "Ask only" },
];

export type AgentModel = "default" | "sonnet" | "opus" | "haiku";

export const AGENT_MODELS: { value: AgentModel; label: string }[] = [
  { value: "default", label: "Default" },
  { value: "sonnet", label: "Sonnet" },
  { value: "opus", label: "Opus" },
  { value: "haiku", label: "Haiku" },
];

export interface Task {
  id: string;
  space_id: string;
  title: string;
  state: TaskState;
  created_at: string;
  updated_at: string;
  claude_session_id: string | null;
  waiting_question: string | null;
  brief: string;
  history: string;
  pending_messages: string[];
  agent_mode: AgentMode;
  agent_model: AgentModel;
  space_name: string | null;
  space_color: string | null;
  space_icon: string | null;
}

export interface Board {
  backlog: TaskSummary[];
  active: TaskSummary[];
  waiting: TaskSummary[];
  done: TaskSummary[];
  archived: TaskSummary[];
}

// --- Spaces ---

export interface SpaceSummary {
  id: string;
  name: string;
  color: string;
  icon: string | null;
  task_counts: Record<TaskState, number>;
  last_activity_at: string | null;
}

export interface SpacesResponse {
  spaces: SpaceSummary[];
  totals: Record<TaskState, number>;
}

export interface Space {
  id: string;
  name: string;
  color: string;
  icon: string | null;
  description: string;
  created_at: string;
  updated_at: string;
  git_repo_url: string | null;
  git_branch: string | null;
  git_share_cronos: boolean;
  agent_defaults: Record<string, string>;
}

export type FileCategory =
  | "agent" | "skill" | "command" | "context"
  | "image" | "text" | "code"
  | "document" | "archive" | "binary" | "directory";

export interface TaskFile {
  name: string;
  path: string;
  size: number;
  modified_at: string;
  is_dir: boolean;
  category: FileCategory;
}

export interface Activity {
  task_id: string;
  space_id: string;
  title: string;
  state: TaskState;
  updated_at: string;
}

export interface PresetColor {
  name: string;
  value: string;
}

// Validated against `--color-surface-1` and `--color-surface-2` in both
// light and dark themes. Avoid pure red (reserved for `--color-danger`).
export const PRESET_SPACE_COLORS: PresetColor[] = [
  { name: "Emerald", value: "#15803D" },
  { name: "Teal", value: "#0F766E" },
  { name: "Sky", value: "#0369A1" },
  { name: "Indigo", value: "#4338CA" },
  { name: "Violet", value: "#7C3AED" },
  { name: "Magenta", value: "#BE185D" },
  { name: "Amber", value: "#B45309" },
  { name: "Slate", value: "#475569" },
];

// Curated emoji set so the sidebar stays visually uniform.
export const PRESET_SPACE_ICONS: string[] = [
  "📦", "🧪", "🛰️", "🪐", "⚙️", "🎯", "🧭", "🛠️",
  "🧱", "📚", "🔬", "🪄", "🌿", "🔌", "🪧", "🧰",
];
