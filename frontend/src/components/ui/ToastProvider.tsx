import React, { createContext, useCallback, useRef, useState } from "react";
import { Toast } from "./Toast";
import type { ToastTone } from "./Toast";

// ── Types ─────────────────────────────────────────────────────────────────────

export interface ToastOptions {
  /** Tone controls the colour/icon of the toast. Defaults to "info". */
  tone?: ToastTone;
  /** Auto-dismiss delay in milliseconds. Defaults to 4000 (4 s). */
  duration?: number;
  /** Optional action button label. */
  actionLabel?: string;
  /** Callback when the action button is clicked. */
  onAction?: () => void;
}

export interface ToastItem extends Required<Pick<ToastOptions, "tone" | "duration">> {
  id: string;
  message: string;
  actionLabel?: string;
  onAction?: () => void;
}

export interface ToastContextValue {
  /**
   * Display a toast message.
   * Returns the generated id so callers can dismiss it programmatically.
   */
  show: (message: string, options?: ToastOptions) => string;
  /** Dismiss a specific toast by id. */
  dismiss: (id: string) => void;
}

// ── Default context (no-op outside provider) ──────────────────────────────────

const noop = () => "";
const noopDismiss = () => {};

export const ToastContext = createContext<ToastContextValue>({
  show: noop,
  dismiss: noopDismiss,
});

// ── Provider ──────────────────────────────────────────────────────────────────

let _counter = 0;
function nextId() {
  return `toast-${++_counter}`;
}

interface Props {
  children: React.ReactNode;
}

export function ToastProvider({ children }: Props) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  // Map from toast id → timeout handle so we can cancel on manual dismiss
  const timers = useRef<Map<string, ReturnType<typeof setTimeout>>>(new Map());

  const dismiss = useCallback((id: string) => {
    // Cancel pending auto-dismiss timer if present
    const t = timers.current.get(id);
    if (t !== undefined) {
      clearTimeout(t);
      timers.current.delete(id);
    }
    setToasts((prev) => prev.filter((item) => item.id !== id));
  }, []);

  const show = useCallback(
    (message: string, options?: ToastOptions): string => {
      const id = nextId();
      const tone = options?.tone ?? "info";
      const duration = options?.duration ?? 4000;

      const item: ToastItem = {
        id,
        message,
        tone,
        duration,
        actionLabel: options?.actionLabel,
        onAction: options?.onAction,
      };

      setToasts((prev) => [...prev, item]);

      // Schedule auto-dismiss
      const timer = setTimeout(() => {
        dismiss(id);
      }, duration);
      timers.current.set(id, timer);

      return id;
    },
    [dismiss],
  );

  return (
    <ToastContext.Provider value={{ show, dismiss }}>
      {children}
      {/* Toast stack — rendered in a fixed portal-like container at bottom-right */}
      <div
        aria-live="polite"
        aria-atomic="false"
        className="fixed bottom-4 right-4 z-[70] flex flex-col gap-2 w-80 pointer-events-none"
        data-testid="toast-stack"
      >
        {toasts.map((item) => (
          <Toast
            key={item.id}
            id={item.id}
            message={item.message}
            tone={item.tone}
            actionLabel={item.actionLabel}
            onAction={item.onAction}
            onDismiss={dismiss}
          />
        ))}
      </div>
    </ToastContext.Provider>
  );
}
