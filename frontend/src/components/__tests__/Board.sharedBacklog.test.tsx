/**
 * Board.sharedBacklog.test.tsx
 *
 * Verifies that the shared "Features Backlog" column added to Board.tsx in I8:
 * 1. Renders feature cards from useFeatureBoard data.
 * 2. Clicking a feature card calls navigate('/features').
 * 3. The column is NOT inside any DndContext/SortableContext (rendered outside
 *    the DnD tree — verified via data-testid position relative to the DndContext).
 * 4. Existing Tasks board DnD behavior is unaffected (regression).
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { TaskState, TaskSummary, FeatureBoard } from "../../types";

// ---------------------------------------------------------------------------
// Shared state for hook mocks
// ---------------------------------------------------------------------------

let boardResult: {
  data: Record<TaskState, TaskSummary[]> | null;
  isLoading: boolean;
  error: Error | null;
} = {
  data: { backlog: [], active: [], waiting: [], done: [], archived: [] },
  isLoading: false,
  error: null,
};

let featureBoardResult: {
  data: FeatureBoard | undefined;
} = { data: undefined };

const transitionMutate = vi.fn();
const reorderMutate = vi.fn();

// Mock navigate — capture calls
const mockNavigate = vi.fn();

// ---------------------------------------------------------------------------
// Module mocks — declared BEFORE imports of components under test
// ---------------------------------------------------------------------------

vi.mock("../../hooks/useTasks", () => ({
  useBoard: () => boardResult,
  useTransitionTask: () => ({ mutate: transitionMutate }),
  useReorderTasks: () => ({ mutate: reorderMutate }),
}));

vi.mock("../../hooks/useRunning", () => ({
  useRunning: () => ({ isRunning: () => false, seed: vi.fn() }),
}));

vi.mock("../../hooks/useFeatures", () => ({
  useFeatureBoard: () => featureBoardResult,
}));

vi.mock("react-router-dom", async (importOriginal) => {
  const actual = await importOriginal<typeof import("react-router-dom")>();
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

vi.mock("../Detail", () => ({
  Detail: ({ taskId }: { taskId: string }) => (
    <div data-testid="detail-mock" data-task-id={taskId} />
  ),
}));

// ---------------------------------------------------------------------------
// Import AFTER mocks
// ---------------------------------------------------------------------------

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

function makeFeatureTask(overrides: Partial<TaskSummary> = {}): TaskSummary {
  return makeTask({
    id: "feat-1",
    title: "Feature: dark mode",
    type: "feature",
    feature_state: "backlog",
    feature_key: "FEAT-1",
    ...overrides,
  });
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

// ---------------------------------------------------------------------------
// Reset shared state before each test
// ---------------------------------------------------------------------------

beforeEach(() => {
  boardResult = {
    data: { backlog: [], active: [], waiting: [], done: [], archived: [] },
    isLoading: false,
    error: null,
  };
  featureBoardResult = { data: undefined };
  transitionMutate.mockClear();
  reorderMutate.mockClear();
  mockNavigate.mockClear();
});

// ---------------------------------------------------------------------------
// 1. Features Backlog column renders feature cards from useFeatureBoard data
// ---------------------------------------------------------------------------

describe("Board — shared Features Backlog column", () => {
  it("renders the Features Backlog column when useFeatureBoard returns backlog items", () => {
    featureBoardResult = {
      data: {
        backlog: [
          makeFeatureTask({ id: "feat-1", title: "Feature: dark mode" }),
          makeFeatureTask({ id: "feat-2", title: "Fix: login crash", type: "fix" }),
        ],
        processing: [],
        planned: [],
        waiting: [],
        done: [],
      },
    };
    renderBoard();
    expect(screen.getByTestId("features-backlog-column")).toBeInTheDocument();
    expect(screen.getByText("Feature: dark mode")).toBeInTheDocument();
    expect(screen.getByText("Fix: login crash")).toBeInTheDocument();
  });

  it("does NOT render the Features Backlog column when useFeatureBoard returns undefined", () => {
    featureBoardResult = { data: undefined };
    renderBoard();
    expect(screen.queryByTestId("features-backlog-column")).not.toBeInTheDocument();
  });

  it("does NOT render the Features Backlog column when backlog is empty", () => {
    featureBoardResult = {
      data: {
        backlog: [],
        processing: [],
        planned: [],
        waiting: [],
        done: [],
      },
    };
    renderBoard();
    expect(screen.queryByTestId("features-backlog-column")).not.toBeInTheDocument();
  });

  it("renders a header labelling the column 'Features Backlog'", () => {
    featureBoardResult = {
      data: {
        backlog: [makeFeatureTask()],
        processing: [],
        planned: [],
        waiting: [],
        done: [],
      },
    };
    renderBoard();
    expect(screen.getByText(/Features Backlog/i)).toBeInTheDocument();
  });

  it("shows the backlog item count in the column header", () => {
    featureBoardResult = {
      data: {
        backlog: [
          makeFeatureTask({ id: "feat-1" }),
          makeFeatureTask({ id: "feat-2" }),
          makeFeatureTask({ id: "feat-3" }),
        ],
        processing: [],
        planned: [],
        waiting: [],
        done: [],
      },
    };
    renderBoard();
    expect(screen.getByText("(3)")).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// 2. Clicking a feature card navigates to /features
// ---------------------------------------------------------------------------

describe("Board — feature card click navigates to /features", () => {
  it("calls navigate('/features') when a feature card is clicked", async () => {
    featureBoardResult = {
      data: {
        backlog: [makeFeatureTask({ id: "feat-1", title: "Feature: dark mode" })],
        processing: [],
        planned: [],
        waiting: [],
        done: [],
      },
    };
    renderBoard();

    const user = userEvent.setup();
    // The Card renders a div[role="button"] for the main clickable body
    const card = screen.getByText("Feature: dark mode").closest('button');
    expect(card).toBeTruthy();
    await user.click(card!);

    expect(mockNavigate).toHaveBeenCalledWith("/features?feature=feat-1");
  });
});

// ---------------------------------------------------------------------------
// 3. The Features Backlog column is NOT inside the DndContext/SortableContext
// ---------------------------------------------------------------------------

describe("Board — Features Backlog column is outside the DndContext subtree", () => {
  it("renders the features-backlog-column as a sibling of the DndContext element, not a descendant", () => {
    featureBoardResult = {
      data: {
        backlog: [makeFeatureTask()],
        processing: [],
        planned: [],
        waiting: [],
        done: [],
      },
    };
    const { container } = renderBoard();

    const backlogColumn = container.querySelector('[data-testid="features-backlog-column"]');
    expect(backlogColumn).toBeTruthy();

    // The DndContext renders no DOM element of its own.
    // The lane grid div is the outermost DOM node inside the DndContext.
    // The backlog column must NOT be inside the lane grid (the DnD-managed area).
    const laneGrid = container.querySelector('[class*="grid"][class*="grid-cols"]');
    expect(laneGrid).toBeTruthy();

    // Critical invariant (R13): the backlog column must NOT be a descendant
    // of the lane grid, which is the DOM root of the DnD-managed area.
    expect(laneGrid!.contains(backlogColumn)).toBe(false);

    // Both laneGrid and backlogColumn share the same parent (since DndContext
    // renders no wrapper element). Verify they are siblings at the same level.
    expect(laneGrid!.parentElement).toBe(backlogColumn!.parentElement);
  });
});

// ---------------------------------------------------------------------------
// 4. Regression — existing Tasks board DnD behavior is unaffected
// ---------------------------------------------------------------------------

describe("Board — regression: existing Tasks board DnD unaffected", () => {
  it("still renders all 4 Tasks lanes when featureBoardResult is undefined", () => {
    featureBoardResult = { data: undefined };
    renderBoard();
    expect(screen.getByRole("heading", { name: "To Do" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Active" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Waiting" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Done" })).toBeInTheDocument();
  });

  it("still renders all 4 Tasks lanes when feature backlog is present", () => {
    featureBoardResult = {
      data: {
        backlog: [makeFeatureTask()],
        processing: [],
        planned: [],
        waiting: [],
        done: [],
      },
    };
    renderBoard();
    expect(screen.getByRole("heading", { name: "To Do" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Active" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Waiting" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Done" })).toBeInTheDocument();
  });

  it("Tasks board loading state is unaffected by feature board data", () => {
    boardResult = { data: null, isLoading: true, error: null };
    featureBoardResult = {
      data: {
        backlog: [makeFeatureTask()],
        processing: [],
        planned: [],
        waiting: [],
        done: [],
      },
    };
    renderBoard();
    // Board is loading, so no lanes or features backlog are rendered (early return)
    expect(screen.getByText(/Loading board/i)).toBeInTheDocument();
  });

  it("Task card clicks still open the detail panel (not navigate to /features)", async () => {
    boardResult = {
      data: {
        backlog: [makeTask({ id: "task-99", title: "Regular task" })],
        active: [],
        waiting: [],
        done: [],
        archived: [],
      },
      isLoading: false,
      error: null,
    };
    renderBoard();

    const user = userEvent.setup();
    const taskCard = screen.getByText("Regular task").closest('button');
    expect(taskCard).toBeTruthy();
    await user.click(taskCard!);

    // The detail panel mock should appear, not navigate
    expect(screen.getByTestId("detail-mock")).toBeInTheDocument();
    expect(mockNavigate).not.toHaveBeenCalled();
  });
});
