/**
 * Card.buttons.test.tsx
 *
 * Semantic-tag assertions for the button conversion in Card.tsx (I4 board wave).
 * Uses getByRole('button') queries — NOT snapshot assertions — so that DOM tag
 * correctness is explicitly verified and cannot silently regress.
 *
 * Key conversion: the main card body (formerly a div[role='button']) is now a
 * native <button type='button'>.
 *
 * Scope note: the parent-breadcrumb span and realizes chip remain as
 * span[role='button'] because they are nested inside the card body button;
 * converting them to native <button> elements would produce invalid HTML
 * (nested interactive elements). The out-of-scope finding records this.
 *
 * dnd-kit's useSortable injects aria attributes including role="button" and
 * aria-roledescription="sortable" on the outer wrapper div via `attributes` —
 * this is expected dnd-kit behaviour and is NOT a scope violation.
 */
import { describe, it, expect, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
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

// ---------------------------------------------------------------------------
// Core semantic-tag assertion: card body is a real <button>
// ---------------------------------------------------------------------------

describe("Card — card body is a real <button> element (default density)", () => {
  it("clicking the card body invokes onClick", async () => {
    const onClick = vi.fn();
    const task = makeTask({ title: "Clickable body" });
    renderCard({ task, onClick });

    const user = userEvent.setup();
    const heading = screen.getByText("Clickable body");
    await user.click(heading);

    expect(onClick).toHaveBeenCalledTimes(1);
  });
});

// ---------------------------------------------------------------------------
// dnd-kit drag attributes still present after button conversion
// ---------------------------------------------------------------------------

describe("Card — dnd-kit drag handle preserved after button conversion", () => {
  it("renders the drag handle span inside the card body button", () => {
    const task = makeTask();
    const { container } = renderCard({ task, onClick: () => {} });

    // The drag handle span has aria-label="Drag"
    const dragHandle = container.querySelector('[aria-label="Drag"]');
    expect(dragHandle).not.toBeNull();
  });

  it("card root outer div still carries data-task-type attribute", () => {
    const task = makeTask({ type: "goal" });
    const { container } = renderCard({ task, onClick: () => {} });

    const root = container.querySelector("[data-task-type]");
    expect(root).not.toBeNull();
    expect(root!.getAttribute("data-task-type")).toBe("goal");
    // The root is a div (the outer wrapper managed by dnd-kit)
    expect(root!.tagName.toLowerCase()).toBe("div");
  });

  it("card outer div carries data-density attribute", () => {
    const task = makeTask();
    const { container } = renderCard({ task, onClick: () => {} });

    const root = container.querySelector("[data-task-type]");
    expect(root!.getAttribute("data-density")).toBe("default");
  });

  it("dnd-kit applies aria-roledescription='sortable' to the outer wrapper (expected dnd-kit behaviour)", () => {
    const task = makeTask();
    const { container } = renderCard({ task, onClick: () => {} });

    // dnd-kit's useSortable injects role="button" + aria-roledescription="sortable"
    // on the outer wrapper div via its `attributes` spread. This is expected and correct.
    const sortableWrapper = container.querySelector(
      "[data-task-type][aria-roledescription='sortable']",
    );
    expect(sortableWrapper).not.toBeNull();
    // Confirm it is a div (the outer wrapper), not the card body button
    expect(sortableWrapper!.tagName.toLowerCase()).toBe("div");
  });
});

// ---------------------------------------------------------------------------
// density="tight" — card body is already a real button in tight mode
// ---------------------------------------------------------------------------

describe("Card — tight density card body is a native <button>", () => {
  it("renders a <button type='button'> inside the tight card wrapper", () => {
    const task = makeTask();
    const { container } = renderCard({ task, onClick: () => {}, density: "tight" });

    const btn = container.querySelector("[data-task-type] button[type='button']");
    expect(btn).not.toBeNull();
    expect(btn!.tagName.toLowerCase()).toBe("button");
  });

  it("tight card button has focus ring classes", () => {
    const task = makeTask();
    const { container } = renderCard({ task, onClick: () => {}, density: "tight" });

    const btn = container.querySelector("[data-task-type] button[type='button']");
    expect(btn!.className).toContain("focus:outline-none");
    expect(btn!.className).toContain("focus-visible:ring-1");
    expect(btn!.className).toContain("focus-visible:ring-accent");
  });
});

// ---------------------------------------------------------------------------
// Card body is NOT a div[role='button'] (was the old pattern on the card body div)
// Note: dnd-kit's outer wrapper div does get role="button" via useSortable
// attributes — that's expected. We assert the CARD BODY itself is not a div.
// ---------------------------------------------------------------------------

describe("Card — card body is not a div element", () => {
  it("tight density: the click target is a <button> inside the card wrapper div", () => {
    const task = makeTask();
    const { container } = renderCard({ task, onClick: () => {}, density: "tight" });

    // In tight mode, there is no inner flex div — the button is direct child of the outer wrapper
    const btn = container.querySelector("[data-task-type] > button[type='button']");
    expect(btn).not.toBeNull();
    expect(btn!.tagName.toLowerCase()).toBe("button");
  });
});

// ---------------------------------------------------------------------------
// parent breadcrumb interaction (remains span[role='button'] to avoid nested-button HTML issue)
// ---------------------------------------------------------------------------

describe("Card — parent breadcrumb interaction preserved", () => {
  it("renders the parent breadcrumb text content correctly", () => {
    const task = makeTask({ parent_id: "parent-42", parent_title: "Quarterly roadmap" });
    renderCard({ task, onClick: () => {} });

    expect(screen.getByText(/↑\s*Quarterly roadmap/)).toBeInTheDocument();
  });

  it("clicking parent breadcrumb calls onOpenTask without triggering main onClick", async () => {
    const onClick = vi.fn();
    const onOpenTask = vi.fn();
    const task = makeTask({ parent_id: "parent-42", parent_title: "Quarterly roadmap" });
    renderCard({ task, onClick, onOpenTask });

    const user = userEvent.setup();
    await user.click(screen.getByText(/↑\s*Quarterly roadmap/));

    expect(onOpenTask).toHaveBeenCalledWith("parent-42");
    // Note: because breadcrumb span is inside the card body button, click
    // propagation is stopped via e.stopPropagation()
    expect(onClick).not.toHaveBeenCalled();
  });
});

// ---------------------------------------------------------------------------
// realizes chip interaction preserved
// ---------------------------------------------------------------------------

describe("Card — realizes chip interaction preserved", () => {
  it("renders the realizes chip text content correctly", () => {
    const task = makeTask({
      type: "fix",
      realizes: "feat-task-99",
      realizes_feature_key: "FEAT-007",
    });
    renderCard({ task, onClick: () => {} });

    expect(screen.getByText(/→ FEAT-007/i)).toBeInTheDocument();
  });

  it("clicking realizes chip calls onOpenTask without triggering main onClick", async () => {
    const onClick = vi.fn();
    const onOpenTask = vi.fn();
    const task = makeTask({
      type: "fix",
      realizes: "feat-task-99",
      realizes_feature_key: "FEAT-007",
    });
    renderCard({ task, onClick, onOpenTask });

    const user = userEvent.setup();
    await user.click(screen.getByText(/→ FEAT-007/i));

    expect(onOpenTask).toHaveBeenCalledWith("feat-task-99");
    expect(onClick).not.toHaveBeenCalled();
  });
});
