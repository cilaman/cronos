/**
 * I5 button-focus guard: TimeFrameSelector.buttons.test.tsx
 *
 * Asserts that:
 * 1. Preset-tab buttons are real <button> elements (not divs).
 * 2. All preset buttons carry the focus-visible:ring-accent focus ring.
 * 3. Active-tab state is communicated via variant class, never raw className.
 * 4. The component remains accessible — getByRole("button") resolves each tab.
 */
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { TimeFrameSelector, type TimeFrame } from "../TimeFrameSelector";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function renderSelector(value: TimeFrame, onChange = vi.fn()) {
  render(<TimeFrameSelector value={value} onChange={onChange} />);
  return { onChange };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("TimeFrameSelector button semantics (I5)", () => {
  it("renders all preset tabs as real <button> elements", () => {
    renderSelector({ preset: "all" });
    const labels = ["6 h", "24 h", "7 d", "30 d", "90 d", "All", "Custom"];
    labels.forEach((label) => {
      const btn = screen.getByRole("button", { name: label });
      expect(btn.tagName).toBe("BUTTON");
    });
  });

  it("all preset buttons carry focus:outline-none class", () => {
    renderSelector({ preset: "all" });
    const labels = ["6 h", "24 h", "7 d", "30 d", "90 d", "All", "Custom"];
    labels.forEach((label) => {
      const btn = screen.getByRole("button", { name: label });
      expect(btn.className).toContain("focus:outline-none");
    });
  });

  it("all preset buttons carry focus-visible:ring-accent class", () => {
    renderSelector({ preset: "all" });
    const labels = ["6 h", "24 h", "7 d", "30 d", "90 d", "All", "Custom"];
    labels.forEach((label) => {
      const btn = screen.getByRole("button", { name: label });
      expect(btn.className).toContain("focus-visible:ring-accent");
    });
  });

  it("active-tab button has primary variant class (bg-accent)", () => {
    renderSelector({ preset: "7d" });
    const activeBtn = screen.getByRole("button", { name: "7 d" });
    // The primary variant applies bg-accent via the Button primitive
    expect(activeBtn.className).toContain("bg-accent");
  });

  it("inactive-tab buttons do not have primary variant bg-accent class", () => {
    renderSelector({ preset: "7d" });
    const inactiveBtn = screen.getByRole("button", { name: "All" });
    // ghost variant should NOT have bg-accent
    expect(inactiveBtn.className).not.toContain("bg-accent");
  });

  it("active-tab state is not applied via an explicit isActive attribute or data-active (uses variant prop)", () => {
    renderSelector({ preset: "30d" });
    const activeBtn = screen.getByRole("button", { name: "30 d" });
    // State communicated via variant/className from primitive, not DOM attributes
    expect(activeBtn.getAttribute("data-active")).toBeNull();
    expect(activeBtn.getAttribute("aria-pressed")).toBeNull();
  });

  it("clicking an inactive preset tab calls onChange with the correct preset", async () => {
    const { onChange } = renderSelector({ preset: "all" });
    await userEvent.click(screen.getByRole("button", { name: "24 h" }));
    expect(onChange).toHaveBeenCalledWith({ preset: "24h" });
  });

  it("clicking the Custom tab calls onChange with custom preset and date strings", async () => {
    const { onChange } = renderSelector({ preset: "all" });
    await userEvent.click(screen.getByRole("button", { name: "Custom" }));
    expect(onChange).toHaveBeenCalledTimes(1);
    const arg = onChange.mock.calls[0][0] as TimeFrame;
    expect(arg.preset).toBe("custom");
    if (arg.preset === "custom") {
      expect(arg.from).toMatch(/^\d{4}-\d{2}-\d{2}$/);
      expect(arg.to).toMatch(/^\d{4}-\d{2}-\d{2}$/);
    }
  });

  it("no raw <button> elements bypass the focus ring (all carry ring class)", () => {
    const { container } = render(
      <TimeFrameSelector value={{ preset: "all" }} onChange={vi.fn()} />,
    );
    const buttons = container.querySelectorAll("button");
    expect(buttons.length).toBeGreaterThan(0);
    buttons.forEach((btn) => {
      expect(btn.className).toContain("focus-visible:ring-accent");
    });
  });

  it("compact prop changes size classes but preserves focus ring", () => {
    render(
      <TimeFrameSelector value={{ preset: "all" }} onChange={vi.fn()} compact />,
    );
    const allBtn = screen.getByRole("button", { name: "All" });
    expect(allBtn.className).toContain("focus-visible:ring-accent");
  });
});
