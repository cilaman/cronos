import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import type { Task } from "../../types";

// ── Module mocks ─────────────────────────────────────────────────────────────

vi.mock("../../hooks/useTasks", () => ({
  useTask: vi.fn(),
  useUpdateTask: vi.fn(),
  useDeleteTask: vi.fn(),
  useArchiveTask: vi.fn(),
  useReplyToTask: vi.fn(),
  useStartTask: vi.fn(),
  useStopTask: vi.fn(),
  useTransitionTask: vi.fn(),
  useRoutePreview: vi.fn(),
  useBoard: vi.fn(),
  usePromoteTask: vi.fn(),
  useSetParent: vi.fn(),
  useSetDependsOn: vi.fn(),
}));

vi.mock("../../hooks/useStats", () => ({
  useTaskStats: vi.fn(),
}));

vi.mock("../../hooks/useTestReports", () => ({
  useTaskTestReportLatest: vi.fn(),
}));

vi.mock("../TaskActionBar", () => ({
  TaskActionBar: (props: {
    taskState: string;
    isStarting: boolean;
    isStopping: boolean;
    isDeleting: boolean;
    isArchiving: boolean;
    isMarkingDone: boolean;
    isSendingToBacklog: boolean;
    onStart: () => void;
    onStop: () => void;
    onEdit: () => void;
    onDelete: () => void;
    onArchive: () => void;
    onMarkDone: () => void;
    onSendToBacklog: () => void;
  }) => (
    <div data-testid="action-bar">
      <button data-testid="start-btn" onClick={props.onStart}>
        Start
      </button>
      <button data-testid="stop-btn" onClick={props.onStop}>
        Stop
      </button>
      <button data-testid="delete-btn" onClick={props.onDelete}>
        Delete
      </button>
      <button data-testid="archive-btn" onClick={props.onArchive}>
        Archive
      </button>
      <button data-testid="done-btn" onClick={props.onMarkDone}>
        Done
      </button>
      <button
        data-testid="send-to-backlog-btn"
        onClick={props.onSendToBacklog}
      >
        Send to Backlog
      </button>
      <button data-testid="edit-btn" onClick={props.onEdit}>
        Edit
      </button>
    </div>
  ),
}));

vi.mock("../ConversationStream", () => ({
  ConversationStream: () => null,
}));

vi.mock("../FilesPanel", () => ({
  FilesPanel: () => null,
}));

vi.mock("../TracePanel", () => ({
  TracePanel: () => null,
}));

vi.mock("../ChatInput", () => ({
  ChatInput: () => null,
}));

vi.mock("../TaskForm", () => ({
  TaskForm: () => null,
}));

vi.mock("../ui/Modal", () => ({
  Modal: (props: { children: React.ReactNode; onClose: () => void }) => (
    <div data-testid="modal" onClick={props.onClose}>
      {props.children}
    </div>
  ),
}));

vi.mock("../ui/SpaceTag", () => ({
  SpaceTag: () => null,
}));

vi.mock("react-markdown", () => ({
  default: (props: { children: string }) => <span>{props.children}</span>,
}));

vi.mock("remark-gfm", () => ({
  default: () => ({}),
}));

vi.mock("../../hooks/useLiveStream", () => ({
  useLiveStream: vi.fn().mockReturnValue({ entries: [], status: "ended" }),
}));

vi.mock("../../assets/cronos-state-active-animated.svg", () => ({
  default: "/mock-active.svg",
}));

// ── Imports after mocks ───────────────────────────────────────────────────────

import React from "react";
import {
  useTask,
  useUpdateTask,
  useDeleteTask,
  useArchiveTask,
  useReplyToTask,
  useStartTask,
  useStopTask,
  useTransitionTask,
  useRoutePreview,
  useBoard,
  usePromoteTask,
  useSetParent,
  useSetDependsOn,
} from "../../hooks/useTasks";
import { useTaskStats } from "../../hooks/useStats";
import { useTaskTestReportLatest } from "../../hooks/useTestReports";
import { useLiveStream } from "../../hooks/useLiveStream";
import { Detail } from "../Detail";

// ── Fixtures ──────────────────────────────────────────────────────────────────

const mockTask: Task = {
  id: "task-abc",
  space_id: "space-1",
  title: "Test Task Title",
  state: "backlog",
  created_at: "2024-01-01T00:00:00Z",
  updated_at: "2024-01-01T00:00:00Z",
  claude_session_id: null,
  waiting_question: null,
  brief: "## Brief\n\nDo the thing.",
  history: "",
  pending_messages: [],
  agent_mode: "auto",
  agent_model: "default",
  priority: 3,
  manual_order: 0,
  space_name: null,
  space_color: null,
  space_icon: null,
};

// ── Test helpers ──────────────────────────────────────────────────────────────

function makeMutation(mutateAsync: ReturnType<typeof vi.fn> = vi.fn().mockResolvedValue(undefined)) {
  return {
    mutateAsync,
    mutate: vi.fn(),
    isPending: false,
    isSuccess: false,
    isError: false,
    isIdle: true,
    error: null,
    reset: vi.fn(),
    data: undefined,
    variables: undefined,
    context: undefined,
    submittedAt: 0,
    status: "idle" as const,
    failureCount: 0,
    failureReason: null,
    isPaused: false,
  };
}

function renderDetail(taskId = "task-abc", onClose = vi.fn()) {
  return render(
    <MemoryRouter>
      <Detail taskId={taskId} onClose={onClose} />
    </MemoryRouter>,
  );
}

// ── Setup ─────────────────────────────────────────────────────────────────────

let startMutateAsync: ReturnType<typeof vi.fn>;
let stopMutateAsync: ReturnType<typeof vi.fn>;
let deleteMutateAsync: ReturnType<typeof vi.fn>;
let archiveMutateAsync: ReturnType<typeof vi.fn>;
let replyMutateAsync: ReturnType<typeof vi.fn>;
let transitionMutateAsync: ReturnType<typeof vi.fn>;
let updateMutateAsync: ReturnType<typeof vi.fn>;

beforeEach(() => {
  startMutateAsync = vi.fn().mockResolvedValue(mockTask);
  stopMutateAsync = vi.fn().mockResolvedValue(mockTask);
  deleteMutateAsync = vi.fn().mockResolvedValue(undefined);
  archiveMutateAsync = vi.fn().mockResolvedValue(mockTask);
  replyMutateAsync = vi.fn().mockResolvedValue(mockTask);
  transitionMutateAsync = vi.fn().mockResolvedValue(mockTask);
  updateMutateAsync = vi.fn().mockResolvedValue(mockTask);

  vi.mocked(useTask).mockReturnValue({
    data: mockTask,
    isLoading: false,
    error: null,
    refetch: vi.fn(),
  } as unknown as ReturnType<typeof useTask>);

  vi.mocked(useUpdateTask).mockReturnValue(
    makeMutation(updateMutateAsync) as unknown as ReturnType<typeof useUpdateTask>,
  );
  vi.mocked(useDeleteTask).mockReturnValue(
    makeMutation(deleteMutateAsync) as unknown as ReturnType<typeof useDeleteTask>,
  );
  vi.mocked(useArchiveTask).mockReturnValue(
    makeMutation(archiveMutateAsync) as unknown as ReturnType<typeof useArchiveTask>,
  );
  vi.mocked(useReplyToTask).mockReturnValue(
    makeMutation(replyMutateAsync) as unknown as ReturnType<typeof useReplyToTask>,
  );
  vi.mocked(useStartTask).mockReturnValue(
    makeMutation(startMutateAsync) as unknown as ReturnType<typeof useStartTask>,
  );
  vi.mocked(useStopTask).mockReturnValue(
    makeMutation(stopMutateAsync) as unknown as ReturnType<typeof useStopTask>,
  );
  vi.mocked(useTransitionTask).mockReturnValue(
    makeMutation(transitionMutateAsync) as unknown as ReturnType<typeof useTransitionTask>,
  );

  vi.mocked(useRoutePreview).mockReturnValue({
    data: undefined,
    isLoading: false,
    error: null,
  } as unknown as ReturnType<typeof useRoutePreview>);

  vi.mocked(useBoard).mockReturnValue({
    data: undefined,
    isLoading: false,
    error: null,
  } as unknown as ReturnType<typeof useBoard>);

  vi.mocked(usePromoteTask).mockReturnValue(
    makeMutation() as unknown as ReturnType<typeof usePromoteTask>,
  );
  vi.mocked(useSetParent).mockReturnValue(
    makeMutation() as unknown as ReturnType<typeof useSetParent>,
  );
  vi.mocked(useSetDependsOn).mockReturnValue(
    makeMutation() as unknown as ReturnType<typeof useSetDependsOn>,
  );

  vi.mocked(useTaskStats).mockReturnValue({
    data: undefined,
    isLoading: true,
  } as unknown as ReturnType<typeof useTaskStats>);

  vi.mocked(useTaskTestReportLatest).mockReturnValue({
    data: undefined,
    isLoading: false,
  } as unknown as ReturnType<typeof useTaskTestReportLatest>);

  vi.mocked(useLiveStream).mockReturnValue({ entries: [], status: "ended" });
});

// ── Tests ─────────────────────────────────────────────────────────────────────

describe("Detail — loading state", () => {
  it("renders a loading skeleton while task is fetching", () => {
    vi.mocked(useTask).mockReturnValue({
      data: undefined,
      isLoading: true,
      error: null,
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof useTask>);

    const { container } = renderDetail();
    expect(container.querySelector(".animate-pulse")).toBeInTheDocument();
  });

  it("renders an error message and retry button on fetch failure", () => {
    vi.mocked(useTask).mockReturnValue({
      data: undefined,
      isLoading: false,
      error: new Error("Network error"),
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof useTask>);

    renderDetail();
    expect(screen.getByText("Network error")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /retry/i })).toBeInTheDocument();
  });
});

describe("Detail — task loaded", () => {
  it("renders the task title", () => {
    renderDetail();
    expect(screen.getByText("Test Task Title")).toBeInTheDocument();
  });

  it("renders the task state badge", () => {
    renderDetail();
    expect(screen.getByText("backlog")).toBeInTheDocument();
  });

  it("renders the priority badge", () => {
    renderDetail();
    expect(screen.getByText("P3")).toBeInTheDocument();
  });

  it("renders the task ID in the header", () => {
    renderDetail();
    expect(screen.getByText("task-abc")).toBeInTheDocument();
  });

  it("calls onClose when the close button is clicked", async () => {
    const onClose = vi.fn();
    renderDetail("task-abc", onClose);
    await userEvent.click(screen.getByRole("button", { name: /close/i }));
    expect(onClose).toHaveBeenCalledOnce();
  });

  it("renders the action bar", () => {
    renderDetail();
    expect(screen.getByTestId("action-bar")).toBeInTheDocument();
  });

  it("renders tab buttons for Details, Stats, and Trace", () => {
    renderDetail();
    expect(screen.getByRole("button", { name: /details/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /stats/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /trace/i })).toBeInTheDocument();
  });

  it("renders Priority, Mode, and Model dropdowns in the header", () => {
    renderDetail();
    const selects = screen.getAllByRole("combobox");
    // At least 3 dropdowns: Priority, Mode, Model
    expect(selects.length).toBeGreaterThanOrEqual(3);
  });
});

describe("Detail — mutations via action bar", () => {
  it("calls startTask.mutateAsync when Start button is clicked", async () => {
    renderDetail();
    await userEvent.click(screen.getByTestId("start-btn"));
    await waitFor(() => expect(startMutateAsync).toHaveBeenCalledOnce());
  });

  it("calls stopTask.mutateAsync when Stop button is clicked", async () => {
    renderDetail();
    await userEvent.click(screen.getByTestId("stop-btn"));
    await waitFor(() => expect(stopMutateAsync).toHaveBeenCalledOnce());
  });

  it("calls archiveTask.mutateAsync when Archive button is clicked", async () => {
    renderDetail();
    await userEvent.click(screen.getByTestId("archive-btn"));
    await waitFor(() => expect(archiveMutateAsync).toHaveBeenCalledOnce());
  });

  it("calls transitionTask.mutateAsync with done state when Done is clicked", async () => {
    renderDetail();
    await userEvent.click(screen.getByTestId("done-btn"));
    await waitFor(() =>
      expect(transitionMutateAsync).toHaveBeenCalledWith({
        id: "task-abc",
        state: "done",
      }),
    );
  });

  it("calls transitionTask.mutateAsync with backlog state when Send to Backlog is clicked", async () => {
    // Mirrors the Mark Done test above. Locks the new onSendToBacklog handler
    // wiring in Detail.tsx (calls transitionTask with state: "backlog").
    renderDetail();
    await userEvent.click(screen.getByTestId("send-to-backlog-btn"));
    await waitFor(() =>
      expect(transitionMutateAsync).toHaveBeenCalledWith({
        id: "task-abc",
        state: "backlog",
      }),
    );
  });

  it("calls deleteTask.mutateAsync and then onClose when delete is confirmed", async () => {
    const onClose = vi.fn();
    vi.spyOn(window, "confirm").mockReturnValue(true);

    renderDetail("task-abc", onClose);
    await userEvent.click(screen.getByTestId("delete-btn"));

    await waitFor(() => {
      expect(deleteMutateAsync).toHaveBeenCalledWith("task-abc");
      expect(onClose).toHaveBeenCalled();
    });

    vi.restoreAllMocks();
  });

  it("does not call deleteTask.mutateAsync when delete is cancelled", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(false);

    renderDetail();
    await userEvent.click(screen.getByTestId("delete-btn"));

    // Confirm was denied — mutateAsync should NOT have been called
    expect(deleteMutateAsync).not.toHaveBeenCalled();

    vi.restoreAllMocks();
  });
});

describe("Detail — tab switching", () => {
  it("renders the brief markdown content on the Details tab", () => {
    renderDetail();
    // react-markdown mock renders children as text
    expect(screen.getByText(/Do the thing/)).toBeInTheDocument();
  });

  it("switches to Stats tab and shows StatsPanel", async () => {
    renderDetail();
    await userEvent.click(screen.getByRole("button", { name: /stats/i }));
    expect(screen.getByText(/Loading stats/)).toBeInTheDocument();
  });
});

describe("Detail — two-pane layout (I4)", () => {
  it("renders context-pane with overflow-y-auto class", () => {
    renderDetail();
    expect(screen.getByTestId("context-pane")).toHaveClass("overflow-y-auto");
  });

  it("renders conversation-pane with overflow-y-auto class", () => {
    renderDetail();
    expect(screen.getByTestId("conversation-pane")).toHaveClass("overflow-y-auto");
  });

  it("renders mobile Context and Conversation sub-tab buttons inside details tab", () => {
    renderDetail();
    expect(screen.getByRole("button", { name: /^context$/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^conversation$/i })).toBeInTheDocument();
  });

  it("conversation pane wrapper has hidden class by default (mobile context tab active)", () => {
    renderDetail();
    const convWrapper = screen.getByTestId("conversation-pane").parentElement;
    expect(convWrapper).toHaveClass("hidden");
  });

  it("clicking Conversation sub-tab removes hidden class from conversation pane wrapper", async () => {
    renderDetail();
    await userEvent.click(screen.getByRole("button", { name: /^conversation$/i }));
    const convWrapper = screen.getByTestId("conversation-pane").parentElement;
    expect(convWrapper).not.toHaveClass("hidden");
  });
});

describe("Detail — NOW running card (I5)", () => {
  it("does NOT render the NOW running card when task is not active", () => {
    renderDetail(); // mockTask has state: "backlog"
    expect(screen.queryByTestId("now-running-card")).not.toBeInTheDocument();
  });

  it("renders the NOW running card when task.state === 'active'", () => {
    vi.mocked(useTask).mockReturnValue({
      data: { ...mockTask, state: "active" },
      isLoading: false,
      error: null,
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof useTask>);

    renderDetail();
    expect(screen.getByTestId("now-running-card")).toBeInTheDocument();
    expect(screen.getByText("NOW running")).toBeInTheDocument();
  });

  it("shows the latest tool name from live stream", async () => {
    vi.mocked(useTask).mockReturnValue({
      data: { ...mockTask, state: "active" },
      isLoading: false,
      error: null,
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof useTask>);

    vi.mocked(useLiveStream).mockReturnValue({
      entries: [
        { id: "1", kind: "tool_call", toolUseId: "t1", name: "Read", input: {} },
        { id: "2", kind: "tool_call", toolUseId: "t2", name: "Write", input: {} },
      ],
      status: "live",
    });

    renderDetail();
    expect(screen.getByTestId("now-tool-name")).toHaveTextContent("Write");
  });

  it("shows the correct step count from live stream", () => {
    vi.mocked(useTask).mockReturnValue({
      data: { ...mockTask, state: "active" },
      isLoading: false,
      error: null,
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof useTask>);

    vi.mocked(useLiveStream).mockReturnValue({
      entries: [
        { id: "1", kind: "tool_call", toolUseId: "t1", name: "Read", input: {} },
        { id: "2", kind: "assistant", text: "hello" },
        { id: "3", kind: "tool_call", toolUseId: "t2", name: "Write", input: {} },
      ],
      status: "live",
    });

    renderDetail();
    expect(screen.getByTestId("now-step-count")).toHaveTextContent("3 steps");
  });

  it("does not render tool-name span when no tool_call entries exist", () => {
    vi.mocked(useTask).mockReturnValue({
      data: { ...mockTask, state: "active" },
      isLoading: false,
      error: null,
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof useTask>);

    vi.mocked(useLiveStream).mockReturnValue({ entries: [], status: "live" });

    renderDetail();
    expect(screen.queryByTestId("now-tool-name")).not.toBeInTheDocument();
    expect(screen.getByTestId("now-step-count")).toHaveTextContent("0 steps");
  });
});

describe("Detail — React is available in mock scope", () => {
  it("React import is reachable (guards against tree-shaking)", () => {
    // This trivial test ensures the React import is counted as used.
    expect(React.version).toBeDefined();
  });
});
