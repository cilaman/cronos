import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";
import type { FeatureBoard, FeatureRead, Task } from "../../types";
import {
  useFeatureBoard,
  useTransitionFeatureState,
  useCreateFeature,
  useFeature,
  usePatchFeature,
  useProcessFeature,
  useSetRealize,
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
    getFeature: vi.fn(),
    patchFeature: vi.fn(),
    processFeature: vi.fn(),
    setRealize: vi.fn(),
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

const mockFeatureRead: FeatureRead = {
  id: "feature-1",
  space_id: "space-1",
  title: "Test Feature",
  state: "backlog",
  created_at: "2024-01-01T00:00:00Z",
  updated_at: "2024-01-01T00:00:00Z",
  brief: "Feature brief",
  priority: 3,
  manual_order: 0,
  type: "feature",
  parent_id: null,
  depends_on: [],
  pr_url: null,
  proposed_pr_path: null,
  feature_state: "backlog",
  feature_key: null,
  realizes: null,
  issue_number: null,
  issue_url: null,
  proposed_issue_path: null,
  waiting_question: null,
  realizing_items: [],
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

// ---------------------------------------------------------------------------
// Tests: useFeature
// ---------------------------------------------------------------------------

describe("useFeature", () => {
  beforeEach(() => vi.clearAllMocks());

  it("fetches a single feature by id with correct query key", async () => {
    const client = makeClient();
    const { api } = await import("../../api");
    vi.mocked(api.getFeature).mockResolvedValue(mockFeatureRead);

    const { result } = renderHook(() => useFeature("feature-1"), {
      wrapper: makeWrapper(client),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(api.getFeature).toHaveBeenCalledWith("feature-1");
    expect(client.getQueryData(["feature", "feature-1"])).toEqual(mockFeatureRead);
  });

  it("is disabled when featureId is null", () => {
    const client = makeClient();

    const { result } = renderHook(() => useFeature(null), {
      wrapper: makeWrapper(client),
    });

    expect(result.current.fetchStatus).toBe("idle");
  });

  it("returns FeatureRead data including waiting_question and realizing_items", async () => {
    const client = makeClient();
    const { api } = await import("../../api");
    const featureWithData: FeatureRead = {
      ...mockFeatureRead,
      waiting_question: "Is this scope correct?",
      realizing_items: [],
    };
    vi.mocked(api.getFeature).mockResolvedValue(featureWithData);

    const { result } = renderHook(() => useFeature("feature-1"), {
      wrapper: makeWrapper(client),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(result.current.data?.waiting_question).toBe("Is this scope correct?");
    expect(result.current.data?.realizing_items).toEqual([]);
  });
});

// ---------------------------------------------------------------------------
// Tests: usePatchFeature
// ---------------------------------------------------------------------------

describe("usePatchFeature", () => {
  beforeEach(() => vi.clearAllMocks());

  it("calls api.patchFeature with featureId and body", async () => {
    const client = makeClient();
    const { api } = await import("../../api");
    vi.mocked(api.patchFeature).mockResolvedValue(mockFeatureRead);

    const { result } = renderHook(() => usePatchFeature(), {
      wrapper: makeWrapper(client),
    });

    await act(async () => {
      await result.current.mutateAsync({
        featureId: "feature-1",
        body: { title: "Updated Title" },
      });
    });

    expect(api.patchFeature).toHaveBeenCalledWith("feature-1", { title: "Updated Title" });
  });

  it("invalidates [feature, featureId] and the triple-key on success", async () => {
    const client = makeClient();
    const { api } = await import("../../api");
    vi.mocked(api.patchFeature).mockResolvedValue(mockFeatureRead);

    const spy = vi.spyOn(client, "invalidateQueries");

    const { result } = renderHook(() => usePatchFeature(), {
      wrapper: makeWrapper(client),
    });

    await act(async () => {
      await result.current.mutateAsync({
        featureId: "feature-1",
        body: { brief: "Updated brief" },
      });
    });

    const invalidatedKeys = spy.mock.calls
      .map(([opts]) => (opts as { queryKey?: unknown[] }).queryKey)
      .filter(Boolean);

    expect(invalidatedKeys).toContainEqual(["feature", "feature-1"]);
    expect(invalidatedKeys).toContainEqual(["features", "space-1"]);
    expect(invalidatedKeys).toContainEqual(["board", "space-1"]);
    expect(invalidatedKeys).toContainEqual(["spaces"]);
  });

  it("can patch only brief without title", async () => {
    const client = makeClient();
    const { api } = await import("../../api");
    vi.mocked(api.patchFeature).mockResolvedValue({ ...mockFeatureRead, brief: "New brief" });

    const { result } = renderHook(() => usePatchFeature(), {
      wrapper: makeWrapper(client),
    });

    await act(async () => {
      await result.current.mutateAsync({ featureId: "feature-1", body: { brief: "New brief" } });
    });

    expect(api.patchFeature).toHaveBeenCalledWith("feature-1", { brief: "New brief" });
  });
});

// ---------------------------------------------------------------------------
// Tests: useProcessFeature
// ---------------------------------------------------------------------------

describe("useProcessFeature", () => {
  beforeEach(() => vi.clearAllMocks());

  it("calls api.processFeature with featureId", async () => {
    const client = makeClient();
    const { api } = await import("../../api");
    const processing: FeatureRead = { ...mockFeatureRead, feature_state: "processing" };
    vi.mocked(api.processFeature).mockResolvedValue(processing);

    const { result } = renderHook(() => useProcessFeature(), {
      wrapper: makeWrapper(client),
    });

    await act(async () => {
      await result.current.mutateAsync("feature-1");
    });

    expect(api.processFeature).toHaveBeenCalledWith("feature-1");
  });

  it("invalidates [feature, featureId] and the triple-key on success", async () => {
    const client = makeClient();
    const { api } = await import("../../api");
    vi.mocked(api.processFeature).mockResolvedValue({
      ...mockFeatureRead,
      feature_state: "processing",
    });

    const spy = vi.spyOn(client, "invalidateQueries");

    const { result } = renderHook(() => useProcessFeature(), {
      wrapper: makeWrapper(client),
    });

    await act(async () => {
      await result.current.mutateAsync("feature-1");
    });

    const invalidatedKeys = spy.mock.calls
      .map(([opts]) => (opts as { queryKey?: unknown[] }).queryKey)
      .filter(Boolean);

    expect(invalidatedKeys).toContainEqual(["feature", "feature-1"]);
    expect(invalidatedKeys).toContainEqual(["features", "space-1"]);
    expect(invalidatedKeys).toContainEqual(["board", "space-1"]);
    expect(invalidatedKeys).toContainEqual(["spaces"]);
  });
});

// ---------------------------------------------------------------------------
// Tests: useSetRealize
// ---------------------------------------------------------------------------

describe("useSetRealize", () => {
  beforeEach(() => vi.clearAllMocks());

  it("calls api.setRealize with featureId and body (link)", async () => {
    const client = makeClient();
    const { api } = await import("../../api");
    vi.mocked(api.setRealize).mockResolvedValue(mockFeatureRead);

    const { result } = renderHook(() => useSetRealize(), {
      wrapper: makeWrapper(client),
    });

    await act(async () => {
      await result.current.mutateAsync({
        featureId: "feature-1",
        body: { item_id: "task-42", feature_id: "feature-1" },
      });
    });

    expect(api.setRealize).toHaveBeenCalledWith("feature-1", {
      item_id: "task-42",
      feature_id: "feature-1",
    });
  });

  it("calls api.setRealize with feature_id null to unlink", async () => {
    const client = makeClient();
    const { api } = await import("../../api");
    vi.mocked(api.setRealize).mockResolvedValue(mockFeatureRead);

    const { result } = renderHook(() => useSetRealize(), {
      wrapper: makeWrapper(client),
    });

    await act(async () => {
      await result.current.mutateAsync({
        featureId: "feature-1",
        body: { item_id: "task-42", feature_id: null },
      });
    });

    expect(api.setRealize).toHaveBeenCalledWith("feature-1", {
      item_id: "task-42",
      feature_id: null,
    });
  });

  it("invalidates [feature, featureId] and the triple-key on success", async () => {
    const client = makeClient();
    const { api } = await import("../../api");
    vi.mocked(api.setRealize).mockResolvedValue(mockFeatureRead);

    const spy = vi.spyOn(client, "invalidateQueries");

    const { result } = renderHook(() => useSetRealize(), {
      wrapper: makeWrapper(client),
    });

    await act(async () => {
      await result.current.mutateAsync({
        featureId: "feature-1",
        body: { item_id: "task-42", feature_id: "feature-1" },
      });
    });

    const invalidatedKeys = spy.mock.calls
      .map(([opts]) => (opts as { queryKey?: unknown[] }).queryKey)
      .filter(Boolean);

    expect(invalidatedKeys).toContainEqual(["feature", "feature-1"]);
    expect(invalidatedKeys).toContainEqual(["features", "space-1"]);
    expect(invalidatedKeys).toContainEqual(["board", "space-1"]);
    expect(invalidatedKeys).toContainEqual(["spaces"]);
  });
});

// Fix TypeScript import for useQueryClient used in invalidateFeatureQueries signature
import { useQueryClient } from "@tanstack/react-query";
