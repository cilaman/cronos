import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { DndContext } from "@dnd-kit/core";
import { SortableContext } from "@dnd-kit/sortable";
import { Card } from "../components/Card";
import type { TaskSummary } from "../types";

function makeTask(overrides: Partial<TaskSummary> = {}): TaskSummary {
  return {
    id: "task-1",
    space_id: "space-1",
    title: "Wire up the thing",
    state: "backlog",
    created_at: "2024-01-15T14:00:00Z",
    updated_at: "2024-01-15T14:30:00Z",
    waiting_question: null,
    brief_preview: "A short description of what needs doing.",
    priority: 3,
    manual_order: 0,
    agent_mode: "auto",
    space_name: "Cronos",
    space_color: "#0F766E",
    space_icon: "🛰️",
    ...overrides,
  };
}

function renderCard(props: Parameters<typeof Card>[0]) {
  return render(
    <DndContext>
      <SortableContext items={[props.task.id]}>
        <Card {...props} />
      </SortableContext>
    </DndContext>,
  );
}

describe("Card — compact prop", () => {
  it("renders brief_preview when compact is false (default)", () => {
    const task = makeTask({ brief_preview: "Brief preview text here" });
    renderCard({ task, onClick: () => {} });
    expect(screen.getByText("Brief preview text here")).toBeInTheDocument();
  });

  it("renders waiting_question when compact is false (default)", () => {
    const task = makeTask({ waiting_question: "Need approval for this?" });
    renderCard({ task, onClick: () => {} });
    expect(screen.getByText(/Need approval for this\?/)).toBeInTheDocument();
  });

  it("renders brief_preview when compact is explicitly false", () => {
    const task = makeTask({ brief_preview: "Visible preview" });
    renderCard({ task, onClick: () => {}, compact: false });
    expect(screen.getByText("Visible preview")).toBeInTheDocument();
  });

  it("renders waiting_question when compact is explicitly false", () => {
    const task = makeTask({ waiting_question: "A question?" });
    renderCard({ task, onClick: () => {}, compact: false });
    expect(screen.getByText(/A question\?/)).toBeInTheDocument();
  });

  it("hides brief_preview when compact is true", () => {
    const task = makeTask({ brief_preview: "Should not appear" });
    renderCard({ task, onClick: () => {}, compact: true });
    expect(screen.queryByText("Should not appear")).not.toBeInTheDocument();
  });

  it("hides waiting_question when compact is true", () => {
    const task = makeTask({ waiting_question: "Hidden question?" });
    renderCard({ task, onClick: () => {}, compact: true });
    expect(screen.queryByText(/Hidden question\?/)).not.toBeInTheDocument();
  });

  it("hides both brief_preview and waiting_question when compact is true", () => {
    const task = makeTask({
      brief_preview: "Hidden preview",
      waiting_question: "Hidden question?",
    });
    renderCard({ task, onClick: () => {}, compact: true });
    expect(screen.queryByText("Hidden preview")).not.toBeInTheDocument();
    expect(screen.queryByText(/Hidden question\?/)).not.toBeInTheDocument();
  });

  it("always renders the task title regardless of compact mode", () => {
    const task = makeTask({ title: "Always visible title" });
    renderCard({ task, onClick: () => {}, compact: true });
    expect(screen.getByText("Always visible title")).toBeInTheDocument();
  });

  it("title is still rendered when compact is false", () => {
    const task = makeTask({ title: "Title in full mode" });
    renderCard({ task, onClick: () => {}, compact: false });
    expect(screen.getByText("Title in full mode")).toBeInTheDocument();
  });

  it("does not render brief preview paragraph when brief_preview is empty (compact=false)", () => {
    const task = makeTask({ brief_preview: "" });
    const { container } = renderCard({ task, onClick: () => {} });
    // No paragraph with the line-clamp-3 class
    expect(container.querySelector(".line-clamp-3")).toBeNull();
  });

  it("shows Auto badge in full mode (compact=false)", () => {
    const task = makeTask({ agent_mode: "auto" });
    renderCard({ task, onClick: () => {}, compact: false });
    expect(screen.getByText("Auto")).toBeInTheDocument();
  });

  it("hides Auto badge in compact mode", () => {
    const task = makeTask({ agent_mode: "auto" });
    renderCard({ task, onClick: () => {}, compact: true });
    expect(screen.queryByText("Auto")).not.toBeInTheDocument();
  });

  it("shows Plan badge in full mode", () => {
    const task = makeTask({ agent_mode: "plan" });
    renderCard({ task, onClick: () => {}, compact: false });
    expect(screen.getByText("Plan")).toBeInTheDocument();
  });

  it("shows Plan badge in compact mode (non-default mode is always shown)", () => {
    const task = makeTask({ agent_mode: "plan" });
    renderCard({ task, onClick: () => {}, compact: true });
    expect(screen.getByText("Plan")).toBeInTheDocument();
  });

  it("shows Ask badge in compact mode (non-default mode is always shown)", () => {
    const task = makeTask({ agent_mode: "ask" });
    renderCard({ task, onClick: () => {}, compact: true });
    expect(screen.getByText("Ask")).toBeInTheDocument();
  });

  it("invokes onClick when the card is clicked", async () => {
    const onClick = vi.fn();
    const task = makeTask({ title: "Clickable card title" });
    const { container } = renderCard({ task, onClick, compact: true });
    const user = userEvent.setup();
    // The card renders as div[role="button"] inside the DnD wrapper.
    const cardButton = container.querySelector("[data-task-type] > div[role='button']");
    expect(cardButton).not.toBeNull();
    await user.click(cardButton!);
    expect(onClick).toHaveBeenCalledTimes(1);
  });
});

// ---------------------------------------------------------------------------
// Autopilot pill
// ---------------------------------------------------------------------------

describe("Card — autopilot AUTO pill", () => {
  it("shows the AUTO pill when space_autopilot is 'enabled'", () => {
    const task = makeTask({ space_autopilot: "enabled" });
    renderCard({ task, onClick: () => {} });
    expect(screen.getByText("AUTO")).toBeInTheDocument();
  });

  it("does NOT show the AUTO pill when space_autopilot is 'disabled'", () => {
    const task = makeTask({ space_autopilot: "disabled" });
    renderCard({ task, onClick: () => {} });
    expect(screen.queryByText("AUTO")).not.toBeInTheDocument();
  });

  it("does NOT show the AUTO pill when space_autopilot is 'paused'", () => {
    const task = makeTask({ space_autopilot: "paused" });
    renderCard({ task, onClick: () => {} });
    expect(screen.queryByText("AUTO")).not.toBeInTheDocument();
  });

  it("does NOT show the AUTO pill when space_autopilot is undefined", () => {
    const task = makeTask({ space_autopilot: undefined });
    renderCard({ task, onClick: () => {} });
    expect(screen.queryByText("AUTO")).not.toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// PR link icons
// ---------------------------------------------------------------------------

describe("Card — pr_url GitPullRequest icon", () => {
  it("shows a link with title 'Open pull request' when pr_url is set", () => {
    const task = makeTask({ pr_url: "https://github.com/org/repo/pull/42" });
    renderCard({ task, onClick: () => {} });
    const link = screen.getByTitle("Open pull request");
    expect(link).toBeInTheDocument();
    expect(link.tagName).toBe("A");
    expect(link).toHaveAttribute("href", "https://github.com/org/repo/pull/42");
    expect(link).toHaveAttribute("target", "_blank");
  });

  it("does NOT show the PR link when pr_url is null", () => {
    const task = makeTask({ pr_url: null });
    renderCard({ task, onClick: () => {} });
    expect(screen.queryByTitle("Open pull request")).not.toBeInTheDocument();
  });

  it("does NOT show the PR link when pr_url is undefined", () => {
    const task = makeTask({ pr_url: undefined });
    renderCard({ task, onClick: () => {} });
    expect(screen.queryByTitle("Open pull request")).not.toBeInTheDocument();
  });
});

describe("Card — proposed_pr_path FileText icon", () => {
  it("shows a button with proposed PR tooltip when proposed_pr_path is set and pr_url is absent", () => {
    const task = makeTask({
      pr_url: null,
      proposed_pr_path: "/workspace/PROPOSED_PR.md",
    });
    renderCard({ task, onClick: () => {} });
    const btn = screen.getByTitle("PROPOSED PR (no GitHub remote)");
    expect(btn).toBeInTheDocument();
    expect(btn.tagName).toBe("BUTTON");
  });

  it("does NOT show the proposed-PR button when pr_url is set (pr_url takes precedence)", () => {
    const task = makeTask({
      pr_url: "https://github.com/org/repo/pull/1",
      proposed_pr_path: "/workspace/PROPOSED_PR.md",
    });
    renderCard({ task, onClick: () => {} });
    expect(screen.queryByTitle("PROPOSED PR (no GitHub remote)")).not.toBeInTheDocument();
  });

  it("does NOT show the proposed-PR button when proposed_pr_path is null", () => {
    const task = makeTask({ proposed_pr_path: null });
    renderCard({ task, onClick: () => {} });
    expect(screen.queryByTitle("PROPOSED PR (no GitHub remote)")).not.toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Goal card — collapsible children
// ---------------------------------------------------------------------------

describe("Card — goal collapsible children", () => {
  const childItems = [
    { id: "child-1", title: "First child task", state: "active" as const, priority: 2, updated_at: "2024-01-15T10:00:00Z" },
    { id: "child-2", title: "Second child task", state: "backlog" as const, priority: 3, updated_at: "2024-01-14T10:00:00Z" },
    { id: "child-3", title: "Third child task", state: "done" as const, priority: 1, updated_at: "2024-01-13T10:00:00Z" },
  ];

  function makeGoalTask(overrides: Partial<TaskSummary> = {}): TaskSummary {
    return makeTask({
      type: "goal",
      children_progress: {
        done: 1,
        total: 3,
        waiting: 0,
        items: childItems,
      },
      ...overrides,
    });
  }

  function getCardBody(container: HTMLElement): HTMLElement {
    // The role=button div directly inside the data-task-type wrapper is the
    // clickable card body that owns the new expand/collapse semantics.
    const root = container.querySelector(
      "[data-task-type] > div[role='button']",
    );
    if (!root) throw new Error("Card body (role=button) not found");
    return root as HTMLElement;
  }

  it("renders the ▶ disclosure indicator for a goal with children", () => {
    const task = makeGoalTask();
    renderCard({ task, onClick: () => {} });
    // The indicator lives inside the title <h3> as a non-interactive marker.
    const indicator = screen.getByText("▶");
    expect(indicator).toBeInTheDocument();
    expect(indicator.getAttribute("aria-hidden")).not.toBeNull();
  });

  it("disclosure indicator gets the rotate-90 class when expanded", () => {
    const task = makeGoalTask();
    const { rerender } = renderCard({ task, onClick: () => {}, expanded: false });
    // Collapsed: no rotation class.
    expect(screen.getByText("▶").className).not.toContain("rotate-90");

    rerender(
      <DndContext>
        <SortableContext items={[task.id]}>
          <Card task={task} onClick={() => {}} expanded={true} />
        </SortableContext>
      </DndContext>,
    );
    expect(screen.getByText("▶").className).toContain("rotate-90");
  });

  it("does not show children rows when collapsed (default)", () => {
    const task = makeGoalTask();
    renderCard({ task, onClick: () => {}, expanded: false });
    expect(screen.queryByText("First child task")).not.toBeInTheDocument();
    expect(screen.queryByText("Second child task")).not.toBeInTheDocument();
  });

  it("shows children rows when expanded prop is true", () => {
    const task = makeGoalTask();
    renderCard({ task, onClick: () => {}, expanded: true });
    expect(screen.getByText("First child task")).toBeInTheDocument();
    expect(screen.getByText("Second child task")).toBeInTheDocument();
    expect(screen.getByText("Third child task")).toBeInTheDocument();
  });

  it("clicking the card body fires onToggleExpand, NOT onClick (goal with children)", async () => {
    const onClick = vi.fn();
    const onToggleExpand = vi.fn();
    const task = makeGoalTask();
    const { container } = renderCard({ task, onClick, onToggleExpand, expanded: false });

    const user = userEvent.setup();
    await user.click(getCardBody(container));

    expect(onToggleExpand).toHaveBeenCalledTimes(1);
    expect(onClick).not.toHaveBeenCalled();
  });

  it("Enter key on the card body fires onToggleExpand, NOT onClick", async () => {
    const onClick = vi.fn();
    const onToggleExpand = vi.fn();
    const task = makeGoalTask();
    const { container } = renderCard({ task, onClick, onToggleExpand });

    const user = userEvent.setup();
    const body = getCardBody(container);
    body.focus();
    await user.keyboard("{Enter}");

    expect(onToggleExpand).toHaveBeenCalledTimes(1);
    expect(onClick).not.toHaveBeenCalled();
  });

  it("Space key on the card body fires onToggleExpand, NOT onClick", async () => {
    const onClick = vi.fn();
    const onToggleExpand = vi.fn();
    const task = makeGoalTask();
    const { container } = renderCard({ task, onClick, onToggleExpand });

    const user = userEvent.setup();
    const body = getCardBody(container);
    body.focus();
    await user.keyboard("[Space]");

    expect(onToggleExpand).toHaveBeenCalledTimes(1);
    expect(onClick).not.toHaveBeenCalled();
  });

  it("sets aria-expanded on the card body for goals with children", () => {
    const task = makeGoalTask();
    const { container, rerender } = renderCard({ task, onClick: () => {}, expanded: false });
    expect(getCardBody(container).getAttribute("aria-expanded")).toBe("false");

    rerender(
      <DndContext>
        <SortableContext items={[task.id]}>
          <Card task={task} onClick={() => {}} expanded={true} />
        </SortableContext>
      </DndContext>,
    );
    expect(getCardBody(container).getAttribute("aria-expanded")).toBe("true");
  });

  it("renders the Open button on goals with children, with the correct aria-label", () => {
    const task = makeGoalTask();
    renderCard({ task, onClick: () => {} });
    const openBtn = screen.getByRole("button", { name: /Open task detail/i });
    expect(openBtn).toBeInTheDocument();
    expect(openBtn.textContent).toMatch(/Open/);
  });

  it("clicking the Open button fires onClick and does NOT toggle expand", async () => {
    const onClick = vi.fn();
    const onToggleExpand = vi.fn();
    const task = makeGoalTask();
    renderCard({ task, onClick, onToggleExpand });

    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: /Open task detail/i }));

    expect(onClick).toHaveBeenCalledTimes(1);
    expect(onToggleExpand).not.toHaveBeenCalled();
  });

  it("calls onOpenTask with child id when a child row is clicked", async () => {
    const onOpenTask = vi.fn();
    const task = makeGoalTask();
    renderCard({ task, onClick: () => {}, onOpenTask, expanded: true });

    const user = userEvent.setup();
    await user.click(screen.getByText("Second child task"));

    expect(onOpenTask).toHaveBeenCalledWith("child-2");
  });

  it("shows state dot for each child row when expanded", () => {
    const task = makeGoalTask();
    renderCard({ task, onClick: () => {}, expanded: true });
    // Each child row has a state dot with aria-label
    const dots = screen.getAllByLabelText(/^(active|backlog|done|waiting|archived)$/);
    expect(dots.length).toBeGreaterThanOrEqual(3);
  });

  it("does not render the disclosure indicator for non-goal tasks", () => {
    const task = makeTask({ type: "task" });
    renderCard({ task, onClick: () => {} });
    expect(screen.queryByText("▶")).not.toBeInTheDocument();
  });

  it("does not render the Open button for non-goal tasks", () => {
    const task = makeTask({ type: "task" });
    renderCard({ task, onClick: () => {} });
    expect(screen.queryByRole("button", { name: /Open task detail/i })).not.toBeInTheDocument();
  });

  it("does not omit aria-expanded for non-goal tasks (must be undefined)", () => {
    const task = makeTask({ type: "task" });
    const { container } = renderCard({ task, onClick: () => {} });
    // Non-goal cards must NOT set aria-expanded at all.
    expect(getCardBody(container).hasAttribute("aria-expanded")).toBe(false);
  });

  it("non-goal click fires onClick (unchanged behavior)", async () => {
    const onClick = vi.fn();
    const onToggleExpand = vi.fn();
    const task = makeTask({ type: "task" });
    const { container } = renderCard({ task, onClick, onToggleExpand });

    const user = userEvent.setup();
    await user.click(getCardBody(container));

    expect(onClick).toHaveBeenCalledTimes(1);
    expect(onToggleExpand).not.toHaveBeenCalled();
  });

  it("does not render the disclosure indicator for a goal with zero children", () => {
    const task = makeGoalTask({
      children_progress: { done: 0, total: 0, waiting: 0, items: [] },
    });
    renderCard({ task, onClick: () => {} });
    expect(screen.queryByText("▶")).not.toBeInTheDocument();
  });

  it("does not render the Open button for a goal with zero children", () => {
    const task = makeGoalTask({
      children_progress: { done: 0, total: 0, waiting: 0, items: [] },
    });
    renderCard({ task, onClick: () => {} });
    expect(screen.queryByRole("button", { name: /Open task detail/i })).not.toBeInTheDocument();
  });

  it("a goal without children behaves like a non-goal: clicking body fires onClick", async () => {
    const onClick = vi.fn();
    const onToggleExpand = vi.fn();
    const task = makeGoalTask({
      children_progress: { done: 0, total: 0, waiting: 0, items: [] },
    });
    const { container } = renderCard({ task, onClick, onToggleExpand });

    const user = userEvent.setup();
    await user.click(getCardBody(container));

    expect(onClick).toHaveBeenCalledTimes(1);
    expect(onToggleExpand).not.toHaveBeenCalled();
  });
});
