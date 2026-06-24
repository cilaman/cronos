import { cn } from "../../utils/cn";

const variants = {
  default:
    "border-hairline-strong bg-canvas text-ink-muted hover:bg-surface-2 hover:text-ink",
  accent:
    "border-accent bg-accent text-canvas hover:bg-accent-bright hover:shadow-accent-glow",
  "accent-soft":
    "border-accent bg-accent/15 text-accent-bright hover:bg-accent/25",
  danger: "border-danger bg-danger text-ink hover:bg-danger/80",
  "danger-hover":
    "border-hairline-strong bg-canvas text-ink-muted hover:border-danger hover:bg-danger/15 hover:text-danger",
};

/**
 * Size guide:
 * - sm / md  → h-11 w-11 (44 px) — WCAG 2.5.5 minimum touch target (default)
 * - compact  → h-8  w-8  (32 px) — opt-in for dense toolbars; explicitly waives WCAG minimum
 */
const sizes = {
  sm: "h-11 w-11 text-xs",
  md: "h-11 w-11 text-sm",
  compact: "h-8 w-8 text-xs",
};

interface Props extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  "aria-label": string;
  variant?: keyof typeof variants;
  size?: keyof typeof sizes;
  loading?: boolean;
}

export function IconButton({
  variant = "default",
  size = "md",
  loading,
  disabled,
  children,
  className,
  ...props
}: Props) {
  return (
    <button
      {...props}
      disabled={disabled || loading}
      className={cn(
        "flex items-center justify-center rounded border transition",
        "focus:outline-none focus-visible:ring-1 focus-visible:ring-accent",
        "disabled:cursor-not-allowed disabled:opacity-50",
        variants[variant],
        sizes[size],
        className,
      )}
    >
      {loading ? "…" : children}
    </button>
  );
}
