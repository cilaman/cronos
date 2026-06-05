import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";
import type { FeatureBoard, Task } from "../../types";
import {
  useFeatureBoard,
  useTransitionFeatureState,
  useCreateFeature,
  invalidateFeatureQueries,
} from "../useFeatures";

// ---------------------------------------------------------------------------
// API mock
// ---------------------------------------------------------------------------

vi.mock("../../api", () => ({
  api: {
    features: vi.fn(),
    transitionFeatureState: vi.fn(),
    createFeature: vi.fn(),
  },
}));

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const emptyFeatureBoard: FeatureBoard = {
  backlog: [],
  processing: [],
  planned: [],
  waiting: [],
  done: [],
};

const mockTask: Task = {
  id: "task-1",
  space_id: "space-1",
  title: "Test Feature",
  state: "backlog",
  created_at: "2024-01-01T00:00:00Z",
  updated_at: "2024-01-01T00:00:00Z",
  claude_session_id: null,
  waiting_question: null,
  brief: "Feature brief",
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

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeClient() {
  return new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
}

function makeWrapper(client: QueryClient) {
  return ({ children }: { children: React.ReactNode }) =>
    React.createElement(QueryClientProvider, { client }, children);
}

// ---------------------------------------------------------------------------
// Tests: useFeatureBoard
// ---------------------------------------------------------------------------

describe("useFeatureBoard", () => {
  beforeEach(() => vi.clearAllMocks());

  it("fetches features with correct query key", async () => {
    const client = makeClient();
    const { api } = await import("../../api");
    vi.mocked(api.features).mockResolvedValue(emptyFeatureBoard);

    const { result } = renderHook(() => useFeatureBoard("space-1"), {
      wrapper: makeWrapper(client),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(api.features).toHaveBeenCalledWith("space-1");
    // Data should be cached under ["features", "space-1"]
    expect(client.getQueryData(["features", "space-1"])).toEqual(emptyFeatureBoard);
  });

  it("is disabled when spaceId is null", () => {
    const client = makeClient();

    const { result } = renderHook(() => useFeatureBoard(null), {
      wrapper: makeWrapper(client),
    });

    expect(result.current.fetchStatus).toBe("idle");
  });
});

// ---------------------------------------------------------------------------
// Tests: useTransitionFeatureState
// ---------------------------------------------------------------------------

describe("useTransitionFeatureState", () => {
  beforeEach(() => vi.clearAllMocks());

  it("calls api.transitionFeatureState with taskId and state", async () => {
    const client = makeClient();
    const { api } = await import("../../api");
    vi.mocked(api.transitionFeatureState).mockResolvedValue(mockTask);

    const { result } = renderHook(() => useTransitionFeatureState("space-1"), {
      wrapper: makeWrapper(client),
    });

    await act(async () => {
      await result.current.mutateAsync({ taskId: "task-1", state: "processing" });
    });

    expect(api.transitionFeatureState).toHaveBeenCalledWith("task-1", "processing");
  });

  it("invalidates all three query keys on success", async () => {
    const client = makeClient();
    const { api } = await import("../../api");
    vi.mocked(api.transitionFeatureState).mockResolvedValue(mockTask);

    const spy = vi.spyOn(client, "invalidateQueries");

    const { result } = renderHook(() => useTransitionFeatureState("space-1"), {
      wrapper: makeWrapper(client),
    });

    await act(async () => {
      await result.current.mutateAsync({ taskId: "task-1", state: "processing" });
    });

    // Collect all exact queryKey invalidation calls
    const invalidatedKeys = spy.mock.calls
      .map(([opts]) => (opts as { queryKey?: unknown[] }).queryKey)
      .filter(Boolean);

    expect(invalidatedKeys).toContainEqual(["features", "space-1"]);
    expect(invalidatedKeys).toContainEqual(["board", "space-1"]);
    expect(invalidatedKeys).toContainEqual(["spaces"]);
  });
});

// ---------------------------------------------------------------------------
// Tests: useCreateFeature
// ---------------------------------------------------------------------------

describe("useCreateFeature", () => {
  beforeEach(() => vi.clearAllMocks());

  it("calls api.createFeature with spaceId and body", async () => {
    const client = makeClient();
    const { api } = await import("../../api");
    vi.mocked(api.createFeature).mockResolvedValue(mockTask);

    const { result } = renderHook(() => useCreateFeature("space-1"), {
      wrapper: makeWrapper(client),
    });

    await act(async () => {
      await result.current.mutateAsync({
        title: "New Feature",
        type: "feature",
        description: "A new feature",
      });
    });

    expect(api.createFeature).toHaveBeenCalledWith("space-1", {
      title: "New Feature",
      type: "feature",
      description: "A new feature",
    });
  });

  it("invalidates all three query keys on success", async () => {
    const client = makeClient();
    const { api } = await import("../../api");
    vi.mocked(api.createFeature).mockResolvedValue(mockTask);

    const spy = vi.spyOn(client, "invalidateQueries");

    const { result } = renderHook(() => useCreateFeature("space-1"), {
      wrapper: makeWrapper(client),
    });

    await act(async () => {
      await result.current.mutateAsync({
        title: "New Fix",
        type: "fix",
      });
    });

    // Collect all exact queryKey invalidation calls
    const invalidatedKeys = spy.mock.calls
      .map(([opts]) => (opts as { queryKey?: unknown[] }).queryKey)
      .filter(Boolean);

    expect(invalidatedKeys).toContainEqual(["features", "space-1"]);
    expect(invalidatedKeys).toContainEqual(["board", "space-1"]);
    expect(invalidatedKeys).toContainEqual(["spaces"]);
  });

  it("invalidates only the correct spaceId keys (not other spaces)", async () => {
    const client = makeClient();
    const { api } = await import("../../api");
    vi.mocked(api.createFeature).mockResolvedValue(mockTask);

    const spy = vi.spyOn(client, "invalidateQueries");

    const { result } = renderHook(() => useCreateFeature("space-42"), {
      wrapper: makeWrapper(client),
    });

    await act(async () => {
      await result.current.mutateAsync({ title: "New Feature", type: "feature" });
    });

    const invalidatedKeys = spy.mock.calls
      .map(([opts]) => (opts as { queryKey?: unknown[] }).queryKey)
      .filter(Boolean);

    // space-42 keys present
    expect(invalidatedKeys).toContainEqual(["features", "space-42"]);
    expect(invalidatedKeys).toContainEqual(["board", "space-42"]);
    // space-1 keys NOT invalidated
    expect(invalidatedKeys).not.toContainEqual(["features", "space-1"]);
    expect(invalidatedKeys).not.toContainEqual(["board", "space-1"]);
    // global spaces key still present
    expect(invalidatedKeys).toContainEqual(["spaces"]);
  });
});

// ---------------------------------------------------------------------------
// Tests: invalidateFeatureQueries (unit test on the helper)
// ---------------------------------------------------------------------------

describe("invalidateFeatureQueries", () => {
  it("calls invalidateQueries for all three required keys", () => {
    const client = makeClient();
    const spy = vi.spyOn(client, "invalidateQueries");

    invalidateFeatureQueries(client as ReturnType<typeof useQueryClient>, "space-99");

    const invalidatedKeys = spy.mock.calls
      .map(([opts]) => (opts as { queryKey?: unknown[] }).queryKey)
      .filter(Boolean);

    expect(invalidatedKeys).toHaveLength(3);
    expect(invalidatedKeys).toContainEqual(["features", "space-99"]);
    expect(invalidatedKeys).toContainEqual(["board", "space-99"]);
    expect(invalidatedKeys).toContainEqual(["spaces"]);
  });
});

// Fix TypeScript import for useQueryClient used in invalidateFeatureQueries signature
import { useQueryClient } from "@tanstack/react-query";
