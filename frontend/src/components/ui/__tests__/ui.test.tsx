import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Button } from "../Button";
import { EmptyState } from "../EmptyState";
import { FormInput, FormTextarea, FormSelect } from "../FormInput";
import { Modal } from "../Modal";

// ── Button ────────────────────────────────────────────────────────────────────

describe("Button", () => {
  it("renders children text", () => {
    render(<Button>Click me</Button>);
    expect(screen.getByRole("button", { name: "Click me" })).toBeInTheDocument();
  });

  it("calls onClick when clicked", async () => {
    const onClick = vi.fn();
    render(<Button onClick={onClick}>Go</Button>);
    await userEvent.click(screen.getByRole("button"));
    expect(onClick).toHaveBeenCalledOnce();
  });

  it("is disabled when disabled prop is set", () => {
    render(<Button disabled>Nope</Button>);
    expect(screen.getByRole("button")).toBeDisabled();
  });

  it("is disabled when loading prop is set", () => {
    render(<Button loading>Saving…</Button>);
    expect(screen.getByRole("button")).toBeDisabled();
  });

  it("applies secondary variant classes", () => {
    render(<Button variant="secondary">Secondary</Button>);
    const btn = screen.getByRole("button");
    expect(btn.className).toContain("bg-surface-2");
  });

  it("applies ghost variant classes", () => {
    render(<Button variant="ghost">Ghost</Button>);
    const btn = screen.getByRole("button");
    expect(btn.className).toContain("border-transparent");
  });

  it("applies danger variant classes", () => {
    render(<Button variant="danger">Delete</Button>);
    const btn = screen.getByRole("button");
    expect(btn.className).toContain("bg-danger");
  });

  it("applies sm size classes", () => {
    render(<Button size="sm">Small</Button>);
    const btn = screen.getByRole("button");
    expect(btn.className).toContain("text-xs");
  });

  it("merges extra className", () => {
    render(<Button className="custom-class">X</Button>);
    expect(screen.getByRole("button").className).toContain("custom-class");
  });
});

// ── EmptyState ────────────────────────────────────────────────────────────────

describe("EmptyState", () => {
  it("renders the title", () => {
    render(<EmptyState title="No tasks" />);
    expect(screen.getByText("No tasks")).toBeInTheDocument();
  });

  it("renders a description when provided", () => {
    render(<EmptyState title="Empty" description="Nothing here yet." />);
    expect(screen.getByText("Nothing here yet.")).toBeInTheDocument();
  });

  it("renders an icon when provided", () => {
    render(<EmptyState title="Empty" icon="🐣" />);
    expect(screen.getByText("🐣")).toBeInTheDocument();
  });

  it("renders children", () => {
    render(
      <EmptyState title="Empty">
        <button>Create one</button>
      </EmptyState>,
    );
    expect(screen.getByRole("button", { name: "Create one" })).toBeInTheDocument();
  });

  it("does not render icon element when icon is omitted", () => {
    render(<EmptyState title="Empty" />);
    // The aria-hidden span should not be present
    expect(document.querySelector("[aria-hidden]")).not.toBeInTheDocument();
  });
});

// ── FormInput ─────────────────────────────────────────────────────────────────

describe("FormInput", () => {
  it("renders an input with provided props", () => {
    render(<FormInput placeholder="Enter text" />);
    expect(screen.getByPlaceholderText("Enter text")).toBeInTheDocument();
  });

  it("forwards type prop", () => {
    render(<FormInput type="email" />);
    expect(screen.getByRole("textbox")).toHaveAttribute("type", "email");
  });

  it("merges className with base styles", () => {
    render(<FormInput className="extra" />);
    const input = screen.getByRole("textbox");
    expect(input.className).toContain("extra");
    expect(input.className).toContain("rounded");
  });
});

describe("FormTextarea", () => {
  it("renders a textarea", () => {
    render(<FormTextarea placeholder="Describe…" />);
    expect(screen.getByPlaceholderText("Describe…")).toBeInTheDocument();
  });
});

describe("FormSelect", () => {
  it("renders a select with options", () => {
    render(
      <FormSelect>
        <option value="a">Alpha</option>
        <option value="b">Beta</option>
      </FormSelect>,
    );
    expect(screen.getByRole("combobox")).toBeInTheDocument();
    expect(screen.getByText("Alpha")).toBeInTheDocument();
  });
});

// ── Modal ─────────────────────────────────────────────────────────────────────

describe("Modal", () => {
  it("renders children", () => {
    render(
      <Modal onClose={vi.fn()}>
        <p>Modal content</p>
      </Modal>,
    );
    expect(screen.getByText("Modal content")).toBeInTheDocument();
  });

  it("calls onClose when backdrop is clicked", async () => {
    const onClose = vi.fn();
    const { container } = render(
      <Modal onClose={onClose}>
        <div>Inner</div>
      </Modal>,
    );
    // Click the outer backdrop div (the first child of body)
    await userEvent.click(container.firstChild as Element);
    expect(onClose).toHaveBeenCalledOnce();
  });

  it("applies custom className", () => {
    const { container } = render(
      <Modal onClose={vi.fn()} className="z-50">
        <span>X</span>
      </Modal>,
    );
    expect((container.firstChild as Element).className).toContain("z-50");
  });
});
