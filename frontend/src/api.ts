import type {
  Activity,
  AgentMode,
  AgentModel,
  Board,
  Space,
  SpacesResponse,
  Task,
  TaskState,
} from "./types";

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

export const api = {
  board: (spaceId: string | null = null) =>
    request<Board>(withSpaceQuery("/api/tasks", spaceId)),
  task: (id: string) => request<Task>(`/api/tasks/${id}`),
  create: (body: {
    space_id: string;
    title: string;
    brief: string;
    agent_model?: AgentModel;
  }) => request<Task>("/api/tasks", { method: "POST", body: JSON.stringify(body) }),
  update: (
    id: string,
    body: {
      title?: string;
      brief?: string;
      agent_mode?: AgentMode;
      agent_model?: AgentModel;
    },
  ) =>
    request<Task>(`/api/tasks/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
  transition: (id: string, state: TaskState) =>
    request<Task>(`/api/tasks/${id}/state`, {
      method: "PATCH",
      body: JSON.stringify({ state }),
    }),
  delete: (id: string) => request<void>(`/api/tasks/${id}`, { method: "DELETE" }),
  start: (id: string) =>
    request<Task>(`/api/tasks/${id}/start`, { method: "POST", body: "{}" }),
  reply: (id: string, message: string) =>
    request<Task>(`/api/tasks/${id}/reply`, {
      method: "POST",
      body: JSON.stringify({ message }),
    }),
  stop: (id: string) =>
    request<Task>(`/api/tasks/${id}/stop`, { method: "POST", body: "{}" }),

  // --- spaces ---
  spaces: () => request<SpacesResponse>("/api/spaces"),
  space: (id: string) => request<Space>(`/api/spaces/${id}`),
  createSpace: (body: {
    name: string;
    color: string;
    icon?: string | null;
    description?: string;
    space_id?: string;
  }) => request<Space>("/api/spaces", { method: "POST", body: JSON.stringify(body) }),
  updateSpace: (
    id: string,
    body: {
      name?: string;
      color?: string;
      icon?: string | null;
      clear_icon?: boolean;
      description?: string;
    },
  ) =>
    request<Space>(`/api/spaces/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
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

  // --- activity ---
  activity: (limit = 50, spaceId: string | null = null) => {
    const params = new URLSearchParams({ limit: String(limit) });
    if (spaceId) params.set("space_id", spaceId);
    return request<Activity[]>(`/api/activity?${params.toString()}`);
  },
};
