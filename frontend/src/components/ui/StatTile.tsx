import { cn } from "../../utils/cn";

type Tone = "neutral" | "success" | "warning" | "danger" | "info";

interface StatTileProps {
  label: string;
  value: React.ReactNode;
  delta?: string | number;
  /** Semantic tone; affects delta colour. Default: neutral */
  tone?: Tone;
  className?: string;
}

const DELTA_TONE_CLASSES: Record<Tone, string> = {
  neutral: "text-ink-muted",
  success: "text-success",
  warning: "text-warning",
  danger: "text-danger",
  info: "text-info",
};

/**
 * Label / value / optional delta tile.
 * Extracted from the DashboardPage inline stat blocks.
 * Use I6 (DashboardPage/StatsPage migration) to swap in this component at call sites.
 */
export function StatTile({
  label,
  value,
  delta,
  tone = "neutral",
  className,
}: StatTileProps) {
  const deltaClass = DELTA_TONE_CLASSES[tone];

  return (
    <div
      className={cn(
        "flex flex-col gap-0.5 rounded border border-hairline bg-surface-2 p-3",
        className,
      )}
    >
      <span className="text-[10px] font-medium uppercase tracking-wide text-ink-faint">
        {label}
      </span>
      <span className="font-display text-xl font-semibold text-ink">
        {value}
      </span>
      {delta !== undefined && delta !== null && delta !== "" && (
        <span className={cn("text-[10px]", deltaClass)}>{delta}</span>
      )}
    </div>
  );
}
