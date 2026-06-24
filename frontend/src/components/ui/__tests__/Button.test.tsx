import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { Button } from "../Button";

// ── Variant focus rings ───────────────────────────────────────────────────────

describe("Button focus ring", () => {
  const variants = [
    "primary",
    "secondary",
    "ghost",
    "danger",
    "tertiary",
    "link",
  ] as const;

  for (const variant of variants) {
    it(`${variant} variant contains the focus-visible ring recipe`, () => {
      render(<Button variant={variant}>Test</Button>);
      const btn = screen.getByRole("button");
      expect(btn.className).toContain("focus:outline-none");
      expect(btn.className).toContain("focus-visible:ring-1");
      expect(btn.className).toContain("focus-visible:ring-accent");
    });
  }
});

// ── New variants ──────────────────────────────────────────────────────────────

describe("Button tertiary variant", () => {
  it("applies border-hairline class", () => {
    render(<Button variant="tertiary">Tertiary</Button>);
    expect(screen.getByRole("button").className).toContain("border-hairline");
  });

  it("applies text-ink-muted class", () => {
    render(<Button variant="tertiary">Tertiary</Button>);
    expect(screen.getByRole("button").className).toContain("text-ink-muted");
  });
});

describe("Button link variant", () => {
  it("applies text-accent class", () => {
    render(<Button variant="link">Link</Button>);
    expect(screen.getByRole("button").className).toContain("text-accent");
  });

  it("applies border-transparent class", () => {
    render(<Button variant="link">Link</Button>);
    expect(screen.getByRole("button").className).toContain("border-transparent");
  });
});

// ── md size ≥ 44px ────────────────────────────────────────────────────────────

describe("Button md size", () => {
  it("applies min-h-[44px] for md size", () => {
    render(<Button size="md">Medium</Button>);
    expect(screen.getByRole("button").className).toContain("min-h-[44px]");
  });
});

// ── Archetype prop ────────────────────────────────────────────────────────────

describe("Button archetype prop", () => {
  it("toolbar-chip applies focus ring + rounded-full", () => {
    render(<Button archetype="toolbar-chip">Chip</Button>);
    const btn = screen.getByRole("button");
    expect(btn.className).toContain("focus:outline-none");
    expect(btn.className).toContain("focus-visible:ring-1");
    expect(btn.className).toContain("focus-visible:ring-accent");
    expect(btn.className).toContain("rounded-full");
  });

  it("dropdown-trigger applies focus ring", () => {
    render(<Button archetype="dropdown-trigger">Dropdown</Button>);
    const btn = screen.getByRole("button");
    expect(btn.className).toContain("focus:outline-none");
    expect(btn.className).toContain("focus-visible:ring-1");
    expect(btn.className).toContain("focus-visible:ring-accent");
    expect(btn.className).toContain("justify-between");
  });

  it("segmented applies focus ring + rounded-none", () => {
    render(<Button archetype="segmented">Seg</Button>);
    const btn = screen.getByRole("button");
    expect(btn.className).toContain("focus:outline-none");
    expect(btn.className).toContain("focus-visible:ring-1");
    expect(btn.className).toContain("focus-visible:ring-accent");
    expect(btn.className).toContain("rounded-none");
  });

  it("list-row applies focus ring + w-full + justify-start", () => {
    render(<Button archetype="list-row">Row</Button>);
    const btn = screen.getByRole("button");
    expect(btn.className).toContain("focus:outline-none");
    expect(btn.className).toContain("focus-visible:ring-1");
    expect(btn.className).toContain("focus-visible:ring-accent");
    expect(btn.className).toContain("w-full");
    expect(btn.className).toContain("justify-start");
  });
});

// ── Loading prop ──────────────────────────────────────────────────────────────

describe("Button loading prop", () => {
  it("renders a spinner element when loading", () => {
    render(<Button loading>Saving</Button>);
    expect(screen.getByTestId("button-spinner")).toBeInTheDocument();
  });

  it("sets the button as disabled when loading", () => {
    render(<Button loading>Saving</Button>);
    expect(screen.getByRole("button")).toBeDisabled();
  });

  it("does not render spinner when not loading", () => {
    render(<Button>Normal</Button>);
    expect(screen.queryByTestId("button-spinner")).not.toBeInTheDocument();
  });
});

// ── leadingIcon prop ──────────────────────────────────────────────────────────

describe("Button leadingIcon prop", () => {
  it("renders the leading icon before children", () => {
    render(
      <Button leadingIcon={<svg data-testid="icon" />}>Label</Button>
    );
    const icon = screen.getByTestId("icon");
    const label = screen.getByText("Label");
    // icon should appear before the label in the DOM
    expect(icon).toBeInTheDocument();
    expect(label).toBeInTheDocument();
    // The icon's parent should be a sibling before the text node
    const btn = screen.getByRole("button");
    const children = Array.from(btn.childNodes);
    const iconWrapperIdx = children.findIndex(
      (n) => n instanceof Element && (n as Element).contains(icon)
    );
    const labelIdx = children.findIndex(
      (n) => n.textContent === "Label"
    );
    expect(iconWrapperIdx).toBeLessThan(labelIdx);
  });

  it("does not render leading icon wrapper when leadingIcon is omitted", () => {
    render(<Button>Label</Button>);
    expect(document.querySelector(".leading-icon")).not.toBeInTheDocument();
  });

  it("does not render leading icon when loading (spinner takes priority)", () => {
    render(
      <Button loading leadingIcon={<svg data-testid="icon" />}>
        Label
      </Button>
    );
    expect(screen.queryByTestId("icon")).not.toBeInTheDocument();
    expect(screen.getByTestId("button-spinner")).toBeInTheDocument();
  });
});

// ── Backward compatibility ────────────────────────────────────────────────────

describe("Button backward compatibility", () => {
  it("renders children text", () => {
    render(<Button>Click me</Button>);
    expect(screen.getByRole("button", { name: /click me/i })).toBeInTheDocument();
  });

  it("applies secondary variant classes", () => {
    render(<Button variant="secondary">Secondary</Button>);
    expect(screen.getByRole("button").className).toContain("bg-surface-2");
  });

  it("applies ghost variant classes", () => {
    render(<Button variant="ghost">Ghost</Button>);
    expect(screen.getByRole("button").className).toContain("border-transparent");
  });

  it("applies danger variant classes", () => {
    render(<Button variant="danger">Delete</Button>);
    expect(screen.getByRole("button").className).toContain("bg-danger");
  });

  it("applies sm size classes", () => {
    render(<Button size="sm">Small</Button>);
    expect(screen.getByRole("button").className).toContain("text-xs");
  });

  it("merges extra className", () => {
    render(<Button className="custom-class">X</Button>);
    expect(screen.getByRole("button").className).toContain("custom-class");
  });

  it("is disabled when disabled prop is set", () => {
    render(<Button disabled>Nope</Button>);
    expect(screen.getByRole("button")).toBeDisabled();
  });
});
