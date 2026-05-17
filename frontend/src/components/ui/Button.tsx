import { cn } from "../../utils/cn";

const variants = {
  primary:
    "border-accent bg-accent text-canvas hover:bg-accent-bright hover:shadow-accent-glow",
  secondary:
    "border-hairline-strong bg-surface-2 text-ink hover:bg-surface-3 hover:border-hairline",
  ghost: "border-transparent text-ink-muted hover:bg-surface-2 hover:text-ink",
  danger: "border-danger bg-danger text-ink hover:bg-danger/80",
};

const sizes = {
  sm: "px-3 py-1 text-xs",
  md: "px-4 py-2 text-sm",
};

interface Props extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: keyof typeof variants;
  size?: keyof typeof sizes;
  loading?: boolean;
}

export function Button({
  variant = "primary",
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
        "rounded border font-medium transition",
        "disabled:cursor-not-allowed disabled:border-hairline disabled:bg-surface-2 disabled:text-ink-faint disabled:shadow-none",
        variants[variant],
        sizes[size],
        className,
      )}
    >
      {children}
    </button>
  );
}
