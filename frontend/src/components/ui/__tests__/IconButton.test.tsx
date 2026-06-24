import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { IconButton } from "../IconButton";

// ── Focus ring ─────────────────────────────────────────────────────────────────

describe("IconButton — focus ring", () => {
  const variants = [
    "default",
    "accent",
    "accent-soft",
    "danger",
    "danger-hover",
  ] as const;

  it.each(variants)(
    "variant=%s has focus:outline-none focus-visible:ring-1 focus-visible:ring-accent",
    (variant) => {
      render(
        <IconButton variant={variant} aria-label={`${variant} button`}>
          ★
        </IconButton>,
      );
      const btn = screen.getByRole("button", { name: `${variant} button` });
      expect(btn.className).toContain("focus:outline-none");
      expect(btn.className).toContain("focus-visible:ring-1");
      expect(btn.className).toContain("focus-visible:ring-accent");
    },
  );

  it("default variant (no explicit variant prop) has focus ring", () => {
    render(<IconButton aria-label="default button">★</IconButton>);
    const btn = screen.getByRole("button", { name: "default button" });
    expect(btn.className).toContain("focus:outline-none");
    expect(btn.className).toContain("focus-visible:ring-1");
    expect(btn.className).toContain("focus-visible:ring-accent");
  });
});

// ── Sizes ──────────────────────────────────────────────────────────────────────

describe("IconButton — sizes", () => {
  it("sm size produces h-11 and w-11 (44 px)", () => {
    render(
      <IconButton size="sm" aria-label="small button">
        ★
      </IconButton>,
    );
    const btn = screen.getByRole("button", { name: "small button" });
    expect(btn.className).toContain("h-11");
    expect(btn.className).toContain("w-11");
  });

  it("md size produces h-11 and w-11 (44 px)", () => {
    render(
      <IconButton size="md" aria-label="medium button">
        ★
      </IconButton>,
    );
    const btn = screen.getByRole("button", { name: "medium button" });
    expect(btn.className).toContain("h-11");
    expect(btn.className).toContain("w-11");
  });

  it("default size (no explicit size prop) produces h-11 and w-11", () => {
    render(<IconButton aria-label="default size button">★</IconButton>);
    const btn = screen.getByRole("button", { name: "default size button" });
    expect(btn.className).toContain("h-11");
    expect(btn.className).toContain("w-11");
  });

  it("compact size produces h-8 and w-8 (32 px)", () => {
    render(
      <IconButton size="compact" aria-label="compact button">
        ★
      </IconButton>,
    );
    const btn = screen.getByRole("button", { name: "compact button" });
    expect(btn.className).toContain("h-8");
    expect(btn.className).toContain("w-8");
  });

  it("compact size does NOT produce h-11 or w-11", () => {
    render(
      <IconButton size="compact" aria-label="compact no-44 button">
        ★
      </IconButton>,
    );
    const btn = screen.getByRole("button", { name: "compact no-44 button" });
    expect(btn.className).not.toContain("h-11");
    expect(btn.className).not.toContain("w-11");
  });
});

// ── aria-label ─────────────────────────────────────────────────────────────────

describe("IconButton — aria-label", () => {
  it("applies aria-label to the button element", () => {
    render(<IconButton aria-label="Close dialog">✕</IconButton>);
    expect(
      screen.getByRole("button", { name: "Close dialog" }),
    ).toBeInTheDocument();
  });

  it("aria-label is accessible via getByRole name query", () => {
    render(
      <IconButton aria-label="Start agent" variant="accent">
        ▶
      </IconButton>,
    );
    const btn = screen.getByRole("button", { name: "Start agent" });
    expect(btn).toBeInTheDocument();
    expect(btn).toHaveAttribute("aria-label", "Start agent");
  });
});

// ── Disabled / loading ─────────────────────────────────────────────────────────

describe("IconButton — disabled and loading states", () => {
  it("is disabled when disabled prop is set", () => {
    render(
      <IconButton aria-label="disabled button" disabled>
        ★
      </IconButton>,
    );
    expect(screen.getByRole("button", { name: "disabled button" })).toBeDisabled();
  });

  it("is disabled when loading prop is set", () => {
    render(
      <IconButton aria-label="loading button" loading>
        ★
      </IconButton>,
    );
    expect(screen.getByRole("button", { name: "loading button" })).toBeDisabled();
  });

  it("renders loading indicator when loading=true", () => {
    render(
      <IconButton aria-label="loading indicator button" loading>
        ★
      </IconButton>,
    );
    const btn = screen.getByRole("button", { name: "loading indicator button" });
    expect(btn.textContent).toBe("…");
  });

  it("renders children when not loading", () => {
    render(<IconButton aria-label="children button">✕</IconButton>);
    const btn = screen.getByRole("button", { name: "children button" });
    expect(btn.textContent).toBe("✕");
  });
});

// ── Interaction ────────────────────────────────────────────────────────────────

describe("IconButton — click interaction", () => {
  it("calls onClick when clicked", async () => {
    const onClick = vi.fn();
    render(
      <IconButton aria-label="clickable" onClick={onClick}>
        ★
      </IconButton>,
    );
    await userEvent.click(screen.getByRole("button", { name: "clickable" }));
    expect(onClick).toHaveBeenCalledOnce();
  });

  it("does not call onClick when disabled", async () => {
    const onClick = vi.fn();
    render(
      <IconButton aria-label="not clickable" onClick={onClick} disabled>
        ★
      </IconButton>,
    );
    await userEvent.click(screen.getByRole("button", { name: "not clickable" }));
    expect(onClick).not.toHaveBeenCalled();
  });
});

// ── className merge ────────────────────────────────────────────────────────────

describe("IconButton — className merging", () => {
  it("merges extra className onto the button", () => {
    render(
      <IconButton aria-label="classed button" className="custom-class">
        ★
      </IconButton>,
    );
    expect(
      screen.getByRole("button", { name: "classed button" }).className,
    ).toContain("custom-class");
  });
});
