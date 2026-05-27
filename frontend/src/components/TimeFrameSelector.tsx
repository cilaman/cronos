import { useState } from "react";

// ── Types ─────────────────────────────────────────────────────────────────────

export type TimeFramePreset = "all" | "6h" | "24h" | "7d" | "30d" | "90d" | "custom";

export interface TimeFrame {
  preset: TimeFramePreset;
  from?: string; // ISO date string (YYYY-MM-DD), only used when preset === 'custom'
  to?: string;
}

export interface ResolvedTimeFrame {
  from_dt?: string;
  to_dt?: string;
}

const PRESETS: { key: TimeFramePreset; label: string }[] = [
  { key: "6h",  label: "6h"  },
  { key: "24h", label: "24h" },
  { key: "7d",  label: "7d"  },
  { key: "30d", label: "30d" },
  { key: "90d", label: "90d" },
  { key: "all", label: "All" },
  { key: "custom", label: "Custom" },
];

function subtractHours(h: number): string {
  return new Date(Date.now() - h * 3_600_000).toISOString();
}

export function resolveTimeFrame(tf: TimeFrame): ResolvedTimeFrame {
  switch (tf.preset) {
    case "6h":  return { from_dt: subtractHours(6) };
    case "24h": return { from_dt: subtractHours(24) };
    case "7d":  return { from_dt: subtractHours(24 * 7) };
    case "30d": return { from_dt: subtractHours(24 * 30) };
    case "90d": return { from_dt: subtractHours(24 * 90) };
    case "custom":
      return {
        from_dt: tf.from ? `${tf.from}T00:00:00` : undefined,
        to_dt: tf.to ? `${tf.to}T23:59:59` : undefined,
      };
    default:
      return {};
  }
}

// ── Component ─────────────────────────────────────────────────────────────────

export function TimeFrameSelector({
  value,
  onChange,
  compact = false,
}: {
  value: TimeFrame;
  onChange: (tf: TimeFrame) => void;
  compact?: boolean;
}) {
  const [localFrom, setLocalFrom] = useState(value.from ?? "");
  const [localTo, setLocalTo] = useState(value.to ?? "");

  const btnBase = compact
    ? "px-2 py-0.5 font-display text-[9px] uppercase tracking-[0.16em] rounded transition"
    : "px-2.5 py-1 font-display text-[10px] uppercase tracking-[0.16em] rounded transition";

  const btnActive = "bg-accent text-canvas";
  const btnInactive = "text-ink-muted hover:text-ink hover:bg-surface-3";

  function handlePreset(key: TimeFramePreset) {
    if (key === "custom") {
      onChange({ preset: "custom", from: localFrom || undefined, to: localTo || undefined });
    } else {
      onChange({ preset: key });
    }
  }

  function handleCustomDates(from: string, to: string) {
    setLocalFrom(from);
    setLocalTo(to);
    if (value.preset === "custom") {
      onChange({ preset: "custom", from: from || undefined, to: to || undefined });
    }
  }

  return (
    <div className="flex flex-wrap items-center gap-2">
      {/* Preset pills */}
      <div className="flex items-center rounded border border-hairline bg-surface-2 p-0.5">
        {PRESETS.map(({ key, label }) => (
          <button
            key={key}
            type="button"
            onClick={() => handlePreset(key)}
            className={`${btnBase} ${value.preset === key ? btnActive : btnInactive}`}
          >
            {label}
          </button>
        ))}
      </div>

      {/* Custom date inputs */}
      {value.preset === "custom" && (
        <div className="flex items-center gap-1">
          <input
            type="date"
            value={localFrom}
            max={localTo || undefined}
            onChange={(e) => handleCustomDates(e.target.value, localTo)}
            className="h-6 rounded border border-hairline bg-surface-2 px-1.5 font-mono text-[10px] text-ink shadow-inset-hairline transition focus:border-accent focus:outline-none"
          />
          <span className="font-mono text-[10px] text-ink-faint">–</span>
          <input
            type="date"
            value={localTo}
            min={localFrom || undefined}
            onChange={(e) => handleCustomDates(localFrom, e.target.value)}
            className="h-6 rounded border border-hairline bg-surface-2 px-1.5 font-mono text-[10px] text-ink shadow-inset-hairline transition focus:border-accent focus:outline-none"
          />
        </div>
      )}
    </div>
  );
}
