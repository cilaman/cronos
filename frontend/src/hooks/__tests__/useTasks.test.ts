import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";
import type { Task } from "../../types";
import {
  useBoard,
  useCreateTask,
  useTask,
  useUpdateTask,
  useDeleteTask,
  useTransitionTask,
  useArchiveTask,
} from "../useTasks";

vi.mock("../../api", () => ({
  api: {
    board: vi.fn(),
    archived: vi.fn(),
    task: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
    reorder: vi.fn(),
    transition: vi.fn(),
    delete: vi.fn(),
    start: vi.fn(),
    reply: vi.fn(),
    stop: vi.fn(),
  },
}));

const mockTask: Task = {
  id: "task-1",
  space_id: "space-1",
  title: "Test Task",
  state: "backlog",
  created_at: "2024-01-01T00:00:00Z",
  updated_at: "2024-01-01T00:00:00Z",
  claude_session_id: null,
  waiting_question: null,
  brief: "Brief",
  history: "",
  pending_messages: [],
  agent_mode: "auto",
  agent_model: "default",
  priority: 3,
  manual_order: 0,
  space_name: null,
  space_color: null,
  space_icon: null,
};

const emptyBoard = {
  backlog: [],
  active: [],
  waiting: [],
  done: [],
  archived: [],
};

function makeClient() {
  return new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
}

function makeWrapper(client: QueryClient) {
  return ({ children }: { children: React.ReactNode }) =>
    React.createElement(QueryClientProvider, { client }, children);
}

describe("useBoard", () => {
  it('uses ["board", "all"] key when spaceId is null', async () => {
    const client = makeClient();
    const { api } = await import("../../api");
    vi.mocked(api.board).mockResolvedValue(emptyBoard);

    const { result } = renderHook(() => useBoard(null), {
      wrapper: makeWrapper(client),
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(api.board).toHaveBeenCalledWith(null);
    // Verify data is cached under ["board", "all"]
    expect(client.getQueryData(["board", "all"])).toEqual(emptyBoard);
  });

  it('uses ["board", spaceId] key when spaceId is provided', async () => {
    const client = makeClient();
    const { api } = await import("../../api");
    vi.mocked(api.board).mockResolvedValue(emptyBoard);

    const { result } = renderHook(() => useBoard("space-1"), {
      wrapper: makeWrapper(client),
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(client.getQueryData(["board", "space-1"])).toEqual(emptyBoard);
  });
});

describe("useTask", () => {
  it("is disabled when id is null", () => {
    const client = makeClient();
    const { result } = renderHook(() => useTask(null), {
      wrapper: makeWrapper(client),
    });
    expect(result.current.fetchStatus).toBe("idle");
  });

  it("fetches when id is provided", async () => {
    const client = makeClient();
    const { api } = await import("../../api");
    vi.mocked(api.task).mockResolvedValue(mockTask);

    const { result } = renderHook(() => useTask("task-1"), {
      wrapper: makeWrapper(client),
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(api.task).toHaveBeenCalledWith("task-1");
    expect(result.current.data).toEqual(mockTask);
  });
});

describe("useCreateTask — board invalidation predicate", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("calls api.create with the provided body", async () => {
    const client = makeClient();
    const { api } = await import("../../api");
    vi.mocked(api.create).mockResolvedValue(mockTask);

    const { result } = renderHook(() => useCreateTask(), {
      wrapper: makeWrapper(client),
    });

    await act(async () => {
      await result.current.mutateAsync({
        space_id: "space-1",
        title: "New",
        brief: "",
      });
    });

    // React Query v5 may pass a context object as second arg; check only the first
    expect(vi.mocked(api.create).mock.calls[0][0]).toEqual({
      space_id: "space-1",
      title: "New",
      brief: "",
    });
  });

  it("invalidates all board variants (not just one key) after creation", async () => {
    const client = makeClient();
    const { api } = await import("../../api");
    vi.mocked(api.create).mockResolvedValue(mockTask);

    // Seed multiple board variants into cache
    client.setQueryData(["board", "all"], emptyBoard);
    client.setQueryData(["board", "space-1"], emptyBoard);
    client.setQueryData(["board", "space-2"], emptyBoard);

    const spy = vi.spyOn(client, "invalidateQueries");

    const { result } = renderHook(() => useCreateTask(), {
      wrapper: makeWrapper(client),
    });

    await act(async () => {
      await result.current.mutateAsync({
        space_id: "space-1",
        title: "New",
        brief: "",
      });
    });

    // Find the predicate-based invalidation call
    type FilterArg = { predicate?: (q: { queryKey: unknown[] }) => boolean };
    let predicate: ((q: { queryKey: unknown[] }) => boolean) | undefined;
    for (const [opts] of spy.mock.calls) {
      const filter = opts as FilterArg;
      if (typeof filter?.predicate === "function") {
        predicate = filter.predicate;
        break;
      }
    }

    expect(predicate).toBeDefined();
    // Must match all board key variants
    expect(predicate!({ queryKey: ["board", "all"] })).toBe(true);
    expect(predicate!({ queryKey: ["board", "space-1"] })).toBe(true);
    expect(predicate!({ queryKey: ["board", "space-2"] })).toBe(true);
    // Must NOT match unrelated queries (cache key drift guard)
    expect(predicate!({ queryKey: ["task", "task-1"] })).toBe(false);
    expect(predicate!({ queryKey: ["spaces"] })).toBe(false);
    expect(predicate!({ queryKey: ["activity", "all", 50] })).toBe(false);
  });

  it("also invalidates spaces and activity after creation", async () => {
    const client = makeClient();
    const { api } = await import("../../api");
    vi.mocked(api.create).mockResolvedValue(mockTask);
    const spy = vi.spyOn(client, "invalidateQueries");

    const { result } = renderHook(() => useCreateTask(), {
      wrapper: makeWrapper(client),
    });

    await act(async () => {
      await result.current.mutateAsync({
        space_id: "space-1",
        title: "New",
        brief: "",
      });
    });

    // Non-predicate calls for exact query keys
    const exactKeys = spy.mock.calls
      .map(([opts]) => (opts as { queryKey?: unknown[] }).queryKey)
      .filter(Boolean);

    expect(exactKeys).toContainEqual(["spaces"]);
    expect(exactKeys).toContainEqual(["activity"]);
  });
});

describe("useUpdateTask", () => {
  it("invalidates the specific task and all boards on success", async () => {
    const client = makeClient();
    const { api } = await import("../../api");
    vi.mocked(api.update).mockResolvedValue({ ...mockTask, title: "Updated" });
    const spy = vi.spyOn(client, "invalidateQueries");

    const { result } = renderHook(() => useUpdateTask("task-1"), {
      wrapper: makeWrapper(client),
    });

    await act(async () => {
      await result.current.mutateAsync({ title: "Updated" });
    });

    const exactKeys = spy.mock.calls
      .map(([opts]) => (opts as { queryKey?: unknown[] }).queryKey)
      .filter(Boolean);

    expect(exactKeys).toContainEqual(["task", "task-1"]);
  });
});

describe("useDeleteTask", () => {
  it("invalidates boards and spaces on delete", async () => {
    const client = makeClient();
    const { api } = await import("../../api");
    vi.mocked(api.delete).mockResolvedValue(undefined);
    const spy = vi.spyOn(client, "invalidateQueries");

    const { result } = renderHook(() => useDeleteTask(), {
      wrapper: makeWrapper(client),
    });

    await act(async () => {
      await result.current.mutateAsync("task-1");
    });

    expect(api.delete).toHaveBeenCalledWith("task-1");

    const exactKeys = spy.mock.calls
      .map(([opts]) => (opts as { queryKey?: unknown[] }).queryKey)
      .filter(Boolean);
    expect(exactKeys).toContainEqual(["spaces"]);
  });
});

describe("useTransitionTask", () => {
  it("invalidates boards and the task after state transition", async () => {
    const client = makeClient();
    const { api } = await import("../../api");
    vi.mocked(api.transition).mockResolvedValue({ ...mockTask, state: "done" });
    const spy = vi.spyOn(client, "invalidateQueries");

    const { result } = renderHook(() => useTransitionTask(), {
      wrapper: makeWrapper(client),
    });

    await act(async () => {
      await result.current.mutateAsync({ id: "task-1", state: "done" });
    });

    expect(api.transition).toHaveBeenCalledWith("task-1", "done");

    const exactKeys = spy.mock.calls
      .map(([opts]) => (opts as { queryKey?: unknown[] }).queryKey)
      .filter(Boolean);
    expect(exactKeys).toContainEqual(["task", "task-1"]);
  });
});

describe("useArchiveTask", () => {
  it("transitions to 'archived' state and invalidates archive list", async () => {
    const client = makeClient();
    const { api } = await import("../../api");
    vi.mocked(api.transition).mockResolvedValue({
      ...mockTask,
      state: "archived",
    });
    const spy = vi.spyOn(client, "invalidateQueries");

    const { result } = renderHook(() => useArchiveTask("task-1"), {
      wrapper: makeWrapper(client),
    });

    await act(async () => {
      await result.current.mutateAsync();
    });

    expect(api.transition).toHaveBeenCalledWith("task-1", "archived");

    const exactKeys = spy.mock.calls
      .map(([opts]) => (opts as { queryKey?: unknown[] }).queryKey)
      .filter(Boolean);
    expect(exactKeys).toContainEqual(["archived"]);
  });
});
