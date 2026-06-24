import { useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { useGlobalStats, useSpaceStats } from "../hooks/useStats";
import { useSpaces } from "../hooks/useSpaces";
import {
  TimeFrameSelector,
  type TimeFrame,
  type TimeFramePreset,
} from "../components/TimeFrameSelector";
import { StatTile } from "../components/ui/StatTile";
import { PageContainer } from "../components/ui/PageContainer";
import { PageHeader } from "../components/ui/PageHeader";
import type { GlobalStats, TaskStats } from "../types";

// ── Formatters ────────────────────────────────────────────────────────────────

function formatTokens(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return String(n);
}

function formatDuration(seconds: number): string {
  if (seconds < 60) return `${Math.round(seconds)}s`;
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  if (h > 0) return `${h}h ${m}m`;
  const s = Math.round(seconds % 60);
  return `${m}m ${s}s`;
}

function formatCost(usd: number): string {
  if (usd === 0) return "$0.00";
  if (usd < 0.0001) return "<$0.0001";
  if (usd < 0.01) return `$${usd.toFixed(4)}`;
  if (usd < 1) return `$${usd.toFixed(3)}`;
  return `$${usd.toFixed(2)}`;
}

// ── URL helpers ───────────────────────────────────────────────────────────────

const VALID_PRESETS = new Set<TimeFramePreset>([
  "6h", "24h", "7d", "30d", "90d", "all", "custom",
]);

function parseTimeFrame(params: URLSearchParams): TimeFrame {
  const raw = params.get("preset");
  if (raw && VALID_PRESETS.has(raw as TimeFramePreset)) {
    if (raw === "custom") {
      const from = params.get("from") ?? "";
      const to = params.get("to") ?? "";
      if (from && to) return { preset: "custom", from, to };
    } else {
      return { preset: raw as Exclude<TimeFramePreset, "custom"> };
    }
  }
  return { preset: "all" };
}

// ── Sub-components ────────────────────────────────────────────────────────────

const EXIT_REASON_STYLE: Record<string, { label: string; cls: string }> = {
  DONE:    { label: "Done",    cls: "text-accent-bright border-accent/30 bg-accent/10" },
  WAIT:    { label: "Wait",    cls: "text-warning border-warning/30 bg-warning/10" },
  BLOCKED: { label: "Blocked", cls: "text-danger border-danger/30 bg-danger/10" },
  STOPPED: { label: "Stopped", cls: "text-ink-muted border-hairline bg-surface-2" },
  CRASHED: { label: "Crashed", cls: "text-danger border-danger/30 bg-danger/10" },
};

function ExitReasonBadge({ reason, count }: { reason: string; count: number }) {
  const style = EXIT_REASON_STYLE[reason] ?? {
    label: reason,
    cls: "text-ink-muted border-hairline bg-surface-2",
  };
  return (
    <div className={`flex items-center gap-2 rounded border px-3 py-2 ${style.cls}`}>
      <span className="font-display text-[10px] uppercase tracking-[0.18em]">
        {style.label}
      </span>
      <span className="ml-auto font-mono text-[13px] font-semibold tabular-nums">
        {count}
      </span>
    </div>
  );
}

function ToolBar({ name, count, max }: { name: string; count: number; max: number }) {
  const pct = max > 0 ? (count / max) * 100 : 0;
  return (
    <div className="grid grid-cols-[7rem_1fr_3.5rem] items-center gap-3">
      <span className="truncate font-mono text-[11px] text-ink-muted">{name}</span>
      <div className="h-1.5 overflow-hidden rounded-full bg-surface-3">
        <div
          className="h-full rounded-full bg-accent transition-all duration-500"
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="text-right font-mono text-[11px] tabular-nums text-ink">
        {count.toLocaleString()}
      </span>
    </div>
  );
}

function SectionHeader({ title, count }: { title: string; count?: number }) {
  return (
    <div className="mb-3 flex items-baseline gap-2">
      <h2 className="font-display text-[11px] font-semibold uppercase tracking-[0.2em] text-ink-muted">
        {title}
      </h2>
      {count !== undefined && (
        <span className="font-mono text-[10px] tabular-nums text-ink-faint">
          {String(count).padStart(2, "0")}
        </span>
      )}
    </div>
  );
}

function GlobalView({ stats }: { stats: GlobalStats }) {
  const totalTokens = stats.total_input_tokens + stats.total_output_tokens;
  const tools = Object.entries(stats.tool_use_summary)
    .sort(([, a], [, b]) => b - a)
    .slice(0, 10);
  const maxTool = tools[0]?.[1] ?? 1;
  return (
    <div className="space-y-8">
      {/* Summary tiles */}
      <section>
        <SectionHeader title="Overview" />
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
          <StatTile label="Total runs" value={stats.total_runs} />
          <StatTile
            label="Total tokens"
            value={formatTokens(totalTokens)}
            tone="info"
            delta={`${formatTokens(stats.total_input_tokens)} in · ${formatTokens(stats.total_output_tokens)} out`}
          />
          <StatTile
            label="Est. cost"
            value={formatCost(stats.total_cost_usd)}
            delta="approximate"
          />
          <StatTile
            label="Total time"
            value={formatDuration(stats.total_duration_seconds)}
          />
          <StatTile
            label="Tasks tracked"
            value={stats.total_tasks_with_stats}
          />
          <StatTile
            label="Avg tokens / run"
            value={formatTokens(stats.avg_tokens_per_run)}
            tone="neutral"
          />
        </div>
      </section>

      <div className="grid gap-6 lg:grid-cols-[2fr_1fr]">
        {/* Tool usage */}
        <section>
          <SectionHeader title="Tool usage" count={tools.length} />
          <div className="rounded-md border border-hairline bg-surface-1 p-4 shadow-inset-hairline">
            {tools.length === 0 ? (
              <p className="py-4 text-center font-mono text-[11px] text-ink-faint">
                No tool data yet
              </p>
            ) : (
              <div className="space-y-3">
                {tools.map(([name, count]) => (
                  <ToolBar key={name} name={name} count={count} max={maxTool} />
                ))}
              </div>
            )}
          </div>
        </section>

        {/* Exit reasons */}
        <section>
          <SectionHeader title="Exit reasons" />
          <div className="space-y-2">
            {["DONE", "WAIT", "BLOCKED", "STOPPED", "CRASHED"].map((reason) => (
              <ExitReasonBadge
                key={reason}
                reason={reason}
                count={stats.exit_reason_counts[reason] ?? 0}
              />
            ))}
          </div>
        </section>
      </div>
    </div>
  );
}

function SpaceTaskTable({ tasks, spaceId }: { tasks: TaskStats[]; spaceId: string }) {
  const sorted = [...tasks].sort((a, b) => {
    const aLast = a.runs[a.runs.length - 1]?.ended_at ?? "";
    const bLast = b.runs[b.runs.length - 1]?.ended_at ?? "";
    return bLast.localeCompare(aLast);
  });

  if (sorted.length === 0) {
    return (
      <div className="rounded-md border border-hairline bg-surface-1 p-8 text-center shadow-inset-hairline">
        <p className="font-mono text-[11px] text-ink-faint">No task statistics in this space yet.</p>
        <p className="mt-1 font-mono text-[10px] text-ink-faint">Start a task to begin collecting data.</p>
      </div>
    );
  }

  return (
    <div className="overflow-hidden rounded-md border border-hairline bg-surface-1 shadow-inset-hairline">
      {/* Table header */}
      <div className="grid grid-cols-[1fr_3rem_5rem_4rem_5rem_5rem] gap-2 border-b border-hairline bg-surface-2 px-4 py-2">
        {["Task", "Runs", "Tokens", "Cost", "Duration", "Last run"].map((h) => (
          <span key={h} className="font-display text-[9px] uppercase tracking-[0.18em] text-ink-faint">
            {h}
          </span>
        ))}
      </div>

      {sorted.map((ts) => {
        const lastRun = ts.runs[ts.runs.length - 1];
        const lastRunAt = lastRun
          ? new Date(lastRun.ended_at).toLocaleDateString(undefined, {
              month: "short",
              day: "numeric",
              hour: "2-digit",
              minute: "2-digit",
            })
          : "—";
        const totalTokens = ts.total_input_tokens + ts.total_output_tokens;

        return (
          <Link
            key={ts.task_id}
            to={`/spaces/${spaceId}?task=${encodeURIComponent(ts.task_id)}`}
            className="grid grid-cols-[1fr_3rem_5rem_4rem_5rem_5rem] items-center gap-2 border-b border-hairline px-4 py-2.5 transition last:border-0 hover:bg-surface-2/60"
          >
            <span className="truncate text-[12px] text-ink">{ts.title}</span>
            <span className="font-mono text-[11px] tabular-nums text-ink-muted">
              {ts.total_runs}
            </span>
            <span className="font-mono text-[11px] tabular-nums text-ink-muted">
              {formatTokens(totalTokens)}
            </span>
            <span className="font-mono text-[11px] tabular-nums text-ink-muted">
              {formatCost(ts.total_cost_usd)}
            </span>
            <span className="font-mono text-[11px] tabular-nums text-ink-muted">
              {formatDuration(ts.total_duration_seconds)}
            </span>
            <span className="font-mono text-[10px] text-ink-faint">{lastRunAt}</span>
          </Link>
        );
      })}
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export function StatsPage() {
  const { spaceId: paramSpaceId } = useParams<{ spaceId?: string }>();
  const [selectedSpaceId, setSelectedSpaceId] = useState<string>(paramSpaceId ?? "");
  const [searchParams, setSearchParams] = useSearchParams();

  const timeFrame = parseTimeFrame(searchParams);

  function handleTimeFrameChange(tf: TimeFrame) {
    const next = new URLSearchParams(searchParams);
    next.set("preset", tf.preset);
    if (tf.preset === "custom") {
      next.set("from", tf.from);
      next.set("to", tf.to);
    } else {
      next.delete("from");
      next.delete("to");
    }
    setSearchParams(next, { replace: true });
  }

  const { data: spacesData } = useSpaces();
  const { data: globalStats, isLoading: globalLoading } = useGlobalStats(timeFrame);
  const { data: spaceStats } = useSpaceStats(selectedSpaceId || undefined, timeFrame);

  const spaces = spacesData?.spaces ?? [];
  const activeSpace = spaces.find((s) => s.id === selectedSpaceId);

  return (
    <PageContainer>
      <div className="space-y-8">
      {/* Page header */}
      <PageHeader
        breadcrumbs={[{ label: "Cronos" }, { label: "Analytics" }]}
        title="Stats"
        subtitle={
          <div className="mt-2 space-y-2">
            {spaces.length > 0 && (
              <div className="flex items-center gap-2">
                <label
                  htmlFor="space-filter"
                  className="font-display text-[10px] uppercase tracking-[0.18em] text-ink-faint"
                >
                  Space
                </label>
                <select
                  id="space-filter"
                  value={selectedSpaceId}
                  onChange={(e) => setSelectedSpaceId(e.target.value)}
                  className="h-9 rounded border border-hairline bg-surface-1 px-3 font-mono text-[12px] text-ink shadow-inset-hairline transition focus:border-accent focus:outline-none"
                >
                  <option value="">All spaces</option>
                  {spaces.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.name}
                    </option>
                  ))}
                </select>
              </div>
            )}
            <TimeFrameSelector value={timeFrame} onChange={handleTimeFrameChange} />
          </div>
        }
      />

      {/* Global stats */}
      {globalLoading ? (
        <div className="py-12 text-center font-mono text-[11px] text-ink-faint">
          Loading your statistics…
        </div>
      ) : globalStats ? (
        <GlobalView stats={globalStats} />
      ) : null}

      {/* Per-space task table */}
      <section>
        <SectionHeader
          title={
            activeSpace
              ? `Tasks — ${activeSpace.name}`
              : "Tasks by space"
          }
          count={spaceStats?.length}
        />

        {!selectedSpaceId ? (
          <div className="rounded-md border border-dashed border-hairline bg-surface-1 p-8 text-center shadow-inset-hairline">
            <p className="font-mono text-[11px] text-ink-faint">
              Select a space above to view per-task statistics.
            </p>
          </div>
        ) : spaceStats ? (
          <SpaceTaskTable tasks={spaceStats} spaceId={selectedSpaceId} />
        ) : (
          <div className="rounded-md border border-hairline bg-surface-1 p-8 text-center shadow-inset-hairline">
            <p className="font-mono text-[11px] text-ink-faint">Loading task statistics…</p>
          </div>
        )}
      </section>
      </div>
    </PageContainer>
  );
}
