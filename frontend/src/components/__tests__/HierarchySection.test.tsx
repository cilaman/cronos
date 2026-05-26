import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import type { Board, Task, TaskSummary } from "../../types";

// ---------------------------------------------------------------------------
// Mock hooks used by HierarchySection. We supply controllable stand-ins so
// the test asserts on the component's rendering behavior, not on the hook
// internals (those are covered by hooks/__tests__/useTasks-hierarchy.test.tsx).
// ---------------------------------------------------------------------------

const promoteMutateAsync = vi.fn().mockResolvedValue(undefined);
const setParentMutateAsync = vi.fn().mockResolvedValue(undefined);
const setDependsOnMutateAsync = vi.fn().mockResolvedValue(undefined);

let boardData: Board | undefined;
let promoteState = { isPending: false, error: null as Error | null };
let setParentState = { isPending: false, error: null as Error | null };
let setDependsOnState = { isPending: false, error: null as Error | null };

vi.mock("../../hooks/useTasks", () => ({
  useBoard: () => ({ data: boardData }),
  usePromoteTask: () => ({
    mutateAsync: promoteMutateAsync,
    isPending: promoteState.isPending,
    error: promoteState.error,
  }),
  useSetParent: () => ({
    mutateAsync: setParentMutateAsync,
    isPending: setParentState.isPending,
    error: setParentState.error,
  }),
  useSetDependsOn: () => ({
    mutateAsync: setDependsOnMutateAsync,
    isPending: setDependsOnState.isPending,
    error: setDependsOnState.error,
  }),
}));

// HierarchySection is a named export from Detail.tsx, made exportable so this
// test can render it in isolation.
import { HierarchySection } from "../Detail";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeTask(overrides: Partial<Task> = {}): Task {
  return {
    id: "t-1",
    space_id: "space-1",
    title: "Title",
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

function makeSummary(overrides: Partial<TaskSummary> = {}): TaskSummary {
  return {
    id: "s-1",
    space_id: "space-1",
    title: "Sum",
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
    ...overrides,
  };
}

function makeBoard(summaries: TaskSummary[] = []): Board {
  return {
    backlog: summaries,
    active: [],
    waiting: [],
    done: [],
    archived: [],
  };
}

function renderSection(task: Task) {
  return render(
    <MemoryRouter initialEntries={["/?task=" + task.id]}>
      <HierarchySection task={task} />
    </MemoryRouter>,
  );
}

beforeEach(() => {
  promoteMutateAsync.mockClear();
  setParentMutateAsync.mockClear();
  setDependsOnMutateAsync.mockClear();
  boardData = makeBoard();
  promoteState = { isPending: false, error: null };
  setParentState = { isPending: false, error: null };
  setDependsOnState = { isPending: false, error: null };
});

// ---------------------------------------------------------------------------
// Type badge
// ---------------------------------------------------------------------------

describe("HierarchySection — TypeBadge", () => {
  it("renders 'task' badge by default when task.type is undefined", () => {
    renderSection(makeTask({ type: undefined }));

    expect(screen.getByText("task")).toBeInTheDocument();
  });

  it("renders 'goal' badge when task.type is 'goal'", () => {
    renderSection(makeTask({ type: "goal" }));

    expect(screen.getByText("goal")).toBeInTheDocument();
  });

  it("renders 'issue' badge when task.type is 'issue'", () => {
    renderSection(makeTask({ type: "issue" }));

    expect(screen.getByText("issue")).toBeInTheDocument();
  });

  it("badge text is rendered in uppercase via the .uppercase class", () => {
    renderSection(makeTask({ type: "goal" }));

    const badge = screen.getByText("goal");
    expect(badge.className).toContain("uppercase");
  });
});

// ---------------------------------------------------------------------------
// Promote button visibility
// ---------------------------------------------------------------------------

describe("HierarchySection — Promote-to-Goal button visibility", () => {
  it("shows the Promote button when task.type is undefined (defaults to 'task')", () => {
    renderSection(makeTask({ type: undefined }));

    expect(
      screen.getByRole("button", { name: /Promote to Goal/i }),
    ).toBeInTheDocument();
  });

  it("shows the Promote button when task.type is 'task'", () => {
    renderSection(makeTask({ type: "task" }));

    expect(
      screen.getByRole("button", { name: /Promote to Goal/i }),
    ).toBeInTheDocument();
  });

  it("shows the Promote button when task.type is 'issue'", () => {
    renderSection(makeTask({ type: "issue" }));

    expect(
      screen.getByRole("button", { name: /Promote to Goal/i }),
    ).toBeInTheDocument();
  });

  it("HIDES the Promote button when task.type is already 'goal'", () => {
    renderSection(makeTask({ type: "goal" }));

    expect(
      screen.queryByRole("button", { name: /Promote to Goal/i }),
    ).not.toBeInTheDocument();
  });

  it("renders the button with 'Promoting…' label and disabled while pending", () => {
    promoteState = { isPending: true, error: null };
    renderSection(makeTask({ type: "task" }));

    const btn = screen.getByRole("button", { name: /Promoting…/i });
    expect(btn).toBeInTheDocument();
    expect(btn).toBeDisabled();
  });

  it("calls promote.mutateAsync when the Promote button is clicked", async () => {
    renderSection(makeTask({ type: "task" }));
    const user = userEvent.setup();

    await user.click(screen.getByRole("button", { name: /Promote to Goal/i }));

    expect(promoteMutateAsync).toHaveBeenCalledTimes(1);
  });

  it("renders the promote error message when promote.error is set", () => {
    promoteState = {
      isPending: false,
      error: new Error('400 on /x: {"detail":"already a goal"}'),
    };
    renderSection(makeTask({ type: "task" }));

    // extractDetail strips the wrapper and yields just the detail.
    expect(screen.getByText("already a goal")).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Children section visibility
// ---------------------------------------------------------------------------

describe("HierarchySection — Children section", () => {
  it("does NOT render the Children section when task.type is not 'goal' (no children, no type)", () => {
    boardData = makeBoard([
      makeSummary({ id: "c1", parent_id: "t-1", title: "Child One" }),
    ]);
    renderSection(makeTask({ id: "t-1", type: "task" }));

    expect(screen.queryByText("Children")).not.toBeInTheDocument();
  });

  it("does NOT render the Children section for a goal that has no children", () => {
    boardData = makeBoard([
      makeSummary({ id: "other", parent_id: null }),
    ]);
    renderSection(makeTask({ id: "t-1", type: "goal" }));

    expect(screen.queryByText("Children")).not.toBeInTheDocument();
  });

  it("renders the Children section for a goal with at least one child", () => {
    boardData = makeBoard([
      makeSummary({ id: "c1", parent_id: "t-1", title: "Child One" }),
    ]);
    renderSection(makeTask({ id: "t-1", type: "goal" }));

    expect(screen.getByText("Children")).toBeInTheDocument();
    // GoalDependencyGraph renders the title in both mobile list and graph node
    expect(screen.getAllByText("Child One").length).toBeGreaterThanOrEqual(1);
  });

  it("lists each child of the goal as a clickable button", () => {
    boardData = makeBoard([
      makeSummary({ id: "c1", parent_id: "t-1", title: "First child" }),
      makeSummary({ id: "c2", parent_id: "t-1", title: "Second child" }),
      makeSummary({ id: "unrelated", parent_id: "other" }),
    ]);
    renderSection(makeTask({ id: "t-1", type: "goal" }));

    expect(screen.getAllByText("First child").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("Second child").length).toBeGreaterThanOrEqual(1);
    // Unrelated tasks must not appear in the Children list.
    expect(screen.queryByText("unrelated")).not.toBeInTheDocument();
  });

  it("renders the state badge next to each child", () => {
    boardData = makeBoard([
      makeSummary({ id: "c1", parent_id: "t-1", title: "Active child", state: "active" }),
    ]);
    renderSection(makeTask({ id: "t-1", type: "goal" }));

    // GoalDependencyGraph renders the state in both mobile list and graph node
    expect(screen.getAllByText("active").length).toBeGreaterThanOrEqual(1);
  });

  it("does NOT render the Children section when board data is not yet loaded", () => {
    boardData = undefined;
    renderSection(makeTask({ id: "t-1", type: "goal" }));

    expect(screen.queryByText("Children")).not.toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Other top-level structure
// ---------------------------------------------------------------------------

describe("HierarchySection — top-level structure", () => {
  it("renders the 'Hierarchy' section heading", () => {
    renderSection(makeTask({ type: "task" }));

    expect(screen.getByText("Hierarchy")).toBeInTheDocument();
  });

  it("renders the Parent picker label", () => {
    renderSection(makeTask({ type: "task" }));

    expect(screen.getByText("Parent")).toBeInTheDocument();
  });

  it("renders the 'Depends on' picker label", () => {
    renderSection(makeTask({ type: "task" }));

    expect(screen.getByText("Depends on")).toBeInTheDocument();
  });

  it("renders existing dependencies as chips with the dep title from the board", () => {
    boardData = makeBoard([
      makeSummary({ id: "d1", title: "Migrate the schema" }),
    ]);
    renderSection(
      makeTask({ id: "t-1", type: "task", depends_on: ["d1"] }),
    );

    // Title from the board summary is displayed (not the bare id).
    expect(screen.getByText("Migrate the schema")).toBeInTheDocument();
  });

  it("falls back to the dep id when the board has no matching task", () => {
    boardData = makeBoard([]);
    renderSection(
      makeTask({ id: "t-1", type: "task", depends_on: ["unknown-id"] }),
    );

    expect(screen.getByText("unknown-id")).toBeInTheDocument();
  });

  it("renders the parent breadcrumb button when parent_id and parent_title are set", () => {
    renderSection(
      makeTask({
        id: "t-1",
        type: "task",
        parent_id: "p1",
        parent_title: "Roadmap",
      }),
    );

    // Parent picker shows current parent title inside a button.
    expect(screen.getByText("Roadmap")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /Change/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /Remove/i }),
    ).toBeInTheDocument();
  });
});
