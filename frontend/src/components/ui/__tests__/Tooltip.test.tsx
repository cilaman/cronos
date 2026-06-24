import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Tooltip } from "../Tooltip";

describe("Tooltip", () => {
  it("renders the child element", () => {
    render(
      <Tooltip content="Helpful hint">
        <button>Hover me</button>
      </Tooltip>,
    );
    expect(screen.getByRole("button", { name: "Hover me" })).toBeInTheDocument();
  });

  it("does not show tooltip initially", () => {
    render(
      <Tooltip content="Hidden tooltip">
        <button>Target</button>
      </Tooltip>,
    );
    expect(screen.queryByRole("tooltip")).not.toBeInTheDocument();
  });

  it("shows tooltip on mouse hover", async () => {
    const user = userEvent.setup();
    render(
      <Tooltip content="Hover tip">
        <button>Target</button>
      </Tooltip>,
    );
    await user.hover(screen.getByRole("button"));
    expect(screen.getByRole("tooltip")).toBeInTheDocument();
    expect(screen.getByRole("tooltip")).toHaveTextContent("Hover tip");
  });

  it("hides tooltip after mouse leave", async () => {
    const user = userEvent.setup();
    render(
      <Tooltip content="Gone soon">
        <button>Target</button>
      </Tooltip>,
    );
    const btn = screen.getByRole("button");
    await user.hover(btn);
    expect(screen.getByRole("tooltip")).toBeInTheDocument();
    await user.unhover(btn);
    expect(screen.queryByRole("tooltip")).not.toBeInTheDocument();
  });

  it("shows tooltip on focus (keyboard accessibility)", async () => {
    const user = userEvent.setup();
    render(
      <Tooltip content="Focus tip">
        <button>Focusable</button>
      </Tooltip>,
    );
    await user.tab();
    expect(screen.getByRole("button")).toHaveFocus();
    expect(screen.getByRole("tooltip")).toBeInTheDocument();
  });

  it("hides tooltip on blur", async () => {
    const user = userEvent.setup();
    render(
      <Tooltip content="Blur me">
        <button>Focusable</button>
      </Tooltip>,
    );
    await user.tab();
    expect(screen.getByRole("tooltip")).toBeInTheDocument();
    await user.tab(); // moves focus away
    expect(screen.queryByRole("tooltip")).not.toBeInTheDocument();
  });

  it("sets aria-describedby on the child when visible", async () => {
    const user = userEvent.setup();
    render(
      <Tooltip content="Described">
        <button>Describable</button>
      </Tooltip>,
    );
    await user.hover(screen.getByRole("button"));
    const btn = screen.getByRole("button");
    const tooltip = screen.getByRole("tooltip");
    expect(btn).toHaveAttribute("aria-describedby", tooltip.id);
  });

  it("applies z-[60] class to the tooltip element", async () => {
    const user = userEvent.setup();
    render(
      <Tooltip content="z-check">
        <button>Target</button>
      </Tooltip>,
    );
    await user.hover(screen.getByRole("button"));
    const tooltip = screen.getByRole("tooltip");
    expect(tooltip.className).toContain("z-[60]");
  });

  it("renders string content in the tooltip", async () => {
    const user = userEvent.setup();
    render(
      <Tooltip content="Plain string">
        <button>Target</button>
      </Tooltip>,
    );
    await user.hover(screen.getByRole("button"));
    expect(screen.getByRole("tooltip")).toHaveTextContent("Plain string");
  });

  it("forwards extra event handlers on the child without overriding them", async () => {
    const user = userEvent.setup();
    const onMouseEnter = vi.fn();
    render(
      <Tooltip content="With handler">
        <button onMouseEnter={onMouseEnter}>Target</button>
      </Tooltip>,
    );
    await user.hover(screen.getByRole("button"));
    expect(onMouseEnter).toHaveBeenCalled();
    expect(screen.getByRole("tooltip")).toBeInTheDocument();
  });

  it("renders React node content in the tooltip", async () => {
    const user = userEvent.setup();
    render(
      <Tooltip content={<span>Rich content</span>}>
        <button>Target</button>
      </Tooltip>,
    );
    await user.hover(screen.getByRole("button"));
    expect(screen.getByText("Rich content")).toBeInTheDocument();
  });
});
