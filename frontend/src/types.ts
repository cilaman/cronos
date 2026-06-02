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
  "waiting->done",
  "done->backlog",
  "done->archived",
  "waiting->archived",
  "archived->backlog",
  "archived->done",
]);

export function canUserTransition(from: TaskState, to: TaskState): boolean {
  if (from === to) return false;
  return USER_TRANSITIONS_SET.has(`${from}->${to}`);
}

export interface ChildProgressItem {
  id: string;
  title: string;
  state: TaskState;
  priority: number;
  updated_at: string;
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
  priority: number;
  manual_order: number;
  agent_mode: AgentMode;
  space_name: string | null;
  space_color: string | null;
  space_icon: string | null;
  space_autopilot?: string | null;
  type?: TaskType;
  parent_id?: string | null;
  parent_title?: string | null;
  depends_on?: string[];
  unmet_dependencies?: Array<{ id: string; title: string }>;
  pr_url?: string | null;
  proposed_pr_path?: string | null;
  children_progress?: { done: number; total: number; waiting: number; items?: ChildProgressItem[] } | null;
  is_running?: boolean;
}

export type AgentMode = "plan" | "auto" | "ask";

export type TaskType = "task" | "goal" | "issue";

export const AGENT_MODES: { value: AgentMode; label: string }[] = [
  { value: "plan", label: "Planning" },
  { value: "auto", label: "Auto" },
  { value: "ask", label: "Ask only" },
];

export type AgentModel = "default" | "sonnet" | "opus" | "haiku" | "opus-4-8";

export const AGENT_MODELS: { value: AgentModel; label: string }[] = [
  { value: "default", label: "Default" },
  { value: "sonnet", label: "Sonnet" },
  { value: "opus", label: "Opus" },
  { value: "haiku", label: "Haiku" },
  { value: "opus-4-8", label: "Opus 4.8" },
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
  priority: number;
  manual_order: number;
  space_name: string | null;
  space_color: string | null;
  space_icon: string | null;
  type?: TaskType;
  parent_id?: string | null;
  parent_title?: string | null;
  depends_on?: string[];
  unmet_dependencies?: Array<{ id: string; title: string }>;
  pr_url?: string | null;
  proposed_pr_path?: string | null;
}

export interface RoutedTo {
  id: string;
  title: string;
}

export interface ReplyResponse {
  task: Task;
  routed_to: RoutedTo | null;
}

export interface Board {
  backlog: TaskSummary[];
  active: TaskSummary[];
  waiting: TaskSummary[];
  done: TaskSummary[];
  archived: TaskSummary[];
}

// --- Views ---

export interface View {
  id: string;
  name: string;
  lanes: TaskState[];
  type_filter: TaskType[] | null;
  default: boolean;
  created_at: string;
  updated_at: string;
}

// --- Spaces ---

export interface SpaceSummary {
  id: string;
  name: string;
  color: string;
  icon: string | null;
  task_counts: Record<TaskState, number>;
  last_activity_at: string | null;
  autopilot?: AutopilotMode;
}

export interface SpacesResponse {
  spaces: SpaceSummary[];
  totals: Record<TaskState, number>;
}

export type AutopilotMode = "disabled" | "enabled" | "paused";

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
  autopilot: AutopilotMode;
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

// --- Stats ---

export interface RunStats {
  run_index: number;
  started_at: string;
  ended_at: string;
  duration_seconds: number;
  model: string;
  real_model: string | null;
  mode: string;
  exit_reason: "DONE" | "WAIT" | "BLOCKED" | "STOPPED" | "CRASHED";
  input_tokens: number;
  output_tokens: number;
  cache_read_tokens: number;
  cache_creation_tokens: number;
  cost_usd: number;
  tool_uses: Record<string, number>;
  error_count: number;
  had_crash: boolean;
}

export interface TaskStats {
  task_id: string;
  space_id: string;
  title: string;
  runs: RunStats[];
  total_runs: number;
  total_input_tokens: number;
  total_output_tokens: number;
  total_cache_tokens: number;
  total_cost_usd: number;
  total_duration_seconds: number;
  tool_use_summary: Record<string, number>;
  exit_reason_counts: Record<string, number>;
  avg_tokens_per_run: number;
  crash_rate: number;
}

export interface GlobalStats {
  total_tasks_with_stats: number;
  total_runs: number;
  total_input_tokens: number;
  total_output_tokens: number;
  total_cache_tokens: number;
  total_cost_usd: number;
  total_duration_seconds: number;
  tool_use_summary: Record<string, number>;
  exit_reason_counts: Record<string, number>;
  avg_tokens_per_run: number;
}

// --- Traces ---

export interface ToolCallTrace {
  tool_call_index: number;
  tool_use_id: string;
  name: string;
  input_summary: string;
  output_summary: string | null;
  is_error: boolean;
  turn_index: number;
  elapsed_seconds: number | null;
}

export interface AssistantTurnTrace {
  turn_index: number;
  text_snippet: string;
  has_thinking: boolean;
  tool_calls: string[];
  input_tokens: number;
  output_tokens: number;
  cache_read_tokens: number;
  cache_creation_tokens: number;
}

export interface RunTrace {
  task_id: string;
  space_id: string;
  run_index: number;
  session_id: string | null;
  model: string;
  real_model: string | null;
  mode: string;
  started_at: string;
  ended_at: string;
  duration_seconds: number;
  exit_reason: string;
  turns: AssistantTurnTrace[];
  tool_calls: ToolCallTrace[];
  total_tool_calls: number;
  unique_tools: string[];
  error_tool_calls: number;
  read_tool_calls: number;
  write_tool_calls: number;
  exploration_ratio: number;
  error_recovery_count: number;
  backtrack_count: number;
  final_text_snippet: string;
  had_crash: boolean;
  memory_injected?: string[] | null;
  memory_hit_rate?: number | null;
}

// --- AI Tools Inventory ---

export interface AiToolEntry {
  name: string;
  path: string;
  description: string | null;
  scope: "space" | "global";
  modified_at: string;
}

export interface HookEntry {
  event: string;
  matcher: string | null;
  command: string;
  scope: "space" | "global";
}

export interface PermissionEntry {
  pattern: string;
  allowed: boolean;
  scope: "space" | "global";
}

export interface SpaceToolsResponse {
  space_id: string;
  agents: AiToolEntry[];
  commands: AiToolEntry[];
  skills: AiToolEntry[];
  context_files: AiToolEntry[];
  hooks: HookEntry[];
  permissions: PermissionEntry[];
  has_claude_md: boolean;
}

export interface AiToolDetail extends AiToolEntry {
  category: "agent" | "command" | "skill" | "context";
  content: string;
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

// ---------------------------------------------------------------------------
// Test reports
// ---------------------------------------------------------------------------

export type TestCaseStatus = "passed" | "failed" | "error" | "skipped";

export interface TestCase {
  id: string;
  name: string;
  status: TestCaseStatus;
  duration_seconds?: number | null;
  error_message?: string | null;
  file_path?: string | null;
  line?: number | null;
}

export interface TestSuite {
  name: string;
  tests: TestCase[];
  passed: number;
  failed: number;
  errors: number;
  skipped: number;
  duration_seconds: number;
}

export interface TestReportSummary {
  id: string;
  space_id: string;
  task_id?: string | null;
  report_type: "task" | "space";
  triggered_by: string;
  started_at: string;
  ended_at: string;
  total_passed: number;
  total_failed: number;
  total_errors: number;
  total_skipped: number;
  total_tests: number;
  coverage_pct?: number | null;
  exit_code: number;
  framework: string;
}

export interface TestReport extends TestReportSummary {
  suites: TestSuite[];
  coverage_data?: Record<string, number> | null;
  raw_output: string;
}

// Build info
export interface BuildInfo {
  commit_sha: string | null;
  build_time: string | null;
  repo_url: string | null;
}

// Memory
export type MemoryKind = "fact" | "procedure" | "observation" | "reference";

export interface MemoryItem {
  id: string;
  scope: string;
  kind: MemoryKind;
  title: string;
  body: string;
  confirmed: boolean;
  confidence: number;
  score: number;
  last_used_at: string;
  ref_count: number;
  ttl_until: string | null;
  sources: string[];
  links: string[];
  created_at?: string;
  updated_at?: string;
}
