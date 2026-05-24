import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";
import type { Task } from "../../types";

// ---------------------------------------------------------------------------
// Mock api before importing the hooks so the module picks up the mock.
// ---------------------------------------------------------------------------

vi.mock("../../api", () => ({
  api: {
    promote: vi.fn(),
    setParent: vi.fn(),
    setDependsOn: vi.fn(),
  },
}));

import { usePromoteTask, useSetParent, useSetDependsOn } from "../useTasks";
import { api } from "../../api";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeTask(overrides: Partial<Task> = {}): Task {
  return {
    id: "task-1",
    space_id: "space-1",
    title: "T",
    state: "backlog",
    created_at: "2024-01-15T14:00:00Z",
    updated_at: "2024-01-15T14:30:00Z",
    claude_session_id: null,
    waiting_question: null,
    brief: "",
    history: "",
    pending_messages: [],
    agent_mode: "auto",
    agent_model: "default",
    priority: 3,
    manual_order: 0,
    space_name: null,
    space_color: null,
    space_icon: null,
    ...overrides,
  };
}

function makeClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, refetchInterval: false },
      mutations: { retry: false },
    },
  });
}

function makeWrapper(client: QueryClient) {
  return ({ children }: { children: React.ReactNode }) =>
    React.createElement(QueryClientProvider, { client }, children);
}

beforeEach(() => {
  vi.mocked(api.promote).mockReset();
  vi.mocked(api.setParent).mockReset();
  vi.mocked(api.setDependsOn).mockReset();
});

// ---------------------------------------------------------------------------
// usePromoteTask
// ---------------------------------------------------------------------------

describe("usePromoteTask", () => {
  it("calls api.promote with the bound task id on mutate", async () => {
    vi.mocked(api.promote).mockResolvedValue(makeTask({ id: "abc" }));
    const client = makeClient();
    const { result } = renderHook(() => usePromoteTask("abc"), {
      wrapper: makeWrapper(client),
    });

    result.current.mutate();
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(api.promote).toHaveBeenCalledTimes(1);
    expect(api.promote).toHaveBeenCalledWith("abc");
  });

  it("writes the updated task into the ['task', id] cache on success", async () => {
    const updated = makeTask({ id: "abc", type: "goal" });
    vi.mocked(api.promote).mockResolvedValue(updated);
    const client = makeClient();
    const { result } = renderHook(() => usePromoteTask("abc"), {
      wrapper: makeWrapper(client),
    });

    result.current.mutate();
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(client.getQueryData(["task", "abc"])).toEqual(updated);
  });

  it("invalidates every cached board variant on success (predicate match)", async () => {
    vi.mocked(api.promote).mockResolvedValue(makeTask({ id: "abc" }));
    const client = makeClient();
    // Seed two board cache variants.
    client.setQueryData(["board", "all"], { backlog: [], active: [], waiting: [], done: [], archived: [] });
    client.setQueryData(["board", "space-1"], { backlog: [], active: [], waiting: [], done: [], archived: [] });
    const invalidateSpy = vi.spyOn(client, "invalidateQueries");

    const { result } = renderHook(() => usePromoteTask("abc"), {
      wrapper: makeWrapper(client),
    });
    result.current.mutate();
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    // The hook passes a predicate that matches any queryKey whose first segment
    // is "board". Verify the call carries that predicate.
    const predicateCall = invalidateSpy.mock.calls.find(
      (call) => typeof call[0] === "object" && call[0] !== null && "predicate" in call[0]!,
    );
    expect(predicateCall).toBeDefined();
    const predicate = (predicateCall![0] as { predicate: (q: { queryKey: unknown }) => boolean })
      .predicate;
    expect(predicate({ queryKey: ["board", "all"] })).toBe(true);
    expect(predicate({ queryKey: ["board", "space-1"] })).toBe(true);
    expect(predicate({ queryKey: ["task", "abc"] })).toBe(false);
    expect(predicate({ queryKey: ["something-else"] })).toBe(false);
  });

  it("surfaces the api error via result.error and isError", async () => {
    vi.mocked(api.promote).mockRejectedValue(new Error("409: cycle"));
    const client = makeClient();
    const { result } = renderHook(() => usePromoteTask("abc"), {
      wrapper: makeWrapper(client),
    });

    result.current.mutate();
    await waitFor(() => expect(result.current.isError).toBe(true));

    expect(result.current.error?.message).toBe("409: cycle");
  });
});

// ---------------------------------------------------------------------------
// useSetParent
// ---------------------------------------------------------------------------

describe("useSetParent", () => {
  it("calls api.setParent with the bound id and supplied parent id", async () => {
    vi.mocked(api.setParent).mockResolvedValue(makeTask({ id: "child", parent_id: "p" }));
    const client = makeClient();
    const { result } = renderHook(() => useSetParent("child"), {
      wrapper: makeWrapper(client),
    });

    result.current.mutate("p");
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(api.setParent).toHaveBeenCalledWith("child", "p");
  });

  it("supports clearing the parent by passing null", async () => {
    vi.mocked(api.setParent).mockResolvedValue(makeTask({ id: "child", parent_id: null }));
    const client = makeClient();
    const { result } = renderHook(() => useSetParent("child"), {
      wrapper: makeWrapper(client),
    });

    result.current.mutate(null);
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(api.setParent).toHaveBeenCalledWith("child", null);
  });

  it("writes the updated task to the ['task', id] cache on success", async () => {
    const updated = makeTask({ id: "child", parent_id: "p" });
    vi.mocked(api.setParent).mockResolvedValue(updated);
    const client = makeClient();
    const { result } = renderHook(() => useSetParent("child"), {
      wrapper: makeWrapper(client),
    });

    result.current.mutate("p");
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(client.getQueryData(["task", "child"])).toEqual(updated);
  });

  it("surfaces backend cycle-detection errors via result.error", async () => {
    vi.mocked(api.setParent).mockRejectedValue(
      new Error('400 Bad Request on /api/tasks/c/parent: {"detail":"cycle detected"}'),
    );
    const client = makeClient();
    const { result } = renderHook(() => useSetParent("c"), {
      wrapper: makeWrapper(client),
    });

    result.current.mutate("p");
    await waitFor(() => expect(result.current.isError).toBe(true));

    expect(result.current.error?.message).toMatch(/cycle detected/);
  });
});

// ---------------------------------------------------------------------------
// useSetDependsOn
// ---------------------------------------------------------------------------

describe("useSetDependsOn", () => {
  it("calls api.setDependsOn with the id and supplied dependency list", async () => {
    vi.mocked(api.setDependsOn).mockResolvedValue(
      makeTask({ id: "t1", depends_on: ["d1", "d2"] }),
    );
    const client = makeClient();
    const { result } = renderHook(() => useSetDependsOn("t1"), {
      wrapper: makeWrapper(client),
    });

    result.current.mutate(["d1", "d2"]);
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(api.setDependsOn).toHaveBeenCalledWith("t1", ["d1", "d2"]);
  });

  it("forwards an empty array to clear all dependencies", async () => {
    vi.mocked(api.setDependsOn).mockResolvedValue(
      makeTask({ id: "t1", depends_on: [] }),
    );
    const client = makeClient();
    const { result } = renderHook(() => useSetDependsOn("t1"), {
      wrapper: makeWrapper(client),
    });

    result.current.mutate([]);
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(api.setDependsOn).toHaveBeenCalledWith("t1", []);
  });

  it("writes the updated task into the cache on success", async () => {
    const updated = makeTask({ id: "t1", depends_on: ["d1"] });
    vi.mocked(api.setDependsOn).mockResolvedValue(updated);
    const client = makeClient();
    const { result } = renderHook(() => useSetDependsOn("t1"), {
      wrapper: makeWrapper(client),
    });

    result.current.mutate(["d1"]);
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(client.getQueryData(["task", "t1"])).toEqual(updated);
  });

  it("does NOT touch the cache when the mutation fails", async () => {
    vi.mocked(api.setDependsOn).mockRejectedValue(new Error("404: not found"));
    const client = makeClient();
    // Pre-seed cache to ensure the hook does not blow it away on error.
    const original = makeTask({ id: "t1", depends_on: ["existing"] });
    client.setQueryData(["task", "t1"], original);

    const { result } = renderHook(() => useSetDependsOn("t1"), {
      wrapper: makeWrapper(client),
    });
    result.current.mutate(["missing"]);
    await waitFor(() => expect(result.current.isError).toBe(true));

    expect(client.getQueryData(["task", "t1"])).toEqual(original);
  });

  it("isPending toggles while the mutation is in flight", async () => {
    let resolveFn: ((v: Task) => void) | undefined;
    vi.mocked(api.setDependsOn).mockReturnValue(
      new Promise<Task>((resolve) => {
        resolveFn = resolve;
      }),
    );
    const client = makeClient();
    const { result } = renderHook(() => useSetDependsOn("t1"), {
      wrapper: makeWrapper(client),
    });

    result.current.mutate(["d1"]);
    await waitFor(() => expect(result.current.isPending).toBe(true));

    resolveFn!(makeTask({ id: "t1", depends_on: ["d1"] }));
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.isPending).toBe(false);
  });
});
