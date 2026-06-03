import { useState } from "react";
import { useToolTelemetry } from "../hooks/useSpaces";
import { cn } from "../utils/cn";

interface Props {
  spaceId: string;
  kind: string;
  name: string;
  window?: string;
}

function successColor(rate: number): string {
  if (rate >= 0.9) return "text-green-600 dark:text-green-400";
  if (rate >= 0.7) return "text-amber-600 dark:text-amber-400";
  return "text-danger";
}

function SuccessBar({ rate }: { rate: number }) {
  const pct = Math.round(rate * 100);
  return (
    <div className="flex items-center gap-1.5" aria-label={`${pct}% success rate`}>
      <div className="h-1 w-16 overflow-hidden rounded-full bg-surface-2">
        <div
          className={cn(
            "h-full rounded-full transition-all",
            rate >= 0.9
              ? "bg-green-500"
              : rate >= 0.7
                ? "bg-amber-500"
                : "bg-danger",
          )}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className={cn("font-mono text-[10px] tabular-nums", successColor(rate))}>
        {pct}%
      </span>
    </div>
  );
}

function StatCell({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="font-mono text-[16px] font-semibold tabular-nums text-ink">
        {value}
      </span>
      <span className="font-display text-[10px] uppercase tracking-[0.14em] text-ink-faint">
        {label}
      </span>
    </div>
  );
}

export function AdoptedToolTelemetry({ spaceId, kind, name, window = "30d" }: Props) {
  const [expanded, setExpanded] = useState(false);
  const { data, isLoading } = useToolTelemetry(spaceId, kind, name, window);

  const calls = data?.calls ?? 0;
  const successRate = data?.avg_success_rate ?? 0;
  const errors = data?.errors ?? 0;
  const rescues = data?.human_rescue_count ?? 0;
  const errorRate = calls > 0 ? errors / calls : 0;

  return (
    <div data-testid="adopted-tool-telemetry">
      {/* Strip */}
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        aria-expanded={expanded}
        aria-label={`Telemetry for ${name}`}
        className="flex w-full items-center gap-3 py-1.5 text-left transition hover:opacity-80 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-accent/40"
        data-testid="telemetry-strip"
      >
        {isLoading ? (
          <span className="font-mono text-[10px] text-ink-faint">loading…</span>
        ) : calls === 0 ? (
          <span className="font-mono text-[10px] text-ink-faint" data-testid="no-calls">
            No calls in {window}
          </span>
        ) : (
          <>
            <span className="font-mono text-[10px] tabular-nums text-ink-muted" data-testid="call-count">
              {calls} call{calls !== 1 ? "s" : ""}
            </span>
            <SuccessBar rate={successRate} />
          </>
        )}
        <span
          className={cn(
            "ml-auto shrink-0 font-mono text-[10px] text-ink-faint transition-transform",
            expanded && "rotate-180",
          )}
          aria-hidden
        >
          ▾
        </span>
      </button>

      {/* Expanded detail */}
      {expanded && (
        <div
          className="mt-1 rounded-md border border-hairline bg-surface-2/60 p-4"
          data-testid="telemetry-detail"
        >
          {calls === 0 ? (
            <p className="text-[12px] text-ink-faint" data-testid="empty-history">
              No usage recorded in the last {window}. Run the tool at least once to see telemetry.
            </p>
          ) : (
            <div className="space-y-4">
              {/* Stats row */}
              <div className="flex flex-wrap gap-6">
                <StatCell label="Calls" value={calls} />
                <StatCell
                  label="Error rate"
                  value={`${Math.round(errorRate * 100)}%`}
                />
                <StatCell label="Rescues" value={rescues} />
                <StatCell
                  label="Success"
                  value={`${Math.round(successRate * 100)}%`}
                />
              </div>

              {/* Visual breakdown bar */}
              <div>
                <p className="mb-1.5 font-display text-[10px] uppercase tracking-[0.14em] text-ink-faint">
                  Calls breakdown
                </p>
                <div className="flex h-4 overflow-hidden rounded bg-surface-2">
                  {/* success portion */}
                  <div
                    className="h-full bg-green-500/60"
                    style={{ width: `${Math.round(successRate * 100)}%` }}
                    title={`${calls - errors} successful`}
                  />
                  {/* error portion */}
                  {errors > 0 && (
                    <div
                      className="h-full bg-danger/60"
                      style={{ width: `${Math.round(errorRate * 100)}%` }}
                      title={`${errors} errored`}
                    />
                  )}
                </div>
                <div className="mt-1 flex gap-3">
                  <span className="flex items-center gap-1 font-mono text-[10px] text-ink-faint">
                    <span className="inline-block h-2 w-2 rounded-sm bg-green-500/60" />
                    {calls - errors} ok
                  </span>
                  {errors > 0 && (
                    <span className="flex items-center gap-1 font-mono text-[10px] text-ink-faint">
                      <span className="inline-block h-2 w-2 rounded-sm bg-danger/60" />
                      {errors} err
                    </span>
                  )}
                </div>
              </div>

              <p className="font-mono text-[10px] text-ink-faint">
                Window: last {window} · per-run history not yet available
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
