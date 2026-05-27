import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import TimeFrameSelector from "../TimeFrameSelector";
import type { TimeFrame } from "../TimeFrameSelector";

function renderSelector(value: TimeFrame, onChange = vi.fn()) {
  render(<TimeFrameSelector value={value} onChange={onChange} />);
  return { onChange };
}

describe("TimeFrameSelector", () => {
  it("renders all preset buttons", () => {
    renderSelector({ preset: "all" });
    for (const label of ["6 h", "24 h", "7 d", "30 d", "90 d", "All", "Custom"]) {
      expect(screen.getByRole("button", { name: label })).toBeInTheDocument();
    }
  });

  it("marks the active preset with aria-pressed=true", () => {
    renderSelector({ preset: "7d" });
    expect(screen.getByRole("button", { name: "7 d" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "All" })).toHaveAttribute("aria-pressed", "false");
  });

  it("calls onChange with the clicked preset", async () => {
    const { onChange } = renderSelector({ preset: "all" });
    await userEvent.click(screen.getByRole("button", { name: "24 h" }));
    expect(onChange).toHaveBeenCalledWith({ preset: "24h" });
  });

  it("does not show date inputs for non-custom presets", () => {
    renderSelector({ preset: "7d" });
    expect(screen.queryByLabelText("From")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("To")).not.toBeInTheDocument();
  });

  it("shows date inputs when custom is active", () => {
    renderSelector({ preset: "custom" });
    expect(screen.getByLabelText("From")).toBeInTheDocument();
    expect(screen.getByLabelText("To")).toBeInTheDocument();
  });

  it("calls onChange with preset:custom (no dates) when Custom clicked", async () => {
    const { onChange } = renderSelector({ preset: "all" });
    await userEvent.click(screen.getByRole("button", { name: "Custom" }));
    expect(onChange).toHaveBeenCalledWith({ preset: "custom" });
  });

  it("calls onChange with from/to when both valid dates are entered", async () => {
    const { onChange } = renderSelector({ preset: "custom" });
    await userEvent.type(screen.getByLabelText("From"), "2024-01-01");
    await userEvent.type(screen.getByLabelText("To"), "2024-01-31");
    expect(onChange).toHaveBeenLastCalledWith({
      preset: "custom",
      from: "2024-01-01",
      to: "2024-01-31",
    });
  });

  it("shows an error and does not call onChange when from > to", async () => {
    const { onChange } = renderSelector({ preset: "custom" });
    await userEvent.type(screen.getByLabelText("From"), "2024-06-01");
    await userEvent.type(screen.getByLabelText("To"), "2024-01-01");
    expect(screen.getByRole("alert")).toBeInTheDocument();
    expect(onChange).not.toHaveBeenCalledWith(
      expect.objectContaining({ from: expect.any(String), to: expect.any(String) }),
    );
  });

  it("shows an error when only one date is filled", async () => {
    const { onChange } = renderSelector({ preset: "custom" });
    await userEvent.type(screen.getByLabelText("From"), "2024-06-01");
    expect(screen.getByRole("alert")).toBeInTheDocument();
    expect(onChange).not.toHaveBeenCalledWith(
      expect.objectContaining({ from: expect.any(String), to: expect.any(String) }),
    );
  });

  it("clears error after switching away from custom", async () => {
    const { onChange } = renderSelector({ preset: "custom" });
    await userEvent.type(screen.getByLabelText("From"), "2024-06-01");
    // error should be showing
    expect(screen.getByRole("alert")).toBeInTheDocument();
    // switch to a preset — parent re-renders with new value
    await userEvent.click(screen.getByRole("button", { name: "7 d" }));
    expect(onChange).toHaveBeenLastCalledWith({ preset: "7d" });
  });

  it("applies extra className to the root element", () => {
    const { container } = render(
      <TimeFrameSelector value={{ preset: "all" }} onChange={vi.fn()} className="my-custom-class" />,
    );
    expect(container.firstChild).toHaveClass("my-custom-class");
  });

  it("populates date inputs from controlled value", () => {
    renderSelector({ preset: "custom", from: "2024-03-01", to: "2024-03-31" });
    expect(screen.getByLabelText<HTMLInputElement>("From").value).toBe("2024-03-01");
    expect(screen.getByLabelText<HTMLInputElement>("To").value).toBe("2024-03-31");
  });
});
