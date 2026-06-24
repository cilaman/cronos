import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { StatTile } from "../StatTile";

describe("StatTile", () => {
  it("renders the label", () => {
    render(<StatTile label="Active tasks" value={42} />);
    expect(screen.getByText("Active tasks")).toBeInTheDocument();
  });

  it("renders the value", () => {
    render(<StatTile label="Score" value={99} />);
    expect(screen.getByText("99")).toBeInTheDocument();
  });

  it("renders string value", () => {
    render(<StatTile label="Status" value="Healthy" />);
    expect(screen.getByText("Healthy")).toBeInTheDocument();
  });

  it("renders a React node as value", () => {
    render(<StatTile label="Label" value={<span data-testid="custom">★</span>} />);
    expect(screen.getByTestId("custom")).toBeInTheDocument();
  });

  it("renders the delta when provided", () => {
    render(<StatTile label="Throughput" value={5} delta="+2 today" />);
    expect(screen.getByText("+2 today")).toBeInTheDocument();
  });

  it("does not render delta element when delta is omitted", () => {
    render(<StatTile label="Count" value={0} />);
    // No element with delta text should exist
    expect(screen.queryByText(/^\+/)).not.toBeInTheDocument();
  });

  it("does not render delta when delta is empty string", () => {
    const { container } = render(<StatTile label="X" value={1} delta="" />);
    // Should only have 2 spans (label + value), not a third for delta
    const spans = container.querySelectorAll("span");
    expect(spans.length).toBe(2);
  });

  it("applies success tone class to delta", () => {
    const { container } = render(
      <StatTile label="Growth" value={10} delta="+5" tone="success" />,
    );
    // The delta span should have text-success
    const spans = container.querySelectorAll("span");
    const deltaSpan = spans[spans.length - 1];
    expect(deltaSpan.className).toContain("text-success");
  });

  it("applies danger tone class to delta", () => {
    const { container } = render(
      <StatTile label="Errors" value={3} delta="+3" tone="danger" />,
    );
    const spans = container.querySelectorAll("span");
    const deltaSpan = spans[spans.length - 1];
    expect(deltaSpan.className).toContain("text-danger");
  });

  it("applies warning tone class to delta", () => {
    const { container } = render(
      <StatTile label="Queue" value={100} delta="high" tone="warning" />,
    );
    const spans = container.querySelectorAll("span");
    const deltaSpan = spans[spans.length - 1];
    expect(deltaSpan.className).toContain("text-warning");
  });

  it("applies info tone class to delta", () => {
    const { container } = render(
      <StatTile label="Info" value={7} delta="note" tone="info" />,
    );
    const spans = container.querySelectorAll("span");
    const deltaSpan = spans[spans.length - 1];
    expect(deltaSpan.className).toContain("text-info");
  });

  it("applies custom className to wrapper", () => {
    const { container } = render(
      <StatTile label="X" value={1} className="col-span-2" />,
    );
    expect((container.firstChild as Element).className).toContain("col-span-2");
  });

  it("uses neutral tone by default", () => {
    const { container } = render(
      <StatTile label="Default" value={0} delta="same" />,
    );
    const spans = container.querySelectorAll("span");
    const deltaSpan = spans[spans.length - 1];
    expect(deltaSpan.className).toContain("text-ink-muted");
  });
});
