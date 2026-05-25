/**
 * Tests for the drag-and-drop behavior added to <Tree /> and <TreeNode />.
 *
 * Strategy: rather than try to simulate real pointer-driven drags in jsdom
 * (which is fragile and not what we own), we mock @dnd-kit/core's DndContext
 * to capture the onDragStart / onDragEnd callbacks Tree passes in, then
 * invoke those callbacks directly with synthetic DragEndEvent objects. This
 * is the "test the boundary, exercise our code" pattern called out in
 * the project's testing guide.
 *
 * We also mock useDndContext and useDroppable so that <TreeNode /> and
 * <GapZone /> can render outside a real DndContext for direct assertions
 * about hover styling.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, act } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { DragEndEvent, DragStartEvent } from "@dnd-kit/core";

// ---------------------------------------------------------------------------
// API mocks — Tree calls api.setParent and api.reorder via mutations.
// These must be mocked BEFORE we import Tree.
// ---------------------------------------------------------------------------

vi.mock("../../api", () => ({
  api: {
    setParent: vi.fn(),
    reorder: vi.fn(),
  },
}));

// ---------------------------------------------------------------------------
// dnd-kit mocks
//
// We replace DndContext with a passthrough that:
//   1. stores the callbacks (onDragStart, onDragEnd, onDragCancel) into a
//      module-level holder so tests can invoke them
//   2. renders children, so the rest of the Tree DOM still mounts
//
// useDroppable returns a stable shape; we expose a helper to toggle `isOver`
// for a specific id when needed.
//
// useSortable and useDndContext are no-op stubs that return the minimum
// shape consumed by Card.tsx and TreeNode.tsx. We let real SortableContext
// pass through; it doesn't break without a real DndContext for our purposes.
// ---------------------------------------------------------------------------

interface DndCallbacks {
  onDragStart?: (e: DragStartEvent) => void;
  onDragEnd?: (e: DragEndEvent) => void;
  onDragCancel?: () => void;
}

const dndState: { callbacks: DndCallbacks; overId: string | null; activeId: string | null } = {
  callbacks: {},
  overId: null,
  activeId: null,
};

vi.mock("@dnd-kit/core", async () => {
  const actual = await vi.importActual<typeof import("@dnd-kit/core")>(
    "@dnd-kit/core",
  );
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const React = (await import("react")) as any;
  return {
    ...actual,
    DndContext: ({
      children,
      onDragStart,
      onDragEnd,
      onDragCancel,
    }: {
      children: React.ReactNode;
      onDragStart?: (e: DragStartEvent) => void;
      onDragEnd?: (e: DragEndEvent) => void;
      onDragCancel?: () => void;
    }) => {
      dndState.callbacks = { onDragStart, onDragEnd, onDragCancel };
      return React.createElement(React.Fragment, null, children);
    },
    DragOverlay: ({ children }: { children: React.ReactNode }) =>
      React.createElement(React.Fragment, null, children),
    useDroppable: ({ id }: { id: string }) => ({
      isOver: dndState.overId === id,
      setNodeRef: () => {},
      node: { current: null },
      rect: { current: null },
      over: null,
      active: null,
    }),
    useDndContext: () => ({
      active: dndState.activeId ? { id: dndState.activeId } : null,
      over: dndState.overId ? { id: dndState.overId } : null,
    }),
    // Keep the real sensor/touch helpers exported but harmless — they're
    // called by Tree.tsx via useSensor/useSensors and must not throw.
    useSensor: () => ({}),
    useSensors: () => [],
    PointerSensor: actual.PointerSensor,
    TouchSensor: actual.TouchSensor,
    closestCenter: actual.closestCenter,
  };
});

vi.mock("@dnd-kit/sortable", async () => {
  const actual = await vi.importActual<typeof import("@dnd-kit/sortable")>(
    "@dnd-kit/sortable",
  );
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const React = (await import("react")) as any;
  return {
    ...actual,
    // Pass-through to render children without needing a real DndContext.
    SortableContext: ({ children }: { children: React.ReactNode }) =>
      React.createElement(React.Fragment, null, children),
    useSortable: () => ({
      attributes: {},
      listeners: {},
      setNodeRef: () => {},
      transform: null,
      transition: undefined,
      isDragging: false,
    }),
  };
});

// Imports must come AFTER the mocks above.
import { Tree } from "../Tree";
import { GapZone } from "../TreeNode";
import { api } from "../../api";
import type { TaskSummary } from "../../types";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeTask(overrides: Partial<TaskSummary> = {}): TaskSummary {
  return {
    id: "task-1",
    space_id: "space-1",
    title: "Test task",
    state: "backlog",
    created_at: "2024-01-01T00:00:00Z",
    updated_at: "2024-01-01T00:00:00Z",
    waiting_question: null,
    brief_preview: "",
    priority: 3,
    manual_order: 0,
    agent_mode: "auto",
    space_name: null,
    space_color: null,
    space_icon: null,
    ...overrides,
  };
}

function renderTree(tasks: TaskSummary[]) {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <Tree tasks={tasks} />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

/**
 * Build a synthetic DragEndEvent. We only populate the fields Tree.onDragEnd
 * actually reads: e.active.id, e.over (or null), e.over.id.
 */
function dragEnd(activeId: string, overId: string | null): DragEndEvent {
  return {
    active: { id: activeId } as DragEndEvent["active"],
    over: overId === null ? null : ({ id: overId } as DragEndEvent["over"]),
    collisions: null,
    delta: { x: 0, y: 0 },
    activatorEvent: new Event("pointerdown"),
  } as DragEndEvent;
}

async function fireDragEnd(activeId: string, overId: string | null) {
  if (!dndState.callbacks.onDragEnd) {
    throw new Error(
      "Tree did not register an onDragEnd callback — check DndContext mock",
    );
  }
  await act(async () => {
    await dndState.callbacks.onDragEnd!(dragEnd(activeId, overId));
  });
}

beforeEach(() => {
  dndState.callbacks = {};
  dndState.overId = null;
  dndState.activeId = null;
  vi.mocked(api.setParent).mockReset();
  vi.mocked(api.reorder).mockReset();
  // Default both mutations to resolve successfully — tests override per-case.
  vi.mocked(api.setParent).mockResolvedValue({} as never);
  vi.mocked(api.reorder).mockResolvedValue(undefined as never);
});

// ===========================================================================
// 1. GapZone — visual hover indicator
// ===========================================================================

describe("GapZone — visual hover indicator", () => {
  it("renders a div with hit-area sizing (h-4) and is aria-hidden", () => {
    dndState.overId = null;

    const { container } = render(<GapZone id="gap:foo" depth={0} />);

    const root = container.firstElementChild as HTMLElement;
    expect(root).not.toBeNull();
    expect(root.className).toContain("h-4");
    expect(root.getAttribute("aria-hidden")).toBe("true");
  });

  it("renders the inner line with bg-transparent when isOver=false", () => {
    dndState.overId = null;

    const { container } = render(<GapZone id="gap:foo" depth={0} />);

    // GapZone is <outer><inner-line/></outer>; outer is firstElementChild.
    const outer = container.firstElementChild as HTMLElement;
    const inner = outer.firstElementChild as HTMLElement;
    expect(inner).not.toBeNull();
    expect(inner.className).toContain("bg-transparent");
    expect(inner.className).not.toContain("bg-ink");
  });

  it("renders the inner line with bg-ink when isOver=true", () => {
    dndState.overId = "gap:foo";

    const { container } = render(<GapZone id="gap:foo" depth={0} />);

    const outer = container.firstElementChild as HTMLElement;
    const inner = outer.firstElementChild as HTMLElement;
    expect(inner).not.toBeNull();
    expect(inner.className).toContain("bg-ink");
    expect(inner.className).not.toContain("bg-transparent");
  });

  it("scales paddingLeft by the depth prop using the --tree-indent CSS var", () => {
    dndState.overId = null;

    const { container: shallow } = render(<GapZone id="gap:a" depth={0} />);
    const { container: deep } = render(<GapZone id="gap:b" depth={3} />);

    const shallowPad = (shallow.firstElementChild as HTMLElement).style
      .paddingLeft;
    const deepPad = (deep.firstElementChild as HTMLElement).style.paddingLeft;
    expect(shallowPad).toMatch(/calc\(0 \*/);
    expect(deepPad).toMatch(/calc\(3 \*/);
    expect(shallowPad).not.toBe(deepPad);
  });
});

// ===========================================================================
// 2. Tree renders gap-end:root and per-task GapZones
// ===========================================================================

describe("<Tree /> — GapZone DOM structure", () => {
  it("renders the gap-end:root terminal gap as the last child of the tree container", () => {
    const tasks = [makeTask({ id: "a", title: "A" })];

    const { container } = renderTree(tasks);

    // The terminal gap is rendered as an aria-hidden div with h-4. With one
    // root task we expect at least two aria-hidden gap zones: the "above"
    // gap for task A and the gap-end:root terminal gap.
    const gaps = container.querySelectorAll('[aria-hidden="true"].h-4');
    expect(gaps.length).toBeGreaterThanOrEqual(2);
  });

  it("renders no gap-end:root when there are no tasks (empty state shown instead)", () => {
    const { container } = renderTree([]);

    expect(screen.getByText("No tasks")).toBeInTheDocument();
    const gaps = container.querySelectorAll('[aria-hidden="true"].h-4');
    expect(gaps.length).toBe(0);
  });

  it("renders the gap-end:<parent> terminal gap when an expanded parent has children", () => {
    const tasks = [
      makeTask({ id: "p", title: "Parent" }),
      makeTask({ id: "c", title: "Child", parent_id: "p" }),
    ];

    // Open the parent so its children + terminal gap render.
    const { container } = render(
      <QueryClientProvider
        client={
          new QueryClient({ defaultOptions: { queries: { retry: false } } })
        }
      >
        <MemoryRouter initialEntries={["/?task=c"]}>
          <Tree tasks={tasks} />
        </MemoryRouter>
      </QueryClientProvider>,
    );

    // Two task gap zones (above-A, above-C), one gap-end:p (after children of p),
    // and one gap-end:root (terminal). At least 4 gap zones total.
    const gaps = container.querySelectorAll('[aria-hidden="true"].h-4');
    expect(gaps.length).toBeGreaterThanOrEqual(4);
  });
});

// ===========================================================================
// 3. Active-state cards get a "Cannot move" tooltip on their wrapper
// ===========================================================================

describe("<Tree /> — active task drag suppression", () => {
  it('puts title="Cannot move a running task" on the active task\'s card wrapper', () => {
    const tasks = [
      makeTask({ id: "running", title: "Running task", state: "active" }),
    ];

    renderTree(tasks);

    const tooltipWrapper = document.querySelector(
      '[title="Cannot move a running task"]',
    );
    expect(tooltipWrapper).not.toBeNull();
    // The Card heading sits inside that wrapper.
    expect(
      tooltipWrapper!.querySelector("h3")?.textContent,
    ).toBe("Running task");
  });

  it("does NOT put the tooltip on non-active tasks", () => {
    const tasks = [
      makeTask({ id: "calm", title: "Calm task", state: "backlog" }),
    ];

    renderTree(tasks);

    expect(
      document.querySelector('[title="Cannot move a running task"]'),
    ).toBeNull();
  });
});

// ===========================================================================
// 4. onDragEnd — reparent on card-body drop
// ===========================================================================

describe("<Tree /> onDragEnd — drop on card body (reparent)", () => {
  it("calls api.setParent(dragged, target) when over.id is a plain task id", async () => {
    const tasks = [
      makeTask({ id: "child", title: "Child" }),
      makeTask({ id: "target", title: "Target parent" }),
    ];

    renderTree(tasks);
    await fireDragEnd("child", "target");

    expect(api.setParent).toHaveBeenCalledTimes(1);
    expect(api.setParent).toHaveBeenCalledWith("child", "target");
    // No reorder when only reparenting.
    expect(api.reorder).not.toHaveBeenCalled();
  });

  it("is a no-op when active and over have the same id (self-drop)", async () => {
    const tasks = [makeTask({ id: "solo", title: "Solo" })];

    renderTree(tasks);
    await fireDragEnd("solo", "solo");

    expect(api.setParent).not.toHaveBeenCalled();
    expect(api.reorder).not.toHaveBeenCalled();
  });

  it("is a no-op when over is null (drop outside any drop zone)", async () => {
    const tasks = [makeTask({ id: "x", title: "X" })];

    renderTree(tasks);
    await fireDragEnd("x", null);

    expect(api.setParent).not.toHaveBeenCalled();
    expect(api.reorder).not.toHaveBeenCalled();
  });

  it("is a no-op when the dragged task does not exist in the tree's tasks", async () => {
    const tasks = [makeTask({ id: "real", title: "Real" })];

    renderTree(tasks);
    await fireDragEnd("ghost", "real");

    expect(api.setParent).not.toHaveBeenCalled();
    expect(api.reorder).not.toHaveBeenCalled();
  });

  it("is a no-op when the dragged task is in active state (cannot move running)", async () => {
    const tasks = [
      makeTask({ id: "running", title: "Running", state: "active" }),
      makeTask({ id: "target", title: "Target" }),
    ];

    renderTree(tasks);
    await fireDragEnd("running", "target");

    expect(api.setParent).not.toHaveBeenCalled();
    expect(api.reorder).not.toHaveBeenCalled();
  });
});

// ===========================================================================
// 5. onDragEnd — gap drop triggers reorder
// ===========================================================================

describe("<Tree /> onDragEnd — gap drop (sibling reorder)", () => {
  it("calls api.reorder with the lane and the new task order (same-parent gap)", async () => {
    // Three siblings in the same lane (backlog) and same parent (none).
    const tasks = [
      makeTask({ id: "a", title: "A", manual_order: 0 }),
      makeTask({ id: "b", title: "B", manual_order: 1 }),
      makeTask({ id: "c", title: "C", manual_order: 2 }),
    ];

    renderTree(tasks);
    // Drop C into the gap above B → expected order: a, c, b.
    await fireDragEnd("c", "gap:b");

    expect(api.setParent).not.toHaveBeenCalled(); // same parent
    expect(api.reorder).toHaveBeenCalledTimes(1);
    expect(api.reorder).toHaveBeenCalledWith("backlog", ["a", "c", "b"]);
  });

  it("excludes tasks from other lanes when computing the new order", async () => {
    const tasks = [
      makeTask({ id: "a", title: "A", state: "backlog", manual_order: 0 }),
      makeTask({ id: "b", title: "B", state: "backlog", manual_order: 1 }),
      makeTask({ id: "d", title: "D", state: "done", manual_order: 0 }),
    ];

    renderTree(tasks);
    await fireDragEnd("a", "gap:b");

    expect(api.reorder).toHaveBeenCalledWith("backlog", ["a", "b"]);
    // D is in lane=done and must not appear in the reorder payload.
  });

  it("sends the dragged task FIRST when dropped before the first sibling", async () => {
    const tasks = [
      makeTask({ id: "a", title: "A", manual_order: 0 }),
      makeTask({ id: "b", title: "B", manual_order: 1 }),
      makeTask({ id: "c", title: "C", manual_order: 2 }),
    ];

    renderTree(tasks);
    await fireDragEnd("c", "gap:a");

    expect(api.reorder).toHaveBeenCalledWith("backlog", ["c", "a", "b"]);
  });
});

// ===========================================================================
// 6. onDragEnd — gap drop with parent change
// ===========================================================================

describe("<Tree /> onDragEnd — gap drop with reparent", () => {
  it("calls setParent THEN reorder when the gap target has a different parent", async () => {
    const tasks = [
      makeTask({ id: "p1", title: "Parent1" }),
      makeTask({ id: "p2", title: "Parent2" }),
      makeTask({ id: "x", title: "X", parent_id: "p1", manual_order: 0 }),
      makeTask({ id: "y", title: "Y", parent_id: "p2", manual_order: 0 }),
    ];

    renderTree(tasks);
    // Drop X (parent=p1) into the gap above Y (parent=p2):
    // → reparent X under p2, then reorder backlog lane to put X before Y.
    await fireDragEnd("x", "gap:y");

    expect(api.setParent).toHaveBeenCalledTimes(1);
    expect(api.setParent).toHaveBeenCalledWith("x", "p2");
    expect(api.reorder).toHaveBeenCalledTimes(1);

    // setParent must complete before reorder (await chain in Tree.onDragEnd).
    const setParentOrder = vi.mocked(api.setParent).mock.invocationCallOrder[0];
    const reorderOrder = vi.mocked(api.reorder).mock.invocationCallOrder[0];
    expect(setParentOrder).toBeLessThan(reorderOrder);
  });

  it("does NOT call setParent when both source and target gap share the same parent", async () => {
    const tasks = [
      makeTask({ id: "p", title: "Parent" }),
      makeTask({ id: "x", title: "X", parent_id: "p", manual_order: 0 }),
      makeTask({ id: "y", title: "Y", parent_id: "p", manual_order: 1 }),
    ];

    renderTree(tasks);
    await fireDragEnd("y", "gap:x");

    expect(api.setParent).not.toHaveBeenCalled();
    expect(api.reorder).toHaveBeenCalledTimes(1);
  });
});

// ===========================================================================
// 7. onDragEnd — gap-end drops
// ===========================================================================

describe("<Tree /> onDragEnd — gap-end drops", () => {
  it("treats gap-end:root as appending under no parent", async () => {
    const tasks = [
      makeTask({ id: "a", title: "A", manual_order: 0 }),
      makeTask({ id: "b", title: "B", manual_order: 1 }),
    ];

    renderTree(tasks);
    // A is already root-level (no parent) → no setParent call, just reorder
    // with A moved to the end.
    await fireDragEnd("a", "gap-end:root");

    expect(api.setParent).not.toHaveBeenCalled();
    expect(api.reorder).toHaveBeenCalledTimes(1);
    expect(api.reorder).toHaveBeenCalledWith("backlog", ["b", "a"]);
  });

  it("treats gap-end:<parentId> as appending under that parent (reparent + reorder)", async () => {
    // Parent is in a different lane so it doesn't pollute the reorder payload.
    const tasks = [
      makeTask({ id: "p", title: "Parent", state: "done" }),
      makeTask({
        id: "child",
        title: "Child",
        parent_id: "p",
        state: "backlog",
        manual_order: 0,
      }),
      makeTask({
        id: "loose",
        title: "Loose",
        state: "backlog",
        manual_order: 1,
      }),
    ];

    renderTree(tasks);
    // Drop loose under parent p as the last child.
    await fireDragEnd("loose", "gap-end:p");

    expect(api.setParent).toHaveBeenCalledTimes(1);
    expect(api.setParent).toHaveBeenCalledWith("loose", "p");
    expect(api.reorder).toHaveBeenCalledTimes(1);
    // Only backlog-lane tasks (child, loose) are in the reorder payload;
    // parent "p" is in lane=done and must be excluded.
    expect(api.reorder).toHaveBeenCalledWith("backlog", ["child", "loose"]);
  });

  it("uses null parent_id when appending to gap-end:root for an already-rooted task", async () => {
    const tasks = [
      makeTask({ id: "p", title: "P" }),
      makeTask({ id: "x", title: "X", parent_id: "p" }),
    ];

    renderTree(tasks);
    // X has parent=p; drop on gap-end:root → reparent to null, then reorder.
    await fireDragEnd("x", "gap-end:root");

    expect(api.setParent).toHaveBeenCalledTimes(1);
    expect(api.setParent).toHaveBeenCalledWith("x", null);
  });
});

// ===========================================================================
// 8. API error → toast appears with role=alert
// ===========================================================================

describe("<Tree /> onDragEnd — error handling", () => {
  it("shows a role=alert toast with the error detail when setParent rejects", async () => {
    vi.mocked(api.setParent).mockRejectedValueOnce(
      new Error('400 Bad Request: {"detail":"Cycle detected"}'),
    );
    const tasks = [
      makeTask({ id: "child", title: "Child" }),
      makeTask({ id: "target", title: "Target" }),
    ];

    renderTree(tasks);
    await fireDragEnd("child", "target");

    await waitFor(() => {
      const alert = screen.getByRole("alert");
      expect(alert).toBeInTheDocument();
      expect(alert.textContent).toContain("Cycle detected");
    });
  });

  it("shows the raw error message when no JSON detail is parseable", async () => {
    vi.mocked(api.setParent).mockRejectedValueOnce(new Error("network down"));
    const tasks = [
      makeTask({ id: "a", title: "A" }),
      makeTask({ id: "b", title: "B" }),
    ];

    renderTree(tasks);
    await fireDragEnd("a", "b");

    await waitFor(() => {
      const alert = screen.getByRole("alert");
      expect(alert.textContent).toContain("network down");
    });
  });

  it("shows a toast when a gap-drop reorder rejects (going through the gap branch)", async () => {
    vi.mocked(api.reorder).mockRejectedValueOnce(
      new Error('500: {"detail":"DB unavailable"}'),
    );
    const tasks = [
      makeTask({ id: "a", title: "A", manual_order: 0 }),
      makeTask({ id: "b", title: "B", manual_order: 1 }),
    ];

    renderTree(tasks);
    await fireDragEnd("a", "gap:b");

    await waitFor(() => {
      const alert = screen.getByRole("alert");
      expect(alert.textContent).toContain("DB unavailable");
    });
  });

  it("does NOT show a toast when the operation succeeds", async () => {
    const tasks = [
      makeTask({ id: "a", title: "A" }),
      makeTask({ id: "b", title: "B" }),
    ];

    renderTree(tasks);
    await fireDragEnd("a", "b");

    // setParent resolved by beforeEach default. Allow microtasks to flush.
    await act(async () => {
      await Promise.resolve();
    });
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });
});

// ===========================================================================
// 9. onDragStart / onDragCancel
// ===========================================================================

describe("<Tree /> onDragStart and onDragCancel", () => {
  it("registers onDragStart with the DndContext", () => {
    renderTree([makeTask({ id: "a", title: "A" })]);

    expect(typeof dndState.callbacks.onDragStart).toBe("function");
  });

  it("registers onDragCancel with the DndContext", () => {
    renderTree([makeTask({ id: "a", title: "A" })]);

    expect(typeof dndState.callbacks.onDragCancel).toBe("function");
  });

  it("onDragStart with a known id sets the active task (DragOverlay would render it)", () => {
    renderTree([makeTask({ id: "a", title: "A" })]);

    // Invoking onDragStart for an existing task must not throw.
    expect(() => {
      dndState.callbacks.onDragStart!({
        active: { id: "a" } as DragStartEvent["active"],
      } as DragStartEvent);
    }).not.toThrow();
  });

  it("onDragStart with an unknown id is a silent no-op (no throw)", () => {
    renderTree([makeTask({ id: "a", title: "A" })]);

    expect(() => {
      dndState.callbacks.onDragStart!({
        active: { id: "missing" } as DragStartEvent["active"],
      } as DragStartEvent);
    }).not.toThrow();
  });

  it("onDragCancel does not throw", () => {
    renderTree([makeTask({ id: "a", title: "A" })]);

    expect(() => dndState.callbacks.onDragCancel!()).not.toThrow();
  });
});

// ===========================================================================
// 10. extractDetail behavior (exercised via the toast text)
// ===========================================================================

describe("<Tree /> error detail extraction", () => {
  it("strips the HTTP-status prefix from the toast when JSON detail is present", async () => {
    vi.mocked(api.setParent).mockRejectedValueOnce(
      new Error('409 Conflict: {"detail":"Would create cycle"}'),
    );
    renderTree([
      makeTask({ id: "a", title: "A" }),
      makeTask({ id: "b", title: "B" }),
    ]);

    await fireDragEnd("a", "b");

    await waitFor(() => {
      const alert = screen.getByRole("alert");
      // The detail field is what's shown — NOT the full "409 Conflict: ..." text.
      expect(alert.textContent).toBe("Would create cycle");
    });
  });

  it("falls back to the full message when the JSON tail is malformed", async () => {
    vi.mocked(api.setParent).mockRejectedValueOnce(
      new Error("oops {not really json"),
    );
    renderTree([
      makeTask({ id: "a", title: "A" }),
      makeTask({ id: "b", title: "B" }),
    ]);

    await fireDragEnd("a", "b");

    await waitFor(() => {
      const alert = screen.getByRole("alert");
      expect(alert.textContent).toContain("oops");
    });
  });
});
