import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Modal } from "../Modal";

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

// ── 7. Close button 44px hit-area wrapper ─────────────────────────────────────

describe("Modal — close button touch target (WCAG 2.5.5)", () => {
  it("close button is wrapped in a span with min-h-[44px] and min-w-[44px]", () => {
    renderModal();
    const closeBtn = screen.getByRole("button", { name: "Close" });
    const wrapper = closeBtn.parentElement;
    expect(wrapper?.tagName.toLowerCase()).toBe("span");
    expect(wrapper?.className).toContain("min-h-[44px]");
    expect(wrapper?.className).toContain("min-w-[44px]");
  });

  it("close button wrapper uses inline-grid place-content-center for centering", () => {
    renderModal();
    const closeBtn = screen.getByRole("button", { name: "Close" });
    const wrapper = closeBtn.parentElement;
    expect(wrapper?.className).toContain("inline-grid");
    expect(wrapper?.className).toContain("place-content-center");
  });

  it("close button SVG glyph preserves 16px dimensions (visual not inflated)", () => {
    renderModal();
    const closeBtn = screen.getByRole("button", { name: "Close" });
    const svg = closeBtn.querySelector("svg");
    expect(svg).not.toBeNull();
    expect(svg?.getAttribute("width")).toBe("16");
    expect(svg?.getAttribute("height")).toBe("16");
  });

  it("hideDefaultClose=true removes the close button and wrapper", () => {
    renderModal({ hideDefaultClose: true });
    expect(screen.queryByRole("button", { name: "Close" })).toBeNull();
  });
});

// ── 8. duration-slow class ────────────────────────────────────────────────────

describe("Modal — motion token class", () => {
  it("panel element has duration-slow class (280ms transition token)", () => {
    renderModal();
    const panel = screen.getByTestId("modal-panel");
    expect(panel.className).toContain("duration-slow");
  });
});

// ── 9. hideDefaultClose prop ─────────────────────────────────────────────────

describe("Modal — hideDefaultClose prop", () => {
  it("hides the X close button when hideDefaultClose=true", () => {
    renderModal({ hideDefaultClose: true });
    expect(screen.queryByRole("button", { name: "Close" })).toBeNull();
  });

  it("still renders the X close button when hideDefaultClose is not set (default)", () => {
    renderModal();
    expect(screen.getByRole("button", { name: "Close" })).toBeInTheDocument();
  });
});
