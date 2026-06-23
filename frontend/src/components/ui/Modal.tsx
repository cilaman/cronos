import React, { useEffect, useRef } from "react";
import { cn } from "../../utils/cn";

interface Props {
  onClose: () => void;
  className?: string;
  children: React.ReactNode;
  dismissable?: boolean;
  title?: string;
  /** When true, Modal does not render its own X close button.
   * Use this when the consumer provides its own close control
   * (e.g. MarkdownEditorModal's own aria-label="Close editor" button). */
  hideDefaultClose?: boolean;
}

const FOCUSABLE =
  'a[href], button:not([disabled]), [tabindex]:not([tabindex="-1"]), input:not([disabled]), select:not([disabled]), textarea:not([disabled])';

export function Modal({
  onClose,
  className,
  children,
  dismissable = true,
  title,
  hideDefaultClose = false,
}: Props) {
  const panelRef = useRef<HTMLDivElement>(null);

  // Keep stable refs so the effect never has to re-run when callbacks change.
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;
  const dismissableRef = useRef(dismissable);
  dismissableRef.current = dismissable;

  // Focus trap — registered once on mount, cleaned up on unmount.
  useEffect(() => {
    const previouslyFocused = document.activeElement as HTMLElement | null;

    // Move focus into the panel on mount
    const panel = panelRef.current;
    if (panel) {
      const focusable = Array.from(
        panel.querySelectorAll<HTMLElement>(FOCUSABLE),
      );
      if (focusable.length > 0) {
        focusable[0].focus();
      }
    }

    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") {
        if (dismissableRef.current) {
          onCloseRef.current();
        }
        return;
      }

      if (e.key === "Tab" && panel) {
        const focusable = Array.from(
          panel.querySelectorAll<HTMLElement>(FOCUSABLE),
        );
        if (focusable.length === 0) return;

        const first = focusable[0];
        const last = focusable[focusable.length - 1];

        if (e.shiftKey) {
          // Shift-Tab: if focus is on first, wrap to last
          if (document.activeElement === first) {
            e.preventDefault();
            last.focus();
          }
        } else {
          // Tab: if focus is on last, wrap to first
          if (document.activeElement === last) {
            e.preventDefault();
            first.focus();
          }
        }
      }
    }

    document.addEventListener("keydown", handleKeyDown);

    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      // Return focus to the element that was focused before opening
      if (previouslyFocused && typeof previouslyFocused.focus === "function") {
        previouslyFocused.focus();
      }
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function handleScrimClick() {
    if (!dismissable) return;
    onClose();
  }

  function handlePanelClick(e: React.MouseEvent) {
    e.stopPropagation();
  }

  return (
    <div
      className={cn(
        "fixed inset-0 z-[30] flex items-center justify-center bg-black/60 backdrop-blur-sm",
        className,
      )}
      onClick={handleScrimClick}
      data-testid="modal-scrim"
    >
      <div
        ref={panelRef}
        className="relative z-[40] w-full max-w-lg rounded-lg bg-surface-1 shadow-lift transition-all duration-slow scale-100 opacity-100"
        onClick={handlePanelClick}
        data-testid="modal-panel"
      >
        {/* Panel header: title (optional) + X close button */}
        <div className="flex items-center justify-between px-4 pt-4">
          {title ? (
            <h2 className="text-base font-semibold text-ink">{title}</h2>
          ) : (
            <span />
          )}
          {!hideDefaultClose && (
            <button
              type="button"
              aria-label="Close"
              onClick={onClose}
              className="ml-auto flex items-center justify-center rounded p-1 text-ink-muted hover:bg-surface-2 hover:text-ink focus:outline-none focus-visible:ring-2 focus-visible:ring-accent"
            >
              <svg
                xmlns="http://www.w3.org/2000/svg"
                width="16"
                height="16"
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
          )}
        </div>

        {/* Panel body */}
        <div>{children}</div>
      </div>
    </div>
  );
}
