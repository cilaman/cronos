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

  it("invokes onClick when the card is clicked", async () => {
    const onClick = vi.fn();
    const task = makeTask({ title: "Clickable card title" });
    renderCard({ task, onClick, compact: true });
    const user = userEvent.setup();
    // The inner <button type="button"> wraps the title; the outer div from
    // useDraggable also exposes role="button", so query by accessible name on
    // the actual <button> element.
    const buttons = screen.getAllByRole("button");
    const cardButton = buttons.find((b) => b.tagName === "BUTTON");
    expect(cardButton).toBeDefined();
    await user.click(cardButton!);
    expect(onClick).toHaveBeenCalledTimes(1);
  });
});
