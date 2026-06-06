import type {
  Activity,
  AdoptionManifest,
  AgentMode,
  AgentModel,
  AiToolDetail,
  Board,
  BuildInfo,
  DiscoveredTool,
  FeatureBoard,
  FeatureState,
  GlobalStats,
  Harness,
  MemoryItem,
  ReplyResponse,
  RunTrace,
  Space,
  SpacesResponse,
  SpaceToolsResponse,
  Task,
  ToolTelemetryResponse,
  TaskFile,
  TaskState,
  TaskStats,
  TaskSummary,
  TestReport,
  TestReportSummary,
  ToolSource,
  View,
} from "./types";

// --- harness run types ---

export interface RunSummary {
  run_id: string;
  harness_id: string;
  status: "running" | "done" | "failed" | "cancelled";
  triggered_at: string; // ISO-8601
  finished_at: string | null;
}

export interface NodeState {
  status: "pending" | "in_progress" | "done" | "failed" | "skipped";
  child_task_id: string | null;
  output: string | null;
  reason: string | null;
  started_at: string | null;
  ended_at: string | null;
}

export interface HarnessRunState {
  run_id: string;
  harness_id: string;
  goal_task_id: string;
  status: "running" | "done" | "failed" | "cancelled";
  nodes_executed: Record<string, NodeState>;
  waiting_node_id: string | null;
}

export interface TriggerRunResponse {
  run_id: string;
  harness_id: string;
  triggered_at: string;
}

// --- end harness run types ---

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    headers:
      init?.body instanceof FormData
        ? init?.headers
        : { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    ...init,
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`${res.status} ${res.statusText} on ${path}: ${text}`);
  }
  if (res.status === 204) return undefined as T;
  const ctype = res.headers.get("content-type") ?? "";
  if (!ctype.includes("application/json")) return undefined as T;
  return res.json() as Promise<T>;
}

function withSpaceQuery(path: string, spaceId: string | null): string {
  if (!spaceId) return path;
  const sep = path.includes("?") ? "&" : "?";
  return `${path}${sep}space_id=${encodeURIComponent(spaceId)}`;
}

function withViewQuery(path: string, viewId: string | null): string {
  if (!viewId) return path;
  const sep = path.includes("?") ? "&" : "?";
  return `${path}${sep}view=${encodeURIComponent(viewId)}`;
}

export function taskFileUrl(taskId: string, filePath: string, download = false): string {
  const encoded = filePath.split("/").map(encodeURIComponent).join("/");
  return `/api/tasks/${taskId}/files/${encoded}${download ? "?download=true" : ""}`;
}

// Future mirror for space-level file manager:
// export function spaceFileUrl(spaceId: string, filePath: string, download = false): string { ... }

export function harnessRunStreamUrl(runId: string): string {
  return `/api/harness-runs/${encodeURIComponent(runId)}/stream`;
}

export const api = {
  board: (spaceId: string | null = null, viewId: string | null = null) =>
    request<Board>(
      // Only send ?view= when scoped to a specific space
      spaceId ? withViewQuery(withSpaceQuery("/api/tasks", spaceId), viewId) : "/api/tasks",
    ),
  archived: (spaceId: string | null = null) =>
    request<TaskSummary[]>(withSpaceQuery("/api/tasks/archived", spaceId)),
  task: (id: string) => request<Task>(`/api/tasks/${id}`),
  create: (body: {
    space_id: string;
    title: string;
    brief: string;
    agent_model?: AgentModel;
    agent_mode?: AgentMode;
    priority?: number;
  }) => request<Task>("/api/tasks", { method: "POST", body: JSON.stringify(body) }),
  update: (
    id: string,
    body: {
      title?: string;
      brief?: string;
      agent_mode?: AgentMode;
      agent_model?: AgentModel;
      priority?: number;
    },
  ) =>
    request<Task>(`/api/tasks/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
  reorder: (lane: TaskState, task_ids: string[]) =>
    request<void>("/api/tasks/reorder", {
      method: "PUT",
      body: JSON.stringify({ lane, task_ids }),
    }),
  transition: (id: string, state: TaskState) =>
    request<Task>(`/api/tasks/${id}/state`, {
      method: "PATCH",
      body: JSON.stringify({ state }),
    }),
  delete: (id: string) => request<void>(`/api/tasks/${id}`, { method: "DELETE" }),
  start: (id: string) =>
    request<Task>(`/api/tasks/${id}/start`, { method: "POST", body: "{}" }),
  reply: (id: string, message: string) =>
    request<ReplyResponse>(`/api/tasks/${id}/reply`, {
      method: "POST",
      body: JSON.stringify({ message }),
    }),
  routePreview: (id: string) =>
    request<ReplyResponse>(`/api/tasks/${id}/route-preview`),
  stop: (id: string) =>
    request<Task>(`/api/tasks/${id}/stop`, { method: "POST", body: "{}" }),
  promote: (id: string) =>
    request<Task>(`/api/tasks/${id}/promote`, { method: "POST", body: "{}" }),
  setParent: (id: string, parent_id: string | null) =>
    request<Task>(`/api/tasks/${id}/parent`, {
      method: "PATCH",
      body: JSON.stringify({ parent_id }),
    }),
  setDependsOn: (id: string, depends_on: string[]) =>
    request<Task>(`/api/tasks/${id}/depends_on`, {
      method: "PATCH",
      body: JSON.stringify({ depends_on }),
    }),

  // --- spaces ---
  spaces: () => request<SpacesResponse>("/api/spaces"),
  space: (id: string) => request<Space>(`/api/spaces/${id}`),
  createSpace: (body: {
    name: string;
    color: string;
    icon?: string | null;
    description?: string;
    space_id?: string;
    repo_url?: string | null;
    branch?: string | null;
    share_cronos?: boolean;
  }) => request<Space>("/api/spaces", { method: "POST", body: JSON.stringify(body) }),
  updateSpace: (
    id: string,
    body: {
      name?: string;
      color?: string;
      icon?: string | null;
      clear_icon?: boolean;
      description?: string;
      autopilot?: "disabled" | "enabled" | "paused";
    },
  ) =>
    request<Space>(`/api/spaces/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
  linkSpaceRepo: (
    id: string,
    body: { repo_url: string; branch: string; share_cronos: boolean },
  ) =>
    request<Space>(`/api/spaces/${id}/link`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  unlinkSpaceRepo: (id: string) =>
    request<Space>(`/api/spaces/${id}/unlink`, { method: "POST", body: "{}" }),
  deleteSpace: (id: string, cascade = false) =>
    request<void>(`/api/spaces/${id}${cascade ? "?cascade=true" : ""}`, {
      method: "DELETE",
    }),
  exportSpace: (id: string) => {
    // Trigger browser download — no fetch wrapper.
    window.location.assign(`/api/spaces/${id}/export`);
  },
  importSpace: async (file: File, renameTo?: string): Promise<Space> => {
    const fd = new FormData();
    fd.append("file", file);
    const url = renameTo
      ? `/api/spaces/import?rename_to=${encodeURIComponent(renameTo)}`
      : "/api/spaces/import";
    return request<Space>(url, { method: "POST", body: fd });
  },

  // --- views ---
  spaceViews: (spaceId: string) => request<View[]>(`/api/spaces/${spaceId}/views`),
  createView: (
    spaceId: string,
    body: { name: string; lanes: string[]; type_filter?: string[] | null; default?: boolean },
  ) => request<View>(`/api/spaces/${spaceId}/views`, { method: "POST", body: JSON.stringify(body) }),
  updateView: (
    spaceId: string,
    viewId: string,
    body: { name?: string; lanes?: string[]; type_filter?: string[] | null; default?: boolean },
  ) =>
    request<View>(`/api/spaces/${spaceId}/views/${viewId}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
  deleteView: (spaceId: string, viewId: string) =>
    request<void>(`/api/spaces/${spaceId}/views/${viewId}`, { method: "DELETE" }),

  // --- task files ---
  taskFiles: (taskId: string) =>
    request<TaskFile[]>(`/api/tasks/${taskId}/files`),

  uploadTaskFile: (taskId: string, file: File, subdir = "") => {
    const fd = new FormData();
    fd.append("file", file);
    const url = subdir
      ? `/api/tasks/${taskId}/files?subdir=${encodeURIComponent(subdir)}`
      : `/api/tasks/${taskId}/files`;
    return request<TaskFile>(url, { method: "POST", body: fd });
  },

  saveTaskFile: (taskId: string, filePath: string, content: string) => {
    const encoded = filePath.split("/").map(encodeURIComponent).join("/");
    return request<TaskFile>(`/api/tasks/${taskId}/files/${encoded}`, {
      method: "PUT",
      body: JSON.stringify({ content }),
    });
  },

  // --- ai tools ---
  spaceTools: (spaceId: string) =>
    request<SpaceToolsResponse>(`/api/spaces/${spaceId}/tools`),
  toolContent: (spaceId: string, path: string, scope: string) =>
    request<AiToolDetail>(`/api/spaces/${spaceId}/tool-content?path=${encodeURIComponent(path)}&scope=${scope}`),

  // --- adoption ---
  adoptTool: (
    spaceId: string,
    body: { source_slug: string; kind: string; name: string },
  ) =>
    request<AdoptionManifest>(`/api/spaces/${spaceId}/adopt`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  unadoptTool: (spaceId: string, kind: string, name: string) =>
    request<void>(`/api/spaces/${spaceId}/adopt/${kind}/${name}`, {
      method: "DELETE",
    }),
  toolTelemetry: (spaceId: string, kind: string, name: string, window?: string) => {
    const qs = window ? `?window=${encodeURIComponent(window)}` : "";
    return request<ToolTelemetryResponse>(`/api/spaces/${spaceId}/tools/${kind}/${name}/telemetry${qs}`);
  },

  // --- discovery ---
  discoverySources: () => request<ToolSource[]>("/api/discovery/sources"),
  discoveryTools: (kind?: string, sourceSlug?: string) => {
    const params = new URLSearchParams();
    if (kind) params.set("kind", kind);
    if (sourceSlug) params.set("source_slug", sourceSlug);
    const qs = params.toString();
    return request<DiscoveredTool[]>(`/api/discovery/tools${qs ? `?${qs}` : ""}`);
  },
  discoveryRefresh: () =>
    request<{ refreshed: number; items: DiscoveredTool[] }>("/api/discovery/refresh", {
      method: "POST",
    }),

  // --- activity ---
  activity: (limit = 50, spaceId: string | null = null) => {
    const params = new URLSearchParams({ limit: String(limit) });
    if (spaceId) params.set("space_id", spaceId);
    return request<Activity[]>(`/api/activity?${params.toString()}`);
  },

  // --- stats ---
  taskStats: (taskId: string) =>
    request<TaskStats>(`/api/tasks/${taskId}/stats`),
  spaceStats: (spaceId: string, fromDt?: string, toDt?: string) => {
    const p = new URLSearchParams();
    if (fromDt) p.set("from_dt", fromDt);
    if (toDt) p.set("to_dt", toDt);
    const qs = p.toString();
    return request<TaskStats[]>(`/api/spaces/${spaceId}/stats${qs ? `?${qs}` : ""}`);
  },
  globalStats: (fromDt?: string, toDt?: string) => {
    const p = new URLSearchParams();
    if (fromDt) p.set("from_dt", fromDt);
    if (toDt) p.set("to_dt", toDt);
    const qs = p.toString();
    return request<GlobalStats>(`/api/stats${qs ? `?${qs}` : ""}`);
  },

  // --- traces ---
  taskTraces: (taskId: string) =>
    request<RunTrace[]>(`/api/tasks/${taskId}/traces`),
  taskTraceLatest: (taskId: string) =>
    request<RunTrace>(`/api/tasks/${taskId}/traces/latest`),
  taskTrace: (taskId: string, runIndex: number) =>
    request<RunTrace>(`/api/tasks/${taskId}/traces/${runIndex}`),

  // --- memory ---
  memoryList: (scope: string) =>
    request<MemoryItem[]>(`/api/memory/${encodeURIComponent(scope)}`),
  memoryConfirm: (scope: string, itemId: string) =>
    request<MemoryItem>(`/api/memory/${encodeURIComponent(scope)}/${itemId}`, {
      method: "PATCH",
      body: JSON.stringify({ confirmed: true }),
    }),
  memoryReject: (scope: string, itemId: string) =>
    request<void>(`/api/memory/${encodeURIComponent(scope)}/${itemId}`, {
      method: "DELETE",
    }),

  // --- build info ---
  getInfo: (): Promise<BuildInfo> => request<BuildInfo>("/api/info"),

  // --- test reports ---
  testReports: (spaceId: string) =>
    request<TestReportSummary[]>(`/api/spaces/${spaceId}/test-reports`),
  testReportLatest: (spaceId: string) =>
    request<TestReport>(`/api/spaces/${spaceId}/test-reports/latest`),
  testReport: (spaceId: string, reportId: string) =>
    request<TestReport>(`/api/spaces/${spaceId}/test-reports/${reportId}`),
  taskTestReports: (taskId: string) =>
    request<TestReportSummary[]>(`/api/tasks/${taskId}/test-reports`),
  taskTestReportLatest: (taskId: string) =>
    request<TestReport>(`/api/tasks/${taskId}/test-reports/latest`),

  // --- harness runs ---
  triggerHarnessRun: (spaceId: string, name: string): Promise<TriggerRunResponse> =>
    request<TriggerRunResponse>(`/api/spaces/${spaceId}/harnesses/${encodeURIComponent(name)}/run`, {
      method: "POST",
      body: "{}",
    }),
  listHarnessRuns: (spaceId: string, name: string): Promise<RunSummary[]> =>
    request<RunSummary[]>(`/api/spaces/${spaceId}/harnesses/${encodeURIComponent(name)}/runs`),
  getHarnessRun: (runId: string): Promise<HarnessRunState> =>
    request<HarnessRunState>(`/api/harness-runs/${encodeURIComponent(runId)}`),
  cancelHarnessRun: (runId: string): Promise<{ run_id: string; status: string }> =>
    request<{ run_id: string; status: string }>(`/api/harness-runs/${encodeURIComponent(runId)}/cancel`, {
      method: "POST",
      body: "{}",
    }),

  // --- harness CRUD ---
  listHarnesses: (spaceId: string): Promise<Harness[]> =>
    request<Harness[]>(`/api/spaces/${spaceId}/harnesses`),
  getHarness: (spaceId: string, name: string): Promise<Harness> =>
    request<Harness>(`/api/spaces/${spaceId}/harnesses/${encodeURIComponent(name)}`),
  createHarness: (
    spaceId: string,
    harness: Omit<Harness, "created_at" | "updated_at" | "version">,
  ): Promise<Harness> =>
    request<Harness>(`/api/spaces/${spaceId}/harnesses`, {
      method: "POST",
      body: JSON.stringify(harness),
    }),
  updateHarness: (spaceId: string, name: string, harness: Harness): Promise<Harness> =>
    request<Harness>(`/api/spaces/${spaceId}/harnesses/${encodeURIComponent(name)}`, {
      method: "PUT",
      body: JSON.stringify(harness),
    }),
  deleteHarness: (spaceId: string, name: string): Promise<void> =>
    request<void>(`/api/spaces/${spaceId}/harnesses/${encodeURIComponent(name)}`, {
      method: "DELETE",
    }),

  // --- features ---
  features: (spaceId: string): Promise<FeatureBoard> =>
    request<FeatureBoard>(`/api/features?space_id=${encodeURIComponent(spaceId)}`),
  transitionFeatureState: (taskId: string, state: FeatureState): Promise<Task> =>
    request<Task>(`/api/features/${taskId}/feature-state`, {
      method: "PATCH",
      body: JSON.stringify({ feature_state: state }),
    }),
  createFeature: (
    spaceId: string,
    body: { title: string; type: "feature" | "fix"; description?: string },
  ): Promise<Task> =>
    request<Task>(`/api/features`, {
      method: "POST",
      body: JSON.stringify({
        space_id: spaceId,
        title: body.title,
        type: body.type,
        brief: body.description ?? "",
      }),
    }),
};
