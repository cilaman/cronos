import { cn } from "../../utils/cn";

type Tone = "neutral" | "success" | "warning" | "danger" | "info";

export interface ProgressSegment {
  value: number;
  tone: Tone;
  label?: string;
}

interface ProgressBarProps {
  value: number;
  max: number;
  segments?: ProgressSegment[];
  tone?: Tone;
  showLabel?: boolean;
  className?: string;
}

const TONE_FILL_CLASSES: Record<Tone, string> = {
  neutral: "bg-ink-muted",
  success: "bg-success",
  warning: "bg-warning",
  danger: "bg-danger",
  info: "bg-info",
};

/**
 * Proportional fill progress bar with optional per-segment colouring.
 * When `segments` is provided it renders multiple coloured fills that sum to `max`.
 * When `tone` is provided (and no segments) it uses a single colour fill.
 * `showLabel` appends the percentage text after the bar.
 */
export function ProgressBar({
  value,
  max,
  segments,
  tone = "neutral",
  showLabel = false,
  className,
}: ProgressBarProps) {
  const safeMax = max > 0 ? max : 1;
  const percentage = Math.min(100, Math.round((value / safeMax) * 100));

  return (
    <div className={cn("flex items-center gap-2", className)}>
      <div
        role="progressbar"
        aria-valuenow={value}
        aria-valuemin={0}
        aria-valuemax={max}
        aria-label={showLabel ? undefined : `${percentage}%`}
        className="relative h-2 flex-1 overflow-hidden rounded-full bg-surface-3"
      >
        {segments && segments.length > 0 ? (
          // Multi-segment mode: render each segment as an absolute fill
          <div className="flex h-full w-full">
            {segments.map((seg, idx) => {
              const segPercent = Math.min(100, (seg.value / safeMax) * 100);
              return (
                <div
                  key={idx}
                  title={seg.label}
                  className={cn("h-full", TONE_FILL_CLASSES[seg.tone])}
                  style={{ width: `${segPercent}%` }}
                />
              );
            })}
          </div>
        ) : (
          // Single fill mode
          <div
            className={cn(
              "h-full rounded-full transition-all",
              TONE_FILL_CLASSES[tone],
            )}
            style={{ width: `${percentage}%` }}
          />
        )}
      </div>
      {showLabel && (
        <span className="text-[10px] tabular-nums text-ink-muted">
          {percentage}%
        </span>
      )}
    </div>
  );
}
