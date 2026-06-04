import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";
import type { HarnessRunState, RunSummary, TriggerRunResponse } from "../../api";
import {
  useHarnessRuns,
  useHarnessRun,
  useTriggerHarnessRun,
  useCancelHarnessRun,
  useHarnessRunStream,
} from "../useHarnessRuns";

// ---------------------------------------------------------------------------
// API mock
// ---------------------------------------------------------------------------

vi.mock("../../api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../api")>();
  return {
    ...actual,
    api: {
      listHarnessRuns: vi.fn(),
      getHarnessRun: vi.fn(),
      triggerHarnessRun: vi.fn(),
      cancelHarnessRun: vi.fn(),
    },
    harnessRunStreamUrl: (runId: string) => `/api/harness-runs/${runId}/stream`,
  };
});

// ---------------------------------------------------------------------------
// FakeEventSource shim (mirrors useLiveStream.test.ts pattern)
// ---------------------------------------------------------------------------

class FakeEventSource {
  static instances: FakeEventSource[] = [];

  onopen: (() => void) | null = null;
  onerror: ((e: Event) => void) | null = null;
  onmessage: ((e: MessageEvent) => void) | null = null;
  closed = false;

  private readonly _listeners = new Map<string, Array<(e: Event) => void>>();

  constructor(public readonly url: string) {
    FakeEventSource.instances.push(this);
  }

  addEventListener(type: string, fn: (e: Event) => void) {
    if (!this._listeners.has(type)) this._listeners.set(type, []);
    this._listeners.get(type)!.push(fn);
  }

  removeEventListener(type: string, fn: (e: Event) => void) {
    const arr = this._listeners.get(type);
    if (!arr) return;
    const idx = arr.indexOf(fn);
    if (idx !== -1) arr.splice(idx, 1);
  }

  close() {
    this.closed = true;
  }

  // Dispatch helpers
  dispatchOpen() {
    this.onopen?.();
  }
  dispatchMessage(data: object) {
    this.onmessage?.({ data: JSON.stringify(data) } as MessageEvent);
  }
  dispatchError() {
    this.onerror?.(new Event("error"));
  }
  dispatchNamed(type: string, data: object) {
    const fns = this._listeners.get(type) ?? [];
    const e = Object.assign(new Event(type), {
      data: JSON.stringify(data),
    }) as MessageEvent;
    fns.forEach((fn) => fn(e));
  }
  dispatchCustom(type: string) {
    const fns = this._listeners.get(type) ?? [];
    fns.forEach((fn) => fn(new Event(type)));
  }
}

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const mockRunSummary: RunSummary = {
  run_id: "run-1",
  harness_id: "harness-a",
  status: "done",
  triggered_at: "2024-01-01T00:00:00Z",
  finished_at: "2024-01-01T00:01:00Z",
};

const mockRunState: HarnessRunState = {
  run_id: "run-1",
  harness_id: "harness-a",
  goal_task_id: "task-1",
  status: "running",
  nodes_executed: {
    node_a: {
      status: "done",
      child_task_id: "task-2",
      output: "ok",
      reason: null,
      started_at: "2024-01-01T00:00:00Z",
      ended_at: "2024-01-01T00:00:30Z",
    },
  },
  waiting_node_id: null,
};

const mockTriggerResponse: TriggerRunResponse = {
  run_id: "run-2",
  harness_id: "harness-a",
  triggered_at: "2024-01-01T00:02:00Z",
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
// Tests
// ---------------------------------------------------------------------------

describe("useHarnessRuns", () => {
  beforeEach(() => vi.clearAllMocks());

  it("test_useHarnessRuns_fetches_list — returns the list from the API", async () => {
    const client = makeClient();
    const { api } = await import("../../api");
    vi.mocked(api.listHarnessRuns).mockResolvedValue([mockRunSummary]);

    const { result } = renderHook(() => useHarnessRuns("space-1", "harness-a"), {
      wrapper: makeWrapper(client),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(api.listHarnessRuns).toHaveBeenCalledWith("space-1", "harness-a");
    expect(result.current.data).toEqual([mockRunSummary]);
  });

  it("caches data under [harness-runs, spaceId, name] key", async () => {
    const client = makeClient();
    const { api } = await import("../../api");
    vi.mocked(api.listHarnessRuns).mockResolvedValue([mockRunSummary]);

    const { result } = renderHook(() => useHarnessRuns("space-1", "harness-a"), {
      wrapper: makeWrapper(client),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(
      client.getQueryData(["harness-runs", "space-1", "harness-a"]),
    ).toEqual([mockRunSummary]);
  });
});

describe("useHarnessRun", () => {
  beforeEach(() => vi.clearAllMocks());

  it("test_useHarnessRun_fetches_single_run — returns RunState for a given runId", async () => {
    const client = makeClient();
    const { api } = await import("../../api");
    vi.mocked(api.getHarnessRun).mockResolvedValue(mockRunState);

    const { result } = renderHook(() => useHarnessRun("run-1"), {
      wrapper: makeWrapper(client),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(api.getHarnessRun).toHaveBeenCalledWith("run-1");
    expect(result.current.data).toEqual(mockRunState);
  });

  it("test_useHarnessRun_skips_when_null — makes no request when runId is null", () => {
    const client = makeClient();

    const { result } = renderHook(() => useHarnessRun(null), {
      wrapper: makeWrapper(client),
    });

    expect(result.current.fetchStatus).toBe("idle");
  });
});

describe("useTriggerHarnessRun", () => {
  beforeEach(() => vi.clearAllMocks());

  it("test_useTriggerHarnessRun_calls_post — calls api.triggerHarnessRun and returns run data", async () => {
    const client = makeClient();
    const { api } = await import("../../api");
    vi.mocked(api.triggerHarnessRun).mockResolvedValue(mockTriggerResponse);

    const { result } = renderHook(() => useTriggerHarnessRun(), {
      wrapper: makeWrapper(client),
    });

    let returned: TriggerRunResponse | undefined;
    await act(async () => {
      returned = await result.current.mutateAsync({ spaceId: "space-1", name: "harness-a" });
    });

    expect(api.triggerHarnessRun).toHaveBeenCalledWith("space-1", "harness-a");
    expect(returned).toEqual(mockTriggerResponse);
  });

  it("invalidates harness-runs list after trigger", async () => {
    const client = makeClient();
    const { api } = await import("../../api");
    vi.mocked(api.triggerHarnessRun).mockResolvedValue(mockTriggerResponse);
    const spy = vi.spyOn(client, "invalidateQueries");

    const { result } = renderHook(() => useTriggerHarnessRun(), {
      wrapper: makeWrapper(client),
    });

    await act(async () => {
      await result.current.mutateAsync({ spaceId: "space-1", name: "harness-a" });
    });

    const exactKeys = spy.mock.calls
      .map(([opts]) => (opts as { queryKey?: unknown[] }).queryKey)
      .filter(Boolean);

    expect(exactKeys).toContainEqual(["harness-runs", "space-1", "harness-a"]);
  });
});

describe("useCancelHarnessRun", () => {
  beforeEach(() => vi.clearAllMocks());

  it("test_useCancelHarnessRun_calls_post_cancel — calls api.cancelHarnessRun with the runId", async () => {
    const client = makeClient();
    const { api } = await import("../../api");
    vi.mocked(api.cancelHarnessRun).mockResolvedValue({
      run_id: "run-1",
      status: "cancelled",
    });

    const { result } = renderHook(() => useCancelHarnessRun(), {
      wrapper: makeWrapper(client),
    });

    await act(async () => {
      await result.current.mutateAsync("run-1");
    });

    expect(api.cancelHarnessRun).toHaveBeenCalledWith("run-1");
  });

  it("invalidates the specific harness-run and all harness-runs lists after cancel", async () => {
    const client = makeClient();
    const { api } = await import("../../api");
    vi.mocked(api.cancelHarnessRun).mockResolvedValue({
      run_id: "run-1",
      status: "cancelled",
    });
    const spy = vi.spyOn(client, "invalidateQueries");

    const { result } = renderHook(() => useCancelHarnessRun(), {
      wrapper: makeWrapper(client),
    });

    await act(async () => {
      await result.current.mutateAsync("run-1");
    });

    const exactKeys = spy.mock.calls
      .map(([opts]) => (opts as { queryKey?: unknown[] }).queryKey)
      .filter(Boolean);

    expect(exactKeys).toContainEqual(["harness-run", "run-1"]);

    // Also verify a predicate-based invalidation was issued for harness-runs lists
    type FilterArg = { predicate?: (q: { queryKey: unknown[] }) => boolean };
    const predicateCall = spy.mock.calls.find(([opts]) => {
      return typeof (opts as FilterArg).predicate === "function";
    });
    expect(predicateCall).toBeDefined();

    const predicate = (predicateCall![0] as FilterArg).predicate!;
    expect(predicate({ queryKey: ["harness-runs", "space-1", "harness-a"] })).toBe(true);
    expect(predicate({ queryKey: ["harness-run", "run-1"] })).toBe(false);
  });
});

describe("useHarnessRunStream", () => {
  beforeEach(() => {
    FakeEventSource.instances = [];
    vi.stubGlobal("EventSource", FakeEventSource);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("starts in connecting status when runId is provided", () => {
    const { result } = renderHook(() => useHarnessRunStream("run-1"));
    expect(result.current.status).toBe("connecting");
    expect(result.current.events).toHaveLength(0);
  });

  it("creates no EventSource and returns ended when runId is null", () => {
    const { result } = renderHook(() => useHarnessRunStream(null));
    expect(result.current.status).toBe("ended");
    expect(FakeEventSource.instances).toHaveLength(0);
  });

  it("opens EventSource with the correct URL", () => {
    renderHook(() => useHarnessRunStream("run-abc"));
    expect(FakeEventSource.instances).toHaveLength(1);
    expect(FakeEventSource.instances[0].url).toBe("/api/harness-runs/run-abc/stream");
  });

  it("transitions to live on open", () => {
    const { result } = renderHook(() => useHarnessRunStream("run-1"));
    const es = FakeEventSource.instances[0];
    act(() => es.dispatchOpen());
    expect(result.current.status).toBe("live");
  });

  it("transitions to error on EventSource error", () => {
    const { result } = renderHook(() => useHarnessRunStream("run-1"));
    const es = FakeEventSource.instances[0];
    act(() => es.dispatchError());
    expect(result.current.status).toBe("error");
  });

  it("closes EventSource and transitions to ended on end event", () => {
    const { result } = renderHook(() => useHarnessRunStream("run-1"));
    const es = FakeEventSource.instances[0];
    act(() => es.dispatchCustom("end"));
    expect(result.current.status).toBe("ended");
    expect(es.closed).toBe(true);
  });

  it("accumulates node_transition events dispatched via named event", () => {
    const { result } = renderHook(() => useHarnessRunStream("run-1"));
    const es = FakeEventSource.instances[0];

    act(() => {
      es.dispatchNamed("node_transition", {
        node_id: "node_a",
        status: "in_progress",
      });
    });

    expect(result.current.events).toHaveLength(1);
    expect(result.current.events[0]).toMatchObject({
      type: "node_transition",
      node_id: "node_a",
      status: "in_progress",
    });
  });

  it("accumulates edge_chosen events", () => {
    const { result } = renderHook(() => useHarnessRunStream("run-1"));
    const es = FakeEventSource.instances[0];

    act(() => {
      es.dispatchNamed("edge_chosen", { from: "node_a", to: "node_b" });
    });

    expect(result.current.events).toHaveLength(1);
    expect(result.current.events[0]).toMatchObject({
      type: "edge_chosen",
      from: "node_a",
      to: "node_b",
    });
  });

  it("accumulates buffer_truncated events", () => {
    const { result } = renderHook(() => useHarnessRunStream("run-1"));
    const es = FakeEventSource.instances[0];

    act(() => {
      es.dispatchNamed("buffer_truncated", { message: "overflow" });
    });

    expect(result.current.events).toHaveLength(1);
    expect(result.current.events[0].type).toBe("buffer_truncated");
  });

  it("closes EventSource on unmount", () => {
    const { unmount } = renderHook(() => useHarnessRunStream("run-1"));
    const es = FakeEventSource.instances[0];
    expect(es.closed).toBe(false);
    unmount();
    expect(es.closed).toBe(true);
  });

  it("creates a new EventSource when runId changes", () => {
    const { rerender } = renderHook(
      ({ runId }: { runId: string | null }) => useHarnessRunStream(runId),
      { initialProps: { runId: "run-1" } },
    );
    const first = FakeEventSource.instances[0];

    rerender({ runId: "run-2" });

    expect(first.closed).toBe(true);
    expect(FakeEventSource.instances).toHaveLength(2);
    expect(FakeEventSource.instances[1].url).toBe("/api/harness-runs/run-2/stream");
  });
});
