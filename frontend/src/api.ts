import type { AgentMode, Board, Task, TaskState } from "./types";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`${res.status} ${res.statusText} on ${path}: ${text}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export const api = {
  board: () => request<Board>("/api/tasks"),
  task: (id: string) => request<Task>(`/api/tasks/${id}`),
  create: (body: { title: string; brief: string }) =>
    request<Task>("/api/tasks", { method: "POST", body: JSON.stringify(body) }),
  update: (
    id: string,
    body: { title?: string; brief?: string; agent_mode?: AgentMode },
  ) =>
    request<Task>(`/api/tasks/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
  transition: (id: string, state: TaskState) =>
    request<Task>(`/api/tasks/${id}/state`, {
      method: "PATCH",
      body: JSON.stringify({ state }),
    }),
  delete: (id: string) =>
    request<void>(`/api/tasks/${id}`, { method: "DELETE" }),
  reply: (id: string, message: string) =>
    request<Task>(`/api/tasks/${id}/reply`, {
      method: "POST",
      body: JSON.stringify({ message }),
    }),
  stop: (id: string) =>
    request<Task>(`/api/tasks/${id}/stop`, { method: "POST", body: "{}" }),
};
