import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { ProgressBar } from "../ProgressBar";

describe("ProgressBar", () => {
  it("renders a progressbar role", () => {
    render(<ProgressBar value={50} max={100} />);
    expect(screen.getByRole("progressbar")).toBeInTheDocument();
  });

  it("sets aria-valuenow correctly", () => {
    render(<ProgressBar value={30} max={100} />);
    expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "30");
  });

  it("sets aria-valuemin to 0", () => {
    render(<ProgressBar value={10} max={100} />);
    expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuemin", "0");
  });

  it("sets aria-valuemax correctly", () => {
    render(<ProgressBar value={10} max={200} />);
    expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuemax", "200");
  });

  it("renders 0% fill when value is 0", () => {
    const { container } = render(<ProgressBar value={0} max={100} />);
    const fill = container.querySelector("[style]") as HTMLElement;
    expect(fill.style.width).toBe("0%");
  });

  it("renders 100% fill when value equals max", () => {
    const { container } = render(<ProgressBar value={100} max={100} />);
    const fill = container.querySelector("[style]") as HTMLElement;
    expect(fill.style.width).toBe("100%");
  });

  it("clamps fill to 100% when value exceeds max", () => {
    const { container } = render(<ProgressBar value={150} max={100} />);
    const fill = container.querySelector("[style]") as HTMLElement;
    expect(fill.style.width).toBe("100%");
  });

  it("shows label when showLabel is true", () => {
    render(<ProgressBar value={75} max={100} showLabel />);
    expect(screen.getByText("75%")).toBeInTheDocument();
  });

  it("does not show label by default", () => {
    render(<ProgressBar value={50} max={100} />);
    expect(screen.queryByText("%")).not.toBeInTheDocument();
  });

  it("applies success tone fill class", () => {
    const { container } = render(
      <ProgressBar value={80} max={100} tone="success" />,
    );
    const fill = container.querySelector("[style]") as HTMLElement;
    expect(fill.className).toContain("bg-success");
  });

  it("applies danger tone fill class", () => {
    const { container } = render(
      <ProgressBar value={80} max={100} tone="danger" />,
    );
    const fill = container.querySelector("[style]") as HTMLElement;
    expect(fill.className).toContain("bg-danger");
  });

  it("applies warning tone fill class", () => {
    const { container } = render(
      <ProgressBar value={50} max={100} tone="warning" />,
    );
    const fill = container.querySelector("[style]") as HTMLElement;
    expect(fill.className).toContain("bg-warning");
  });

  it("renders multiple segments when segments prop is provided", () => {
    const segments = [
      { value: 30, tone: "success" as const, label: "Done" },
      { value: 20, tone: "warning" as const, label: "In progress" },
    ];
    const { container } = render(
      <ProgressBar value={50} max={100} segments={segments} />,
    );
    // Should have 2 coloured fills (one per segment)
    const fills = container.querySelectorAll("[style]");
    expect(fills.length).toBe(2);
  });

  it("applies custom className", () => {
    const { container } = render(
      <ProgressBar value={10} max={100} className="my-bar" />,
    );
    expect((container.firstChild as Element).className).toContain("my-bar");
  });

  it("handles max=0 gracefully (no division by zero)", () => {
    render(<ProgressBar value={0} max={0} showLabel />);
    expect(screen.getByText("0%")).toBeInTheDocument();
  });

  it("segment fill widths reflect proportional values", () => {
    const segments = [
      { value: 50, tone: "success" as const },
      { value: 50, tone: "danger" as const },
    ];
    const { container } = render(
      <ProgressBar value={100} max={100} segments={segments} />,
    );
    const fills = container.querySelectorAll("[style]") as NodeListOf<HTMLElement>;
    expect(fills[0].style.width).toBe("50%");
    expect(fills[1].style.width).toBe("50%");
  });
});
