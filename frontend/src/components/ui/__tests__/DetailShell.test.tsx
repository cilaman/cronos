import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import type { Task } from "../../../types";
import type { FeatureRead } from "../../../types";
import { DetailShell } from "../DetailShell";

// ---------------------------------------------------------------------------
// Modal passthrough — we render directly without mocking to keep the test
// exercising real Modal, but its fixed overlay doesn't affect DOM queries.
// ---------------------------------------------------------------------------

vi.mock("../../ui/Modal", () => ({
  Modal: (props: { children: React.ReactNode; onClose: () => void }) => (
    <div data-testid="shell-modal" onClick={props.onClose}>
      {props.children}
    </div>
  ),
}));

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const mockTask: Task = {
  id: "task-1",
  space_id: "s-1",
  title: "My Task Title",
  state: "active",
  created_at: "2024-01-01T00:00:00Z",
  updated_at: "2024-01-01T00:00:00Z",
  claude_session_id: null,
  waiting_question: null,
  brief: "Task brief text",
  history: "",
  pending_messages: [],
  agent_mode: "auto",
  agent_model: "default",
  priority: 2,
  manual_order: 0,
  space_name: null,
  space_color: null,
  space_icon: null,
};

const mockFeature: FeatureRead = {
  id: "feat-1",
  space_id: "s-1",
  title: "My Feature Title",
  state: "backlog",
  created_at: "2024-01-01T00:00:00Z",
  updated_at: "2024-01-01T00:00:00Z",
  brief: "Feature brief",
  priority: 3,
  manual_order: 0,
  type: "feature",
  parent_id: null,
  depends_on: [],
  pr_url: null,
  proposed_pr_path: null,
  feature_state: "planned",
  feature_key: "FEAT-7",
  realizes: null,
  issue_number: null,
  issue_url: null,
  proposed_issue_path: null,
  waiting_question: null,
  realizing_items: [],
};

function wrap(ui: React.ReactElement) {
  return render(<MemoryRouter>{ui}</MemoryRouter>);
}

// ---------------------------------------------------------------------------
// Loading state
// ---------------------------------------------------------------------------

describe("DetailShell — loading state", () => {
  it("renders skeleton when isLoading is true (task)", () => {
    const { container } = wrap(
      <DetailShell variant="task" entity={null} isLoading onClose={vi.fn()} />,
    );
    expect(container.querySelector(".animate-pulse")).toBeInTheDocument();
  });

  it("renders skeleton when isLoading is true (feature)", () => {
    const { container } = wrap(
      <DetailShell variant="feature" entity={null} isLoading onClose={vi.fn()} />,
    );
    expect(container.querySelector(".animate-pulse")).toBeInTheDocument();
  });

  it("does NOT render entity content when isLoading", () => {
    wrap(
      <DetailShell variant="task" entity={mockTask} isLoading onClose={vi.fn()} />,
    );
    expect(screen.queryByRole("heading", { name: "My Task Title" })).not.toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Error state
// ---------------------------------------------------------------------------

describe("DetailShell — error state", () => {
  it("renders error message and Retry button when error is set", () => {
    wrap(
      <DetailShell
        variant="task"
        entity={null}
        error={new Error("Load failed")}
        onRetry={vi.fn()}
        onClose={vi.fn()}
      />,
    );
    expect(screen.getByText("Load failed")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Retry" })).toBeInTheDocument();
  });

  it("calls onRetry when Retry is clicked", async () => {
    const onRetry = vi.fn();
    wrap(
      <DetailShell
        variant="task"
        entity={null}
        error={new Error("oops")}
        onRetry={onRetry}
        onClose={vi.fn()}
      />,
    );
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "Retry" }));
    expect(onRetry).toHaveBeenCalledOnce();
  });

  it("does not render Retry when onRetry is omitted", () => {
    wrap(
      <DetailShell
        variant="task"
        entity={null}
        error={new Error("oops")}
        onClose={vi.fn()}
      />,
    );
    expect(screen.queryByRole("button", { name: "Retry" })).not.toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Task variant — header content
// ---------------------------------------------------------------------------

describe("DetailShell — task variant", () => {
  it("renders task title as h2", () => {
    wrap(
      <DetailShell variant="task" entity={mockTask} onClose={vi.fn()} />,
    );
    expect(screen.getByRole("heading", { level: 2, name: "My Task Title" })).toBeInTheDocument();
  });

  it("renders task state badge", () => {
    wrap(
      <DetailShell variant="task" entity={mockTask} onClose={vi.fn()} />,
    );
    expect(screen.getByText("active")).toBeInTheDocument();
  });

  it("renders task id", () => {
    wrap(
      <DetailShell variant="task" entity={mockTask} onClose={vi.fn()} />,
    );
    expect(screen.getByText("task-1")).toBeInTheDocument();
  });

  it("renders headerActions inside the header", () => {
    wrap(
      <DetailShell
        variant="task"
        entity={mockTask}
        onClose={vi.fn()}
        headerActions={<button>Extra Action</button>}
      />,
    );
    expect(screen.getByRole("button", { name: "Extra Action" })).toBeInTheDocument();
  });

  it("renders footer content below the header", () => {
    wrap(
      <DetailShell
        variant="task"
        entity={mockTask}
        onClose={vi.fn()}
        footer={<div data-testid="task-footer">Footer</div>}
      />,
    );
    expect(screen.getByTestId("task-footer")).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Feature variant — header content
// ---------------------------------------------------------------------------

describe("DetailShell — feature variant", () => {
  it("renders feature title as h2", () => {
    wrap(
      <DetailShell variant="feature" entity={mockFeature} onClose={vi.fn()} />,
    );
    expect(screen.getByRole("heading", { level: 2, name: "My Feature Title" })).toBeInTheDocument();
  });

  it("renders feature_state badge", () => {
    wrap(
      <DetailShell variant="feature" entity={mockFeature} onClose={vi.fn()} />,
    );
    expect(screen.getByText("planned")).toBeInTheDocument();
  });

  it("renders feature type badge", () => {
    wrap(
      <DetailShell variant="feature" entity={mockFeature} onClose={vi.fn()} />,
    );
    expect(screen.getByText("feature")).toBeInTheDocument();
  });

  it("renders feature_key", () => {
    wrap(
      <DetailShell variant="feature" entity={mockFeature} onClose={vi.fn()} />,
    );
    expect(screen.getByText("FEAT-7")).toBeInTheDocument();
  });

  it("renders feature id", () => {
    wrap(
      <DetailShell variant="feature" entity={mockFeature} onClose={vi.fn()} />,
    );
    expect(screen.getByText("feat-1")).toBeInTheDocument();
  });

  it("renders headerActions passed by caller", () => {
    wrap(
      <DetailShell
        variant="feature"
        entity={mockFeature}
        onClose={vi.fn()}
        headerActions={<button>Edit</button>}
      />,
    );
    expect(screen.getByRole("button", { name: "Edit" })).toBeInTheDocument();
  });

  it("renders footer content", () => {
    wrap(
      <DetailShell
        variant="feature"
        entity={mockFeature}
        onClose={vi.fn()}
        footer={<div data-testid="feat-footer">Content</div>}
      />,
    );
    expect(screen.getByTestId("feat-footer")).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Close button
// ---------------------------------------------------------------------------

describe("DetailShell — close button", () => {
  it("renders Close button and calls onClose on click", async () => {
    const onClose = vi.fn();
    wrap(
      <DetailShell variant="task" entity={mockTask} onClose={onClose} />,
    );
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "Close" }));
    expect(onClose).toHaveBeenCalledOnce();
  });

  it("renders Close button for feature variant too", async () => {
    const onClose = vi.fn();
    wrap(
      <DetailShell variant="feature" entity={mockFeature} onClose={onClose} />,
    );
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "Close" }));
    expect(onClose).toHaveBeenCalledOnce();
  });
});
