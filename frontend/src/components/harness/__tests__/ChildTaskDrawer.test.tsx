import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import type { Task } from "../../../types";

// ── Module mocks ─────────────────────────────────────────────────────────────

vi.mock("../../../hooks/useTasks", () => ({
  useTask: vi.fn(),
}));

vi.mock("../../ConversationStream", () => ({
  ConversationStream: ({ task }: { task: Task }) => (
    <div data-testid="conversation-stream" data-task-id={task.id}>
      ConversationStream:{task.title}
    </div>
  ),
}));

import { useTask } from "../../../hooks/useTasks";
import { ChildTaskDrawer } from "../ChildTaskDrawer";

// ── Helpers ───────────────────────────────────────────────────────────────────

function makeTask(overrides: Partial<Task> = {}): Task {
  return {
    id: "task-abc",
    space_id: "space-1",
    title: "Child Task Title",
    state: "active",
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    claude_session_id: null,
    waiting_question: null,
    brief: "Do something",
    history: "[]",
    pending_messages: [],
    agent_mode: "auto",
    agent_model: "default",
    priority: 0,
    manual_order: 0,
    space_name: null,
    space_color: null,
    space_icon: null,
    ...overrides,
  };
}

const mockedUseTask = vi.mocked(useTask);

// ── Tests ─────────────────────────────────────────────────────────────────────

describe("ChildTaskDrawer", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders nothing when child_task_id is null (R3 AC-2)", () => {
    mockedUseTask.mockReturnValue({
      data: undefined,
      isLoading: false,
    } as ReturnType<typeof useTask>);

    const { container } = render(
      <ChildTaskDrawer child_task_id={null} />
    );

    expect(container.firstChild).toBeNull();
  });

  it("renders the drawer container when child_task_id is provided", () => {
    mockedUseTask.mockReturnValue({
      data: makeTask(),
      isLoading: false,
    } as ReturnType<typeof useTask>);

    render(<ChildTaskDrawer child_task_id="task-abc" />);

    expect(screen.getByTestId("child-task-drawer")).toBeTruthy();
  });

  it("shows loading skeleton while task is loading", () => {
    mockedUseTask.mockReturnValue({
      data: undefined,
      isLoading: true,
    } as ReturnType<typeof useTask>);

    render(<ChildTaskDrawer child_task_id="task-abc" />);

    expect(screen.getByTestId("child-task-drawer-skeleton")).toBeTruthy();
    expect(screen.getByLabelText("Loading task")).toBeTruthy();
    expect(screen.queryByTestId("conversation-stream")).toBeNull();
  });

  it("renders ConversationStream after task resolves (skeleton -> ConversationStream transition)", () => {
    // Start with loading state
    mockedUseTask.mockReturnValueOnce({
      data: undefined,
      isLoading: true,
    } as ReturnType<typeof useTask>);

    const { rerender } = render(<ChildTaskDrawer child_task_id="task-abc" />);
    expect(screen.getByTestId("child-task-drawer-skeleton")).toBeTruthy();
    expect(screen.queryByTestId("conversation-stream")).toBeNull();

    // Now task resolves
    mockedUseTask.mockReturnValueOnce({
      data: makeTask({ id: "task-abc", title: "Child Task Title" }),
      isLoading: false,
    } as ReturnType<typeof useTask>);

    rerender(<ChildTaskDrawer child_task_id="task-abc" />);
    expect(screen.queryByTestId("child-task-drawer-skeleton")).toBeNull();
    const stream = screen.getByTestId("conversation-stream");
    expect(stream).toBeTruthy();
    expect(stream.getAttribute("data-task-id")).toBe("task-abc");
  });

  it("passes the resolved task to ConversationStream with correct id", () => {
    const task = makeTask({ id: "task-xyz", title: "My Task" });
    mockedUseTask.mockReturnValue({
      data: task,
      isLoading: false,
    } as ReturnType<typeof useTask>);

    render(<ChildTaskDrawer child_task_id="task-xyz" />);

    const stream = screen.getByTestId("conversation-stream");
    expect(stream.getAttribute("data-task-id")).toBe("task-xyz");
    expect(stream.textContent).toBe("ConversationStream:My Task");
  });

  it("calls useTask with the provided child_task_id", () => {
    mockedUseTask.mockReturnValue({
      data: makeTask(),
      isLoading: false,
    } as ReturnType<typeof useTask>);

    render(<ChildTaskDrawer child_task_id="task-abc" />);

    expect(mockedUseTask).toHaveBeenCalledWith("task-abc");
  });

  it("calls useTask with null when child_task_id is null", () => {
    mockedUseTask.mockReturnValue({
      data: undefined,
      isLoading: false,
    } as ReturnType<typeof useTask>);

    render(<ChildTaskDrawer child_task_id={null} />);

    expect(mockedUseTask).toHaveBeenCalledWith(null);
  });

  it("renders 'task not found' fallback when task is undefined and not loading", () => {
    mockedUseTask.mockReturnValue({
      data: undefined,
      isLoading: false,
    } as ReturnType<typeof useTask>);

    render(<ChildTaskDrawer child_task_id="task-missing" />);

    expect(screen.getByText("// task not found")).toBeTruthy();
    expect(screen.queryByTestId("conversation-stream")).toBeNull();
  });

  it("renders close button when onClose prop is provided", () => {
    const onClose = vi.fn();
    mockedUseTask.mockReturnValue({
      data: makeTask(),
      isLoading: false,
    } as ReturnType<typeof useTask>);

    render(<ChildTaskDrawer child_task_id="task-abc" onClose={onClose} />);

    expect(screen.getByLabelText("Close drawer")).toBeTruthy();
  });

  it("does not render close button when onClose is not provided", () => {
    mockedUseTask.mockReturnValue({
      data: makeTask(),
      isLoading: false,
    } as ReturnType<typeof useTask>);

    render(<ChildTaskDrawer child_task_id="task-abc" />);

    expect(screen.queryByLabelText("Close drawer")).toBeNull();
  });
});
