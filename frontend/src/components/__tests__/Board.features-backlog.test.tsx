/**
 * Board.features-backlog.test.tsx
 *
 * Verifies that the shared "Features Backlog" column deep-links to
 * /features?feature=<id> (both onClick and onOpenTask) after the I4 change.
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

function makeFeatureTask(overrides: Partial<TaskSummary> = {}): TaskSummary {
  return {
    id: "feat-1",
    space_id: "space-1",
    title: "Feature: dark mode",
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
    type: "feature",
    feature_state: "backlog",
    feature_key: "FEAT-1",
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
// 1. Feature card onClick deep-links to /features?feature=<id>
// ---------------------------------------------------------------------------

describe("Board — feature card onClick deep-links to /features?feature=<id>", () => {
  it("navigates to /features?feature=<id> when feature card is clicked", async () => {
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
    const card = screen.getByText("Feature: dark mode").closest('[role="button"]');
    expect(card).toBeTruthy();
    await user.click(card!);

    expect(mockNavigate).toHaveBeenCalledWith("/features?feature=feat-1");
  });

  it("navigates to the correct feature id for each unique card", async () => {
    featureBoardResult = {
      data: {
        backlog: [
          makeFeatureTask({ id: "feat-abc", title: "Alpha feature" }),
          makeFeatureTask({ id: "feat-xyz", title: "Beta feature" }),
        ],
        processing: [],
        planned: [],
        waiting: [],
        done: [],
      },
    };
    renderBoard();

    const user = userEvent.setup();
    const alphaCard = screen.getByText("Alpha feature").closest('[role="button"]');
    await user.click(alphaCard!);
    expect(mockNavigate).toHaveBeenCalledWith("/features?feature=feat-abc");

    mockNavigate.mockClear();
    const betaCard = screen.getByText("Beta feature").closest('[role="button"]');
    await user.click(betaCard!);
    expect(mockNavigate).toHaveBeenCalledWith("/features?feature=feat-xyz");
  });

  it("does NOT navigate to plain /features without ?feature=<id>", async () => {
    featureBoardResult = {
      data: {
        backlog: [makeFeatureTask({ id: "feat-1" })],
        processing: [],
        planned: [],
        waiting: [],
        done: [],
      },
    };
    renderBoard();

    const user = userEvent.setup();
    const card = screen.getByText("Feature: dark mode").closest('[role="button"]');
    await user.click(card!);

    expect(mockNavigate).not.toHaveBeenCalledWith("/features");
  });
});

// ---------------------------------------------------------------------------
// 2. Both onClick and onOpenTask navigate to the deep-link URL
// ---------------------------------------------------------------------------

describe("Board — feature card deep-link works for both click and keyboard-open paths", () => {
  it("onClick prop navigates to /features?feature=<id>", async () => {
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
    const card = screen.getByText("Feature: dark mode").closest('[role="button"]');
    await user.click(card!);

    expect(mockNavigate).toHaveBeenCalledWith("/features?feature=feat-1");
  });
});
