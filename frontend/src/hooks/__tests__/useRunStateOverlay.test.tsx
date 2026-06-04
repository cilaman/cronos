/**
 * Tests for useRunStateOverlay — I3 arc6-live-overlay
 *
 * Key behaviors:
 *  - live mode: consumes useHarnessRunStream events, reduces into nodeStatuses/edgeStatuses
 *  - replay mode: consumes useHarnessRun snapshot, maps nodes_executed → nodeStatuses
 *  - rAF batching: multiple events dispatched synchronously are coalesced into a
 *    single rAF flush (non-stutter assertion)
 *  - mode switch: resets all maps and closes the live EventSource
 *  - bufferTruncated: set on first buffer_truncated event
 *  - null runId: returns empty maps with status=ended
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";
import type { HarnessRunState } from "../../api";
import { useRunStateOverlay } from "../useRunStateOverlay";

// ---------------------------------------------------------------------------
// Fake EventSource — same shape as useHarnessRuns.test.tsx
// ---------------------------------------------------------------------------

class FakeEventSource {
  static instances: FakeEventSource[] = [];
  static constructorCallCount = 0;
  static closeCallCount = 0;

  onopen: (() => void) | null = null;
  onerror: ((e: Event) => void) | null = null;
  onmessage: ((e: MessageEvent) => void) | null = null;
  closed = false;

  private readonly _listeners = new Map<string, Array<(e: Event) => void>>();

  constructor(public readonly url: string) {
    FakeEventSource.instances.push(this);
    FakeEventSource.constructorCallCount++;
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
    FakeEventSource.closeCallCount++;
  }

  dispatchOpen() {
    this.onopen?.();
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
// rAF shim — synchronous execution of rAF callbacks for test control
// ---------------------------------------------------------------------------

type RafCallback = (time: number) => void;
let rafQueue: RafCallback[] = [];
let rafHandleCounter = 0;
const rafHandles = new Map<number, RafCallback>();

function fakeRaf(cb: RafCallback): number {
  const handle = ++rafHandleCounter;
  rafHandles.set(handle, cb);
  rafQueue.push(cb);
  return handle;
}

function fakeCaf(handle: number): void {
  const cb = rafHandles.get(handle);
  if (cb) {
    rafHandles.delete(handle);
    rafQueue = rafQueue.filter((c) => c !== cb);
  }
}

function flushRaf(): void {
  const pending = [...rafQueue];
  rafQueue = [];
  rafHandles.clear();
  pending.forEach((cb) => cb(0));
}

// ---------------------------------------------------------------------------
// API mock — only the pieces useRunStateOverlay depends on
// ---------------------------------------------------------------------------

vi.mock("../../api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../api")>();
  return {
    ...actual,
    api: {
      ...((actual as { api?: object }).api ?? {}),
      listHarnessRuns: vi.fn(),
      getHarnessRun: vi.fn(),
      triggerHarnessRun: vi.fn(),
      cancelHarnessRun: vi.fn(),
    },
    harnessRunStreamUrl: (runId: string) => `/api/harness-runs/${runId}/stream`,
  };
});

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const mockRunState: HarnessRunState = {
  run_id: "run-replay",
  harness_id: "harness-a",
  goal_task_id: "task-1",
  status: "done",
  nodes_executed: {
    "node-a": {
      status: "done",
      child_task_id: "task-2",
      output: "ok",
      reason: null,
      started_at: "2024-01-01T00:00:00Z",
      ended_at: "2024-01-01T00:00:30Z",
    },
    "node-b": {
      status: "failed",
      child_task_id: null,
      output: null,
      reason: "timeout",
      started_at: "2024-01-01T00:00:10Z",
      ended_at: "2024-01-01T00:00:20Z",
    },
  },
  waiting_node_id: null,
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
// Setup / teardown
// ---------------------------------------------------------------------------

beforeEach(() => {
  FakeEventSource.instances = [];
  FakeEventSource.constructorCallCount = 0;
  FakeEventSource.closeCallCount = 0;
  rafQueue = [];
  rafHandleCounter = 0;
  rafHandles.clear();
  vi.stubGlobal("EventSource", FakeEventSource);
  vi.stubGlobal("requestAnimationFrame", fakeRaf);
  vi.stubGlobal("cancelAnimationFrame", fakeCaf);
  vi.clearAllMocks();
});

afterEach(() => {
  // Flush any leftover rAF callbacks before restoring globals.
  flushRaf();
  vi.unstubAllGlobals();
});

// ---------------------------------------------------------------------------
// Tests: null runId
// ---------------------------------------------------------------------------

describe("useRunStateOverlay — null runId", () => {
  it("returns empty maps and ended status in live mode", () => {
    const client = makeClient();
    const { result } = renderHook(
      () => useRunStateOverlay(null, "live"),
      { wrapper: makeWrapper(client) },
    );

    expect(result.current.nodeStatuses.size).toBe(0);
    expect(result.current.edgeStatuses.size).toBe(0);
    expect(result.current.bufferTruncated).toBe(false);
    expect(result.current.status).toBe("ended");
  });

  it("returns empty maps and ended status in replay mode", () => {
    const client = makeClient();
    const { result } = renderHook(
      () => useRunStateOverlay(null, "replay"),
      { wrapper: makeWrapper(client) },
    );

    expect(result.current.nodeStatuses.size).toBe(0);
    expect(result.current.edgeStatuses.size).toBe(0);
    expect(result.current.status).toBe("ended");
  });
});

// ---------------------------------------------------------------------------
// Tests: live mode — SSE event processing
// ---------------------------------------------------------------------------

describe("useRunStateOverlay — live mode", () => {
  it("opens an EventSource for a non-null runId", () => {
    const client = makeClient();
    renderHook(() => useRunStateOverlay("run-live", "live"), {
      wrapper: makeWrapper(client),
    });
    expect(FakeEventSource.instances).toHaveLength(1);
    expect(FakeEventSource.instances[0].url).toBe("/api/harness-runs/run-live/stream");
  });

  it("does NOT open an EventSource in replay mode", () => {
    const client = makeClient();
    renderHook(() => useRunStateOverlay("run-replay", "replay"), {
      wrapper: makeWrapper(client),
    });
    expect(FakeEventSource.instances).toHaveLength(0);
  });

  it("processes node_transition event and populates nodeStatuses after rAF flush", async () => {
    const client = makeClient();
    const { result } = renderHook(
      () => useRunStateOverlay("run-live", "live"),
      { wrapper: makeWrapper(client) },
    );

    const es = FakeEventSource.instances[0];

    act(() => {
      es.dispatchNamed("node_transition", {
        node_id: "node-a",
        status: "in_progress",
        started_at: "2024-01-01T00:00:00Z",
        ended_at: null,
        child_task_id: "task-2",
      });
    });

    // Before rAF flush: map is still empty (event is pending).
    // After rAF flush: map is populated.
    act(() => {
      flushRaf();
    });

    await waitFor(() => {
      expect(result.current.nodeStatuses.size).toBeGreaterThan(0);
    });

    const overlay = result.current.nodeStatuses.get("node-a");
    expect(overlay).toBeDefined();
    expect(overlay?.runStatus).toBe("in_progress");
    expect(overlay?.startedAt).toBe("2024-01-01T00:00:00Z");
    expect(overlay?.childTaskId).toBe("task-2");
  });

  it("accumulates updates for the same node via last-write-wins merge", async () => {
    const client = makeClient();
    const { result } = renderHook(
      () => useRunStateOverlay("run-live", "live"),
      { wrapper: makeWrapper(client) },
    );

    const es = FakeEventSource.instances[0];

    act(() => {
      es.dispatchNamed("node_transition", {
        node_id: "node-a",
        status: "in_progress",
        started_at: "2024-01-01T00:00:00Z",
        ended_at: null,
        child_task_id: null,
      });
    });

    act(() => {
      flushRaf();
    });

    await waitFor(() => expect(result.current.nodeStatuses.get("node-a")?.runStatus).toBe("in_progress"));

    act(() => {
      es.dispatchNamed("node_transition", {
        node_id: "node-a",
        status: "done",
        started_at: "2024-01-01T00:00:00Z",
        ended_at: "2024-01-01T00:00:05Z",
        child_task_id: "task-2",
      });
    });

    act(() => {
      flushRaf();
    });

    await waitFor(() => expect(result.current.nodeStatuses.get("node-a")?.runStatus).toBe("done"));

    const overlay = result.current.nodeStatuses.get("node-a");
    expect(overlay?.endedAt).toBe("2024-01-01T00:00:05Z");
    expect(overlay?.childTaskId).toBe("task-2");
  });

  it("processes edge_chosen event and populates edgeStatuses after rAF flush", async () => {
    const client = makeClient();
    const { result } = renderHook(
      () => useRunStateOverlay("run-live", "live"),
      { wrapper: makeWrapper(client) },
    );

    const es = FakeEventSource.instances[0];

    act(() => {
      es.dispatchNamed("edge_chosen", {
        edge_id: "edge-a-b",
        from: "node-a",
        to: "node-b",
      });
    });

    act(() => {
      flushRaf();
    });

    await waitFor(() => {
      expect(result.current.edgeStatuses.size).toBeGreaterThan(0);
    });

    expect(result.current.edgeStatuses.get("edge-a-b")).toBe("done");
  });

  it("falls back to from__to key for edge_chosen when edge_id is absent", async () => {
    const client = makeClient();
    const { result } = renderHook(
      () => useRunStateOverlay("run-live", "live"),
      { wrapper: makeWrapper(client) },
    );

    const es = FakeEventSource.instances[0];

    act(() => {
      es.dispatchNamed("edge_chosen", { from: "node-a", to: "node-b" });
    });

    act(() => {
      flushRaf();
    });

    await waitFor(() => expect(result.current.edgeStatuses.size).toBeGreaterThan(0));
    expect(result.current.edgeStatuses.get("node-a__node-b")).toBe("done");
  });

  it("sets bufferTruncated=true on buffer_truncated event", async () => {
    const client = makeClient();
    const { result } = renderHook(
      () => useRunStateOverlay("run-live", "live"),
      { wrapper: makeWrapper(client) },
    );

    const es = FakeEventSource.instances[0];

    expect(result.current.bufferTruncated).toBe(false);

    act(() => {
      es.dispatchNamed("buffer_truncated", { message: "overflow" });
    });

    act(() => {
      flushRaf();
    });

    await waitFor(() => expect(result.current.bufferTruncated).toBe(true));
  });

  it("reflects live stream status (connecting → live → ended)", async () => {
    const client = makeClient();
    const { result } = renderHook(
      () => useRunStateOverlay("run-live", "live"),
      { wrapper: makeWrapper(client) },
    );

    // Initial status from useHarnessRunStream is 'connecting'
    expect(result.current.status).toBe("connecting");

    const es = FakeEventSource.instances[0];
    act(() => {
      es.dispatchOpen();
    });

    await waitFor(() => expect(result.current.status).toBe("live"));

    act(() => {
      es.dispatchCustom("end");
    });

    await waitFor(() => expect(result.current.status).toBe("ended"));
  });

  // -------------------------------------------------------------------------
  // R7: rAF batching — 20 events in a single synchronous burst coalesce into
  // a single rAF flush, so setNodeStatuses is called at most once per burst.
  // -------------------------------------------------------------------------

  it("coalesces 20 synchronous node_transition events into a single rAF flush (R7)", async () => {
    const client = makeClient();
    const { result } = renderHook(
      () => useRunStateOverlay("run-live", "live"),
      { wrapper: makeWrapper(client) },
    );

    const es = FakeEventSource.instances[0];

    // Dispatch 20 events inside a single act() — they all land before rAF fires.
    act(() => {
      for (let i = 0; i < 20; i++) {
        es.dispatchNamed("node_transition", {
          node_id: `node-${i}`,
          status: "in_progress",
          started_at: "2024-01-01T00:00:00Z",
          ended_at: null,
          child_task_id: null,
        });
      }
    });

    // Only one rAF should have been scheduled (not 20).
    expect(rafQueue.length).toBe(1);

    act(() => {
      flushRaf();
    });

    await waitFor(() => expect(result.current.nodeStatuses.size).toBe(20));
  });
});

// ---------------------------------------------------------------------------
// Tests: replay mode — REST snapshot
// ---------------------------------------------------------------------------

describe("useRunStateOverlay — replay mode", () => {
  it("populates nodeStatuses from HarnessRunState.nodes_executed", async () => {
    const client = makeClient();
    const { api } = await import("../../api");
    vi.mocked(api.getHarnessRun).mockResolvedValue(mockRunState);

    const { result } = renderHook(
      () => useRunStateOverlay("run-replay", "replay"),
      { wrapper: makeWrapper(client) },
    );

    await waitFor(() => expect(result.current.nodeStatuses.size).toBe(2));

    const nodeA = result.current.nodeStatuses.get("node-a");
    expect(nodeA?.runStatus).toBe("done");
    expect(nodeA?.childTaskId).toBe("task-2");
    expect(nodeA?.startedAt).toBe("2024-01-01T00:00:00Z");
    expect(nodeA?.endedAt).toBe("2024-01-01T00:00:30Z");

    const nodeB = result.current.nodeStatuses.get("node-b");
    expect(nodeB?.runStatus).toBe("failed");
    expect(nodeB?.childTaskId).toBeUndefined();
  });

  it("returns status=ended in replay mode", async () => {
    const client = makeClient();
    const { api } = await import("../../api");
    vi.mocked(api.getHarnessRun).mockResolvedValue(mockRunState);

    const { result } = renderHook(
      () => useRunStateOverlay("run-replay", "replay"),
      { wrapper: makeWrapper(client) },
    );

    expect(result.current.status).toBe("ended");
  });

  it("does not open an EventSource for replay mode", async () => {
    const client = makeClient();
    const { api } = await import("../../api");
    vi.mocked(api.getHarnessRun).mockResolvedValue(mockRunState);

    renderHook(() => useRunStateOverlay("run-replay", "replay"), {
      wrapper: makeWrapper(client),
    });

    expect(FakeEventSource.instances).toHaveLength(0);
  });
});

// ---------------------------------------------------------------------------
// Tests: mode switch — EventSource lifecycle (R mitigation)
// ---------------------------------------------------------------------------

describe("useRunStateOverlay — mode switch", () => {
  it("closes the live EventSource when switching from live to replay", async () => {
    const client = makeClient();
    const { api } = await import("../../api");
    vi.mocked(api.getHarnessRun).mockResolvedValue(mockRunState);

    const { rerender } = renderHook(
      ({ mode }: { mode: "live" | "replay" }) =>
        useRunStateOverlay("run-1", mode),
      {
        wrapper: makeWrapper(client),
        initialProps: { mode: "live" as const },
      },
    );

    expect(FakeEventSource.instances).toHaveLength(1);
    const liveEs = FakeEventSource.instances[0];
    expect(liveEs.closed).toBe(false);

    rerender({ mode: "replay" as const });

    // After switching to replay, the live EventSource must be closed.
    await waitFor(() => expect(liveEs.closed).toBe(true));

    // No new EventSource should be opened for replay.
    expect(FakeEventSource.instances).toHaveLength(1);
  });

  it("resets nodeStatuses and edgeStatuses when runId changes", async () => {
    const client = makeClient();

    const { result, rerender } = renderHook(
      ({ runId }: { runId: string }) => useRunStateOverlay(runId, "live"),
      {
        wrapper: makeWrapper(client),
        initialProps: { runId: "run-1" },
      },
    );

    const es1 = FakeEventSource.instances[0];

    act(() => {
      es1.dispatchNamed("node_transition", {
        node_id: "node-a",
        status: "done",
        started_at: null,
        ended_at: null,
        child_task_id: null,
      });
    });

    act(() => {
      flushRaf();
    });

    await waitFor(() => expect(result.current.nodeStatuses.size).toBe(1));

    // Switch to a new runId.
    rerender({ runId: "run-2" });

    await waitFor(() => expect(result.current.nodeStatuses.size).toBe(0));
    expect(result.current.edgeStatuses.size).toBe(0);
    expect(result.current.bufferTruncated).toBe(false);
  });

  it("does not keep prior live EventSource open after switching to replay (EventSource constructor vs close balance)", async () => {
    // This test mirrors the I7 requirement: spy on EventSource constructor count vs close count.
    const client = makeClient();
    const { api } = await import("../../api");
    vi.mocked(api.getHarnessRun).mockResolvedValue(mockRunState);

    const initialConstructorCount = FakeEventSource.constructorCallCount;
    const initialCloseCount = FakeEventSource.closeCallCount;

    const { rerender } = renderHook(
      ({ mode }: { mode: "live" | "replay" }) =>
        useRunStateOverlay("run-1", mode),
      {
        wrapper: makeWrapper(client),
        initialProps: { mode: "live" as const },
      },
    );

    // One EventSource created for live mode.
    expect(FakeEventSource.constructorCallCount - initialConstructorCount).toBe(1);

    rerender({ mode: "replay" as const });

    // The live EventSource must have been closed.
    await waitFor(() => {
      expect(FakeEventSource.closeCallCount - initialCloseCount).toBeGreaterThanOrEqual(1);
    });

    // No extra EventSource created for replay.
    expect(FakeEventSource.constructorCallCount - initialConstructorCount).toBe(1);
  });

  it("resets bufferTruncated when switching runs", async () => {
    const client = makeClient();

    const { result, rerender } = renderHook(
      ({ runId }: { runId: string }) => useRunStateOverlay(runId, "live"),
      {
        wrapper: makeWrapper(client),
        initialProps: { runId: "run-1" },
      },
    );

    const es1 = FakeEventSource.instances[0];

    act(() => {
      es1.dispatchNamed("buffer_truncated", { message: "overflow" });
    });

    act(() => {
      flushRaf();
    });

    await waitFor(() => expect(result.current.bufferTruncated).toBe(true));

    rerender({ runId: "run-2" });

    await waitFor(() => expect(result.current.bufferTruncated).toBe(false));
  });
});
