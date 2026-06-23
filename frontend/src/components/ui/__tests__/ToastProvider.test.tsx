import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, act, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import React from "react";
import { ToastProvider } from "../ToastProvider";
import { useToast } from "../useToast";

// ── Helper: consumer component ────────────────────────────────────────────────

interface TriggerProps {
  message?: string;
  tone?: "success" | "warning" | "danger" | "info";
  duration?: number;
  actionLabel?: string;
  onAction?: () => void;
  /** If provided, the component will call dismiss(id) on click of this button. */
  dismissLabel?: string;
}

function ToastTrigger({
  message = "Test message",
  tone,
  duration,
  actionLabel,
  onAction,
  dismissLabel,
}: TriggerProps) {
  const { show, dismiss } = useToast();
  const [lastId, setLastId] = React.useState<string | null>(null);

  function handleShow() {
    const id = show(message, { tone, duration, actionLabel, onAction });
    setLastId(id);
  }

  function handleDismiss() {
    if (lastId) dismiss(lastId);
  }

  return (
    <div>
      <button type="button" onClick={handleShow}>
        Show toast
      </button>
      {dismissLabel && (
        <button type="button" onClick={handleDismiss}>
          {dismissLabel}
        </button>
      )}
      {lastId && <span data-testid="last-id">{lastId}</span>}
    </div>
  );
}

function renderWithProvider(ui: React.ReactNode) {
  return render(<ToastProvider>{ui}</ToastProvider>);
}

// ── Context value ─────────────────────────────────────────────────────────────

describe("ToastProvider — context value", () => {
  it("provides show and dismiss functions to children", () => {
    let capturedCtx: ReturnType<typeof useToast> | null = null;
    function Inspector() {
      capturedCtx = useToast();
      return null;
    }
    renderWithProvider(<Inspector />);
    expect(typeof capturedCtx!.show).toBe("function");
    expect(typeof capturedCtx!.dismiss).toBe("function");
  });
});

// ── Show toast ────────────────────────────────────────────────────────────────

describe("ToastProvider — show", () => {
  it("renders a toast message after show() is called", async () => {
    const user = userEvent.setup();
    renderWithProvider(<ToastTrigger message="Hello" />);
    await user.click(screen.getByRole("button", { name: "Show toast" }));
    expect(screen.getByText("Hello")).toBeInTheDocument();
  });

  it("show() returns a non-empty string id", async () => {
    const user = userEvent.setup();
    renderWithProvider(<ToastTrigger message="Check id" />);
    await user.click(screen.getByRole("button", { name: "Show toast" }));
    const idEl = screen.getByTestId("last-id");
    expect(idEl.textContent).toMatch(/^toast-\d+$/);
  });

  it("renders multiple toasts when show() is called multiple times", async () => {
    const user = userEvent.setup();
    renderWithProvider(
      <div>
        <ToastTrigger message="First" />
        <ToastTrigger message="Second" />
      </div>,
    );
    const buttons = screen.getAllByRole("button", { name: "Show toast" });
    await user.click(buttons[0]);
    await user.click(buttons[1]);
    expect(screen.getByText("First")).toBeInTheDocument();
    expect(screen.getByText("Second")).toBeInTheDocument();
  });

  it("renders with the correct tone when tone option is provided", async () => {
    const user = userEvent.setup();
    renderWithProvider(<ToastTrigger message="Warning!" tone="warning" />);
    await user.click(screen.getByRole("button", { name: "Show toast" }));
    const toastEls = screen
      .getAllByRole("status")
      .filter((el) => el.getAttribute("data-tone") === "warning");
    expect(toastEls.length).toBeGreaterThan(0);
  });
});

// ── Auto-dismiss ──────────────────────────────────────────────────────────────

describe("ToastProvider — auto-dismiss", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.runOnlyPendingTimers();
    vi.useRealTimers();
  });

  it("removes the toast after the default duration (4000 ms)", async () => {
    renderWithProvider(<ToastTrigger message="Auto gone" />);
    // Use fireEvent to avoid userEvent's internal setTimeout interaction with fake timers
    act(() => {
      fireEvent.click(screen.getByRole("button", { name: "Show toast" }));
    });
    expect(screen.getByText("Auto gone")).toBeInTheDocument();

    act(() => {
      vi.advanceTimersByTime(4000);
    });

    expect(screen.queryByText("Auto gone")).not.toBeInTheDocument();
  });

  it("removes the toast after a custom duration", async () => {
    renderWithProvider(<ToastTrigger message="Short" duration={1500} />);
    act(() => {
      fireEvent.click(screen.getByRole("button", { name: "Show toast" }));
    });
    expect(screen.getByText("Short")).toBeInTheDocument();

    act(() => {
      vi.advanceTimersByTime(1499);
    });
    expect(screen.getByText("Short")).toBeInTheDocument();

    act(() => {
      vi.advanceTimersByTime(1);
    });
    expect(screen.queryByText("Short")).not.toBeInTheDocument();
  });
});

// ── Manual dismiss ────────────────────────────────────────────────────────────

describe("ToastProvider — manual dismiss", () => {
  it("removes the toast when the dismiss button is clicked", async () => {
    const user = userEvent.setup();
    renderWithProvider(<ToastTrigger message="Bye" />);
    await user.click(screen.getByRole("button", { name: "Show toast" }));
    expect(screen.getByText("Bye")).toBeInTheDocument();

    await user.click(
      screen.getByRole("button", { name: "Dismiss notification" }),
    );
    expect(screen.queryByText("Bye")).not.toBeInTheDocument();
  });

  it("removes the toast when dismiss(id) is called programmatically", async () => {
    const user = userEvent.setup();
    renderWithProvider(
      <ToastTrigger message="Manual" dismissLabel="Dismiss it" />,
    );
    await user.click(screen.getByRole("button", { name: "Show toast" }));
    expect(screen.getByText("Manual")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Dismiss it" }));
    expect(screen.queryByText("Manual")).not.toBeInTheDocument();
  });
});

// ── aria-live region ──────────────────────────────────────────────────────────

describe("ToastProvider — aria-live region", () => {
  it("renders an aria-live=polite container", () => {
    renderWithProvider(<div />);
    const region = document.querySelector('[aria-live="polite"]');
    expect(region).toBeInTheDocument();
  });
});

// ── useToast outside provider (no-op safety) ──────────────────────────────────

describe("useToast outside ToastProvider", () => {
  it("returns no-op show function that does not throw", () => {
    let capturedFn: (() => string) | null = null;
    function Consumer() {
      const { show } = useToast();
      capturedFn = () => show("test");
      return null;
    }
    // Render WITHOUT ToastProvider
    render(<Consumer />);
    expect(() => capturedFn!()).not.toThrow();
  });

  it("returns no-op dismiss function that does not throw", () => {
    let capturedFn: ((id: string) => void) | null = null;
    function Consumer() {
      const { dismiss } = useToast();
      capturedFn = dismiss;
      return null;
    }
    render(<Consumer />);
    expect(() => capturedFn!("any-id")).not.toThrow();
  });
});

// ── Action button ─────────────────────────────────────────────────────────────

describe("ToastProvider — action button", () => {
  it("renders an action button with the provided label", async () => {
    const user = userEvent.setup();
    renderWithProvider(
      <ToastTrigger message="Action toast" actionLabel="Undo" />,
    );
    await user.click(screen.getByRole("button", { name: "Show toast" }));
    expect(screen.getByRole("button", { name: "Undo" })).toBeInTheDocument();
  });

  it("calls onAction callback when action button is clicked", async () => {
    const user = userEvent.setup();
    const onAction = vi.fn();
    renderWithProvider(
      <ToastTrigger message="Undo?" actionLabel="Undo" onAction={onAction} />,
    );
    await user.click(screen.getByRole("button", { name: "Show toast" }));
    await user.click(screen.getByRole("button", { name: "Undo" }));
    expect(onAction).toHaveBeenCalledOnce();
  });

  it("dismisses the toast after action button is clicked", async () => {
    const user = userEvent.setup();
    renderWithProvider(
      <ToastTrigger message="Gone after action" actionLabel="Do it" />,
    );
    await user.click(screen.getByRole("button", { name: "Show toast" }));
    expect(screen.getByText("Gone after action")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Do it" }));
    expect(screen.queryByText("Gone after action")).not.toBeInTheDocument();
  });
});
