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

// ── Sizes — visual button dimensions ──────────────────────────────────────────

describe("IconButton — inner visual button dimensions", () => {
  it("sm size produces h-7 and w-7 on the inner button (28 px visual)", () => {
    render(
      <IconButton size="sm" aria-label="small button">
        ★
      </IconButton>,
    );
    const btn = screen.getByRole("button", { name: "small button" });
    expect(btn.className).toContain("h-7");
    expect(btn.className).toContain("w-7");
  });

  it("md size produces h-8 and w-8 on the inner button (32 px visual)", () => {
    render(
      <IconButton size="md" aria-label="medium button">
        ★
      </IconButton>,
    );
    const btn = screen.getByRole("button", { name: "medium button" });
    expect(btn.className).toContain("h-8");
    expect(btn.className).toContain("w-8");
  });

  it("default size (no explicit size prop) uses md — h-8 and w-8", () => {
    render(<IconButton aria-label="default size button">★</IconButton>);
    const btn = screen.getByRole("button", { name: "default size button" });
    expect(btn.className).toContain("h-8");
    expect(btn.className).toContain("w-8");
  });

  it("compact size produces h-8 and w-8 on the button (32 px visual)", () => {
    render(
      <IconButton size="compact" aria-label="compact button">
        ★
      </IconButton>,
    );
    const btn = screen.getByRole("button", { name: "compact button" });
    expect(btn.className).toContain("h-8");
    expect(btn.className).toContain("w-8");
  });

  it("sm size does NOT produce h-11 or w-11 on the inner button", () => {
    render(
      <IconButton size="sm" aria-label="sm no-44-inner button">
        ★
      </IconButton>,
    );
    const btn = screen.getByRole("button", { name: "sm no-44-inner button" });
    expect(btn.className).not.toContain("h-11");
    expect(btn.className).not.toContain("w-11");
  });

  it("md size does NOT produce h-11 or w-11 on the inner button", () => {
    render(
      <IconButton size="md" aria-label="md no-44-inner button">
        ★
      </IconButton>,
    );
    const btn = screen.getByRole("button", { name: "md no-44-inner button" });
    expect(btn.className).not.toContain("h-11");
    expect(btn.className).not.toContain("w-11");
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

// ── Sizes — outer hit-area wrapper ────────────────────────────────────────────

describe("IconButton — outer 44px hit-area wrapper", () => {
  it("sm size is wrapped in a span with min-h-[44px] and min-w-[44px]", () => {
    render(
      <IconButton size="sm" aria-label="sm wrapped">
        ★
      </IconButton>,
    );
    const btn = screen.getByRole("button", { name: "sm wrapped" });
    const wrapper = btn.parentElement;
    expect(wrapper?.tagName.toLowerCase()).toBe("span");
    expect(wrapper?.className).toContain("min-h-[44px]");
    expect(wrapper?.className).toContain("min-w-[44px]");
  });

  it("md size is wrapped in a span with min-h-[44px] and min-w-[44px]", () => {
    render(
      <IconButton size="md" aria-label="md wrapped">
        ★
      </IconButton>,
    );
    const btn = screen.getByRole("button", { name: "md wrapped" });
    const wrapper = btn.parentElement;
    expect(wrapper?.tagName.toLowerCase()).toBe("span");
    expect(wrapper?.className).toContain("min-h-[44px]");
    expect(wrapper?.className).toContain("min-w-[44px]");
  });

  it("default size (no explicit size prop) is wrapped with 44px hit area", () => {
    render(<IconButton aria-label="default wrapped">★</IconButton>);
    const btn = screen.getByRole("button", { name: "default wrapped" });
    const wrapper = btn.parentElement;
    expect(wrapper?.tagName.toLowerCase()).toBe("span");
    expect(wrapper?.className).toContain("min-h-[44px]");
    expect(wrapper?.className).toContain("min-w-[44px]");
  });

  it("compact size is NOT wrapped — button's parent is not a min-h-[44px] span", () => {
    render(
      <IconButton size="compact" aria-label="compact no-wrap">
        ★
      </IconButton>,
    );
    const btn = screen.getByRole("button", { name: "compact no-wrap" });
    // compact renders the button directly — parent is the testing container div, NOT a wrapper span
    expect(btn.parentElement?.tagName.toLowerCase()).not.toBe("span");
    // And the parent should not have the 44px classes
    expect(btn.parentElement?.className ?? "").not.toContain("min-h-[44px]");
    expect(btn.parentElement?.className ?? "").not.toContain("min-w-[44px]");
  });

  it("sm wrapper uses inline-grid and place-content-center for centering", () => {
    render(
      <IconButton size="sm" aria-label="sm grid">
        ★
      </IconButton>,
    );
    const btn = screen.getByRole("button", { name: "sm grid" });
    const wrapper = btn.parentElement;
    expect(wrapper?.className).toContain("inline-grid");
    expect(wrapper?.className).toContain("place-content-center");
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
