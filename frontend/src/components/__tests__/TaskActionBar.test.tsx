import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { TaskActionBar } from "../TaskActionBar";
import type { TaskState } from "../../types";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

interface Handlers {
  onStart: ReturnType<typeof vi.fn>;
  onStop: ReturnType<typeof vi.fn>;
  onEdit: ReturnType<typeof vi.fn>;
  onDelete: ReturnType<typeof vi.fn>;
  onArchive: ReturnType<typeof vi.fn>;
  onMarkDone: ReturnType<typeof vi.fn>;
  onSendToBacklog: ReturnType<typeof vi.fn>;
}

function makeHandlers(): Handlers {
  return {
    onStart: vi.fn(),
    onStop: vi.fn(),
    onEdit: vi.fn(),
    onDelete: vi.fn(),
    onArchive: vi.fn(),
    onMarkDone: vi.fn(),
    onSendToBacklog: vi.fn(),
  };
}

function renderBar(taskState: TaskState, handlers: Handlers = makeHandlers()) {
  render(
    <TaskActionBar
      taskState={taskState}
      isStarting={false}
      isStopping={false}
      isDeleting={false}
      isArchiving={false}
      isMarkingDone={false}
      isSendingToBacklog={false}
      onStart={handlers.onStart}
      onStop={handlers.onStop}
      onEdit={handlers.onEdit}
      onDelete={handlers.onDelete}
      onArchive={handlers.onArchive}
      onMarkDone={handlers.onMarkDone}
      onSendToBacklog={handlers.onSendToBacklog}
    />,
  );
  return handlers;
}

/** All button aria-labels emitted by TaskActionBar, in render order. */
const ALL_LABELS = [
  "Start agent",
  "Stop agent",
  "Mark task as done",
  "Send task to backlog",
  "Archive task",
  "Cancel task (archive)",
  "Edit task",
  "Delete task",
] as const;

function visibleLabels(): string[] {
  return ALL_LABELS.filter((label) => screen.queryByLabelText(label) !== null);
}

// ---------------------------------------------------------------------------
// Per-state button-set lockdown
//
// Each parametrized case asserts the exact visible button set for one
// TaskState. The set is intentionally compared with toEqual (not
// toContain) so an accidental new button or a removed button on the wrong
// state surfaces immediately.
// ---------------------------------------------------------------------------

describe("TaskActionBar — visible button set per state", () => {
  it.each([
    {
      state: "backlog" as TaskState,
      expected: ["Start agent", "Edit task", "Delete task"],
    },
    {
      state: "active" as TaskState,
      expected: ["Stop agent", "Edit task", "Delete task"],
    },
    {
      state: "waiting" as TaskState,
      expected: [
        "Mark task as done",
        "Send task to backlog",
        // Note: 'waiting' uses the alternate archive label
        "Cancel task (archive)",
        "Edit task",
        "Delete task",
      ],
    },
    {
      state: "done" as TaskState,
      expected: [
        "Send task to backlog",
        "Archive task",
        "Edit task",
        "Delete task",
      ],
    },
    {
      state: "archived" as TaskState,
      expected: [
        "Mark task as done",
        "Send task to backlog",
        "Edit task",
        "Delete task",
      ],
    },
  ])(
    "state='$state' renders exactly: $expected",
    ({ state, expected }) => {
      renderBar(state);
      expect(visibleLabels()).toEqual(expected);
    },
  );
});

// ---------------------------------------------------------------------------
// Click → callback wiring for the NEW buttons (and Mark Done on archived,
// which is also newly added behavior).
// ---------------------------------------------------------------------------

describe("TaskActionBar — Send to Backlog button", () => {
  it.each<TaskState>(["waiting", "done", "archived"])(
    "calls onSendToBacklog when clicked from state='%s'",
    async (state) => {
      const handlers = renderBar(state);

      await userEvent.click(screen.getByLabelText("Send task to backlog"));

      expect(handlers.onSendToBacklog).toHaveBeenCalledOnce();
      // Sanity: no other action callback fired.
      expect(handlers.onMarkDone).not.toHaveBeenCalled();
      expect(handlers.onArchive).not.toHaveBeenCalled();
      expect(handlers.onStart).not.toHaveBeenCalled();
      expect(handlers.onStop).not.toHaveBeenCalled();
    },
  );

  it("does not render the Send to Backlog button on state='backlog'", () => {
    renderBar("backlog");
    expect(screen.queryByLabelText("Send task to backlog")).toBeNull();
  });

  it("does not render the Send to Backlog button on state='active'", () => {
    renderBar("active");
    expect(screen.queryByLabelText("Send task to backlog")).toBeNull();
  });
});

describe("TaskActionBar — Mark Done button", () => {
  it("calls onMarkDone when clicked from state='waiting'", async () => {
    const handlers = renderBar("waiting");

    await userEvent.click(screen.getByLabelText("Mark task as done"));

    expect(handlers.onMarkDone).toHaveBeenCalledOnce();
  });

  it("calls onMarkDone when clicked from state='archived' (newly exposed)", async () => {
    const handlers = renderBar("archived");

    await userEvent.click(screen.getByLabelText("Mark task as done"));

    expect(handlers.onMarkDone).toHaveBeenCalledOnce();
    expect(handlers.onSendToBacklog).not.toHaveBeenCalled();
  });

  it("does not render the Mark Done button on state='done'", () => {
    // Regression guard: a 'done' task should NOT show the Mark Done button
    // (it's already done). Without this guard the showMarkDone predicate
    // could accidentally include 'done' and produce a no-op idempotent
    // button that confuses the user.
    renderBar("done");
    expect(screen.queryByLabelText("Mark task as done")).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// Loading-state behavior — the new isSendingToBacklog prop is forwarded.
// ---------------------------------------------------------------------------

describe("TaskActionBar — isSendingToBacklog disables the button", () => {
  it("disables the Send to Backlog button while pending", () => {
    render(
      <TaskActionBar
        taskState="done"
        isStarting={false}
        isStopping={false}
        isDeleting={false}
        isArchiving={false}
        isMarkingDone={false}
        isSendingToBacklog={true}
        onStart={vi.fn()}
        onStop={vi.fn()}
        onEdit={vi.fn()}
        onDelete={vi.fn()}
        onArchive={vi.fn()}
        onMarkDone={vi.fn()}
        onSendToBacklog={vi.fn()}
      />,
    );

    const btn = screen.getByLabelText("Send task to backlog");
    expect(btn).toBeDisabled();
  });

  it("clicking a disabled Send to Backlog button does not fire the callback", async () => {
    const onSendToBacklog = vi.fn();
    render(
      <TaskActionBar
        taskState="done"
        isStarting={false}
        isStopping={false}
        isDeleting={false}
        isArchiving={false}
        isMarkingDone={false}
        isSendingToBacklog={true}
        onStart={vi.fn()}
        onStop={vi.fn()}
        onEdit={vi.fn()}
        onDelete={vi.fn()}
        onArchive={vi.fn()}
        onMarkDone={vi.fn()}
        onSendToBacklog={onSendToBacklog}
      />,
    );

    await userEvent.click(screen.getByLabelText("Send task to backlog"));

    expect(onSendToBacklog).not.toHaveBeenCalled();
  });
});
