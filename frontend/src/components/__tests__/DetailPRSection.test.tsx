import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { Board, Task } from "../../types";

// ---------------------------------------------------------------------------
// Mock all hooks consumed by Detail so we can drive the rendered task purely
// through the `useTask` return value. The "Pull Request" section is a pure
// function of (task.state, task.pr_url, task.proposed_pr_path).
// ---------------------------------------------------------------------------

let currentTask: Task | null = null;

const baseMutation = {
  mutateAsync: vi.fn().mockResolvedValue(undefined),
  isPending: false,
  error: null as Error | null,
};

vi.mock("../../hooks/useTasks", () => ({
  useTask: () => ({
    data: currentTask,
    isLoading: false,
    error: null,
    refetch: vi.fn(),
  }),
  useUpdateTask: () => baseMutation,
  useDeleteTask: () => baseMutation,
  useArchiveTask: () => baseMutation,
  useReplyToTask: () => baseMutation,
  useStartTask: () => baseMutation,
  useStopTask: () => baseMutation,
  useTransitionTask: () => baseMutation,
  usePromoteTask: () => baseMutation,
  useSetParent: () => baseMutation,
  useSetDependsOn: () => baseMutation,
  useBoard: () =>
    ({
      data: {
        backlog: [],
        active: [],
        waiting: [],
        done: [],
        archived: [],
      } as Board,
    }),
  useRoutePreview: () => ({ data: undefined }),
}));

vi.mock("../../hooks/useStats", () => ({
  useTaskStats: () => ({ data: undefined, isLoading: false }),
}));

vi.mock("../../hooks/useTestReports", () => ({
  useTaskTestReportLatest: () => ({ data: null }),
}));

// Heavy children — render as stubs so we don't have to satisfy their props.
vi.mock("../ChatInput", () => ({ ChatInput: () => <div data-testid="chat-input-stub" /> }));
vi.mock("../ConversationStream", () => ({
  ConversationStream: () => <div data-testid="conversation-stub" />,
}));
vi.mock("../FilesPanel", () => ({ FilesPanel: () => <div data-testid="files-stub" /> }));
vi.mock("../TaskActionBar", () => ({ TaskActionBar: () => <div data-testid="action-bar-stub" /> }));
vi.mock("../TaskForm", () => ({ TaskForm: () => <div data-testid="task-form-stub" /> }));
vi.mock("../TracePanel", () => ({ TracePanel: () => <div data-testid="trace-stub" /> }));

// Import AFTER vi.mock so mocked hooks are wired in.
import { Detail } from "../Detail";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeTask(overrides: Partial<Task> = {}): Task {
  return {
    id: "t-1",
    space_id: "space-1",
    title: "Demo Task",
    state: "done",
    created_at: "2024-01-15T14:00:00Z",
    updated_at: "2024-01-15T14:30:00Z",
    claude_session_id: null,
    waiting_question: null,
    brief: "Demo brief.",
    history: "",
    pending_messages: [],
    agent_mode: "auto",
    agent_model: "default",
    priority: 3,
    manual_order: 0,
    space_name: null,
    space_color: null,
    space_icon: null,
    pr_url: null,
    proposed_pr_path: null,
    ...overrides,
  };
}

function renderDetail() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: Infinity } },
  });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <Detail taskId="t-1" onClose={() => {}} />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  baseMutation.mutateAsync.mockClear();
  currentTask = null;
});

// ---------------------------------------------------------------------------
// Pull Request section — visibility matrix
// ---------------------------------------------------------------------------

describe("Detail — Pull Request section", () => {
  it("renders the Pull Request section heading when task is DONE and pr_url is set", () => {
    currentTask = makeTask({
      state: "done",
      pr_url: "https://github.com/org/repo/pull/42",
    });
    renderDetail();
    expect(screen.getByText("Pull Request")).toBeInTheDocument();
  });

  it("renders the pr_url as a link with target=_blank when DONE and pr_url is set", () => {
    const url = "https://github.com/org/repo/pull/42";
    currentTask = makeTask({ state: "done", pr_url: url });
    renderDetail();
    const link = screen.getByRole("link", { name: new RegExp(url) });
    expect(link).toHaveAttribute("href", url);
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", expect.stringContaining("noopener"));
  });

  it("renders the proposed_pr_path as a code block when DONE and pr_url is absent", () => {
    const path = "/repo/.cronos/pull_requests/t-1.md";
    currentTask = makeTask({
      state: "done",
      pr_url: null,
      proposed_pr_path: path,
    });
    renderDetail();
    expect(screen.getByText("Pull Request")).toBeInTheDocument();
    expect(screen.getByText(path)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Copy path" })).toBeInTheDocument();
  });

  it("prefers pr_url over proposed_pr_path when BOTH are present (DONE)", () => {
    currentTask = makeTask({
      state: "done",
      pr_url: "https://github.com/org/repo/pull/9",
      proposed_pr_path: "/repo/.cronos/pull_requests/t-1.md",
    });
    renderDetail();
    // The link is rendered…
    expect(screen.getByRole("link", { name: /pull\/9/ })).toBeInTheDocument();
    // …and the Copy-path button (proposed-PR branch) is NOT.
    expect(screen.queryByRole("button", { name: "Copy path" })).not.toBeInTheDocument();
  });

  it("does NOT render the Pull Request section when task is DONE but both pr fields are null", () => {
    currentTask = makeTask({ state: "done", pr_url: null, proposed_pr_path: null });
    renderDetail();
    expect(screen.queryByText("Pull Request")).not.toBeInTheDocument();
  });

  it("does NOT render the Pull Request section when task is in BACKLOG (even if pr_url set)", () => {
    currentTask = makeTask({
      state: "backlog",
      pr_url: "https://github.com/org/repo/pull/1",
    });
    renderDetail();
    expect(screen.queryByText("Pull Request")).not.toBeInTheDocument();
  });

  it("does NOT render the Pull Request section when task is ACTIVE (even if proposed_pr_path set)", () => {
    currentTask = makeTask({
      state: "active",
      proposed_pr_path: "/repo/.cronos/pull_requests/t-1.md",
    });
    renderDetail();
    expect(screen.queryByText("Pull Request")).not.toBeInTheDocument();
  });

  it("does NOT render the Pull Request section when task is WAITING with pr_url", () => {
    currentTask = makeTask({
      state: "waiting",
      pr_url: "https://github.com/org/repo/pull/2",
    });
    renderDetail();
    expect(screen.queryByText("Pull Request")).not.toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Copy-path button — clipboard interaction
// ---------------------------------------------------------------------------

describe("Detail — proposed_pr_path Copy path button", () => {
  it("writes proposed_pr_path to the clipboard when Copy path is clicked", () => {
    const path = "/repo/.cronos/pull_requests/t-1.md";
    currentTask = makeTask({
      state: "done",
      pr_url: null,
      proposed_pr_path: path,
    });
    const writeText = vi.fn().mockResolvedValue(undefined);
    // jsdom provides no Clipboard API by default; defineProperty is needed
    // because `navigator.clipboard` is a read-only getter in newer jsdom.
    // We use fireEvent (not userEvent) here because userEvent.setup() installs
    // its own clipboard wrapper that would intercept our spy.
    Object.defineProperty(navigator, "clipboard", {
      value: { writeText },
      configurable: true,
      writable: true,
    });

    renderDetail();
    fireEvent.click(screen.getByRole("button", { name: "Copy path" }));
    expect(writeText).toHaveBeenCalledTimes(1);
    expect(writeText).toHaveBeenCalledWith(path);
  });
});
