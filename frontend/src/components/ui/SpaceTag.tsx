import { cn } from "../../utils/cn";

const DOT_SIZE = { xs: "h-1.5 w-1.5", sm: "h-2 w-2", md: "h-3 w-3" };
const ICON_SIZE = { xs: "text-[11px]", sm: "text-[13px]", md: "text-base" };
const TEXT_SIZE = { xs: "text-[10px]", sm: "text-[10px]", md: "text-[12px]" };

interface Props {
  color?: string | null;
  icon?: string | null;
  name?: string | null;
  size?: "xs" | "sm" | "md";
  className?: string;
}

export function SpaceTag({ color, icon, name, size = "sm", className }: Props) {
  const fallback = "rgb(var(--color-hairline-strong))";
  return (
    <span className={cn("flex items-center gap-1.5", className)}>
      <span
        aria-hidden
        className={cn("shrink-0 rounded-sm", DOT_SIZE[size])}
        style={{ backgroundColor: color ?? fallback }}
      />
      {icon && (
        <span aria-hidden className={cn("shrink-0 leading-none", ICON_SIZE[size])}>
          {icon}
        </span>
      )}
      {name && (
        <span
          className={cn(
            "truncate font-mono uppercase tracking-[0.14em] text-ink-muted",
            TEXT_SIZE[size],
          )}
        >
          {name}
        </span>
      )}
    </span>
  );
}
