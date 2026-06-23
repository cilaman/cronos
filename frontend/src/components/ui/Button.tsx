import { cn } from "../../utils/cn";

const variants = {
  primary:
    "border-accent bg-accent text-canvas hover:bg-accent-bright hover:shadow-accent-glow",
  secondary:
    "border-hairline-strong bg-surface-2 text-ink hover:bg-surface-3 hover:border-hairline",
  ghost: "border-transparent text-ink-muted hover:bg-surface-2 hover:text-ink",
  danger: "border-danger bg-danger text-ink hover:bg-danger/80",
  tertiary:
    "border-hairline text-ink-muted hover:bg-surface-2 hover:text-ink hover:border-hairline-strong",
  link: "border-transparent text-accent hover:text-accent-bright hover:underline",
};

const sizes = {
  sm: "px-3 py-1 text-xs",
  md: "min-h-[44px] px-4 py-2 text-sm",
};

const archetypes: Record<string, string> = {
  "toolbar-chip":
    "rounded-full px-3 py-1 text-xs font-medium border border-hairline",
  "dropdown-trigger": "rounded justify-between gap-2",
  segmented: "rounded-none first:rounded-l last:rounded-r border-r-0 last:border-r",
  "list-row":
    "rounded-none w-full justify-start text-left px-3 py-2 border-0 border-b border-hairline last:border-b-0",
};

/** Focus ring applied to every variant unconditionally */
const FOCUS_RING = "focus:outline-none focus-visible:ring-1 focus-visible:ring-accent";

export type ButtonVariant = keyof typeof variants;
export type ButtonSize = keyof typeof sizes;
export type ButtonArchetype = keyof typeof archetypes;

interface Props extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  loading?: boolean;
  leadingIcon?: React.ReactNode;
  archetype?: ButtonArchetype;
}

export function Button({
  variant = "primary",
  size = "md",
  loading,
  disabled,
  children,
  className,
  leadingIcon,
  archetype,
  ...props
}: Props) {
  return (
    <button
      {...props}
      disabled={disabled || loading}
      className={cn(
        "inline-flex items-center justify-center gap-1.5 rounded border font-medium transition",
        FOCUS_RING,
        "disabled:cursor-not-allowed disabled:border-hairline disabled:bg-surface-2 disabled:text-ink-faint disabled:shadow-none",
        variants[variant],
        sizes[size],
        archetype && archetypes[archetype],
        className,
      )}
    >
      {loading && (
        <span
          aria-hidden="true"
          className="spinner h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent"
          data-testid="button-spinner"
        />
      )}
      {!loading && leadingIcon && (
        <span className="leading-icon" aria-hidden="true">
          {leadingIcon}
        </span>
      )}
      {children}
    </button>
  );
}
