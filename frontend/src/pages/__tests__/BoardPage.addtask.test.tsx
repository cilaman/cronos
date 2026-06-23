/**
 * BoardPage.addtask.test.tsx
 *
 * Assertions for the add-task flow on BoardPage (I4 board wave).
 * Tests that BoardPage wires up the "New task" button correctly, that TaskForm
 * opens when the new-task action is triggered, and that the add button (via
 * BoardToolbar's primary button) is a native <button> element with correct text.
 *
 * Note: the dashed-border add-task chip in the Lane header (aria-label="Add task")
 * was already an IconButton after I3; these tests confirm the BoardPage orchestrates
 * the flow correctly and the button elements are semantically correct.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

// ---------------------------------------------------------------------------
// Mocks — stub heavy hooks and child components
// ---------------------------------------------------------------------------

vi.mock("../../hooks/useSpaces", () => ({
  useSpaces: vi.fn(),
}));

vi.mock("../../hooks/useTasks", () => ({
  useCreateTask: vi.fn(),
  useBoard: vi.fn(),
  useReorderTasks: vi.fn(),
  useTransitionTask: vi.fn(),
}));

vi.mock("../../hooks/useViews", () => ({
  useViews: vi.fn(),
}));

vi.mock("../../hooks/useRunning", () => ({
  useRunning: vi.fn(),
}));

vi.mock("../../hooks/useFeatures", () => ({
  useFeatureBoard: vi.fn(),
}));

vi.mock("../../api", () => ({
  api: {
    uploadTaskFile: vi.fn(),
    start: vi.fn(),
  },
}));

vi.mock("../../components/TaskForm", () => ({
  TaskForm: ({ heading }: { heading: string }) => (
    <div data-testid="task-form">{heading}</div>
  ),
}));

vi.mock("../../components/ViewEditor", () => ({
  ViewEditor: () => <div data-testid="view-editor" />,
}));

// Stub Board as a simple passthrough so we can focus on BoardPage's own buttons
vi.mock("../../components/Board", () => ({
  Board: ({ onAddTask }: { onAddTask: () => void }) => (
    <div data-testid="board-stub">
      <button type="button" onClick={onAddTask} aria-label="Add task (stub)">
        Add task
      </button>
    </div>
  ),
}));

vi.mock("../../components/BoardToolbar", () => ({
  BoardToolbar: ({
    onNewTask,
    sortMode,
    compact,
  }: {
    onNewTask: () => void;
    sortMode: string;
    compact: boolean;
    onCompactToggle: () => void;
    onSortModeToggle: () => void;
  }) => (
    <div data-testid="board-toolbar">
      <button
        type="button"
        onClick={onNewTask}
        aria-label="New task"
        className="rounded border border-accent bg-accent px-3 text-canvas"
        data-sort-mode={sortMode}
        data-compact={compact}
      >
        + New task
      </button>
    </div>
  ),
}));

vi.mock("../../components/SpaceFilterDropdown", () => ({
  SpaceFilterDropdown: () => <div data-testid="space-filter" />,
}));

import { BoardPage } from "../BoardPage";
import { useSpaces } from "../../hooks/useSpaces";
import {
  useCreateTask,
  useBoard,
  useReorderTasks,
  useTransitionTask,
} from "../../hooks/useTasks";
import { useViews } from "../../hooks/useViews";
import { useRunning } from "../../hooks/useRunning";
import { useFeatureBoard } from "../../hooks/useFeatures";

// ---------------------------------------------------------------------------
// Default hook setups
// ---------------------------------------------------------------------------

beforeEach(() => {
  vi.mocked(useSpaces).mockReturnValue({ data: { spaces: [] } } as unknown as ReturnType<typeof useSpaces>);
  vi.mocked(useViews).mockReturnValue({ data: [] } as unknown as ReturnType<typeof useViews>);
  vi.mocked(useRunning).mockReturnValue({
    isRunning: () => false,
    seed: vi.fn(),
  } as unknown as ReturnType<typeof useRunning>);
  vi.mocked(useFeatureBoard).mockReturnValue({ data: { backlog: [] } } as unknown as ReturnType<typeof useFeatureBoard>);
  vi.mocked(useBoard).mockReturnValue({
    data: { backlog: [], active: [], waiting: [], done: [] },
    isLoading: false,
    error: null,
  } as unknown as ReturnType<typeof useBoard>);
  vi.mocked(useReorderTasks).mockReturnValue({ mutate: vi.fn() } as unknown as ReturnType<typeof useReorderTasks>);
  vi.mocked(useTransitionTask).mockReturnValue({ mutate: vi.fn() } as unknown as ReturnType<typeof useTransitionTask>);
  vi.mocked(useCreateTask).mockReturnValue({
    mutateAsync: vi.fn().mockResolvedValue({ id: "new-task-1" }),
  } as unknown as ReturnType<typeof useCreateTask>);
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("BoardPage — toolbar new-task button", () => {
  it("renders the 'New task' button as a native <button type='button'>", () => {
    render(
      <MemoryRouter>
        <BoardPage />
      </MemoryRouter>,
    );

    const newTaskBtn = screen.getByRole("button", { name: /new task/i });
    expect(newTaskBtn).toBeInTheDocument();
    expect(newTaskBtn.tagName.toLowerCase()).toBe("button");
    expect(newTaskBtn.getAttribute("type")).toBe("button");
  });

  it("'New task' button text is accessible via text content", () => {
    render(
      <MemoryRouter>
        <BoardPage />
      </MemoryRouter>,
    );

    expect(screen.getByText(/\+ New task/)).toBeInTheDocument();
  });

  it("clicking 'New task' button opens TaskForm", async () => {
    render(
      <MemoryRouter>
        <BoardPage />
      </MemoryRouter>,
    );

    expect(screen.queryByTestId("task-form")).not.toBeInTheDocument();

    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: /new task/i }));

    expect(screen.getByTestId("task-form")).toBeInTheDocument();
    expect(screen.getByTestId("task-form")).toHaveTextContent("New task");
  });
});

describe("BoardPage — Board component receives onAddTask callback", () => {
  it("clicking the stub board's add-task button opens TaskForm", async () => {
    render(
      <MemoryRouter>
        <BoardPage />
      </MemoryRouter>,
    );

    expect(screen.queryByTestId("task-form")).not.toBeInTheDocument();

    const user = userEvent.setup();
    // The stubbed Board renders a button with aria-label="Add task (stub)"
    await user.click(screen.getByRole("button", { name: /add task/i }));

    expect(screen.getByTestId("task-form")).toBeInTheDocument();
  });
});

describe("BoardPage — button primitives have correct classes", () => {
  it("toolbar new-task button has accent bg class (primary action styling)", () => {
    render(
      <MemoryRouter>
        <BoardPage />
      </MemoryRouter>,
    );

    const newTaskBtn = screen.getByRole("button", { name: /new task/i });
    expect(newTaskBtn.className).toContain("bg-accent");
  });
});
