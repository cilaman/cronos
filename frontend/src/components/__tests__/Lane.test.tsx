import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { DndContext } from "@dnd-kit/core";
import { Lane } from "../Lane";
import type { TaskState, TaskSummary } from "../../types";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeTask(overrides: Partial<TaskSummary> = {}): TaskSummary {
  return {
    id: "task-1",
    space_id: "space-1",
    title: "A task",
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
    ...overrides,
  };
}

function renderLane(props: Partial<React.ComponentProps<typeof Lane>> & {
  state: TaskState;
  label: string;
}) {
  return render(
    <DndContext>
      <Lane
        tasks={[]}
        onOpen={() => {}}
        onAdd={() => {}}
        {...props}
      />
    </DndContext>,
  );
}

// ---------------------------------------------------------------------------
// onHideLane × button
// ---------------------------------------------------------------------------

describe("Lane — onHideLane × button", () => {
  it("renders the hide button when onHideLane is provided", () => {
    renderLane({
      state: "active",
      label: "Active",
      onHideLane: vi.fn(),
    });
    expect(screen.getByRole("button", { name: /Hide Active lane/i })).toBeInTheDocument();
  });

  it("does NOT render the hide button when onHideLane is undefined", () => {
    renderLane({ state: "active", label: "Active" });
    expect(screen.queryByRole("button", { name: /Hide .* lane/i })).not.toBeInTheDocument();
  });

  it("uses the lane label in the aria-label (e.g. 'Hide Waiting lane')", () => {
    renderLane({
      state: "waiting",
      label: "Waiting",
      onHideLane: vi.fn(),
    });
    expect(screen.getByRole("button", { name: "Hide Waiting lane" })).toBeInTheDocument();
  });

  it("invokes onHideLane with the lane state when clicked", async () => {
    const onHideLane = vi.fn();
    renderLane({
      state: "done",
      label: "Done",
      onHideLane,
    });

    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: /Hide Done lane/i }));

    expect(onHideLane).toHaveBeenCalledTimes(1);
    expect(onHideLane).toHaveBeenCalledWith("done");
  });

  it("the hide button is always visible (no opacity-0 / hover-reveal classes)", () => {
    renderLane({
      state: "active",
      label: "Active",
      onHideLane: vi.fn(),
    });
    const btn = screen.getByRole("button", { name: /Hide Active lane/i });
    // Iteration 2 dropped the opacity gymnastics — the × is rendered visible.
    expect(btn.className).not.toContain("opacity-0");
    expect(btn.className).not.toContain("group-hover/lane:opacity-100");
    expect(btn.className).not.toContain("focus:opacity-100");
  });

  it("the hide button keeps its hover/focus styling classes", () => {
    renderLane({
      state: "active",
      label: "Active",
      onHideLane: vi.fn(),
    });
    const btn = screen.getByRole("button", { name: /Hide Active lane/i });
    expect(btn.className).toContain("hover:text-ink");
    expect(btn.className).toContain("hover:bg-surface-2");
    expect(btn.className).toContain("focus-visible:ring-accent");
  });

  it("the hide button carries a descriptive title attribute", () => {
    renderLane({
      state: "active",
      label: "Active",
      onHideLane: vi.fn(),
    });
    const btn = screen.getByRole("button", { name: /Hide Active lane/i });
    expect(btn.getAttribute("title")).toBe("Hide Active");
  });
});

// ---------------------------------------------------------------------------
// Backlog "+ New task" button — preserved alongside the hide ×
// ---------------------------------------------------------------------------

describe("Lane — backlog '+ New task' button", () => {
  it("renders the '+ New task' button only on the backlog lane", () => {
    renderLane({ state: "backlog", label: "To Do" });
    expect(screen.getByRole("button", { name: /New task/i })).toBeInTheDocument();
  });

  it("does NOT render '+ New task' on non-backlog lanes", () => {
    renderLane({ state: "active", label: "Active" });
    expect(screen.queryByRole("button", { name: /New task/i })).not.toBeInTheDocument();
  });

  it("clicking '+ New task' invokes onAdd", async () => {
    const onAdd = vi.fn();
    renderLane({ state: "backlog", label: "To Do", onAdd });

    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: /New task/i }));

    expect(onAdd).toHaveBeenCalledTimes(1);
  });

  it("renders BOTH '+ New task' and the hide × on the backlog lane when onHideLane is provided", () => {
    renderLane({
      state: "backlog",
      label: "To Do",
      onAdd: () => {},
      onHideLane: vi.fn(),
    });
    expect(screen.getByRole("button", { name: /New task/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Hide To Do lane/i })).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Lane header content — label + count + running pulse
// ---------------------------------------------------------------------------

describe("Lane — header", () => {
  it("renders the lane label", () => {
    renderLane({ state: "active", label: "Active" });
    expect(screen.getByRole("heading", { name: "Active" })).toBeInTheDocument();
  });

  it("renders a zero-padded count of tasks", () => {
    renderLane({
      state: "active",
      label: "Active",
      tasks: [makeTask({ id: "t1" }), makeTask({ id: "t2" }), makeTask({ id: "t3" })],
    });
    expect(screen.getByText("03")).toBeInTheDocument();
  });

  it("shows the running pulse when any task isRunning returns true", () => {
    renderLane({
      state: "active",
      label: "Active",
      tasks: [makeTask({ id: "t1" })],
      isRunning: (id) => id === "t1",
    });
    expect(screen.getByLabelText("Task running")).toBeInTheDocument();
  });

  it("hides the running pulse when no task is running", () => {
    renderLane({
      state: "active",
      label: "Active",
      tasks: [makeTask({ id: "t1" })],
      isRunning: () => false,
    });
    expect(screen.queryByLabelText("Task running")).not.toBeInTheDocument();
  });
});
