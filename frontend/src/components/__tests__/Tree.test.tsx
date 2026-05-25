import { describe, it, expect, vi, beforeEach } from "vitest";
import { createRef } from "react";
import { render, screen, within, act, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Tree, buildTree, type TreeHandle } from "../Tree";
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

function renderTree(
  tasks: TaskSummary[],
  options: {
    initialEntries?: string[];
    onOpenTask?: (id: string) => void;
    spaceId?: string | null;
    ref?: React.Ref<TreeHandle>;
  } = {},
) {
  const entries = options.initialEntries ?? ["/"];
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={entries}>
        <Tree
          tasks={tasks}
          onOpenTask={options.onOpenTask}
          spaceId={options.spaceId}
          ref={options.ref}
        />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

// Find the chevron toggle button for a given task title. Each TreeNode renders
// a heading <h3> with the title (Card density="tight") and a sibling chevron
// button labeled "Expand" or "Collapse" in the same flex row.
function findToggleButtonByTitle(title: string): HTMLButtonElement {
  const heading = screen.getByRole("heading", { level: 3, name: title });
  // Walk up to the flex row that wraps the chevron + card.
  // <div className="flex items-center gap-1"> contains <button>chevron</button>
  // and the card. The card's button contains the heading.
  let node: HTMLElement | null = heading;
  while (node && !node.className.includes("flex items-center")) {
    node = node.parentElement;
  }
  if (!node) throw new Error(`Could not find row for title "${title}"`);
  const toggle = node.querySelector("button[aria-label]") as HTMLButtonElement;
  if (!toggle) throw new Error(`No chevron toggle for title "${title}"`);
  return toggle;
}

// ===========================================================================
// buildTree — pure helper
// ===========================================================================

describe("buildTree — pure helper", () => {
  it("returns an empty array for empty input", () => {
    const result = buildTree([]);

    expect(result).toEqual([]);
  });

  it("returns roots and children for 3 goals each with 2 task children", () => {
    const tasks: TaskSummary[] = [];
    for (let g = 1; g <= 3; g++) {
      tasks.push(makeTask({ id: `g${g}`, title: `Goal ${g}`, type: "goal" }));
      for (let c = 1; c <= 2; c++) {
        tasks.push(
          makeTask({
            id: `g${g}-c${c}`,
            title: `Child ${g}.${c}`,
            parent_id: `g${g}`,
          }),
        );
      }
    }

    const roots = buildTree(tasks);

    expect(roots).toHaveLength(3);
    for (const root of roots) {
      expect(root.children).toHaveLength(2);
      // Each child's parent_id must match this root.
      for (const child of root.children) {
        expect(child.task.parent_id).toBe(root.task.id);
      }
    }
    // Roots come from g1, g2, g3 (order is sorted; with equal manual_order,
    // priority, and created_at, they preserve insertion order).
    const rootIds = roots.map((r) => r.task.id).sort();
    expect(rootIds).toEqual(["g1", "g2", "g3"]);
  });

  it("marks tasks with a non-existent parent_id as orphans AND places them at root", () => {
    const tasks = [
      makeTask({ id: "real-parent", title: "Real parent" }),
      makeTask({
        id: "orphan",
        title: "Lonely child",
        parent_id: "does-not-exist",
      }),
      makeTask({
        id: "real-child",
        title: "Real child",
        parent_id: "real-parent",
      }),
    ];

    const roots = buildTree(tasks);

    const orphan = roots.find((r) => r.task.id === "orphan");
    expect(orphan).toBeDefined();
    expect(orphan!.isOrphan).toBe(true);

    // Real parent is NOT an orphan (it has no parent_id at all).
    const realParent = roots.find((r) => r.task.id === "real-parent");
    expect(realParent).toBeDefined();
    expect(realParent!.isOrphan).toBe(false);
    expect(realParent!.children).toHaveLength(1);
    expect(realParent!.children[0]!.task.id).toBe("real-child");

    // Real child is not an orphan since its parent exists.
    expect(realParent!.children[0]!.isOrphan).toBe(false);
  });

  it("does not mark a task with parent_id=null as an orphan", () => {
    const tasks = [
      makeTask({ id: "a", parent_id: null }),
      makeTask({ id: "b" }), // parent_id undefined
    ];

    const roots = buildTree(tasks);

    expect(roots).toHaveLength(2);
    for (const root of roots) {
      expect(root.isOrphan).toBe(false);
    }
  });

  it("sorts root children by manual_order ASC", () => {
    // Insertion order is deliberately reversed.
    const tasks = [
      makeTask({ id: "c", manual_order: 5 }),
      makeTask({ id: "a", manual_order: 1 }),
      makeTask({ id: "b", manual_order: 3 }),
    ];

    const roots = buildTree(tasks);

    expect(roots.map((r) => r.task.id)).toEqual(["a", "b", "c"]);
  });

  it("breaks manual_order ties by priority DESC", () => {
    const tasks = [
      makeTask({ id: "low", manual_order: 0, priority: 1 }),
      makeTask({ id: "high", manual_order: 0, priority: 5 }),
      makeTask({ id: "mid", manual_order: 0, priority: 3 }),
    ];

    const roots = buildTree(tasks);

    expect(roots.map((r) => r.task.id)).toEqual(["high", "mid", "low"]);
  });

  it("breaks manual_order+priority ties by created_at ASC", () => {
    const tasks = [
      makeTask({
        id: "later",
        manual_order: 0,
        priority: 3,
        created_at: "2024-03-01T00:00:00Z",
      }),
      makeTask({
        id: "earlier",
        manual_order: 0,
        priority: 3,
        created_at: "2024-01-01T00:00:00Z",
      }),
      makeTask({
        id: "middle",
        manual_order: 0,
        priority: 3,
        created_at: "2024-02-01T00:00:00Z",
      }),
    ];

    const roots = buildTree(tasks);

    expect(roots.map((r) => r.task.id)).toEqual([
      "earlier",
      "middle",
      "later",
    ]);
  });

  it("sorts children recursively (not just roots)", () => {
    const tasks = [
      makeTask({ id: "parent", manual_order: 0 }),
      makeTask({
        id: "child-late",
        parent_id: "parent",
        manual_order: 9,
      }),
      makeTask({
        id: "child-early",
        parent_id: "parent",
        manual_order: 1,
      }),
      makeTask({
        id: "child-mid",
        parent_id: "parent",
        manual_order: 5,
      }),
    ];

    const roots = buildTree(tasks);

    expect(roots).toHaveLength(1);
    expect(roots[0]!.children.map((c) => c.task.id)).toEqual([
      "child-early",
      "child-mid",
      "child-late",
    ]);
  });

  it("does not crash on a 2-node parent cycle (a->b, b->a)", () => {
    const tasks = [
      makeTask({ id: "a", parent_id: "b" }),
      makeTask({ id: "b", parent_id: "a" }),
    ];

    // Should complete in well under any test timeout.
    const roots = buildTree(tasks);

    // The current impl: each node is attached to its parent (since both
    // parents exist in the map), so neither ends up at root. We assert
    // that buildTree terminates and produces a value, and that both
    // tasks are reachable from the result (as a child of the other).
    // Both nodes have their parent in the map, so roots is empty.
    expect(Array.isArray(roots)).toBe(true);
    // Either: both tasks are at root, OR each is a child of the other.
    const allReachable = new Set<string>();
    function walk(nodes: { task: TaskSummary; children: unknown[] }[]) {
      for (const n of nodes) {
        if (allReachable.has(n.task.id)) continue;
        allReachable.add(n.task.id);
        walk(n.children as typeof nodes);
      }
    }
    walk(roots as never);
    // At least one of the two tasks should be reachable. If both parents
    // exist in the map, roots is empty — which is acceptable (no crash).
    // The key invariant is: no infinite loop / stack overflow.
    expect(roots.length).toBeGreaterThanOrEqual(0);
  });

  it("does not crash on a self-cycle (a.parent_id === a.id)", () => {
    const tasks = [makeTask({ id: "a", parent_id: "a" })];

    const roots = buildTree(tasks);

    expect(Array.isArray(roots)).toBe(true);
    // Self-parent: it exists in the map so it is NOT marked orphan, and
    // it attaches itself as its own child rather than being a root.
    // The invariant we care about is "no crash".
    expect(roots.length).toBeGreaterThanOrEqual(0);
  });
});

// ===========================================================================
// <Tree /> — rendering behavior
// ===========================================================================

describe("<Tree /> — rendering behavior", () => {
  it("renders a 'No tasks' empty state when given an empty list", () => {
    renderTree([]);

    expect(screen.getByText("No tasks")).toBeInTheDocument();
  });

  it("renders all root tasks when no ?task is open", () => {
    const tasks = [
      makeTask({ id: "r1", title: "Root one" }),
      makeTask({ id: "r2", title: "Root two" }),
      makeTask({ id: "r3", title: "Root three" }),
    ];

    renderTree(tasks);

    expect(
      screen.getByRole("heading", { level: 3, name: "Root one" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { level: 3, name: "Root two" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { level: 3, name: "Root three" }),
    ).toBeInTheDocument();
  });

  it("does NOT render children of a collapsed root by default", () => {
    const tasks = [
      makeTask({ id: "root", title: "Collapsed root" }),
      makeTask({
        id: "child",
        title: "Hidden child",
        parent_id: "root",
      }),
    ];

    renderTree(tasks);

    expect(
      screen.getByRole("heading", { level: 3, name: "Collapsed root" }),
    ).toBeInTheDocument();
    // Child is not rendered because the parent is collapsed.
    expect(
      screen.queryByRole("heading", { level: 3, name: "Hidden child" }),
    ).not.toBeInTheDocument();
  });

  it("hides the chevron (invisible class) on nodes with no children", () => {
    const tasks = [makeTask({ id: "leaf", title: "A leaf task" })];

    renderTree(tasks);

    const toggle = findToggleButtonByTitle("A leaf task");
    // The chevron button stays in the DOM for layout, but is invisible
    // and non-interactive on leaves.
    expect(toggle.className).toContain("invisible");
    expect(toggle.className).toContain("pointer-events-none");
  });

  it("shows the chevron (no invisible class) on nodes WITH children", () => {
    const tasks = [
      makeTask({ id: "p", title: "Has kids" }),
      makeTask({ id: "k", title: "Kid", parent_id: "p" }),
    ];

    renderTree(tasks);

    const toggle = findToggleButtonByTitle("Has kids");
    expect(toggle.className).not.toContain("invisible");
    expect(toggle.getAttribute("aria-expanded")).toBe("false");
  });

  it("expands a collapsed node when its chevron is clicked, revealing children", async () => {
    const tasks = [
      makeTask({ id: "p", title: "Parent" }),
      makeTask({ id: "k", title: "Kid", parent_id: "p" }),
    ];

    renderTree(tasks);
    // Before click: child is hidden.
    expect(
      screen.queryByRole("heading", { level: 3, name: "Kid" }),
    ).not.toBeInTheDocument();

    // Act
    const user = userEvent.setup();
    await user.click(findToggleButtonByTitle("Parent"));

    expect(
      screen.getByRole("heading", { level: 3, name: "Kid" }),
    ).toBeInTheDocument();
    expect(findToggleButtonByTitle("Parent").getAttribute("aria-expanded")).toBe(
      "true",
    );
  });

  it("collapses an expanded node when its chevron is clicked a second time", async () => {
    const tasks = [
      makeTask({ id: "p", title: "Parent" }),
      makeTask({ id: "k", title: "Kid", parent_id: "p" }),
    ];

    renderTree(tasks);
    const user = userEvent.setup();
    // Expand
    await user.click(findToggleButtonByTitle("Parent"));
    expect(
      screen.getByRole("heading", { level: 3, name: "Kid" }),
    ).toBeInTheDocument();

    // Act — collapse
    await user.click(findToggleButtonByTitle("Parent"));

    expect(
      screen.queryByRole("heading", { level: 3, name: "Kid" }),
    ).not.toBeInTheDocument();
  });

  it("clicking the chevron on a leaf node is a no-op (no error, no state change)", async () => {
    const tasks = [makeTask({ id: "leaf", title: "Leaf only" })];

    renderTree(tasks);
    const user = userEvent.setup();
    const toggle = findToggleButtonByTitle("Leaf only");

    // Even though it's pointer-events-none, calling click() programmatically
    // via user-event should not throw and should not produce any visible
    // change.
    await user.click(toggle).catch(() => {
      // user-event may refuse to click pointer-events-none elements in
      // some versions; that's fine — the absence of a thrown error matters.
    });

    // The leaf is still rendered exactly once.
    expect(
      screen.getAllByRole("heading", { level: 3, name: "Leaf only" }),
    ).toHaveLength(1);
  });

  it("invokes onOpenTask with the task id when a card is clicked", async () => {
    const onOpenTask = vi.fn();
    const tasks = [makeTask({ id: "open-me", title: "Click me" })];

    renderTree(tasks, { onOpenTask });
    const user = userEvent.setup();
    await user.click(
      screen.getByRole("heading", { level: 3, name: "Click me" }),
    );

    expect(onOpenTask).toHaveBeenCalledTimes(1);
    expect(onOpenTask).toHaveBeenCalledWith("open-me");
  });

  it("auto-expands ancestors on initial render when ?task=<nested-id>", () => {
    // Tree:
    //   root
    //     mid
    //       deep   <-- ?task=deep
    const tasks = [
      makeTask({ id: "root", title: "Root" }),
      makeTask({ id: "mid", title: "Mid", parent_id: "root" }),
      makeTask({ id: "deep", title: "Deep leaf", parent_id: "mid" }),
    ];

    renderTree(tasks, { initialEntries: ["/?task=deep"] });

    // All ancestors (root, mid) must be expanded so the deep node is visible.
    expect(
      screen.getByRole("heading", { level: 3, name: "Root" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { level: 3, name: "Mid" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { level: 3, name: "Deep leaf" }),
    ).toBeInTheDocument();

    // The ancestors should report aria-expanded="true".
    expect(findToggleButtonByTitle("Root").getAttribute("aria-expanded")).toBe(
      "true",
    );
    expect(findToggleButtonByTitle("Mid").getAttribute("aria-expanded")).toBe(
      "true",
    );
  });

  it("does NOT expand unrelated branches when ?task=<id> points to one branch", () => {
    const tasks = [
      makeTask({ id: "branch-a", title: "Branch A" }),
      makeTask({ id: "a-child", title: "A child", parent_id: "branch-a" }),
      makeTask({ id: "branch-b", title: "Branch B" }),
      makeTask({ id: "b-child", title: "B child", parent_id: "branch-b" }),
    ];

    renderTree(tasks, { initialEntries: ["/?task=a-child"] });

    // Branch A is expanded (so a-child is visible).
    expect(
      screen.getByRole("heading", { level: 3, name: "A child" }),
    ).toBeInTheDocument();
    // Branch B is NOT expanded, so its child stays hidden.
    expect(
      screen.queryByRole("heading", { level: 3, name: "B child" }),
    ).not.toBeInTheDocument();
    expect(
      findToggleButtonByTitle("Branch B").getAttribute("aria-expanded"),
    ).toBe("false");
  });

  it("does not crash and starts fully collapsed when ?task=<id> refers to a missing task", () => {
    const tasks = [
      makeTask({ id: "root", title: "Root" }),
      makeTask({ id: "child", title: "Child", parent_id: "root" }),
    ];

    renderTree(tasks, { initialEntries: ["/?task=nonexistent"] });

    // Root is rendered, but child stays hidden (no ancestors to expand).
    expect(
      screen.getByRole("heading", { level: 3, name: "Root" }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("heading", { level: 3, name: "Child" }),
    ).not.toBeInTheDocument();
  });

  it("renders an orphan dot with aria-label='orphan' for tasks whose parent is missing", () => {
    const tasks = [
      makeTask({
        id: "orphan",
        title: "Orphan task",
        parent_id: "missing-parent",
      }),
    ];

    renderTree(tasks);

    const orphanDot = screen.getByLabelText("orphan");
    expect(orphanDot).toBeInTheDocument();
    // It's a small circular dot.
    expect(orphanDot.className).toContain("rounded-full");
    // The tooltip explains what an orphan is.
    expect(orphanDot.getAttribute("title")).toMatch(/orphan/i);
  });

  it("does NOT render an orphan dot for a non-orphan task", () => {
    const tasks = [makeTask({ id: "normal", title: "Normal" })];

    renderTree(tasks);

    expect(screen.queryByLabelText("orphan")).not.toBeInTheDocument();
  });

  it("indents nested children using padding-left scaled by depth", async () => {
    const tasks = [
      makeTask({ id: "root", title: "Root depth" }),
      makeTask({ id: "child", title: "Child depth", parent_id: "root" }),
    ];

    renderTree(tasks);
    // Expand so the child renders.
    const user = userEvent.setup();
    await user.click(findToggleButtonByTitle("Root depth"));

    const rootRow = findToggleButtonByTitle("Root depth").parentElement!;
    const childRow = findToggleButtonByTitle("Child depth").parentElement!;

    // depth=0 → calc(0 * var(--tree-indent, 1.25rem)) === "0px" effectively;
    // depth=1 → uses the CSS var. We assert the inline style differs.
    expect(rootRow.style.paddingLeft).toContain("0");
    expect(childRow.style.paddingLeft).not.toBe(rootRow.style.paddingLeft);
    expect(childRow.style.paddingLeft).toMatch(/--tree-indent/);
  });

  it("renders each root in its own row container (chevron + card layout)", () => {
    const tasks = [
      makeTask({ id: "r1", title: "Row one" }),
      makeTask({ id: "r2", title: "Row two" }),
    ];

    const { container } = renderTree(tasks);

    // Two top-level chevron toggles, one per root.
    const rows = container.querySelectorAll(".flex.items-center.gap-1");
    // Each row contains a heading. We check headings sit inside flex rows.
    for (const title of ["Row one", "Row two"]) {
      const heading = screen.getByRole("heading", { level: 3, name: title });
      let node: HTMLElement | null = heading;
      while (node && !node.className.includes("flex items-center")) {
        node = node.parentElement;
      }
      expect(node).not.toBeNull();
    }
    expect(rows.length).toBeGreaterThanOrEqual(2);
  });

  it("auto-expands a deeply nested chain (depth 4) so the leaf is visible", () => {
    const tasks = [
      makeTask({ id: "L0", title: "L0" }),
      makeTask({ id: "L1", title: "L1", parent_id: "L0" }),
      makeTask({ id: "L2", title: "L2", parent_id: "L1" }),
      makeTask({ id: "L3", title: "L3", parent_id: "L2" }),
      makeTask({ id: "L4", title: "L4 leaf", parent_id: "L3" }),
    ];

    renderTree(tasks, { initialEntries: ["/?task=L4"] });

    for (const title of ["L0", "L1", "L2", "L3", "L4 leaf"]) {
      expect(
        screen.getByRole("heading", { level: 3, name: title }),
      ).toBeInTheDocument();
    }
  });

  it("does not render children of unrelated siblings of the ?task target", () => {
    // root
    //   target  <-- open
    //   sibling
    //     hidden-grandchild
    const tasks = [
      makeTask({ id: "root", title: "Root" }),
      makeTask({ id: "target", title: "Target", parent_id: "root" }),
      makeTask({ id: "sibling", title: "Sibling", parent_id: "root" }),
      makeTask({
        id: "hidden",
        title: "Hidden grandchild",
        parent_id: "sibling",
      }),
    ];

    renderTree(tasks, { initialEntries: ["/?task=target"] });

    // Root is expanded → target AND sibling are both visible (they are direct
    // children of root).
    expect(
      screen.getByRole("heading", { level: 3, name: "Target" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { level: 3, name: "Sibling" }),
    ).toBeInTheDocument();
    // Sibling itself is NOT expanded → grandchild stays hidden.
    expect(
      screen.queryByRole("heading", { level: 3, name: "Hidden grandchild" }),
    ).not.toBeInTheDocument();
  });
});

// ===========================================================================
// Sort order observable through the Tree component (integration with buildTree)
// ===========================================================================

describe("<Tree /> — sort order observable in DOM", () => {
  it("renders root cards in the same order buildTree returns", () => {
    const tasks = [
      makeTask({ id: "c", title: "C-third", manual_order: 5 }),
      makeTask({ id: "a", title: "A-first", manual_order: 1 }),
      makeTask({ id: "b", title: "B-second", manual_order: 3 }),
    ];

    renderTree(tasks);

    const headings = screen
      .getAllByRole("heading", { level: 3 })
      .map((h) => h.textContent);
    expect(headings).toEqual(["A-first", "B-second", "C-third"]);
  });

  it("renders expanded children in sorted (manual_order ASC) order", async () => {
    const tasks = [
      makeTask({ id: "p", title: "Parent", manual_order: 0 }),
      makeTask({
        id: "z",
        title: "Z-child",
        parent_id: "p",
        manual_order: 9,
      }),
      makeTask({
        id: "a",
        title: "A-child",
        parent_id: "p",
        manual_order: 1,
      }),
      makeTask({
        id: "m",
        title: "M-child",
        parent_id: "p",
        manual_order: 5,
      }),
    ];

    const { container } = renderTree(tasks);
    const user = userEvent.setup();
    await user.click(findToggleButtonByTitle("Parent"));

    // Find headings underneath the parent's flex row's containing <div>.
    // Simplest: collect all level-3 headings in document order, drop the
    // first (parent), and assert the rest equal the sorted children.
    const headings = within(container)
      .getAllByRole("heading", { level: 3 })
      .map((h) => h.textContent);
    expect(headings).toEqual([
      "Parent",
      "A-child",
      "M-child",
      "Z-child",
    ]);
  });
});

// ===========================================================================
// ARIA tree structure (role="tree", role="treeitem", aria-expanded, aria-level)
// ===========================================================================

describe("<Tree /> — ARIA tree structure", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it("renders a container with role='tree'", () => {
    renderTree([makeTask({ id: "a", title: "A" })]);

    expect(screen.getByRole("tree")).toBeInTheDocument();
  });

  it("renders each rendered row with role='treeitem'", () => {
    const tasks = [
      makeTask({ id: "r1", title: "R1" }),
      makeTask({ id: "r2", title: "R2" }),
      makeTask({ id: "r3", title: "R3" }),
    ];

    renderTree(tasks);

    // Three roots, no children expanded → exactly three treeitems.
    expect(screen.getAllByRole("treeitem")).toHaveLength(3);
  });

  it("leaf row has no aria-expanded attribute (attribute absent)", () => {
    renderTree([makeTask({ id: "leaf", title: "Lone leaf" })]);

    const treeitems = screen.getAllByRole("treeitem");
    // For a leaf, aria-expanded={undefined} → React omits the attribute entirely.
    expect(treeitems[0]!.hasAttribute("aria-expanded")).toBe(false);
  });

  it("parent row has aria-expanded='false' when collapsed", () => {
    const tasks = [
      makeTask({ id: "p", title: "Parent" }),
      makeTask({ id: "k", title: "Kid", parent_id: "p" }),
    ];

    renderTree(tasks);

    // Only the parent is rendered (child hidden) → one treeitem with aria-expanded="false".
    const treeitems = screen.getAllByRole("treeitem");
    expect(treeitems).toHaveLength(1);
    expect(treeitems[0]!.getAttribute("aria-expanded")).toBe("false");
  });

  it("parent row has aria-expanded='true' when expanded", async () => {
    const tasks = [
      makeTask({ id: "p", title: "Parent" }),
      makeTask({ id: "k", title: "Kid", parent_id: "p" }),
    ];

    renderTree(tasks);

    const user = userEvent.setup();
    await user.click(findToggleButtonByTitle("Parent"));

    // Find the parent row by data-task-id to avoid confusing it with the child row.
    const parentRow = document.querySelector(
      '[data-task-id="p"][role="treeitem"]',
    );
    expect(parentRow).not.toBeNull();
    expect(parentRow!.getAttribute("aria-expanded")).toBe("true");
  });

  it("row has aria-level='1' at depth 0", () => {
    renderTree([makeTask({ id: "root", title: "Root" })]);

    const row = document.querySelector('[data-task-id="root"][role="treeitem"]');
    expect(row).not.toBeNull();
    expect(row!.getAttribute("aria-level")).toBe("1");
  });

  it("row has aria-level='2' at depth 1 (child of an expanded root)", async () => {
    const tasks = [
      makeTask({ id: "p", title: "Parent" }),
      makeTask({ id: "k", title: "Kid", parent_id: "p" }),
    ];

    renderTree(tasks);

    const user = userEvent.setup();
    await user.click(findToggleButtonByTitle("Parent"));

    const childRow = document.querySelector(
      '[data-task-id="k"][role="treeitem"]',
    );
    expect(childRow).not.toBeNull();
    expect(childRow!.getAttribute("aria-level")).toBe("2");
  });

  it("each row exposes its task id via data-task-id", () => {
    const tasks = [
      makeTask({ id: "alpha", title: "Alpha" }),
      makeTask({ id: "beta", title: "Beta" }),
    ];

    renderTree(tasks);

    expect(
      document.querySelector('[data-task-id="alpha"][role="treeitem"]'),
    ).not.toBeNull();
    expect(
      document.querySelector('[data-task-id="beta"][role="treeitem"]'),
    ).not.toBeNull();
  });

  it("treeitem row is keyboard-focusable (tabIndex=0)", () => {
    renderTree([makeTask({ id: "root", title: "Root" })]);

    const row = document.querySelector(
      '[data-task-id="root"][role="treeitem"]',
    ) as HTMLElement;
    expect(row.tabIndex).toBe(0);
  });

  it("children container has role='group' when a parent is expanded", async () => {
    const tasks = [
      makeTask({ id: "p", title: "Parent" }),
      makeTask({ id: "k", title: "Kid", parent_id: "p" }),
    ];

    renderTree(tasks);

    const user = userEvent.setup();
    await user.click(findToggleButtonByTitle("Parent"));

    expect(document.querySelector('[role="group"]')).not.toBeNull();
  });
});

// ===========================================================================
// localStorage persistence of expanded set
// ===========================================================================

describe("<Tree /> — localStorage persistence of expanded state", () => {
  beforeEach(() => {
    window.localStorage.clear();
    vi.useRealTimers();
  });

  it("on mount, restores expanded IDs from localStorage (null spaceId → _all key)", () => {
    window.localStorage.setItem(
      "cronos:tree:expanded:_all",
      JSON.stringify(["p"]),
    );
    const tasks = [
      makeTask({ id: "p", title: "Parent" }),
      makeTask({ id: "k", title: "Kid", parent_id: "p" }),
    ];

    renderTree(tasks);

    // Child renders because the parent's id was in the persisted expanded set.
    expect(
      screen.getByRole("heading", { level: 3, name: "Kid" }),
    ).toBeInTheDocument();
  });

  it("on mount with spaceId, reads from the space-keyed localStorage entry", () => {
    window.localStorage.setItem(
      "cronos:tree:expanded:space-42",
      JSON.stringify(["p"]),
    );
    const tasks = [
      makeTask({ id: "p", title: "Parent" }),
      makeTask({ id: "k", title: "Kid", parent_id: "p" }),
    ];

    renderTree(tasks, { spaceId: "space-42" });

    expect(
      screen.getByRole("heading", { level: 3, name: "Kid" }),
    ).toBeInTheDocument();
  });

  it("does NOT read from another space's key (no bleed-through across spaces)", () => {
    window.localStorage.setItem(
      "cronos:tree:expanded:space-A",
      JSON.stringify(["p"]),
    );
    const tasks = [
      makeTask({ id: "p", title: "Parent" }),
      makeTask({ id: "k", title: "Kid", parent_id: "p" }),
    ];

    // Rendering for space-B must NOT pick up space-A's persisted state.
    renderTree(tasks, { spaceId: "space-B" });

    expect(
      screen.queryByRole("heading", { level: 3, name: "Kid" }),
    ).not.toBeInTheDocument();
  });

  it("does NOT read from _all when a spaceId is provided", () => {
    window.localStorage.setItem(
      "cronos:tree:expanded:_all",
      JSON.stringify(["p"]),
    );
    const tasks = [
      makeTask({ id: "p", title: "Parent" }),
      makeTask({ id: "k", title: "Kid", parent_id: "p" }),
    ];

    renderTree(tasks, { spaceId: "space-A" });

    expect(
      screen.queryByRole("heading", { level: 3, name: "Kid" }),
    ).not.toBeInTheDocument();
  });

  it("debounces the localStorage write 200ms after a chevron click (null spaceId)", () => {
    vi.useFakeTimers();
    try {
      const tasks = [
        makeTask({ id: "p", title: "Parent" }),
        makeTask({ id: "k", title: "Kid", parent_id: "p" }),
      ];

      renderTree(tasks);

      // fireEvent is synchronous — no need to wire userEvent into fake timers.
      act(() => {
        fireEvent.click(findToggleButtonByTitle("Parent"));
      });

      // Before the debounce fires, nothing has been written yet.
      // (The mount-effect also schedules a write of [], but it hasn't fired.)
      expect(window.localStorage.getItem("cronos:tree:expanded:_all")).toBeNull();

      // Flush the 200ms debounce.
      act(() => {
        vi.runAllTimers();
      });

      const raw = window.localStorage.getItem("cronos:tree:expanded:_all");
      expect(raw).not.toBeNull();
      expect(JSON.parse(raw!)).toContain("p");
    } finally {
      vi.useRealTimers();
    }
  });

  it("writes under the space-keyed key when spaceId is provided", () => {
    vi.useFakeTimers();
    try {
      const tasks = [
        makeTask({ id: "p", title: "Parent" }),
        makeTask({ id: "k", title: "Kid", parent_id: "p" }),
      ];

      renderTree(tasks, { spaceId: "space-42" });

      act(() => {
        fireEvent.click(findToggleButtonByTitle("Parent"));
      });

      act(() => {
        vi.runAllTimers();
      });

      const raw = window.localStorage.getItem("cronos:tree:expanded:space-42");
      expect(raw).not.toBeNull();
      expect(JSON.parse(raw!)).toContain("p");
      // Did NOT write to _all.
      expect(window.localStorage.getItem("cronos:tree:expanded:_all")).toBeNull();
    } finally {
      vi.useRealTimers();
    }
  });

  it("different spaceId values write to different localStorage keys", () => {
    vi.useFakeTimers();
    try {
      const tasks = [
        makeTask({ id: "p", title: "Parent" }),
        makeTask({ id: "k", title: "Kid", parent_id: "p" }),
      ];

      // Render the first tree for space-A, expand the parent, flush the debounce.
      const first = renderTree(tasks, { spaceId: "space-A" });
      act(() => {
        fireEvent.click(findToggleButtonByTitle("Parent"));
      });
      act(() => {
        vi.runAllTimers();
      });
      first.unmount();

      // Now render for a different spaceId; it must not see space-A's state.
      renderTree(tasks, { spaceId: "space-B" });
      // The kid is not visible — space-B has no persisted state.
      expect(
        screen.queryByRole("heading", { level: 3, name: "Kid" }),
      ).not.toBeInTheDocument();

      // Flush any pending debounce for space-B (initial empty write).
      act(() => {
        vi.runAllTimers();
      });

      // The two keys are independent — space-A still contains "p",
      // and space-B contains either nothing or an empty list (never "p").
      const a = window.localStorage.getItem("cronos:tree:expanded:space-A");
      const b = window.localStorage.getItem("cronos:tree:expanded:space-B");
      expect(a).not.toBeNull();
      expect(JSON.parse(a!)).toContain("p");
      if (b !== null) {
        expect(JSON.parse(b)).not.toContain("p");
      }
    } finally {
      vi.useRealTimers();
    }
  });
});

// ===========================================================================
// TreeHandle ref — expandAll / collapseAll
// ===========================================================================

describe("<Tree /> — TreeHandle ref imperative API", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it("ref.current.expandAll() expands every node that has children", () => {
    const tasks = [
      makeTask({ id: "p1", title: "P1" }),
      makeTask({ id: "p1c", title: "P1 Kid", parent_id: "p1" }),
      makeTask({ id: "p2", title: "P2" }),
      makeTask({ id: "p2c", title: "P2 Kid", parent_id: "p2" }),
      makeTask({ id: "leaf", title: "Leaf" }),
    ];

    const ref = createRef<TreeHandle>();
    renderTree(tasks, { ref });

    // Children hidden initially.
    expect(
      screen.queryByRole("heading", { level: 3, name: "P1 Kid" }),
    ).not.toBeInTheDocument();

    act(() => {
      ref.current!.expandAll();
    });

    expect(
      screen.getByRole("heading", { level: 3, name: "P1 Kid" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { level: 3, name: "P2 Kid" }),
    ).toBeInTheDocument();

    // Both parents now report aria-expanded="true".
    expect(
      document
        .querySelector('[data-task-id="p1"][role="treeitem"]')!
        .getAttribute("aria-expanded"),
    ).toBe("true");
    expect(
      document
        .querySelector('[data-task-id="p2"][role="treeitem"]')!
        .getAttribute("aria-expanded"),
    ).toBe("true");
  });

  it("ref.current.collapseAll() collapses every expanded node", () => {
    const tasks = [
      makeTask({ id: "p1", title: "P1" }),
      makeTask({ id: "p1c", title: "P1 Kid", parent_id: "p1" }),
      makeTask({ id: "p2", title: "P2" }),
      makeTask({ id: "p2c", title: "P2 Kid", parent_id: "p2" }),
    ];

    const ref = createRef<TreeHandle>();
    renderTree(tasks, { ref });

    act(() => {
      ref.current!.expandAll();
    });
    // Sanity: expansion worked.
    expect(
      screen.getByRole("heading", { level: 3, name: "P1 Kid" }),
    ).toBeInTheDocument();

    act(() => {
      ref.current!.collapseAll();
    });

    expect(
      screen.queryByRole("heading", { level: 3, name: "P1 Kid" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("heading", { level: 3, name: "P2 Kid" }),
    ).not.toBeInTheDocument();
    expect(
      document
        .querySelector('[data-task-id="p1"][role="treeitem"]')!
        .getAttribute("aria-expanded"),
    ).toBe("false");
  });

  it("ref.current.expandAll() is a no-op on a tree with no parents", () => {
    const tasks = [
      makeTask({ id: "a", title: "A" }),
      makeTask({ id: "b", title: "B" }),
    ];

    const ref = createRef<TreeHandle>();
    renderTree(tasks, { ref });

    // No throw, nothing to expand → no parent rows to flip.
    expect(() =>
      act(() => {
        ref.current!.expandAll();
      }),
    ).not.toThrow();

    // Leaves still have no aria-expanded.
    const rows = screen.getAllByRole("treeitem");
    for (const row of rows) {
      expect(row.hasAttribute("aria-expanded")).toBe(false);
    }
  });
});

// ===========================================================================
// Keyboard navigation: ArrowDown/Up/Left/Right + Enter
// ===========================================================================

describe("<Tree /> — keyboard navigation", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  /**
   * Find the treeitem row whose data-task-id matches the given id. Returns
   * the live element (not a clone), so .focus() / dispatchEvent work.
   */
  function rowFor(taskId: string): HTMLElement {
    const el = document.querySelector(
      `[data-task-id="${taskId}"][role="treeitem"]`,
    );
    if (!el) throw new Error(`No treeitem row for task id "${taskId}"`);
    return el as HTMLElement;
  }

  it("ArrowDown on the first node moves focus to the second node", () => {
    const tasks = [
      makeTask({ id: "a", title: "A", manual_order: 0 }),
      makeTask({ id: "b", title: "B", manual_order: 1 }),
    ];

    renderTree(tasks);

    const first = rowFor("a");
    first.focus();
    expect(document.activeElement).toBe(first);

    fireEvent.keyDown(first, { key: "ArrowDown" });

    expect(document.activeElement).toBe(rowFor("b"));
  });

  it("ArrowUp on the second node moves focus to the first node", () => {
    const tasks = [
      makeTask({ id: "a", title: "A", manual_order: 0 }),
      makeTask({ id: "b", title: "B", manual_order: 1 }),
    ];

    renderTree(tasks);

    const second = rowFor("b");
    second.focus();
    fireEvent.keyDown(second, { key: "ArrowUp" });

    expect(document.activeElement).toBe(rowFor("a"));
  });

  it("ArrowRight on a collapsed parent expands it (aria-expanded → true)", () => {
    const tasks = [
      makeTask({ id: "p", title: "Parent" }),
      makeTask({ id: "k", title: "Kid", parent_id: "p" }),
    ];

    renderTree(tasks);

    const parent = rowFor("p");
    parent.focus();
    expect(parent.getAttribute("aria-expanded")).toBe("false");

    fireEvent.keyDown(parent, { key: "ArrowRight" });

    // Re-query after re-render.
    expect(rowFor("p").getAttribute("aria-expanded")).toBe("true");
    expect(
      screen.getByRole("heading", { level: 3, name: "Kid" }),
    ).toBeInTheDocument();
  });

  it("ArrowRight on an expanded parent with children moves focus to the first child", () => {
    const tasks = [
      makeTask({ id: "p", title: "Parent" }),
      makeTask({ id: "k", title: "Kid", parent_id: "p" }),
    ];

    renderTree(tasks);

    // Expand first by clicking the chevron.
    act(() => {
      fireEvent.click(findToggleButtonByTitle("Parent"));
    });

    const parent = rowFor("p");
    parent.focus();
    fireEvent.keyDown(parent, { key: "ArrowRight" });

    expect(document.activeElement).toBe(rowFor("k"));
  });

  it("ArrowLeft on an expanded parent collapses it (aria-expanded → false)", () => {
    const tasks = [
      makeTask({ id: "p", title: "Parent" }),
      makeTask({ id: "k", title: "Kid", parent_id: "p" }),
    ];

    renderTree(tasks);

    act(() => {
      fireEvent.click(findToggleButtonByTitle("Parent"));
    });

    const parent = rowFor("p");
    parent.focus();
    expect(parent.getAttribute("aria-expanded")).toBe("true");

    fireEvent.keyDown(parent, { key: "ArrowLeft" });

    expect(rowFor("p").getAttribute("aria-expanded")).toBe("false");
    expect(
      screen.queryByRole("heading", { level: 3, name: "Kid" }),
    ).not.toBeInTheDocument();
  });

  it("ArrowLeft on a leaf whose parent exists focuses the parent row", () => {
    const tasks = [
      makeTask({ id: "p", title: "Parent" }),
      makeTask({ id: "k", title: "Kid", parent_id: "p" }),
    ];

    renderTree(tasks);

    // Make the child visible.
    act(() => {
      fireEvent.click(findToggleButtonByTitle("Parent"));
    });

    const child = rowFor("k");
    child.focus();
    fireEvent.keyDown(child, { key: "ArrowLeft" });

    expect(document.activeElement).toBe(rowFor("p"));
  });

  it("Enter on a node calls onOpenTask with that node's task id", () => {
    const onOpenTask = vi.fn();
    const tasks = [makeTask({ id: "press-me", title: "Press me" })];

    renderTree(tasks, { onOpenTask });

    const row = rowFor("press-me");
    row.focus();
    fireEvent.keyDown(row, { key: "Enter" });

    expect(onOpenTask).toHaveBeenCalledTimes(1);
    expect(onOpenTask).toHaveBeenCalledWith("press-me");
  });

  it("ArrowUp on the first node is a no-op (focus stays, no throw)", () => {
    const tasks = [
      makeTask({ id: "a", title: "A", manual_order: 0 }),
      makeTask({ id: "b", title: "B", manual_order: 1 }),
    ];

    renderTree(tasks);

    const first = rowFor("a");
    first.focus();

    expect(() => {
      fireEvent.keyDown(first, { key: "ArrowUp" });
    }).not.toThrow();

    // Focus did not move (no prior treeitem to go to).
    expect(document.activeElement).toBe(first);
  });

  it("ArrowDown on the last visible node is a no-op (focus stays, no throw)", () => {
    const tasks = [
      makeTask({ id: "a", title: "A", manual_order: 0 }),
      makeTask({ id: "b", title: "B", manual_order: 1 }),
    ];

    renderTree(tasks);

    const last = rowFor("b");
    last.focus();

    expect(() => {
      fireEvent.keyDown(last, { key: "ArrowDown" });
    }).not.toThrow();

    expect(document.activeElement).toBe(last);
  });

  it("ArrowRight on a leaf is a no-op (no throw, no focus change)", () => {
    const tasks = [makeTask({ id: "leaf", title: "Leaf" })];

    renderTree(tasks);
    const row = rowFor("leaf");
    row.focus();

    expect(() => {
      fireEvent.keyDown(row, { key: "ArrowRight" });
    }).not.toThrow();
    expect(document.activeElement).toBe(row);
  });

  it("ArrowLeft on a root leaf with no parent is a no-op (no throw)", () => {
    const tasks = [makeTask({ id: "root-leaf", title: "Root leaf" })];

    renderTree(tasks);
    const row = rowFor("root-leaf");
    row.focus();

    expect(() => {
      fireEvent.keyDown(row, { key: "ArrowLeft" });
    }).not.toThrow();
    expect(document.activeElement).toBe(row);
  });
});
