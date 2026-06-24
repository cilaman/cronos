import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { DndContext } from "@dnd-kit/core";
import { Lane } from "../Lane";

const FOCUS_RING_CLASSES = [
  "focus:outline-none",
  "focus-visible:ring-1",
  "focus-visible:ring-accent",
];

function renderLane(props: Partial<React.ComponentProps<typeof Lane>> & {
  state: string;
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
// Add-task button — semantic correctness
// ---------------------------------------------------------------------------

describe("Lane buttons — add-task (New task)", () => {
  it("renders a <button> element (not a div with role=button)", () => {
    renderLane({ state: "backlog", label: "Backlog" });
    const btn = screen.getByRole("button", { name: "New task" });
    expect(btn.tagName).toBe("BUTTON");
  });

  it('has aria-label "New task"', () => {
    renderLane({ state: "backlog", label: "Backlog" });
    expect(screen.getByRole("button", { name: "New task" })).toBeInTheDocument();
  });

  it("carries all three focus-ring classes", () => {
    renderLane({ state: "backlog", label: "Backlog" });
    const btn = screen.getByRole("button", { name: "New task" });
    for (const cls of FOCUS_RING_CLASSES) {
      expect(btn.className).toContain(cls);
    }
  });

  it("is only visible on backlog lane by default", () => {
    renderLane({ state: "active", label: "Active" });
    expect(screen.queryByRole("button", { name: "New task" })).not.toBeInTheDocument();
  });

  it("is visible when showAdd=true on any lane", () => {
    renderLane({ state: "done", label: "Done", showAdd: true });
    expect(screen.getByRole("button", { name: "New task" })).toBeInTheDocument();
  });

  it("calls onAdd when clicked", async () => {
    const onAdd = vi.fn();
    renderLane({ state: "backlog", label: "Backlog", onAdd });
    screen.getByRole("button", { name: "New task" }).click();
    expect(onAdd).toHaveBeenCalledTimes(1);
  });
});

// ---------------------------------------------------------------------------
// Hide-lane button — semantic correctness
// ---------------------------------------------------------------------------

describe("Lane buttons — hide-lane", () => {
  it("renders a <button> element (not a div with role=button)", () => {
    renderLane({ state: "active", label: "Active", onHideLane: vi.fn() });
    const btn = screen.getByRole("button", { name: /Hide Active lane/i });
    expect(btn.tagName).toBe("BUTTON");
  });

  it("has a descriptive aria-label containing the lane label", () => {
    renderLane({ state: "waiting", label: "Waiting", onHideLane: vi.fn() });
    expect(
      screen.getByRole("button", { name: "Hide Waiting lane" }),
    ).toBeInTheDocument();
  });

  it("carries all three focus-ring classes", () => {
    renderLane({ state: "active", label: "Active", onHideLane: vi.fn() });
    const btn = screen.getByRole("button", { name: /Hide Active lane/i });
    for (const cls of FOCUS_RING_CLASSES) {
      expect(btn.className).toContain(cls);
    }
  });

  it("is not rendered when onHideLane is undefined", () => {
    renderLane({ state: "active", label: "Active" });
    expect(screen.queryByRole("button", { name: /Hide/i })).not.toBeInTheDocument();
  });

  it("calls onHideLane with the lane state when clicked", () => {
    const onHideLane = vi.fn();
    renderLane({ state: "done", label: "Done", onHideLane });
    screen.getByRole("button", { name: /Hide Done lane/i }).click();
    expect(onHideLane).toHaveBeenCalledWith("done");
  });

  it("has a title attribute set to 'Hide <label>'", () => {
    renderLane({ state: "active", label: "Active", onHideLane: vi.fn() });
    const btn = screen.getByRole("button", { name: /Hide Active lane/i });
    expect(btn.getAttribute("title")).toBe("Hide Active");
  });
});

// ---------------------------------------------------------------------------
// Both buttons coexist on the backlog lane
// ---------------------------------------------------------------------------

describe("Lane buttons — coexistence on backlog", () => {
  it("renders both add-task and hide-lane when both props are provided on backlog", () => {
    renderLane({
      state: "backlog",
      label: "Backlog",
      onAdd: vi.fn(),
      onHideLane: vi.fn(),
    });
    expect(screen.getByRole("button", { name: "New task" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Hide Backlog lane/i })).toBeInTheDocument();
  });

  it("both buttons are real <button> elements", () => {
    renderLane({
      state: "backlog",
      label: "Backlog",
      onAdd: vi.fn(),
      onHideLane: vi.fn(),
    });
    const buttons = screen.getAllByRole("button");
    for (const btn of buttons) {
      expect(btn.tagName).toBe("BUTTON");
    }
  });
});
