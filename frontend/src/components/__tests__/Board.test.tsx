import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { TaskState, TaskSummary } from "../../types";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

// useBoard returns a 4-lane board. We override via boardResult so each
// test can shape the lanes without re-mocking.
let boardResult: {
  data: Record<TaskState, TaskSummary[]> | null;
  isLoading: boolean;
  error: Error | null;
} = {
  data: { backlog: [], active: [], waiting: [], done: [], archived: [] },
  isLoading: false,
  error: null,
};

const transitionMutate = vi.fn();
const reorderMutate = vi.fn();

vi.mock("../../hooks/useTasks", () => ({
  useBoard: () => boardResult,
  useTransitionTask: () => ({ mutate: transitionMutate }),
  useReorderTasks: () => ({ mutate: reorderMutate }),
}));

vi.mock("../../hooks/useRunning", () => ({
  useRunning: () => ({ isRunning: () => false, seed: vi.fn() }),
}));

// Detail mounts on openId and reads from `useTask`; stub it out so we don't
// need to provide a full task fixture for these board-shape tests.
vi.mock("../Detail", () => ({
  Detail: ({ taskId }: { taskId: string }) => (
    <div data-testid="detail-mock" data-task-id={taskId} />
  ),
}));

// Import AFTER vi.mock so mocks apply.
import { Board } from "../Board";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeTask(overrides: Partial<TaskSummary> = {}): TaskSummary {
  return {
    id: "task-1",
    space_id: "space-1",
    title: "A task",
    state: "backlog",
    created_at: "2024-01-15T14:00:00Z",
    updated_at: "2024-01-15T14:30:00Z",
    waiting_question: null,
    brief_preview: "",
    priority: 3,
    manual_order: 0,
    agent_mode: "auto",
    space_name: "Cronos",
    space_color: "#0F766E",
    space_icon: "🛰️",
    ...overrides,
  };
}

function renderBoard(props: Partial<React.ComponentProps<typeof Board>> = {}) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false, refetchInterval: false, staleTime: Infinity },
    },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/spaces/space-1"]}>
        <Board spaceId="space-1" onAddTask={() => {}} {...props} />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  boardResult = {
    data: { backlog: [], active: [], waiting: [], done: [], archived: [] },
    isLoading: false,
    error: null,
  };
  transitionMutate.mockClear();
  reorderMutate.mockClear();
});

// ---------------------------------------------------------------------------
// isLoading early return — the new useMemo move means this must not crash.
// ---------------------------------------------------------------------------

describe("Board — isLoading early return", () => {
  it("renders the Loading… message and does not crash (regression: useMemo moved above early return)", () => {
    boardResult = { data: null, isLoading: true, error: null };
    renderBoard();
    expect(screen.getByText(/Loading board/i)).toBeInTheDocument();
  });

  it("renders an error message when error is set (and not a 404)", () => {
    boardResult = {
      data: null,
      isLoading: false,
      error: new Error("500 Internal Server Error"),
    };
    renderBoard();
    expect(screen.getByText(/Error: 500 Internal Server Error/)).toBeInTheDocument();
  });

  it("silently swallows 404 errors (BoardPage handles them via URL reset)", () => {
    boardResult = {
      data: null,
      isLoading: false,
      error: new Error("404 Not Found"),
    };
    const { container } = renderBoard();
    // No error paragraph and no lanes rendered (data is null).
    expect(container.textContent).not.toMatch(/Error: 404/);
    expect(screen.queryByRole("heading", { name: "To Do" })).not.toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// visibleLaneStates — hides lanes and renders restore chips.
// ---------------------------------------------------------------------------

describe("Board — visibleLaneStates / hidden lane chip row", () => {
  it("renders all four default lanes when visibleLaneStates is omitted", () => {
    renderBoard();
    expect(screen.getByRole("heading", { name: "To Do" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Active" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Waiting" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Done" })).toBeInTheDocument();
  });

  it("hides lanes that are not in visibleLaneStates", () => {
    renderBoard({ visibleLaneStates: ["active", "waiting"] });
    expect(screen.queryByRole("heading", { name: "To Do" })).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Done" })).not.toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Active" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Waiting" })).toBeInTheDocument();
  });

  it("does NOT render the 'Hidden:' chip row when all lanes are visible", () => {
    renderBoard({
      visibleLaneStates: ["backlog", "active", "waiting", "done"],
    });
    expect(screen.queryByText("Hidden:")).not.toBeInTheDocument();
  });

  it("renders the 'Hidden:' chip row and one chip per hidden lane when some are hidden", () => {
    renderBoard({ visibleLaneStates: ["active", "waiting"] });
    expect(screen.getByText("Hidden:")).toBeInTheDocument();
    // Hidden lanes are To Do and Done; chip labels are "+ <label>".
    expect(screen.getByRole("button", { name: /Show To Do lane/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Show Done lane/i })).toBeInTheDocument();
    // Visible lanes must NOT appear as restore chips.
    expect(screen.queryByRole("button", { name: /Show Active lane/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Show Waiting lane/i })).not.toBeInTheDocument();
  });

  it("clicking a hidden-lane chip fires onShowLane(state)", async () => {
    const onShowLane = vi.fn();
    renderBoard({
      visibleLaneStates: ["active", "waiting"],
      onShowLane,
    });

    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: /Show To Do lane/i }));

    expect(onShowLane).toHaveBeenCalledTimes(1);
    expect(onShowLane).toHaveBeenCalledWith("backlog");
  });

  it("falls back to activeLaneStates (deprecated) when visibleLaneStates is undefined", () => {
    renderBoard({ activeLaneStates: ["backlog"] });
    expect(screen.getByRole("heading", { name: "To Do" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Active" })).not.toBeInTheDocument();
    // hiddenLanes shows the 3 others as chips.
    expect(screen.getByText("Hidden:")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Show Active lane/i })).toBeInTheDocument();
  });

  it("visibleLaneStates takes precedence over activeLaneStates when both are set", () => {
    renderBoard({
      activeLaneStates: ["backlog"],
      visibleLaneStates: ["done"],
    });
    expect(screen.getByRole("heading", { name: "Done" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "To Do" })).not.toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// onHideLane prop wiring — each visible Lane should receive it.
// ---------------------------------------------------------------------------

describe("Board — onHideLane wiring to each Lane", () => {
  it("renders a 'Hide <label> lane' button per visible lane when onHideLane is provided", () => {
    renderBoard({ onHideLane: vi.fn() });
    expect(screen.getByRole("button", { name: /Hide To Do lane/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Hide Active lane/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Hide Waiting lane/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Hide Done lane/i })).toBeInTheDocument();
  });

  it("does NOT render any 'Hide … lane' button when onHideLane is omitted", () => {
    renderBoard();
    expect(screen.queryByRole("button", { name: /Hide .* lane/i })).not.toBeInTheDocument();
  });

  it("invokes onHideLane with the lane state when a lane's × is clicked", async () => {
    const onHideLane = vi.fn();
    renderBoard({ onHideLane });

    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: /Hide Waiting lane/i }));

    expect(onHideLane).toHaveBeenCalledTimes(1);
    expect(onHideLane).toHaveBeenCalledWith("waiting");
  });

  it("only renders the × on lanes that are actually visible", () => {
    renderBoard({
      visibleLaneStates: ["active"],
      onHideLane: vi.fn(),
    });
    expect(screen.getByRole("button", { name: /Hide Active lane/i })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Hide To Do lane/i })).not.toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// hideExpandedChildren — children whose expanded parent is on the board
// are filtered out. Pre-existing behavior but the useMemo was just moved
// above the early returns, so re-verify it didn't regress.
// ---------------------------------------------------------------------------

describe("Board — hideExpandedChildren (regression: useMemo above early return)", () => {
  it("filters out child tasks when their parent goal is in expandedGoals", () => {
    boardResult = {
      data: {
        backlog: [
          makeTask({ id: "child-1", title: "Child of expanded goal", parent_id: "goal-1" }),
          makeTask({ id: "child-2", title: "Independent task" }),
        ],
        active: [],
        waiting: [],
        done: [],
        archived: [],
      },
      isLoading: false,
      error: null,
    };
    renderBoard({
      hideExpandedChildren: true,
      expandedGoals: new Set(["goal-1"]),
    });
    expect(screen.queryByText("Child of expanded goal")).not.toBeInTheDocument();
    expect(screen.getByText("Independent task")).toBeInTheDocument();
  });

  it("does NOT filter when hideExpandedChildren is false", () => {
    boardResult = {
      data: {
        backlog: [
          makeTask({ id: "child-1", title: "Child of expanded goal", parent_id: "goal-1" }),
        ],
        active: [],
        waiting: [],
        done: [],
        archived: [],
      },
      isLoading: false,
      error: null,
    };
    renderBoard({
      hideExpandedChildren: false,
      expandedGoals: new Set(["goal-1"]),
    });
    expect(screen.getByText("Child of expanded goal")).toBeInTheDocument();
  });
});
