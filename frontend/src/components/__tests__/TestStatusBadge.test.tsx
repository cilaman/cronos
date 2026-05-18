import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { TestStatusBadge } from "../TestStatusBadge";

describe("TestStatusBadge", () => {
  it("renders 'Passed' label for passed status", () => {
    render(<TestStatusBadge status="passed" />);
    expect(screen.getByText("Passed")).toBeInTheDocument();
  });

  it("renders 'Failed' label for failed status", () => {
    render(<TestStatusBadge status="failed" />);
    expect(screen.getByText("Failed")).toBeInTheDocument();
  });

  it("renders 'Error' label for error status", () => {
    render(<TestStatusBadge status="error" />);
    expect(screen.getByText("Error")).toBeInTheDocument();
  });

  it("renders 'Skipped' label for skipped status", () => {
    render(<TestStatusBadge status="skipped" />);
    expect(screen.getByText("Skipped")).toBeInTheDocument();
  });

  it("applies sm size classes when size='sm'", () => {
    const { container } = render(<TestStatusBadge status="passed" size="sm" />);
    const badge = container.firstChild as HTMLElement;
    expect(badge.className).toContain("px-1.5");
    expect(badge.className).toContain("text-[9px]");
  });

  it("applies md size classes by default", () => {
    const { container } = render(<TestStatusBadge status="passed" />);
    const badge = container.firstChild as HTMLElement;
    expect(badge.className).toContain("px-2");
    expect(badge.className).toContain("text-[10px]");
  });

  it("renders as a span element", () => {
    const { container } = render(<TestStatusBadge status="passed" />);
    expect(container.firstChild?.nodeName).toBe("SPAN");
  });
});
