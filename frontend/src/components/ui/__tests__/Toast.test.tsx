import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Toast } from "../Toast";

// ── Helpers ───────────────────────────────────────────────────────────────────

function renderToast(overrides: Partial<Parameters<typeof Toast>[0]> = {}) {
  const defaults = {
    id: "t1",
    message: "Hello world",
    tone: "info" as const,
    onDismiss: vi.fn(),
  };
  const props = { ...defaults, ...overrides };
  return { ...render(<Toast {...props} />), props };
}

// ── Rendering ─────────────────────────────────────────────────────────────────

describe("Toast rendering", () => {
  it("renders the message text", () => {
    renderToast({ message: "Something happened" });
    expect(screen.getByText("Something happened")).toBeInTheDocument();
  });

  it("renders a dismiss button with accessible label", () => {
    renderToast();
    expect(
      screen.getByRole("button", { name: "Dismiss notification" }),
    ).toBeInTheDocument();
  });

  it("has role=status for screen reader announcement", () => {
    renderToast();
    expect(screen.getByRole("status")).toBeInTheDocument();
  });

  it("sets data-tone attribute to the tone value", () => {
    renderToast({ tone: "danger" });
    const el = screen.getByRole("status");
    expect(el).toHaveAttribute("data-tone", "danger");
  });
});

// ── Tone variants ──────────────────────────────────────────────────────────────

describe("Toast tone variants", () => {
  const tones = ["success", "warning", "danger", "info"] as const;

  for (const tone of tones) {
    it(`renders ${tone} tone without throwing`, () => {
      renderToast({ tone });
      expect(screen.getByRole("status")).toBeInTheDocument();
    });

    it(`applies border-l-4 class for ${tone} tone`, () => {
      renderToast({ tone });
      expect(screen.getByRole("status").className).toContain("border-l-4");
    });
  }
});

// ── Dismiss ───────────────────────────────────────────────────────────────────

describe("Toast dismiss", () => {
  it("calls onDismiss with the toast id when dismiss button clicked", async () => {
    const onDismiss = vi.fn();
    renderToast({ id: "abc", onDismiss });
    await userEvent.click(
      screen.getByRole("button", { name: "Dismiss notification" }),
    );
    expect(onDismiss).toHaveBeenCalledOnce();
    expect(onDismiss).toHaveBeenCalledWith("abc");
  });
});

// ── Action button ─────────────────────────────────────────────────────────────

describe("Toast action button", () => {
  it("renders action button when actionLabel is provided", () => {
    renderToast({ actionLabel: "Undo" });
    expect(screen.getByRole("button", { name: "Undo" })).toBeInTheDocument();
  });

  it("does not render action button when actionLabel is absent", () => {
    renderToast({ actionLabel: undefined });
    // Only the dismiss button should be present
    expect(screen.getAllByRole("button")).toHaveLength(1);
  });

  it("calls onAction and then onDismiss when action button is clicked", async () => {
    const onAction = vi.fn();
    const onDismiss = vi.fn();
    renderToast({ id: "xyz", actionLabel: "Retry", onAction, onDismiss });
    await userEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(onAction).toHaveBeenCalledOnce();
    expect(onDismiss).toHaveBeenCalledWith("xyz");
  });

  it("calls onDismiss even if onAction is not provided", async () => {
    const onDismiss = vi.fn();
    renderToast({ id: "def", actionLabel: "View", onAction: undefined, onDismiss });
    await userEvent.click(screen.getByRole("button", { name: "View" }));
    expect(onDismiss).toHaveBeenCalledWith("def");
  });
});

// ── No focus steal ────────────────────────────────────────────────────────────

describe("Toast accessibility — no focus steal", () => {
  it("does not move focus to the toast on render", () => {
    // Render an input first so there is a focused element
    const { container } = render(
      <div>
        <input data-testid="other-input" autoFocus />
        <Toast id="t1" message="Notice" tone="info" onDismiss={vi.fn()} />
      </div>,
    );
    // The active element should still be the input, not any toast button
    const input = container.querySelector("input");
    expect(document.activeElement).toBe(input);
  });
});
