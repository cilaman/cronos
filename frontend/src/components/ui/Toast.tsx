import { cn } from "../../utils/cn";

// ── Types ─────────────────────────────────────────────────────────────────────

export type ToastTone = "success" | "warning" | "danger" | "info";

interface Props {
  id: string;
  message: string;
  tone: ToastTone;
  /** Optional label for the action button. */
  actionLabel?: string;
  /** Called when the action button is clicked. */
  onAction?: () => void;
  /** Called when the dismiss button is clicked or the toast self-dismisses. */
  onDismiss: (id: string) => void;
}

// ── Tone styles ───────────────────────────────────────────────────────────────

const toneClasses: Record<ToastTone, string> = {
  success: "border-l-4 border-l-[var(--color-success,#22c55e)] bg-surface-1 text-ink",
  warning: "border-l-4 border-l-[var(--color-warning,#f59e0b)] bg-surface-1 text-ink",
  danger:  "border-l-4 border-l-danger bg-surface-1 text-ink",
  info:    "border-l-4 border-l-accent bg-surface-1 text-ink",
};

const toneIconLabel: Record<ToastTone, string> = {
  success: "✓",
  warning: "⚠",
  danger:  "✕",
  info:    "ℹ",
};

// ── Component ─────────────────────────────────────────────────────────────────

/**
 * Single toast message renderer.
 *
 * Does NOT manage its own dismiss timer — timer is owned by ToastProvider.
 * Dismissal is signalled upward via `onDismiss(id)`.
 *
 * Accessibility: rendered inside an `aria-live="polite"` region owned by
 * ToastProvider so screen readers announce new toasts without stealing focus.
 */
export function Toast({
  id,
  message,
  tone,
  actionLabel,
  onAction,
  onDismiss,
}: Props) {
  function handleDismiss() {
    onDismiss(id);
  }

  function handleAction() {
    onAction?.();
    onDismiss(id);
  }

  return (
    <div
      role="status"
      data-testid={`toast-${id}`}
      data-tone={tone}
      className={cn(
        "pointer-events-auto flex items-start gap-3 rounded shadow-lift px-4 py-3 text-sm",
        toneClasses[tone],
      )}
    >
      {/* Tone icon */}
      <span aria-hidden="true" className="mt-px shrink-0 font-bold">
        {toneIconLabel[tone]}
      </span>

      {/* Message */}
      <span className="flex-1">{message}</span>

      {/* Optional action button */}
      {actionLabel && (
        <button
          type="button"
          onClick={handleAction}
          className="shrink-0 font-medium underline hover:no-underline focus:outline-none focus-visible:ring-2 focus-visible:ring-accent"
        >
          {actionLabel}
        </button>
      )}

      {/* Dismiss button — does not steal focus on mount */}
      <button
        type="button"
        aria-label="Dismiss notification"
        onClick={handleDismiss}
        className="shrink-0 rounded p-0.5 text-ink-muted hover:bg-surface-2 hover:text-ink focus:outline-none focus-visible:ring-2 focus-visible:ring-accent"
      >
        <svg
          xmlns="http://www.w3.org/2000/svg"
          width="12"
          height="12"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden="true"
        >
          <line x1="18" y1="6" x2="6" y2="18" />
          <line x1="6" y1="6" x2="18" y2="18" />
        </svg>
      </button>
    </div>
  );
}
