import React, { useState, useId } from "react";
import { cn } from "../../utils/cn";

interface TooltipProps {
  content: React.ReactNode;
  children: React.ReactElement;
  /** Placement of the tooltip relative to the child element */
  placement?: "top" | "bottom" | "left" | "right";
  className?: string;
}

/**
 * Keyboard-reachable tooltip primitive.
 * Shows on focus (keyboard) and hover (mouse).
 * z-[60]: design system z-index ladder §2.5 — tooltip layer (above modals at z-40, dropdowns at z-[20]).
 */
export function Tooltip({
  content,
  children,
  placement = "top",
  className,
}: TooltipProps) {
  const [visible, setVisible] = useState(false);
  const tooltipId = useId();

  const placementClasses: Record<NonNullable<TooltipProps["placement"]>, string> = {
    top: "bottom-full left-1/2 mb-1.5 -translate-x-1/2",
    bottom: "top-full left-1/2 mt-1.5 -translate-x-1/2",
    left: "right-full top-1/2 mr-1.5 -translate-y-1/2",
    right: "left-full top-1/2 ml-1.5 -translate-y-1/2",
  };

  // Clone the child to inject accessibility + event props
  const child = React.cloneElement(children, {
    "aria-describedby": visible ? tooltipId : undefined,
    onMouseEnter: (e: React.MouseEvent) => {
      setVisible(true);
      children.props.onMouseEnter?.(e);
    },
    onMouseLeave: (e: React.MouseEvent) => {
      setVisible(false);
      children.props.onMouseLeave?.(e);
    },
    onFocus: (e: React.FocusEvent) => {
      setVisible(true);
      children.props.onFocus?.(e);
    },
    onBlur: (e: React.FocusEvent) => {
      setVisible(false);
      children.props.onBlur?.(e);
    },
  });

  return (
    <span className={cn("relative inline-flex", className)}>
      {child}
      {visible && (
        <span
          id={tooltipId}
          role="tooltip"
          className={cn(
            // z-[60]: design system z-index ladder §2.5 — tooltip layer
            "pointer-events-none absolute z-[60] whitespace-nowrap rounded bg-ink px-2 py-1 text-[10px] text-canvas shadow",
            placementClasses[placement],
          )}
        >
          {content}
        </span>
      )}
    </span>
  );
}
