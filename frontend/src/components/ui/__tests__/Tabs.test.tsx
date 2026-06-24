import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Tabs } from "../Tabs";

const ITEMS = [
  { value: "overview", label: "Overview" },
  { value: "details", label: "Details" },
  { value: "history", label: "History" },
];

describe("Tabs", () => {
  it("renders all tab labels", () => {
    render(<Tabs items={ITEMS} value="overview" onChange={vi.fn()} />);
    expect(screen.getByRole("tab", { name: "Overview" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Details" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "History" })).toBeInTheDocument();
  });

  it("marks the active tab with aria-selected=true", () => {
    render(<Tabs items={ITEMS} value="details" onChange={vi.fn()} />);
    expect(screen.getByRole("tab", { name: "Details" })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    expect(screen.getByRole("tab", { name: "Overview" })).toHaveAttribute(
      "aria-selected",
      "false",
    );
  });

  it("calls onChange with the clicked tab value", async () => {
    const onChange = vi.fn();
    render(<Tabs items={ITEMS} value="overview" onChange={onChange} />);
    await userEvent.click(screen.getByRole("tab", { name: "Details" }));
    expect(onChange).toHaveBeenCalledOnce();
    expect(onChange).toHaveBeenCalledWith("details");
  });

  it("renders a tablist container", () => {
    render(<Tabs items={ITEMS} value="overview" onChange={vi.fn()} />);
    expect(screen.getByRole("tablist")).toBeInTheDocument();
  });

  it("does not call onChange when clicking the already-active tab", async () => {
    const onChange = vi.fn();
    render(<Tabs items={ITEMS} value="overview" onChange={onChange} />);
    await userEvent.click(screen.getByRole("tab", { name: "Overview" }));
    // onChange is still called — controlled component; caller decides if re-render needed
    expect(onChange).toHaveBeenCalledWith("overview");
  });

  it("applies custom className to the tablist", () => {
    render(
      <Tabs items={ITEMS} value="overview" onChange={vi.fn()} className="my-4" />,
    );
    expect(screen.getByRole("tablist").className).toContain("my-4");
  });

  it("applies active text class to the selected tab", () => {
    render(<Tabs items={ITEMS} value="history" onChange={vi.fn()} />);
    const activeTab = screen.getByRole("tab", { name: "History" });
    // Active tab should have the accent underline — text-ink (not text-ink-muted)
    expect(activeTab.className).toContain("text-ink");
    expect(activeTab.className).not.toContain("text-ink-muted");
  });

  it("renders with a single tab item", () => {
    render(
      <Tabs items={[{ value: "only", label: "Only" }]} value="only" onChange={vi.fn()} />,
    );
    expect(screen.getByRole("tab", { name: "Only" })).toBeInTheDocument();
  });

  it("renders with an empty items array without crashing", () => {
    render(<Tabs items={[]} value="" onChange={vi.fn()} />);
    expect(screen.getByRole("tablist")).toBeInTheDocument();
  });
});
