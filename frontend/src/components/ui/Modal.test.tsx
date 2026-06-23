import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Modal } from "./Modal";

// Helper: render a Modal with default props and optional overrides
function renderModal(
  props: Partial<React.ComponentProps<typeof Modal>> = {},
  children: React.ReactNode = <p>Modal content</p>,
) {
  const onClose = props.onClose ?? vi.fn();
  const result = render(
    <Modal onClose={onClose} {...props}>
      {children}
    </Modal>,
  );
  return { ...result, onClose };
}

// ── 1. Renders children ────────────────────────────────────────────────────────

describe("Modal — renders children", () => {
  it("renders children inside the modal", () => {
    renderModal({}, <p>Hello World</p>);
    expect(screen.getByText("Hello World")).toBeInTheDocument();
  });

  it("renders title when provided", () => {
    renderModal({ title: "My Dialog" });
    expect(screen.getByText("My Dialog")).toBeInTheDocument();
  });

  it("always renders an X close button", () => {
    renderModal();
    expect(screen.getByRole("button", { name: "Close" })).toBeInTheDocument();
  });
});

// ── 2. Scrim click — dismissable=true (default) ────────────────────────────────

describe("Modal — scrim click (dismissable=true)", () => {
  it("calls onClose when the scrim is clicked", async () => {
    const { onClose } = renderModal();
    await userEvent.click(screen.getByTestId("modal-scrim"));
    expect(onClose).toHaveBeenCalledOnce();
  });
});

// ── 3. Scrim click — dismissable=false ────────────────────────────────────────

describe("Modal — scrim click (dismissable=false)", () => {
  it("does NOT call onClose when scrim is clicked and dismissable=false", async () => {
    const { onClose } = renderModal({ dismissable: false });
    await userEvent.click(screen.getByTestId("modal-scrim"));
    expect(onClose).not.toHaveBeenCalled();
  });
});

// ── 4. Escape key — dismissable=true (default) ────────────────────────────────

describe("Modal — Escape key (dismissable=true)", () => {
  it("calls onClose when Escape is pressed and dismissable=true", () => {
    const { onClose } = renderModal();
    fireEvent.keyDown(document, { key: "Escape" });
    expect(onClose).toHaveBeenCalledOnce();
  });
});

// ── 5. Escape key — dismissable=false ─────────────────────────────────────────

describe("Modal — Escape key (dismissable=false)", () => {
  it("does NOT call onClose when Escape is pressed and dismissable=false", () => {
    const { onClose } = renderModal({ dismissable: false });
    fireEvent.keyDown(document, { key: "Escape" });
    expect(onClose).not.toHaveBeenCalled();
  });
});

// ── 6. X button always calls onClose ──────────────────────────────────────────

describe("Modal — X button", () => {
  it("always calls onClose even when dismissable=false", async () => {
    const { onClose } = renderModal({ dismissable: false });
    await userEvent.click(screen.getByRole("button", { name: "Close" }));
    expect(onClose).toHaveBeenCalledOnce();
  });

  it("calls onClose when dismissable=true (default)", async () => {
    const { onClose } = renderModal();
    await userEvent.click(screen.getByRole("button", { name: "Close" }));
    expect(onClose).toHaveBeenCalledOnce();
  });
});

// ── 7 & 8. Focus trap — Tab and Shift-Tab ────────────────────────────────────

describe("Modal — focus trap", () => {
  beforeEach(() => {
    // jsdom does not implement layout so tabIndex ordering is based on DOM order
  });

  it("Tab key cycles focus forward within the modal", async () => {
    const user = userEvent.setup();
    render(
      <Modal onClose={vi.fn()}>
        <input data-testid="input-1" />
        <button type="button">Button 1</button>
      </Modal>,
    );
    // The modal has a Close (X) button at position 0 in DOM order,
    // then input-1, then Button 1.
    // Focus the X button first (it receives focus on mount as the first focusable)
    const closeBtn = screen.getByRole("button", { name: "Close" });
    const btn1 = screen.getByRole("button", { name: "Button 1" });

    // Move focus to the last element then Tab should wrap to first
    btn1.focus();
    expect(document.activeElement).toBe(btn1);
    await user.tab();
    // After wrapping, focus should be on the first focusable (Close button)
    expect(document.activeElement).toBe(closeBtn);
  });

  it("Shift-Tab cycles focus backward within the modal", async () => {
    const user = userEvent.setup();
    render(
      <Modal onClose={vi.fn()}>
        <input data-testid="input-1" />
        <button type="button">Button 1</button>
      </Modal>,
    );
    const closeBtn = screen.getByRole("button", { name: "Close" });

    // Focus on the first element then Shift-Tab should wrap to last
    closeBtn.focus();
    expect(document.activeElement).toBe(closeBtn);
    await user.tab({ shift: true });
    // After wrapping backward, focus should be on the last focusable (Button 1)
    const btn1 = screen.getByRole("button", { name: "Button 1" });
    expect(document.activeElement).toBe(btn1);
  });
});

// ── 9. duration-slow class ────────────────────────────────────────────────────

describe("Modal — motion token class", () => {
  it("panel element has duration-slow class (280ms transition token)", () => {
    renderModal();
    const panel = screen.getByTestId("modal-panel");
    expect(panel.className).toContain("duration-slow");
  });
});
