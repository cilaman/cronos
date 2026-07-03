// ---------------------------------------------------------------------------
// Generated schema aliases — single source of truth for backend-derived types.
// Run `npm run generate:types` to refresh from backend OpenAPI schema.
// Consume ALL backend types from this file; never import from ./generated directly.
// ---------------------------------------------------------------------------
import type { components } from './generated/api-types';

// ---------------------------------------------------------------------------
// Backend schema aliases — types whose shapes are fully compatible with
// the generated OpenAPI schema (no field optionality or union narrowing issues).
// ---------------------------------------------------------------------------

export type TaskState = components['schemas']['TaskState'];
export type FeatureState = components['schemas']['FeatureState'];
export type MemoryKind = components['schemas']['MemoryKind'];
export type NodeType = components['schemas']['NodeType'];
export type Position = components['schemas']['Position'];
export type NodeRef = components['schemas']['NodeRef'];
export type RoutedTo = components['schemas']['RoutedTo'];
export type Activity = components['schemas']['Activity'];
export type ToolCallTrace = components['schemas']['ToolCallTrace'];
export type AssistantTurnTrace = components['schemas']['AssistantTurnTrace'];
export type PluginComponent = components['schemas']['PluginComponent'];
export type PluginEntry = components['schemas']['PluginEntry'];
export type MarketplacePluginEntry = components['schemas']['MarketplacePluginEntry'];
export type MarketplaceEntry = components['schemas']['MarketplaceEntry'];
export type PluginsResponse = components['schemas']['PluginsResponse'];
export type AdoptionManifest = components['schemas']['AdoptionManifest'];
export type TestCase = components['schemas']['TestCase'];
export type TestSuite = components['schemas']['TestSuite'];
export type TestReportSummary = components['schemas']['TestReportSummary'];
export type TestReport = components['schemas']['TestReport'];

// Name-mapped aliases (backend schema name differs from legacy frontend name)
/** Alias for AdoptedToolEntry — shape is exact. */
export type AdoptedTool = components['schemas']['AdoptedToolEntry'];
/** FileEntry.category is `string` in the schema; consumers cast to FileCategory where needed. */
export type TaskFile = components['schemas']['FileEntry'];

// ---------------------------------------------------------------------------
// Non-derivable types: retained as hand-written because:
//   a) the backend schema makes fields optional that consumers depend on as required,
//   b) the type is UI-only (no backend schema equivalent),
//   c) the union is narrower than the backend string type for type-safety guards, or
//   d) the type is not exposed as an OpenAPI component schema.
// ---------------------------------------------------------------------------

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

// ---------------------------------------------------------------------------
// Feature / Fix state machine
// ---------------------------------------------------------------------------

/**
 * Lane metadata for the Features Kanban board.
 * INTENTIONALLY disjoint from LANES (TaskState lanes) — the arrays share no
 * element identity even though some string values are reused across systems.
 * Never insert FeatureState values into the LANES array or vice-versa.
 */
export const FEATURE_LANES: { state: FeatureState; label: string }[] = [
  { state: "backlog", label: "Backlog" },
  { state: "planned", label: "Planned" },
  { state: "processing", label: "Processing" },
  { state: "waiting", label: "Waiting" },
  { state: "done", label: "Done" },
];

// User-initiated feature transitions. Mirrors FEATURE_USER_TRANSITIONS in
// backend/app/feature_state.py (7 edges).
const FEATURE_USER_TRANSITIONS_SET = new Set<string>([
  "backlog->processing",
  "processing->backlog",
  "planned->processing",
  "waiting->processing",
  "waiting->planned",
  "planned->done",
  "done->backlog",
]);

/** Guard for legal user-initiated feature state transitions (drag-and-drop). */
export function canFeatureTransition(
  from: FeatureState,
  to: FeatureState
): boolean {
  if (from === to) return false;
  return FEATURE_USER_TRANSITIONS_SET.has(`${from}->${to}`);
}

/** Features/fixes grouped by FeatureState lane — mirrors backend FeatureBoard. */
export interface FeatureBoard {
  backlog: TaskSummary[];
  processing: TaskSummary[];
  planned: TaskSummary[];
  waiting: TaskSummary[];
  done: TaskSummary[];
}

/** Full feature/fix representation returned by GET /api/features/{id}. */
export interface FeatureRead {
  id: string;
  space_id: string;
  title: string;
  state: TaskState;
  created_at: string;
  updated_at: string;
  brief: string;
  priority: number;
  manual_order: number;
  type: TaskType;
  parent_id: string | null;
  depends_on: string[];
  pr_url: string | null;
  proposed_pr_path: string | null;
  feature_state: FeatureState | null;
  feature_key: string | null;
  realizes: string | null;
  issue_number: number | null;
  issue_url: string | null;
  proposed_issue_path: string | null;
  waiting_question: string | null;
  realizing_items: TaskSummary[];
}

export interface ChildProgressItem {
  id: string;
  title: string;
  state: TaskState;
  priority: number;
  updated_at: string;
  type?: TaskType;
  children_progress?: { done: number; total: number; waiting: number; items?: ChildProgressItem[] } | null;
}

// Non-derivable: unmet_dependencies shape diverges (backend list[str] vs frontend
// {id,title}[] for Card tooltip display); missing parent_title / realized_by fields.
export interface TaskSummary {
  id: string;
  space_id: string;
  title: string;
  state: TaskState;
  created_at: string;
  updated_at: string;
  waiting_question: string | null;
  waiting_kind?: "signoff" | "node_failed" | "stalled" | "escalated" | null;
  waiting_node_id?: string | null;
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
  // Feature/fix fields (optional — only present on type=feature|fix tasks)
  feature_state?: FeatureState | null;
  feature_key?: string | null;
  issue_number?: number | null;
  issue_url?: string | null;
  proposed_issue_path?: string | null;
  realizes?: string | null;
  realized_by?: string[];
  realizing_count?: number;
  realizes_feature_key?: string | null;
  realized_by_count?: number;
}

export type AgentMode = "plan" | "auto" | "ask";

export type TaskType = "task" | "goal" | "issue" | "feature" | "fix";

export const AGENT_MODES: { value: AgentMode; label: string }[] = [
  { value: "plan", label: "Planning" },
  { value: "auto", label: "Auto" },
  { value: "ask", label: "Ask only" },
];

export type AgentModel = "default" | "sonnet" | "opus" | "haiku" | "opus-4-8" | "fable-5";

export const AGENT_MODELS: { value: AgentModel; label: string }[] = [
  { value: "default", label: "Default" },
  { value: "sonnet", label: "Sonnet" },
  { value: "opus", label: "Opus" },
  { value: "haiku", label: "Haiku" },
  { value: "opus-4-8", label: "Opus 4.8" },
  { value: "fable-5", label: "Fable 5" },
];

// Non-derivable: missing parent_title / realized_by; unmet_dependencies shape diverges.
export interface Task {
  id: string;
  space_id: string;
  title: string;
  state: TaskState;
  created_at: string;
  updated_at: string;
  claude_session_id: string | null;
  waiting_question: string | null;
  // Structured wait metadata (§5.6): 'signoff' waits get Approve/Reject controls.
  waiting_kind?: "signoff" | "node_failed" | "stalled" | "escalated" | null;
  waiting_node_id?: string | null;
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
  // Feature/fix fields (optional — only present on type=feature|fix tasks)
  feature_state?: FeatureState | null;
  feature_key?: string | null;
  issue_number?: number | null;
  issue_url?: string | null;
  realizes?: string | null;
  realized_by?: string[];
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

// Non-derivable: type_filter is required here; backend schema makes it optional.
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

// Non-derivable: not in backend schema as a standalone enum type.
export type AutopilotMode = "disabled" | "enabled" | "paused";

// Non-derivable: task_counts is required and uses TaskState keys.
export interface SpaceSummary {
  id: string;
  name: string;
  color: string;
  icon: string | null;
  task_counts: Record<TaskState, number>;
  last_activity_at: string | null;
  autopilot?: AutopilotMode;
}

// Non-derivable: totals is required; uses typed Record<TaskState/FeatureState> keys.
export interface SpacesResponse {
  spaces: SpaceSummary[];
  totals: Record<TaskState, number>;
  feature_totals?: Record<FeatureState, number>;
}

// Non-derivable: agent_defaults required; autopilot narrower union.
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

// --- Stats ---

// Non-derivable: runs/tool_uses/exit_reason_counts required (backend makes them optional).
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

// Non-derivable: runs is required; consumers access .runs without optional chaining.
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

// Non-derivable: tool_use_summary/exit_reason_counts required; consumers don't guard.
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

// Non-derivable: turns/tool_calls/unique_tools required; TracePanel.tsx accesses
// these without optional chaining.
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

// Non-derivable: scope "space"|"global"|"plugin" is narrower than backend string.
export interface AiToolEntry {
  name: string;
  path: string;
  description: string | null;
  scope: "space" | "global" | "plugin";
  modified_at: string;
}

export interface AiToolDetail extends AiToolEntry {
  category: "agent" | "command" | "skill" | "context";
  content: string;
}

export interface ToolTelemetryResponse {
  kind: string;
  name: string;
  calls: number;
  errors: number;
  avg_success_rate: number;
  human_rescue_count: number;
}

// --- Plugin Management ---
// (PluginComponent, PluginEntry, MarketplacePluginEntry, MarketplaceEntry,
//  PluginsResponse, AdoptedTool aliased from generated above)

// Non-derivable: scope narrower union for ScopeBadge type safety.
export interface HookEntry {
  event: string;
  matcher: string | null;
  command: string;
  scope: "space" | "global";
}

// Non-derivable: scope narrower union.
export interface PermissionEntry {
  pattern: string;
  allowed: boolean;
  scope: "space" | "global";
}

export type AdoptedToolStatus = "pristine" | "edited" | "evolved";

// Non-derivable: AiToolEntry.scope is narrower than generated string type.
export interface SpaceToolsResponse {
  space_id: string;
  agents: AiToolEntry[];
  commands: AiToolEntry[];
  skills: AiToolEntry[];
  context_files: AiToolEntry[];
  hooks: HookEntry[];
  permissions: PermissionEntry[];
  has_claude_md: boolean;
  adopted: AdoptedTool[];
}

// Non-derivable: sources/links are required; created_at/updated_at not in backend schema.
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

// --- Discovery ---

// Non-derivable: not exposed as an OpenAPI component schema.
export interface DiscoveredTool {
  source_url: string;
  source_slug: string;
  kind: "agent" | "skill" | "command" | "hook";
  name: string;
  relative_path: string;
  description: string | null;
  source_sha: string;
}

// Non-derivable: not exposed as an OpenAPI component schema.
export interface ToolSource {
  url: string;
  branch: string | null;
  enabled: boolean;
  label: string | null;
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
// (TestCase, TestSuite, TestReportSummary, TestReport aliased above)
// ---------------------------------------------------------------------------

// Non-derivable: not a top-level schema (inline within TestCase.status field).
export type TestCaseStatus = "passed" | "failed" | "error" | "skipped";

// Build info — not in backend OpenAPI schema.
export interface BuildInfo {
  commit_sha: string | null;
  build_time: string | null;
  repo_url: string | null;
}

// --- Harness visual editor ---
// NodeType, Position, NodeRef aliased from generated above.

/** @deprecated Only kept for historical test fixtures; HarnessNode.ports is now a dict. */
export interface NodePort {
  id: string;
  label: string;
  port_type: 'input' | 'output';
}

// Non-derivable: ports/data are required (generated makes them optional); consumers
// access these fields without optional chaining.
export interface HarnessNode {
  id: string;
  type: NodeType;
  label: string;
  position: Position;
  /** Port dict keyed by port-id — mirrors backend HarnessNode.ports: dict[str, dict]. */
  ports: Record<string, Record<string, unknown>>;
  /** Arbitrary node-specific configuration — mirrors backend HarnessNode.data. */
  data: Record<string, unknown>;
}

// Non-derivable: label field present in frontend for display but absent from backend schema.
export interface HarnessEdge {
  id: string;
  source: NodeRef;
  target: NodeRef;
  /** Optional guard expression evaluated by the executor; null = unconditional. */
  condition?: string | null;
  label?: string;
}

// Non-derivable: nodes/edges/variables are required with stricter value types.
export interface Harness {
  name: string;
  description?: string;
  nodes: HarnessNode[];
  edges: HarnessEdge[];
  variables: Record<string, string>;
  created_at?: string;
  updated_at?: string;
  version?: string | number;
}
