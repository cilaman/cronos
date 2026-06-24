import React, { useRef, useEffect, useCallback } from "react";
import { cn } from "../../utils/cn";

export interface DropdownItem {
  value: string;
  label: string;
  disabled?: boolean;
}

interface DropdownProps {
  /** The trigger element rendered as the dropdown anchor */
  trigger: React.ReactNode;
  items: DropdownItem[];
  onSelect: (value: string) => void;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  className?: string;
  /** Alignment of the dropdown panel relative to the trigger */
  align?: "left" | "right";
}

/**
 * Keyboard-managed trigger + items dropdown.
 * Extracted from the ViewPicker inline pattern.
 * z-[20] matches the design system z-index ladder (docs/ui-ux-review/02-design-system.md §2.5).
 * ESC closes the dropdown; outside-click closes the dropdown.
 */
export function Dropdown({
  trigger,
  items,
  onSelect,
  open,
  onOpenChange,
  className,
  align = "left",
}: DropdownProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  const close = useCallback(() => onOpenChange(false), [onOpenChange]);

  // Close on outside click
  useEffect(() => {
    if (!open) return;
    function handleClickOutside(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        close();
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [open, close]);

  // Close on ESC
  useEffect(() => {
    if (!open) return;
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") {
        close();
      }
    }
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [open, close]);

  return (
    <div ref={containerRef} className={cn("relative inline-block", className)}>
      {/* Trigger wrapper — passes click through to the rendered trigger */}
      <div
        onClick={() => onOpenChange(!open)}
        style={{ display: "contents" }}
      >
        {trigger}
      </div>

      {open && (
        <ul
          role="menu"
          className={cn(
            "absolute top-full mt-1 min-w-[8rem] rounded border border-hairline bg-surface-2 py-1 shadow-md",
            // z-[20]: design system z-index ladder §2.5 — dropdown layer
            "z-[20]",
            align === "right" ? "right-0" : "left-0",
          )}
        >
          {items.map((item) => (
            <li key={item.value} role="none">
              <button
                role="menuitem"
                disabled={item.disabled}
                onClick={() => {
                  if (!item.disabled) {
                    onSelect(item.value);
                    close();
                  }
                }}
                className={cn(
                  "w-full px-3 py-1.5 text-left text-xs transition-colors",
                  item.disabled
                    ? "cursor-not-allowed text-ink-faint"
                    : "text-ink hover:bg-surface-3",
                )}
              >
                {item.label}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
