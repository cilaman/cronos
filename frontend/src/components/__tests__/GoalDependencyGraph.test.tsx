import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { GoalDependencyGraph } from "../GoalDependencyGraph";
import type { Task, TaskSummary } from "../../types";

// ---------------------------------------------------------------------------
// Test helpers
// ---------------------------------------------------------------------------

function makeGoal(overrides: Partial<Task> = {}): Task {
  return {
    id: "goal-1",
    space_id: "space-1",
    title: "My Goal",
    state: "active",
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
    type: "goal",
    parent_id: null,
    parent_title: null,
    depends_on: [],
    ...overrides,
  };
}

function makeChild(overrides: Partial<TaskSummary> = {}): TaskSummary {
  return {
    id: "child-1",
    space_id: "space-1",
    title: "Child",
    state: "backlog",
    created_at: "2024-01-15T14:00:00Z",
    updated_at: "2024-01-15T14:30:00Z",
    waiting_question: null,
    brief_preview: "",
    priority: 3,
    manual_order: 0,
    agent_mode: "auto",
    space_name: null,
    space_color: null,
    space_icon: null,
    parent_id: "goal-1",
    depends_on: [],
    ...overrides,
  };
}

// 5-node fixture matching the acceptance spec:
// edges T3→T1, T4→T2&T3, T5→T1&T4 (→ means "depends on")
const FIVE_CHILDREN: TaskSummary[] = [
  makeChild({ id: "T1", title: "Task 1", depends_on: [] }),
  makeChild({ id: "T2", title: "Task 2", depends_on: [] }),
  makeChild({ id: "T3", title: "Task 3", depends_on: ["T1"] }),
  makeChild({ id: "T4", title: "Task 4", depends_on: ["T2", "T3"] }),
  makeChild({ id: "T5", title: "Task 5", depends_on: ["T1", "T4"] }),
];

const GOAL = makeGoal();
const NO_RUNNING = new Set<string>();

function renderGraph(
  children: TaskSummary[] = FIVE_CHILDREN,
  runningIds: Set<string> = NO_RUNNING,
  onOpenTask = vi.fn(),
) {
  return render(
    <GoalDependencyGraph
      goal={GOAL}
      children={children}
      onOpenTask={onOpenTask}
      runningIds={runningIds}
    />,
  );
}

// ---------------------------------------------------------------------------
// Snapshot — 5-node layout
// ---------------------------------------------------------------------------

describe("GoalDependencyGraph — snapshot", () => {
  it("matches snapshot for 5-node fixture with dependency edges", () => {
    const { asFragment } = renderGraph();
    expect(asFragment()).toMatchSnapshot();
  });
});

// ---------------------------------------------------------------------------
// Node rendering
// ---------------------------------------------------------------------------

describe("GoalDependencyGraph — node rendering", () => {
  it("renders all 5 nodes with their titles", () => {
    renderGraph();
    // findAllByText because titles appear in both mobile list and graph
    expect(screen.getAllByText("Task 1").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("Task 2").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("Task 3").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("Task 4").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("Task 5").length).toBeGreaterThanOrEqual(1);
  });

  it("renders a dag-node for each child in the graph", () => {
    renderGraph();
    for (const id of ["T1", "T2", "T3", "T4", "T5"]) {
      expect(screen.getByTestId(`dag-node-${id}`)).toBeInTheDocument();
    }
  });

  it("applies animate-pulse to running nodes", () => {
    renderGraph(FIVE_CHILDREN, new Set(["T3"]));
    const t3 = screen.getByTestId("dag-node-T3");
    expect(t3.className).toContain("animate-pulse");
  });

  it("does NOT apply animate-pulse to non-running nodes", () => {
    renderGraph(FIVE_CHILDREN, new Set(["T3"]));
    const t1 = screen.getByTestId("dag-node-T1");
    expect(t1.className).not.toContain("animate-pulse");
  });

  it("applies opacity-60 to done nodes", () => {
    const children = [
      makeChild({ id: "T1", title: "Task 1", state: "done" }),
      makeChild({ id: "T2", title: "Task 2", state: "backlog" }),
    ];
    renderGraph(children);
    const t1 = screen.getByTestId("dag-node-T1");
    expect(t1.className).toContain("opacity-60");
    const t2 = screen.getByTestId("dag-node-T2");
    expect(t2.className).not.toContain("opacity-60");
  });

  it("applies amber border to waiting nodes", () => {
    const children = [
      makeChild({ id: "T1", title: "Task 1", state: "waiting" }),
    ];
    renderGraph(children);
    const t1 = screen.getByTestId("dag-node-T1");
    expect(t1.className).toContain("border-amber-300");
  });
});

// ---------------------------------------------------------------------------
// Click handler
// ---------------------------------------------------------------------------

describe("GoalDependencyGraph — click handler", () => {
  let onOpenTask: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    onOpenTask = vi.fn();
  });

  it("calls onOpenTask with the correct id when a graph node is clicked", async () => {
    renderGraph(FIVE_CHILDREN, NO_RUNNING, onOpenTask);
    const user = userEvent.setup();

    await user.click(screen.getByTestId("dag-node-T1"));

    expect(onOpenTask).toHaveBeenCalledTimes(1);
    expect(onOpenTask).toHaveBeenCalledWith("T1");
  });

  it("calls onOpenTask with the correct id for each node", async () => {
    renderGraph(FIVE_CHILDREN, NO_RUNNING, onOpenTask);
    const user = userEvent.setup();

    await user.click(screen.getByTestId("dag-node-T3"));
    expect(onOpenTask).toHaveBeenCalledWith("T3");

    await user.click(screen.getByTestId("dag-node-T5"));
    expect(onOpenTask).toHaveBeenCalledWith("T5");
  });
});

// ---------------------------------------------------------------------------
// Empty state
// ---------------------------------------------------------------------------

describe("GoalDependencyGraph — empty state", () => {
  it("shows empty state message when there are no children", () => {
    renderGraph([]);
    expect(screen.getByText("No children yet")).toBeInTheDocument();
  });

  it("does not render the SVG graph when there are no children", () => {
    const { container } = renderGraph([]);
    const svg = container.querySelector("svg");
    expect(svg).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// View mode toggle
// ---------------------------------------------------------------------------

describe("GoalDependencyGraph — view toggle", () => {
  it("shows Graph and List view toggle buttons", () => {
    renderGraph();
    expect(screen.getByRole("button", { name: "Graph" })).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "List view" }),
    ).toBeInTheDocument();
  });

  it("switches to list view when List view button is clicked", async () => {
    renderGraph();
    const user = userEvent.setup();

    // Graph is shown initially (SVG present)
    const { container } = renderGraph();
    expect(container.querySelector("svg")).toBeInTheDocument();

    await user.click(screen.getAllByRole("button", { name: "List view" })[0]);

    // After clicking List view, the flat list text should be visible
    // (we check for the state badge presence)
    expect(screen.getAllByText("backlog").length).toBeGreaterThan(0);
  });
});
