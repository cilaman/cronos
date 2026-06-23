import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { EmptyState } from "../EmptyState";

// ---------------------------------------------------------------------------
// Basic rendering
// ---------------------------------------------------------------------------

describe("EmptyState — basic rendering", () => {
  it("renders the title text", () => {
    render(<EmptyState title="No items found" />);
    expect(screen.getByText("No items found")).toBeInTheDocument();
  });

  it("does not render description when omitted", () => {
    render(<EmptyState title="No items found" />);
    // There should be exactly the title paragraph; no second p element with text.
    expect(screen.queryByText("description text")).not.toBeInTheDocument();
  });

  it("renders description when provided", () => {
    render(<EmptyState title="No items" description="Try creating one first." />);
    expect(screen.getByText("Try creating one first.")).toBeInTheDocument();
  });

  it("renders icon when provided", () => {
    render(<EmptyState title="No items" icon={<span data-testid="icon">🌀</span>} />);
    expect(screen.getByTestId("icon")).toBeInTheDocument();
  });

  it("does not render an icon wrapper when icon is omitted", () => {
    const { container } = render(<EmptyState title="No items" />);
    // The icon span carries aria-hidden="true"; if it doesn't render there should be none.
    const hiddenSpans = container.querySelectorAll('[aria-hidden="true"]');
    expect(hiddenSpans).toHaveLength(0);
  });
});

// ---------------------------------------------------------------------------
// action prop
// ---------------------------------------------------------------------------

describe("EmptyState — action prop", () => {
  it("does not render an action button when action is not provided", () => {
    render(<EmptyState title="No items" />);
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });

  it("renders an action button when action prop is provided", () => {
    render(
      <EmptyState
        title="No items"
        action={{ label: "Create one", onClick: vi.fn() }}
      />,
    );
    expect(screen.getByRole("button", { name: "Create one" })).toBeInTheDocument();
  });

  it("calls onClick when action button is clicked", async () => {
    const handleClick = vi.fn();
    render(
      <EmptyState
        title="No items"
        action={{ label: "Create one", onClick: handleClick }}
      />,
    );
    await userEvent.click(screen.getByRole("button", { name: "Create one" }));
    expect(handleClick).toHaveBeenCalledTimes(1);
  });

  it("action button has type='button' to prevent accidental form submit", () => {
    render(
      <EmptyState
        title="No items"
        action={{ label: "Do it", onClick: vi.fn() }}
      />,
    );
    const btn = screen.getByRole("button", { name: "Do it" });
    expect(btn).toHaveAttribute("type", "button");
  });

  it("renders both action button and children when both are provided", () => {
    render(
      <EmptyState
        title="No items"
        action={{ label: "Primary", onClick: vi.fn() }}
      >
        <span data-testid="custom-child">Extra</span>
      </EmptyState>,
    );
    expect(screen.getByRole("button", { name: "Primary" })).toBeInTheDocument();
    expect(screen.getByTestId("custom-child")).toBeInTheDocument();
  });

  it("renders children even when action is not provided (backward compat)", () => {
    render(
      <EmptyState title="No items">
        <button type="button">Custom CTA</button>
      </EmptyState>,
    );
    expect(screen.getByRole("button", { name: "Custom CTA" })).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Accessibility
// ---------------------------------------------------------------------------

describe("EmptyState — accessibility", () => {
  it("icon span carries aria-hidden to hide it from assistive technology", () => {
    const { container } = render(
      <EmptyState title="No items" icon={<span>🌀</span>} />,
    );
    const iconWrapper = container.querySelector('[aria-hidden="true"]');
    expect(iconWrapper).toBeInTheDocument();
  });

  it("action button label is accessible as its text content", () => {
    render(
      <EmptyState
        title="No items"
        action={{ label: "Add something", onClick: vi.fn() }}
      />,
    );
    // getByRole("button", { name: ... }) asserts accessible name via text content
    expect(screen.getByRole("button", { name: "Add something" })).toBeInTheDocument();
  });
});
