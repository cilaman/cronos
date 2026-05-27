import { useEffect, useState } from "react";

export type Preset = "6h" | "24h" | "7d" | "30d" | "90d" | "all" | "custom";

export interface TimeFrame {
  preset: Preset;
  from?: string; // ISO date string, only when preset === 'custom'
  to?: string;   // ISO date string, only when preset === 'custom'
}

interface Props {
  value: TimeFrame;
  onChange: (tf: TimeFrame) => void;
  className?: string;
}

const PRESETS: { label: string; value: Preset }[] = [
  { label: "6 h", value: "6h" },
  { label: "24 h", value: "24h" },
  { label: "7 d", value: "7d" },
  { label: "30 d", value: "30d" },
  { label: "90 d", value: "90d" },
  { label: "All", value: "all" },
  { label: "Custom", value: "custom" },
];

export default function TimeFrameSelector({ value, onChange, className }: Props) {
  const [localFrom, setLocalFrom] = useState(value.from ?? "");
  const [localTo, setLocalTo] = useState(value.to ?? "");
  const [error, setError] = useState<string | null>(null);

  // Sync local inputs when parent restores state (e.g. from URL)
  useEffect(() => {
    setLocalFrom(value.from ?? "");
    setLocalTo(value.to ?? "");
  }, [value.from, value.to]);

  function handlePreset(preset: Preset) {
    setError(null);
    onChange(preset === "custom" ? { preset: "custom" } : { preset });
  }

  function handleDateChange(from: string, to: string) {
    setLocalFrom(from);
    setLocalTo(to);
    if (!from || !to) {
      setError("Both dates are required.");
      return;
    }
    if (from > to) {
      setError("From must be on or before To.");
      return;
    }
    setError(null);
    onChange({ preset: "custom", from, to });
  }

  return (
    <div className={["flex flex-wrap items-center gap-2", className].filter(Boolean).join(" ")}>
      <div
        className="inline-flex items-center rounded border border-hairline bg-surface-1"
        role="group"
        aria-label="Time frame"
      >
        {PRESETS.map((p, i) => (
          <span key={p.value} className="contents">
            {i > 0 && <span className="h-4 w-px bg-hairline" aria-hidden="true" />}
            <button
              type="button"
              onClick={() => handlePreset(p.value)}
              aria-pressed={value.preset === p.value}
              className={[
                "h-8 px-2.5 font-display text-[10px] uppercase tracking-[0.14em] transition focus:outline-none focus-visible:ring-1 focus-visible:ring-inset focus-visible:ring-accent",
                i === 0 && "rounded-l",
                i === PRESETS.length - 1 && "rounded-r",
                value.preset === p.value
                  ? "bg-accent/10 text-accent-bright"
                  : "text-ink-muted hover:bg-surface-2 hover:text-ink",
              ]
                .filter(Boolean)
                .join(" ")}
            >
              {p.label}
            </button>
          </span>
        ))}
      </div>

      {value.preset === "custom" && (
        <div className="flex flex-wrap items-center gap-2">
          <div className="flex items-center gap-1.5">
            <label
              htmlFor="tf-from"
              className="font-display text-[10px] uppercase tracking-[0.14em] text-ink-muted"
            >
              From
            </label>
            <input
              id="tf-from"
              type="date"
              value={localFrom}
              onChange={(e) => handleDateChange(e.target.value, localTo)}
              className="h-8 rounded border border-hairline bg-surface-2 px-2 font-mono text-[11px] text-ink shadow-inset-hairline transition focus:border-accent focus:outline-none"
            />
          </div>
          <div className="flex items-center gap-1.5">
            <label
              htmlFor="tf-to"
              className="font-display text-[10px] uppercase tracking-[0.14em] text-ink-muted"
            >
              To
            </label>
            <input
              id="tf-to"
              type="date"
              value={localTo}
              onChange={(e) => handleDateChange(localFrom, e.target.value)}
              className="h-8 rounded border border-hairline bg-surface-2 px-2 font-mono text-[11px] text-ink shadow-inset-hairline transition focus:border-accent focus:outline-none"
            />
          </div>
          {error && (
            <p className="font-mono text-[10px] text-danger" role="alert">
              {error}
            </p>
          )}
        </div>
      )}
    </div>
  );
}
