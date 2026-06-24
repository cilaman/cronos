import { cn } from "../utils/cn";
import { Button } from "./ui/Button";

export type TimeFramePreset = "6h" | "24h" | "7d" | "30d" | "90d" | "all" | "custom";

export type TimeFrame =
  | { preset: Exclude<TimeFramePreset, "custom"> }
  | { preset: "custom"; from: string; to: string };

const PRESETS: { value: TimeFramePreset; label: string }[] = [
  { value: "6h", label: "6 h" },
  { value: "24h", label: "24 h" },
  { value: "7d", label: "7 d" },
  { value: "30d", label: "30 d" },
  { value: "90d", label: "90 d" },
  { value: "all", label: "All" },
  { value: "custom", label: "Custom" },
];

const DURATION_MS: Record<string, number> = {
  "6h": 6 * 3600 * 1000,
  "24h": 24 * 3600 * 1000,
  "7d": 7 * 86400 * 1000,
  "30d": 30 * 86400 * 1000,
  "90d": 90 * 86400 * 1000,
};

export function timeFrameToDateParams(tf: TimeFrame): { fromDt?: string; toDt?: string } {
  if (tf.preset === "all") return {};
  if (tf.preset === "custom") {
    return {
      fromDt: `${tf.from}T00:00:00`,
      toDt: `${tf.to}T23:59:59`,
    };
  }
  const now = new Date();
  return {
    fromDt: new Date(now.getTime() - DURATION_MS[tf.preset]).toISOString(),
    toDt: now.toISOString(),
  };
}

interface Props {
  value: TimeFrame;
  onChange: (tf: TimeFrame) => void;
  compact?: boolean;
}

export function TimeFrameSelector({ value, onChange, compact = false }: Props) {
  const today = new Date().toISOString().slice(0, 10);
  const sevenDaysAgo = new Date(Date.now() - DURATION_MS["7d"]).toISOString().slice(0, 10);

  const customFrom = value.preset === "custom" ? value.from : sevenDaysAgo;
  const customTo = value.preset === "custom" ? value.to : today;

  return (
    <div className="flex flex-wrap items-center gap-3">
      <div className="flex items-center rounded-md border border-hairline bg-surface-1 p-1 shadow-inset-hairline">
        {PRESETS.map(({ value: preset, label }) => (
          <Button
            key={preset}
            type="button"
            archetype="segmented"
            variant={value.preset === preset ? "primary" : "ghost"}
            size="sm"
            onClick={() => {
              if (preset === "custom") {
                onChange({ preset: "custom", from: customFrom, to: customTo });
              } else {
                onChange({ preset });
              }
            }}
            className={cn(
              "font-display uppercase tracking-[0.1em]",
              compact
                ? "px-2 py-0.5 text-[9px]"
                : "px-2.5 py-1 text-[11px]",
            )}
          >
            {label}
          </Button>
        ))}
      </div>

      {value.preset === "custom" && (
        <div className="flex items-center gap-2">
          <input
            type="date"
            value={value.from}
            max={value.to}
            onChange={(e) =>
              onChange({ preset: "custom", from: e.target.value, to: value.to })
            }
            className="h-8 rounded border border-hairline bg-surface-1 px-2 font-mono text-[11px] text-ink shadow-inset-hairline focus:border-accent focus:outline-none"
          />
          <span className="font-mono text-[10px] text-ink-faint">→</span>
          <input
            type="date"
            value={value.to}
            min={value.from}
            max={today}
            onChange={(e) =>
              onChange({ preset: "custom", from: value.from, to: e.target.value })
            }
            className="h-8 rounded border border-hairline bg-surface-1 px-2 font-mono text-[11px] text-ink shadow-inset-hairline focus:border-accent focus:outline-none"
          />
        </div>
      )}
    </div>
  );
}
