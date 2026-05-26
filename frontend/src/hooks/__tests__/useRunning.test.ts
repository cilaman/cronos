import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useRunning } from "../useRunning";

// ---------------------------------------------------------------------------
// EventSource mock
// ---------------------------------------------------------------------------

type ESListener = (e: { data: string }) => void;

class MockEventSource {
  static instances: MockEventSource[] = [];
  url: string;
  onmessage: ESListener | null = null;
  onerror: (() => void) | null = null;
  closed = false;

  constructor(url: string) {
    this.url = url;
    MockEventSource.instances.push(this);
  }

  dispatch(data: unknown) {
    this.onmessage?.({ data: JSON.stringify(data) });
  }

  close() {
    this.closed = true;
  }
}

beforeEach(() => {
  MockEventSource.instances = [];
  vi.stubGlobal("EventSource", MockEventSource);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function lastES(): MockEventSource {
  const es = MockEventSource.instances.at(-1);
  if (!es) throw new Error("No EventSource created");
  return es;
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("useRunning — SSE reducer", () => {
  it("adds a task id on run_start", () => {
    const { result } = renderHook(() => useRunning("space-1"));

    act(() => lastES().dispatch({ type: "run_start", task_id: "task-a" }));

    expect(result.current.isRunning("task-a")).toBe(true);
  });

  it("removes a task id on run_end", () => {
    const { result } = renderHook(() => useRunning("space-1"));

    act(() => lastES().dispatch({ type: "run_start", task_id: "task-a" }));
    expect(result.current.isRunning("task-a")).toBe(true);

    act(() => lastES().dispatch({ type: "run_end", task_id: "task-a" }));
    expect(result.current.isRunning("task-a")).toBe(false);
  });

  it("tracks multiple running tasks independently", () => {
    const { result } = renderHook(() => useRunning("space-1"));
    const es = lastES();

    act(() => {
      es.dispatch({ type: "run_start", task_id: "goal-1" });
      es.dispatch({ type: "run_start", task_id: "child-1" });
    });

    expect(result.current.isRunning("goal-1")).toBe(true);
    expect(result.current.isRunning("child-1")).toBe(true);

    act(() => es.dispatch({ type: "run_end", task_id: "child-1" }));

    expect(result.current.isRunning("goal-1")).toBe(true);
    expect(result.current.isRunning("child-1")).toBe(false);
  });

  it("ignores events without task_id", () => {
    const { result } = renderHook(() => useRunning("space-1"));

    act(() => lastES().dispatch({ type: "run_start" }));

    expect(result.current.isRunning("task-a")).toBe(false);
  });

  it("ignores unknown event types", () => {
    const { result } = renderHook(() => useRunning("space-1"));

    act(() => lastES().dispatch({ type: "assistant", task_id: "task-a" }));

    expect(result.current.isRunning("task-a")).toBe(false);
  });

  it("run_end on unknown id is a no-op", () => {
    const { result } = renderHook(() => useRunning("space-1"));

    act(() => lastES().dispatch({ type: "run_end", task_id: "ghost" }));

    expect(result.current.isRunning("ghost")).toBe(false);
  });
});

describe("useRunning — seed", () => {
  it("seed populates initial running set", () => {
    const { result } = renderHook(() => useRunning("space-1"));

    act(() => result.current.seed(["task-a", "task-b"]));

    expect(result.current.isRunning("task-a")).toBe(true);
    expect(result.current.isRunning("task-b")).toBe(true);
  });

  it("seed is idempotent for already-running ids", () => {
    const { result } = renderHook(() => useRunning("space-1"));

    act(() => result.current.seed(["task-a"]));
    act(() => result.current.seed(["task-a"]));

    expect(result.current.isRunning("task-a")).toBe(true);
  });

  it("seed with empty array is a no-op", () => {
    const { result } = renderHook(() => useRunning("space-1"));

    act(() => lastES().dispatch({ type: "run_start", task_id: "task-a" }));
    act(() => result.current.seed([]));

    expect(result.current.isRunning("task-a")).toBe(true);
  });

  it("SSE run_end removes a seed-added id", () => {
    const { result } = renderHook(() => useRunning("space-1"));

    act(() => result.current.seed(["task-a"]));
    expect(result.current.isRunning("task-a")).toBe(true);

    act(() => lastES().dispatch({ type: "run_end", task_id: "task-a" }));
    expect(result.current.isRunning("task-a")).toBe(false);
  });
});

describe("useRunning — lifecycle", () => {
  it("opens EventSource with the correct space URL", () => {
    renderHook(() => useRunning("my-space"));
    expect(lastES().url).toBe("/api/spaces/my-space/stream");
  });

  it("does not open EventSource when spaceId is null", () => {
    const before = MockEventSource.instances.length;
    renderHook(() => useRunning(null));
    expect(MockEventSource.instances.length).toBe(before);
  });

  it("closes EventSource on unmount", () => {
    const { unmount } = renderHook(() => useRunning("space-1"));
    const es = lastES();
    unmount();
    expect(es.closed).toBe(true);
  });

  it("resets running set when spaceId changes", () => {
    const { result, rerender } = renderHook(
      ({ id }: { id: string | null }) => useRunning(id),
      { initialProps: { id: "space-1" } },
    );

    act(() => lastES().dispatch({ type: "run_start", task_id: "task-a" }));
    expect(result.current.isRunning("task-a")).toBe(true);

    act(() => rerender({ id: "space-2" }));

    expect(result.current.isRunning("task-a")).toBe(false);
  });
});
