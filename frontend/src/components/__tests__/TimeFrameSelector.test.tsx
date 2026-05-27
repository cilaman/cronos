import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {
  TimeFrameSelector,
  timeFrameToDateParams,
  type TimeFrame,
} from "../TimeFrameSelector";

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

  it("marks the active preset visually", () => {
    renderSelector({ preset: "7d" });
    expect(screen.getByRole("button", { name: "7 d" }).className).toContain("bg-accent");
    expect(screen.getByRole("button", { name: "All" }).className).not.toContain("bg-accent");
  });

  it("calls onChange with the clicked preset", async () => {
    const { onChange } = renderSelector({ preset: "all" });
    await userEvent.click(screen.getByRole("button", { name: "24 h" }));
    expect(onChange).toHaveBeenCalledWith({ preset: "24h" });
  });

  it("does not show date inputs for non-custom presets", () => {
    const { container } = render(
      <TimeFrameSelector value={{ preset: "7d" }} onChange={vi.fn()} />,
    );
    expect(container.querySelectorAll('input[type="date"]')).toHaveLength(0);
  });

  it("shows date inputs when custom is active", () => {
    const { container } = render(
      <TimeFrameSelector
        value={{ preset: "custom", from: "2024-01-01", to: "2024-01-31" }}
        onChange={vi.fn()}
      />,
    );
    expect(container.querySelectorAll('input[type="date"]')).toHaveLength(2);
  });

  it("calls onChange with custom + default date range when Custom clicked", async () => {
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

  it("populates date inputs from controlled value", () => {
    const { container } = render(
      <TimeFrameSelector
        value={{ preset: "custom", from: "2024-03-01", to: "2024-03-31" }}
        onChange={vi.fn()}
      />,
    );
    const inputs = container.querySelectorAll<HTMLInputElement>('input[type="date"]');
    expect(inputs[0].value).toBe("2024-03-01");
    expect(inputs[1].value).toBe("2024-03-31");
  });

  it("calls onChange with updated `from` when first date input changes", () => {
    const onChange = vi.fn();
    const { container } = render(
      <TimeFrameSelector
        value={{ preset: "custom", from: "2024-03-01", to: "2024-03-31" }}
        onChange={onChange}
      />,
    );
    const [fromInput] = container.querySelectorAll<HTMLInputElement>('input[type="date"]');
    fireEvent.change(fromInput, { target: { value: "2024-03-05" } });
    expect(onChange).toHaveBeenCalledWith({
      preset: "custom",
      from: "2024-03-05",
      to: "2024-03-31",
    });
  });

  it("calls onChange with updated `to` when second date input changes", () => {
    const onChange = vi.fn();
    const { container } = render(
      <TimeFrameSelector
        value={{ preset: "custom", from: "2024-03-01", to: "2024-03-31" }}
        onChange={onChange}
      />,
    );
    const inputs = container.querySelectorAll<HTMLInputElement>('input[type="date"]');
    fireEvent.change(inputs[1], { target: { value: "2024-03-15" } });
    expect(onChange).toHaveBeenCalledWith({
      preset: "custom",
      from: "2024-03-01",
      to: "2024-03-15",
    });
  });
});

describe("timeFrameToDateParams", () => {
  it("returns empty object for `all`", () => {
    expect(timeFrameToDateParams({ preset: "all" })).toEqual({});
  });

  it("converts custom range to ISO-ish boundaries", () => {
    expect(
      timeFrameToDateParams({ preset: "custom", from: "2024-01-01", to: "2024-01-31" }),
    ).toEqual({
      fromDt: "2024-01-01T00:00:00",
      toDt: "2024-01-31T23:59:59",
    });
  });

  it("produces a from < to ISO range for fixed presets", () => {
    const params = timeFrameToDateParams({ preset: "7d" });
    expect(params.fromDt).toBeDefined();
    expect(params.toDt).toBeDefined();
    expect(new Date(params.fromDt!).getTime()).toBeLessThan(new Date(params.toDt!).getTime());
  });
});
