import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useLiveStream } from "../useLiveStream";

// In-process EventSource shim — no real network connections in tests.
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

  // Test helpers
  dispatchOpen() {
    this.onopen?.();
  }
  dispatchMessage(data: object) {
    this.onmessage?.({ data: JSON.stringify(data) } as MessageEvent);
  }
  dispatchError() {
    this.onerror?.(new Event("error"));
  }
  dispatchCustom(type: string) {
    const fns = this._listeners.get(type) ?? [];
    fns.forEach((fn) => fn(new Event(type)));
  }
}

describe("useLiveStream", () => {
  beforeEach(() => {
    FakeEventSource.instances = [];
    vi.stubGlobal("EventSource", FakeEventSource);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("starts in connecting status when enabled", () => {
    const { result } = renderHook(() => useLiveStream("task-1", true));
    expect(result.current.status).toBe("connecting");
    expect(result.current.entries).toHaveLength(0);
  });

  it("ends immediately and creates no EventSource when disabled", () => {
    const { result } = renderHook(() => useLiveStream("task-1", false));
    expect(result.current.status).toBe("ended");
    expect(FakeEventSource.instances).toHaveLength(0);
  });

  it("creates EventSource with the correct URL", () => {
    renderHook(() => useLiveStream("task-abc", true));
    expect(FakeEventSource.instances).toHaveLength(1);
    expect(FakeEventSource.instances[0].url).toBe("/api/tasks/task-abc/stream");
  });

  it("closes EventSource on unmount (guards against reconnect storms)", () => {
    const { unmount } = renderHook(() => useLiveStream("task-1", true));
    const es = FakeEventSource.instances[0];
    expect(es.closed).toBe(false);
    unmount();
    expect(es.closed).toBe(true);
  });

  it("closes old and creates new EventSource when enabled flips off then on", () => {
    const { rerender } = renderHook(
      ({ enabled }: { enabled: boolean }) => useLiveStream("task-1", enabled),
      { initialProps: { enabled: true } },
    );
    const first = FakeEventSource.instances[0];

    rerender({ enabled: false });
    expect(first.closed).toBe(true);
    expect(FakeEventSource.instances).toHaveLength(1); // no new ES while disabled

    rerender({ enabled: true });
    expect(FakeEventSource.instances).toHaveLength(2);
    expect(FakeEventSource.instances[1].closed).toBe(false);
  });

  it("closes old EventSource when taskId changes (prevents duplicate connections)", () => {
    const { rerender } = renderHook(
      ({ taskId }: { taskId: string }) => useLiveStream(taskId, true),
      { initialProps: { taskId: "task-1" } },
    );
    const first = FakeEventSource.instances[0];

    rerender({ taskId: "task-2" });

    expect(first.closed).toBe(true);
    expect(FakeEventSource.instances).toHaveLength(2);
    expect(FakeEventSource.instances[1].url).toBe("/api/tasks/task-2/stream");
  });

  it("sets status to 'live' on open", () => {
    const { result } = renderHook(() => useLiveStream("task-1", true));
    const es = FakeEventSource.instances[0];
    act(() => es.dispatchOpen());
    expect(result.current.status).toBe("live");
  });

  it("sets status to 'error' on EventSource error", () => {
    const { result } = renderHook(() => useLiveStream("task-1", true));
    const es = FakeEventSource.instances[0];
    act(() => es.dispatchError());
    expect(result.current.status).toBe("error");
  });

  it("sets status to 'ended' and closes ES when 'end' event fires", () => {
    const { result } = renderHook(() => useLiveStream("task-1", true));
    const es = FakeEventSource.instances[0];
    act(() => es.dispatchCustom("end"));
    expect(result.current.status).toBe("ended");
    expect(es.closed).toBe(true);
  });

  it("parses assistant text events into entries", () => {
    const { result } = renderHook(() => useLiveStream("task-1", true));
    const es = FakeEventSource.instances[0];

    act(() => {
      es.dispatchMessage({
        type: "assistant",
        message: { content: [{ type: "text", text: "Hello world" }] },
      });
    });

    expect(result.current.entries).toHaveLength(1);
    expect(result.current.entries[0]).toMatchObject({
      kind: "assistant",
      text: "Hello world",
    });
  });

  it("parses tool_use blocks from assistant events", () => {
    const { result } = renderHook(() => useLiveStream("task-1", true));
    const es = FakeEventSource.instances[0];

    act(() => {
      es.dispatchMessage({
        type: "assistant",
        message: {
          content: [
            {
              type: "tool_use",
              id: "tu-1",
              name: "Read",
              input: { file_path: "/foo.ts" },
            },
          ],
        },
      });
    });

    expect(result.current.entries).toHaveLength(1);
    expect(result.current.entries[0]).toMatchObject({
      kind: "tool_call",
      toolUseId: "tu-1",
      name: "Read",
    });
  });

  it("parses thinking blocks from assistant events", () => {
    const { result } = renderHook(() => useLiveStream("task-1", true));
    const es = FakeEventSource.instances[0];

    act(() => {
      es.dispatchMessage({
        type: "assistant",
        message: {
          content: [{ type: "thinking", thinking: "Let me think…" }],
        },
      });
    });

    expect(result.current.entries[0]).toMatchObject({
      kind: "thinking",
      text: "Let me think…",
    });
  });

  it("parses tool_result from user events", () => {
    const { result } = renderHook(() => useLiveStream("task-1", true));
    const es = FakeEventSource.instances[0];

    act(() => {
      es.dispatchMessage({
        type: "user",
        message: {
          content: [
            {
              type: "tool_result",
              tool_use_id: "tu-1",
              content: "file contents here",
              is_error: false,
            },
          ],
        },
      });
    });

    expect(result.current.entries[0]).toMatchObject({
      kind: "tool_result",
      toolUseId: "tu-1",
      output: "file contents here",
      isError: false,
    });
  });

  it("parses system events", () => {
    const { result } = renderHook(() => useLiveStream("task-1", true));
    const es = FakeEventSource.instances[0];

    act(() => {
      es.dispatchMessage({ type: "system", subtype: "info" });
    });

    expect(result.current.entries[0]).toMatchObject({ kind: "system" });
  });

  it("ignores malformed JSON without throwing", () => {
    const { result } = renderHook(() => useLiveStream("task-1", true));
    const es = FakeEventSource.instances[0];

    act(() => {
      es.onmessage?.({ data: "not valid json{{{" } as MessageEvent);
    });

    expect(result.current.entries).toHaveLength(0);
    expect(result.current.status).toBe("connecting");
  });

  it("clears entries on run_start after a run_end (prevents doubled history)", () => {
    const { result } = renderHook(() => useLiveStream("task-1", true));
    const es = FakeEventSource.instances[0];

    act(() => {
      es.dispatchMessage({
        type: "assistant",
        message: { content: [{ type: "text", text: "First run output" }] },
      });
      es.dispatchMessage({ type: "run_end" });
    });
    expect(result.current.entries).toHaveLength(1);

    // A new run starts — should clear the first run's entries
    act(() => {
      es.dispatchMessage({ type: "run_start" });
    });
    expect(result.current.entries).toHaveLength(0);
  });

  it("does NOT clear entries on run_start when no prior run_end was seen", () => {
    const { result } = renderHook(() => useLiveStream("task-1", true));
    const es = FakeEventSource.instances[0];

    act(() => {
      es.dispatchMessage({
        type: "assistant",
        message: { content: [{ type: "text", text: "Live output" }] },
      });
      // run_start without a preceding run_end
      es.dispatchMessage({ type: "run_start" });
    });

    expect(result.current.entries).toHaveLength(1);
  });

  it("removes 'end' event listener on cleanup", () => {
    const { unmount } = renderHook(() => useLiveStream("task-1", true));
    const es = FakeEventSource.instances[0];
    // Confirm listener was registered
    expect((es as unknown as { _listeners: Map<string, unknown[]> })._listeners.get("end")).toHaveLength(1);
    unmount();
    expect((es as unknown as { _listeners: Map<string, unknown[]> })._listeners.get("end")).toHaveLength(0);
  });
});
