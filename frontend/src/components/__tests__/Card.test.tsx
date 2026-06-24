import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {
  DndContext,
  PointerSensor,
  useSensor,
  useSensors,
} from "@dnd-kit/core";
import { SortableContext } from "@dnd-kit/sortable";
import { Card } from "../Card";
import type { TaskSummary } from "../../types";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

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

// Wrapper that mirrors the real Tree's DndContext sensor config — a
// PointerSensor with distance:8 activation. Without this, the default
// sensor activates with zero movement and synthesized clicks in jsdom
// are eaten by the drag listeners on tight-density cards.
function CardHarness({ children }: { children: React.ReactNode }) {
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 8 } }),
  );
  return <DndContext sensors={sensors}>{children}</DndContext>;
}

function renderCard(props: Parameters<typeof Card>[0]) {
  return render(
    <CardHarness>
      <SortableContext items={[props.task.id]}>
        <Card {...props} />
      </SortableContext>
    </CardHarness>,
  );
}

/**
 * Return the root <div> that Card renders (the element with data-task-type).
 * The outer wrapper from <DndContext> sits above it.
 */
function getCardRoot(container: HTMLElement): HTMLElement {
  const root = container.querySelector("[data-task-type]");
  if (!root) throw new Error("Card root with data-task-type not found");
  return root as HTMLElement;
}

// ---------------------------------------------------------------------------
// Plain task (no type / parent / deps)
// ---------------------------------------------------------------------------

describe("Card — plain task (no type, no parent, no deps)", () => {
  it("renders without GOAL or ISSUE type badge", () => {
    const task = makeTask();

    renderCard({ task, onClick: () => {} });

    // The type badge uses the literal type name as text.
    expect(screen.queryByText("goal")).not.toBeInTheDocument();
    expect(screen.queryByText("issue")).not.toBeInTheDocument();
  });

  it("renders no parent breadcrumb", () => {
    const task = makeTask();

    renderCard({ task, onClick: () => {} });

    // The breadcrumb begins with the up arrow character.
    expect(screen.queryByText(/↑/)).not.toBeInTheDocument();
  });

  it("renders no dependency pills (no 'Blocked by' or 'Blocks')", () => {
    const task = makeTask();

    renderCard({ task, onClick: () => {} });

    expect(screen.queryByText(/Blocked by/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/^Blocks/i)).not.toBeInTheDocument();
  });

  it("defaults data-task-type to 'task' when type is unset", () => {
    const task = makeTask();

    const { container } = renderCard({ task, onClick: () => {} });

    expect(getCardRoot(container).getAttribute("data-task-type")).toBe("task");
  });

  it("does not apply the goal top-border styling for a plain task", () => {
    const task = makeTask();

    const { container } = renderCard({ task, onClick: () => {} });

    const button = container.querySelector("[data-task-type] div[role='button']");
    expect(button).not.toBeNull();
    // The goal-specific class is only added for type=goal.
    expect(button!.className).not.toContain("border-t-ink");
    // Inline borderTopWidth is only set for goals.
    expect((button as HTMLElement).style.borderTopWidth).toBe("");
  });
});

// ---------------------------------------------------------------------------
// type=goal
// ---------------------------------------------------------------------------

describe("Card — type=goal", () => {
  it("renders the GOAL badge text", () => {
    const task = makeTask({ type: "goal" });

    renderCard({ task, onClick: () => {} });

    // The badge text is the lower-case type; the uppercase visual is via CSS.
    const badge = screen.getByText("goal");
    expect(badge).toBeInTheDocument();
    expect(badge.className).toContain("uppercase");
  });

  it("sets data-task-type='goal' on the root", () => {
    const task = makeTask({ type: "goal" });

    const { container } = renderCard({ task, onClick: () => {} });

    expect(getCardRoot(container).getAttribute("data-task-type")).toBe("goal");
  });

  it("applies the thicker top border styling for goals", () => {
    const task = makeTask({ type: "goal" });

    const { container } = renderCard({ task, onClick: () => {} });

    const button = container.querySelector("[data-task-type] div[role='button']");
    expect(button).not.toBeNull();
    expect(button!.className).toContain("border-t-ink");
    expect((button as HTMLElement).style.borderTopWidth).toBe("2px");
  });
});

// ---------------------------------------------------------------------------
// type=issue
// ---------------------------------------------------------------------------

describe("Card — type=issue", () => {
  it("renders the ISSUE badge text", () => {
    const task = makeTask({ type: "issue" });

    renderCard({ task, onClick: () => {} });

    const badge = screen.getByText("issue");
    expect(badge).toBeInTheDocument();
    expect(badge.className).toContain("uppercase");
  });

  it("sets data-task-type='issue' on the root", () => {
    const task = makeTask({ type: "issue" });

    const { container } = renderCard({ task, onClick: () => {} });

    expect(getCardRoot(container).getAttribute("data-task-type")).toBe("issue");
  });

  it("does NOT apply the goal-only thicker top border for issues", () => {
    const task = makeTask({ type: "issue" });

    const { container } = renderCard({ task, onClick: () => {} });

    const button = container.querySelector("[data-task-type] div[role='button']");
    expect(button).not.toBeNull();
    expect(button!.className).not.toContain("border-t-ink");
    expect((button as HTMLElement).style.borderTopWidth).toBe("");
  });

  it("does not render a type badge when type is the default 'task'", () => {
    const task = makeTask({ type: "task" });

    renderCard({ task, onClick: () => {} });

    // No badge text should appear for the default type.
    expect(screen.queryByText("task")).not.toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Parent breadcrumb
// ---------------------------------------------------------------------------

describe("Card — parent breadcrumb", () => {
  it("renders the breadcrumb when parent_id and parent_title are set", () => {
    const task = makeTask({
      parent_id: "parent-42",
      parent_title: "Quarterly roadmap",
    });

    renderCard({ task, onClick: () => {} });

    expect(screen.getByText(/↑\s*Quarterly roadmap/)).toBeInTheDocument();
  });

  it("does not render the breadcrumb when only parent_id is set", () => {
    const task = makeTask({ parent_id: "parent-42", parent_title: null });

    renderCard({ task, onClick: () => {} });

    expect(screen.queryByText(/↑/)).not.toBeInTheDocument();
  });

  it("does not render the breadcrumb when only parent_title is set", () => {
    const task = makeTask({ parent_id: null, parent_title: "Lonely title" });

    renderCard({ task, onClick: () => {} });

    expect(screen.queryByText(/↑/)).not.toBeInTheDocument();
  });

  it("calls onOpenTask with the parent id when the breadcrumb is clicked", async () => {
    const onOpenTask = vi.fn();
    const onClick = vi.fn();
    const task = makeTask({
      parent_id: "parent-42",
      parent_title: "Quarterly roadmap",
    });

    renderCard({ task, onClick, onOpenTask });
    const user = userEvent.setup();
    const crumb = screen.getByText(/↑\s*Quarterly roadmap/);
    await user.click(crumb);

    expect(onOpenTask).toHaveBeenCalledTimes(1);
    expect(onOpenTask).toHaveBeenCalledWith("parent-42");
  });

  it("does not bubble the click to the card's onClick handler", async () => {
    const onOpenTask = vi.fn();
    const onClick = vi.fn();
    const task = makeTask({
      parent_id: "parent-42",
      parent_title: "Quarterly roadmap",
    });

    renderCard({ task, onClick, onOpenTask });
    const user = userEvent.setup();
    await user.click(screen.getByText(/↑\s*Quarterly roadmap/));

    expect(onClick).not.toHaveBeenCalled();
  });

  it("does not throw when the breadcrumb is clicked without an onOpenTask prop", async () => {
    const onClick = vi.fn();
    const task = makeTask({
      parent_id: "parent-42",
      parent_title: "Quarterly roadmap",
    });

    renderCard({ task, onClick });
    const user = userEvent.setup();
    // Should not throw, and onClick on the outer button must not fire.
    await user.click(screen.getByText(/↑\s*Quarterly roadmap/));

    expect(onClick).not.toHaveBeenCalled();
  });
});

// ---------------------------------------------------------------------------
// unmet_dependencies → "Blocked by N" pill
// ---------------------------------------------------------------------------

describe("Card — Blocked by pill", () => {
  it("renders 'Blocked by 2' pill when unmet_dependencies has 2 items", () => {
    const task = makeTask({
      unmet_dependencies: [
        { id: "dep-1", title: "Migrate the schema" },
        { id: "dep-2", title: "Approve the design" },
      ],
    });

    renderCard({ task, onClick: () => {} });

    expect(screen.getByText(/Blocked by 2/i)).toBeInTheDocument();
  });

  it("lists blocker titles in the title attribute (tooltip)", () => {
    const task = makeTask({
      unmet_dependencies: [
        { id: "dep-1", title: "Migrate the schema" },
        { id: "dep-2", title: "Approve the design" },
      ],
    });

    renderCard({ task, onClick: () => {} });

    const pill = screen.getByText(/Blocked by 2/i);
    expect(pill.getAttribute("title")).toBe(
      "Migrate the schema, Approve the design",
    );
  });

  it("does not render the pill when unmet_dependencies is empty", () => {
    const task = makeTask({ unmet_dependencies: [] });

    renderCard({ task, onClick: () => {} });

    expect(screen.queryByText(/Blocked by/i)).not.toBeInTheDocument();
  });

  it("does not render the pill when unmet_dependencies is undefined", () => {
    const task = makeTask({ unmet_dependencies: undefined });

    renderCard({ task, onClick: () => {} });

    expect(screen.queryByText(/Blocked by/i)).not.toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// blocksCount prop → "Blocks N" pill
// ---------------------------------------------------------------------------

describe("Card — Blocks pill", () => {
  it("renders 'Blocks 3' pill when blocksCount=3", () => {
    const task = makeTask();

    renderCard({ task, onClick: () => {}, blocksCount: 3 });

    expect(screen.getByText(/^Blocks 3$/)).toBeInTheDocument();
  });

  it("does not render the pill when blocksCount=0 (default)", () => {
    const task = makeTask();

    renderCard({ task, onClick: () => {} });

    expect(screen.queryByText(/^Blocks /)).not.toBeInTheDocument();
  });

  it("does not render the pill when blocksCount is explicitly 0", () => {
    const task = makeTask();

    renderCard({ task, onClick: () => {}, blocksCount: 0 });

    expect(screen.queryByText(/^Blocks /)).not.toBeInTheDocument();
  });

  it("renders the pill for a count of 1", () => {
    const task = makeTask();

    renderCard({ task, onClick: () => {}, blocksCount: 1 });

    expect(screen.getByText(/^Blocks 1$/)).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// density="tight" — single-line stacked variant
// ---------------------------------------------------------------------------

describe("Card — density='tight'", () => {
  it("renders the title in a single-line truncated <h3>", () => {
    const task = makeTask({
      title: "A very very very very very long title that should be truncated",
    });

    renderCard({ task, onClick: () => {}, density: "tight" });

    const heading = screen.getByRole("heading", { level: 3 });
    expect(heading).toBeInTheDocument();
    expect(heading.textContent).toBe(
      "A very very very very very long title that should be truncated",
    );
    expect(heading.className).toContain("truncate");
  });

  it("does NOT render brief_preview in tight mode", () => {
    const task = makeTask({ brief_preview: "Should not be visible in tight" });

    renderCard({ task, onClick: () => {}, density: "tight" });

    expect(
      screen.queryByText("Should not be visible in tight"),
    ).not.toBeInTheDocument();
  });

  it("does NOT render waiting_question in tight mode", () => {
    const task = makeTask({
      waiting_question: "Hidden tight-mode question?",
    });

    renderCard({ task, onClick: () => {}, density: "tight" });

    expect(
      screen.queryByText(/Hidden tight-mode question\?/),
    ).not.toBeInTheDocument();
  });

  it("does NOT render the parent breadcrumb in tight mode", () => {
    const task = makeTask({
      parent_id: "parent-99",
      parent_title: "Should not show in tight",
    });

    renderCard({ task, onClick: () => {}, density: "tight" });

    expect(screen.queryByText(/↑/)).not.toBeInTheDocument();
    expect(
      screen.queryByText(/Should not show in tight/),
    ).not.toBeInTheDocument();
  });

  it("sets data-density='tight' on the root element", () => {
    const task = makeTask();

    const { container } = renderCard({
      task,
      onClick: () => {},
      density: "tight",
    });

    expect(getCardRoot(container).getAttribute("data-density")).toBe("tight");
  });

  it("renders a state badge pill for the task's state", () => {
    const task = makeTask({ state: "active" });

    renderCard({ task, onClick: () => {}, density: "tight" });

    const stateBadge = screen.getByText("Active");
    expect(stateBadge).toBeInTheDocument();
    expect(stateBadge.className).toContain("rounded");
  });

  it("renders a priority dot with aria-label containing 'priority'", () => {
    const task = makeTask({ priority: 1 });

    renderCard({ task, onClick: () => {}, density: "tight" });

    const priorityDot = screen.getByLabelText(/priority 1/i);
    expect(priorityDot).toBeInTheDocument();
    expect(priorityDot.className).toContain("rounded-full");
  });

  it("renders a 'Blocked by N' pill when unmet_dependencies is set", () => {
    const task = makeTask({
      unmet_dependencies: [
        { id: "dep-1", title: "Migrate the schema" },
        { id: "dep-2", title: "Approve the design" },
        { id: "dep-3", title: "Land the migration" },
      ],
    });

    renderCard({ task, onClick: () => {}, density: "tight" });

    const pill = screen.getByText(/Blocked by 3/i);
    expect(pill).toBeInTheDocument();
    expect(pill.getAttribute("title")).toBe(
      "Migrate the schema, Approve the design, Land the migration",
    );
  });

  it("renders a 'Blocks N' pill when blocksCount > 0", () => {
    const task = makeTask();

    renderCard({
      task,
      onClick: () => {},
      density: "tight",
      blocksCount: 5,
    });

    expect(screen.getByText(/^Blocks 5$/)).toBeInTheDocument();
  });

  it("renders the type pill text for type='goal'", () => {
    const task = makeTask({ type: "goal" });

    renderCard({ task, onClick: () => {}, density: "tight" });

    const badge = screen.getByText("goal");
    expect(badge).toBeInTheDocument();
    expect(badge.className).toContain("uppercase");
  });

  it("renders the type pill text for type='issue'", () => {
    const task = makeTask({ type: "issue" });

    renderCard({ task, onClick: () => {}, density: "tight" });

    const badge = screen.getByText("issue");
    expect(badge).toBeInTheDocument();
    expect(badge.className).toContain("uppercase");
  });

  it("does NOT render a type pill for default type='task'", () => {
    const task = makeTask({ type: "task" });

    renderCard({ task, onClick: () => {}, density: "tight" });

    expect(screen.queryByText("task")).not.toBeInTheDocument();
  });

  it("uses a flex-col justify-center layout with min-h-[44px] tap target", () => {
    const task = makeTask();

    const { container } = renderCard({
      task,
      onClick: () => {},
      density: "tight",
    });

    const button = container.querySelector("button");
    expect(button).not.toBeNull();
    expect(button!.className).toContain("flex-col");
    expect(button!.className).toContain("justify-center");
    expect(button!.className).toContain("min-h-[44px]");
  });

  it("still invokes onClick when the tight card is clicked", async () => {
    const onClick = vi.fn();
    const task = makeTask({ title: "Clickable tight card" });

    renderCard({ task, onClick, density: "tight" });

    const user = userEvent.setup();
    const heading = screen.getByRole("heading", { level: 3 });
    // Click the inner button via the heading (heading is inside the <button>).
    await user.click(heading);

    expect(onClick).toHaveBeenCalledTimes(1);
  });
});

// ---------------------------------------------------------------------------
// data-density attribute for non-tight values
// ---------------------------------------------------------------------------

describe("Card — data-density for non-tight values", () => {
  it("sets data-density='default' on the root when density is omitted", () => {
    const task = makeTask();

    const { container } = renderCard({ task, onClick: () => {} });

    expect(getCardRoot(container).getAttribute("data-density")).toBe("default");
  });

  it("sets data-density='default' when explicitly set to 'default'", () => {
    const task = makeTask();

    const { container } = renderCard({
      task,
      onClick: () => {},
      density: "default",
    });

    expect(getCardRoot(container).getAttribute("data-density")).toBe("default");
  });

  it("sets data-density='compact' when density='compact'", () => {
    const task = makeTask();

    const { container } = renderCard({
      task,
      onClick: () => {},
      density: "compact",
    });

    expect(getCardRoot(container).getAttribute("data-density")).toBe("compact");
  });
});

// ---------------------------------------------------------------------------
// Layout test — 6 tight cards stacked in a 640px-tall container
// ---------------------------------------------------------------------------

describe("Card — tight density stack layout", () => {
  it("renders all 6 tight cards' titles when stacked vertically", () => {
    const tasks = Array.from({ length: 6 }, (_, i) =>
      makeTask({
        id: `task-${i + 1}`,
        title: `Tight stacked card #${i + 1}`,
      }),
    );

    render(
      <div style={{ height: 640, display: "flex", flexDirection: "column" }}>
        <CardHarness>
          <SortableContext items={tasks.map((t) => t.id)}>
            {tasks.map((t) => (
              <Card key={t.id} task={t} onClick={() => {}} density="tight" />
            ))}
          </SortableContext>
        </CardHarness>
      </div>,
    );

    for (let i = 1; i <= 6; i++) {
      expect(
        screen.getByText(`Tight stacked card #${i}`),
      ).toBeInTheDocument();
    }
    // And every rendered card should advertise data-density='tight'.
    expect(document.querySelectorAll('[data-density="tight"]').length).toBe(6);
  });
});

// ---------------------------------------------------------------------------
// All-combined: a goal that blocks others and is blocked
// ---------------------------------------------------------------------------

describe("Card — combined goal that blocks others and is blocked", () => {
  it("renders the goal badge, parent breadcrumb, blocked-by, and blocks pills together", async () => {
    const onOpenTask = vi.fn();
    const task = makeTask({
      type: "goal",
      parent_id: "parent-99",
      parent_title: "Annual plan",
      unmet_dependencies: [
        { id: "dep-1", title: "Finalize budget" },
        { id: "dep-2", title: "Hire designer" },
      ],
    });

    const { container } = renderCard({
      task,
      onClick: () => {},
      onOpenTask,
      blocksCount: 4,
    });

    // Type badge + data-task-type
    expect(screen.getByText("goal")).toBeInTheDocument();
    expect(getCardRoot(container).getAttribute("data-task-type")).toBe("goal");

    // Goal-specific border styling
    const button = container.querySelector("[data-task-type] div[role='button']");
    expect(button!.className).toContain("border-t-ink");
    expect((button as HTMLElement).style.borderTopWidth).toBe("2px");

    // Parent breadcrumb
    const crumb = screen.getByText(/↑\s*Annual plan/);
    expect(crumb).toBeInTheDocument();

    // Both dependency pills
    const blockedBy = screen.getByText(/Blocked by 2/i);
    expect(blockedBy).toBeInTheDocument();
    expect(blockedBy.getAttribute("title")).toBe(
      "Finalize budget, Hire designer",
    );
    expect(screen.getByText(/^Blocks 4$/)).toBeInTheDocument();

    // Breadcrumb still wired up
    const user = userEvent.setup();
    await user.click(crumb);
    expect(onOpenTask).toHaveBeenCalledWith("parent-99");
  });
});

// ---------------------------------------------------------------------------
// type=feature — badge style and feature-specific fields
// ---------------------------------------------------------------------------

describe("Card — type=feature", () => {
  it("renders the FEATURE badge text with emerald style", () => {
    const task = makeTask({ type: "feature" });

    renderCard({ task, onClick: () => {} });

    const badge = screen.getByText("feature");
    expect(badge).toBeInTheDocument();
    expect(badge.className).toContain("uppercase");
    expect(badge.className).toContain("feature");
  });

  it("sets data-task-type='feature' on the root", () => {
    const task = makeTask({ type: "feature" });

    const { container } = renderCard({ task, onClick: () => {} });

    expect(getCardRoot(container).getAttribute("data-task-type")).toBe("feature");
  });
});

// ---------------------------------------------------------------------------
// type=fix — badge style
// ---------------------------------------------------------------------------

describe("Card — type=fix", () => {
  it("renders the FIX badge text with rose style", () => {
    const task = makeTask({ type: "fix" });

    renderCard({ task, onClick: () => {} });

    const badge = screen.getByText("fix");
    expect(badge).toBeInTheDocument();
    expect(badge.className).toContain("uppercase");
    expect(badge.className).toContain("fix");
  });

  it("sets data-task-type='fix' on the root", () => {
    const task = makeTask({ type: "fix" });

    const { container } = renderCard({ task, onClick: () => {} });

    expect(getCardRoot(container).getAttribute("data-task-type")).toBe("fix");
  });
});

// ---------------------------------------------------------------------------
// feature_key chip
// ---------------------------------------------------------------------------

describe("Card — feature_key chip", () => {
  it("renders the feature_key chip when feature_key is present", () => {
    const task = makeTask({ type: "feature", feature_key: "FEAT-123" });

    renderCard({ task, onClick: () => {} });

    expect(screen.getByText("FEAT-123")).toBeInTheDocument();
  });

  it("does NOT render a feature_key chip when feature_key is absent", () => {
    const task = makeTask({ type: "feature", feature_key: null });

    renderCard({ task, onClick: () => {} });

    expect(screen.queryByText(/FEAT-/)).not.toBeInTheDocument();
  });

  it("does NOT render a feature_key chip when feature_key is undefined", () => {
    const task = makeTask({ type: "feature" });

    renderCard({ task, onClick: () => {} });

    expect(screen.queryByText(/FEAT-/)).not.toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// issue_url anchor
// ---------------------------------------------------------------------------

describe("Card — issue_url anchor", () => {
  it("renders a GitHub issue link with #number when issue_url and issue_number are present", () => {
    const task = makeTask({
      type: "feature",
      issue_url: "https://github.com/owner/repo/issues/42",
      issue_number: 42,
    });

    renderCard({ task, onClick: () => {} });

    const anchor = screen.getByTitle("Open GitHub issue");
    expect(anchor).toBeInTheDocument();
    expect(anchor.getAttribute("href")).toBe(
      "https://github.com/owner/repo/issues/42",
    );
    expect(anchor.getAttribute("target")).toBe("_blank");
    expect(screen.getByText("#42")).toBeInTheDocument();
  });

  it("renders GitHub issue link without number when issue_number is null", () => {
    const task = makeTask({
      type: "feature",
      issue_url: "https://github.com/owner/repo/issues/99",
      issue_number: null,
    });

    renderCard({ task, onClick: () => {} });

    const anchor = screen.getByTitle("Open GitHub issue");
    expect(anchor).toBeInTheDocument();
    expect(screen.queryByText(/#\d+/)).not.toBeInTheDocument();
  });

  it("renders a Draft issue button when only proposed_issue_path is set", () => {
    const task = makeTask({
      type: "feature",
      issue_url: null,
      proposed_issue_path: ".cronos/proposed-issues/feat-001.md",
    });

    renderCard({ task, onClick: () => {} });

    const btn = screen.getByTitle("Draft issue (no GitHub remote)");
    expect(btn).toBeInTheDocument();
    expect(screen.getByText("Draft issue")).toBeInTheDocument();
    expect(screen.queryByTitle("Open GitHub issue")).not.toBeInTheDocument();
  });

  it("renders nothing for issue when both issue_url and proposed_issue_path are absent", () => {
    const task = makeTask({ type: "feature", issue_url: null, proposed_issue_path: null });

    renderCard({ task, onClick: () => {} });

    expect(screen.queryByTitle("Open GitHub issue")).not.toBeInTheDocument();
    expect(screen.queryByTitle("Draft issue (no GitHub remote)")).not.toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// realizes chip
// ---------------------------------------------------------------------------

describe("Card — realizes chip", () => {
  it("renders feature key when realizes and realizes_feature_key are both set", () => {
    const task = makeTask({
      type: "fix",
      realizes: "feat-task-99",
      realizes_feature_key: "FEAT-007",
    });

    renderCard({ task, onClick: () => {} });

    expect(screen.getByText(/→ FEAT-007/i)).toBeInTheDocument();
    // raw UUID must not appear
    expect(screen.queryByText(/feat-task-99/)).not.toBeInTheDocument();
  });

  it("renders fallback '→ realizes (unknown)' when realizes is set but realizes_feature_key is null", () => {
    const task = makeTask({
      type: "fix",
      realizes: "feat-task-99",
      realizes_feature_key: null,
    });

    renderCard({ task, onClick: () => {} });

    expect(screen.getByText(/→ realizes \(unknown\)/i)).toBeInTheDocument();
    expect(screen.queryByText(/feat-task-99/)).not.toBeInTheDocument();
  });

  it("does NOT render the realizes chip when realizes is null", () => {
    const task = makeTask({ type: "fix", realizes: null });

    renderCard({ task, onClick: () => {} });

    expect(screen.queryByText(/→/)).not.toBeInTheDocument();
  });

  it("calls onOpenTask with the realizes id when the chip is clicked", async () => {
    const onOpenTask = vi.fn();
    const onClick = vi.fn();
    const task = makeTask({
      type: "fix",
      realizes: "feat-task-99",
      realizes_feature_key: "FEAT-007",
    });

    renderCard({ task, onClick, onOpenTask });
    const user = userEvent.setup();
    await user.click(screen.getByText(/→ FEAT-007/i));

    expect(onOpenTask).toHaveBeenCalledTimes(1);
    expect(onOpenTask).toHaveBeenCalledWith("feat-task-99");
    expect(onClick).not.toHaveBeenCalled();
  });
});

// ---------------------------------------------------------------------------
// realizing_count badge (feature/fix cards only)
// ---------------------------------------------------------------------------

describe("Card — realizing_count badge", () => {
  it("renders 'N linked' badge on a feature card when realizing_count > 0", () => {
    const task = makeTask({
      type: "feature",
      realizing_count: 3,
    });

    renderCard({ task, onClick: () => {} });

    expect(screen.getByText(/3 linked/i)).toBeInTheDocument();
  });

  it("renders 'N linked' badge on a fix card", () => {
    const task = makeTask({
      type: "fix",
      realizing_count: 1,
    });

    renderCard({ task, onClick: () => {} });

    expect(screen.getByText(/1 linked/i)).toBeInTheDocument();
  });

  it("does NOT render the badge when realizing_count is 0", () => {
    const task = makeTask({
      type: "feature",
      realizing_count: 0,
    });

    renderCard({ task, onClick: () => {} });

    expect(screen.queryByText(/linked/i)).not.toBeInTheDocument();
  });

  it("does NOT render the badge when realizing_count is absent", () => {
    const task = makeTask({ type: "feature" });

    renderCard({ task, onClick: () => {} });

    expect(screen.queryByText(/linked/i)).not.toBeInTheDocument();
  });

  it("does NOT render the badge on a non-feature/fix card type", () => {
    const task = makeTask({
      type: "goal",
      realizing_count: 5,
    });

    renderCard({ task, onClick: () => {} });

    expect(screen.queryByText(/linked/i)).not.toBeInTheDocument();
  });
});
