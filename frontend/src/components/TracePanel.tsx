import { useState } from "react";
import { useTaskTraces } from "../hooks/useTraces";
import type { RunTrace, ToolCallTrace } from "../types";

// ── Helpers ───────────────────────────────────────────────────────────────────

function fmtDuration(seconds: number): string {
  if (seconds < 60) return `${Math.round(seconds)}s`;
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  return `${m}m ${s}s`;
}

function fmtPct(ratio: number): string {
  return `${Math.round(ratio * 100)}%`;
}

// ── Tool category colour coding ───────────────────────────────────────────────

const READ_TOOLS = new Set(["Read", "Grep", "Glob", "WebFetch", "WebSearch"]);
const WRITE_TOOLS = new Set(["Edit", "Write", "NotebookEdit"]);
const AGENT_TOOLS = new Set(["Agent", "Skill", "Task", "TaskCreate", "TaskUpdate"]);

function toolCategory(name: string): "read" | "write" | "bash" | "agent" | "other" {
  if (READ_TOOLS.has(name)) return "read";
  if (WRITE_TOOLS.has(name)) return "write";
  if (AGENT_TOOLS.has(name)) return "agent";
  if (name === "Bash") return "bash";
  return "other";
}

const CATEGORY_STYLE: Record<string, string> = {
  read:  "bg-sky-500/10 text-sky-400 border-sky-500/30",
  write: "bg-amber-500/10 text-amber-400 border-amber-500/30",
  bash:  "bg-slate-500/10 text-slate-400 border-slate-500/30",
  agent: "bg-violet-500/10 text-violet-400 border-violet-500/30",
  other: "bg-surface-2 text-ink-muted border-hairline",
};

// ── Exit-reason badge ─────────────────────────────────────────────────────────

const EXIT_STYLE: Record<string, string> = {
  DONE:    "text-accent-bright bg-accent/10 border-accent/30",
  WAIT:    "text-warning bg-warning/10 border-warning/30",
  BLOCKED: "text-danger bg-danger/10 border-danger/30",
  STOPPED: "text-ink-muted bg-surface-2 border-hairline",
  CRASHED: "text-danger bg-danger/10 border-danger/30",
};

function ExitBadge({ reason }: { reason: string }) {
  const cls = EXIT_STYLE[reason] ?? "text-ink-muted bg-surface-2 border-hairline";
  return (
    <span className={`rounded border px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-[0.12em] ${cls}`}>
      {reason}
    </span>
  );
}

// ── Stat chip ─────────────────────────────────────────────────────────────────

function StatChip({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col gap-0.5 rounded border border-hairline bg-surface-2 px-3 py-2">
      <span className="font-display text-[9px] uppercase tracking-[0.18em] text-ink-faint">
        {label}
      </span>
      <span className="font-mono text-[13px] font-semibold tabular-nums text-ink">
        {value}
      </span>
    </div>
  );
}

// ── Signal bar ────────────────────────────────────────────────────────────────

function SignalBar({ label, value, max, display }: { label: string; value: number; max: number; display: string }) {
  const pct = max > 0 ? Math.min((value / max) * 100, 100) : 0;
  return (
    <div className="grid grid-cols-[7rem_1fr_3rem] items-center gap-2">
      <span className="truncate font-mono text-[10px] text-ink-muted">{label}</span>
      <div className="h-1 overflow-hidden rounded-full bg-surface-3">
        <div
          className="h-full rounded-full bg-accent transition-all duration-500"
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="text-right font-mono text-[10px] tabular-nums text-ink">{display}</span>
    </div>
  );
}

// ── Tool call row ─────────────────────────────────────────────────────────────

function ToolCallRow({ tc, index }: { tc: ToolCallTrace; index: number }) {
  const [expanded, setExpanded] = useState(false);
  const cat = toolCategory(tc.name);
  const badgeCls = CATEGORY_STYLE[cat];
  const rowBorder = tc.is_error ? "border-l-2 border-l-danger" : "border-l-2 border-l-transparent";

  return (
    <div className={`flex gap-3 px-3 py-2 hover:bg-surface-2/50 ${rowBorder}`}>
      {/* Step number */}
      <span className="mt-0.5 w-5 shrink-0 text-right font-mono text-[9px] tabular-nums text-ink-faint">
        {index + 1}
      </span>

      {/* Tool name badge */}
      <span className={`mt-0.5 shrink-0 rounded border px-1.5 py-0.5 font-mono text-[9px] uppercase tracking-[0.1em] ${badgeCls}`}>
        {tc.name}
      </span>

      {/* Input/output */}
      <div className="min-w-0 flex-1">
        <button
          type="button"
          onClick={() => setExpanded((v) => !v)}
          className="w-full text-left"
        >
          <p className={`font-mono text-[10px] text-ink-muted ${expanded ? "" : "truncate"}`}>
            {tc.input_summary}
          </p>
        </button>
        {expanded && tc.output_summary && (
          <p className="mt-1 rounded bg-surface-2 px-2 py-1 font-mono text-[9px] text-ink-faint">
            {tc.output_summary}
          </p>
        )}
      </div>

      {/* Status icon */}
      <span className={`mt-0.5 shrink-0 font-mono text-[11px] ${tc.is_error ? "text-danger" : "text-accent-bright"}`}>
        {tc.is_error ? "✗" : "✓"}
      </span>
    </div>
  );
}

// ── Trace view for a single run ───────────────────────────────────────────────

function TraceView({ trace }: { trace: RunTrace }) {
  const totalTokens = trace.turns.reduce(
    (acc, t) => acc + t.input_tokens + t.output_tokens, 0
  );

  // Group tool calls by turn for display
  const toolsByTurn: Map<number, ToolCallTrace[]> = new Map();
  for (const tc of trace.tool_calls) {
    const arr = toolsByTurn.get(tc.turn_index) ?? [];
    arr.push(tc);
    toolsByTurn.set(tc.turn_index, arr);
  }

  return (
    <div className="flex-1 space-y-5 overflow-y-auto overscroll-contain p-4">
      {/* Summary chips */}
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        <StatChip label="Tool calls" value={String(trace.total_tool_calls)} />
        <StatChip label="Errors" value={String(trace.error_tool_calls)} />
        <StatChip label="Turns" value={String(trace.turns.length)} />
        <StatChip label="Duration" value={fmtDuration(trace.duration_seconds)} />
      </div>

      {/* Quality signals */}
      <div>
        <p className="mb-2 font-display text-[10px] font-semibold uppercase tracking-[0.2em] text-ink-faint">
          Quality signals
        </p>
        <div className="rounded-md border border-hairline bg-surface-1 p-3 shadow-inset-hairline space-y-2.5">
          <SignalBar
            label="Exploration"
            value={trace.exploration_ratio}
            max={1}
            display={fmtPct(trace.exploration_ratio)}
          />
          <SignalBar
            label="Error recovery"
            value={trace.error_recovery_count}
            max={Math.max(trace.error_tool_calls, 1)}
            display={String(trace.error_recovery_count)}
          />
          <SignalBar
            label="Backtrack"
            value={trace.backtrack_count}
            max={Math.max(trace.backtrack_count, 5)}
            display={String(trace.backtrack_count)}
          />
          {totalTokens > 0 && (
            <SignalBar
              label="Output ratio"
              value={trace.turns.reduce((a, t) => a + t.output_tokens, 0)}
              max={totalTokens}
              display={fmtPct(
                totalTokens > 0
                  ? trace.turns.reduce((a, t) => a + t.output_tokens, 0) / totalTokens
                  : 0
              )}
            />
          )}
        </div>
      </div>

      {/* Tool call chain */}
      <div>
        <p className="mb-2 font-display text-[10px] font-semibold uppercase tracking-[0.2em] text-ink-faint">
          Tool call chain
        </p>
        {trace.tool_calls.length === 0 ? (
          <p className="px-4 py-6 text-center font-mono text-[11px] text-ink-faint">
            No tool calls recorded for this run.
          </p>
        ) : (
          <div className="rounded-md border border-hairline bg-surface-1 shadow-inset-hairline divide-y divide-hairline">
            {trace.turns.map((turn) => {
              const tcs = toolsByTurn.get(turn.turn_index) ?? [];
              return (
                <div key={turn.turn_index}>
                  {/* Turn header */}
                  <div className="flex items-center gap-2 bg-surface-2/60 px-3 py-1.5">
                    <span className="font-display text-[9px] uppercase tracking-[0.16em] text-ink-faint">
                      Turn {turn.turn_index + 1}
                    </span>
                    {turn.has_thinking && (
                      <span className="rounded bg-violet-500/10 px-1 py-0.5 font-mono text-[8px] text-violet-400">
                        thinking
                      </span>
                    )}
                    {(turn.input_tokens > 0 || turn.output_tokens > 0) && (
                      <span className="font-mono text-[9px] text-ink-faint tabular-nums">
                        {turn.input_tokens + turn.output_tokens} tok
                      </span>
                    )}
                    {turn.text_snippet && (
                      <span className="min-w-0 flex-1 truncate font-mono text-[9px] text-ink-faint">
                        {turn.text_snippet.slice(0, 80)}
                      </span>
                    )}
                  </div>
                  {/* Tool calls in this turn */}
                  {tcs.map((tc) => (
                    <ToolCallRow key={tc.tool_use_id} tc={tc} index={tc.tool_call_index} />
                  ))}
                  {tcs.length === 0 && turn.text_snippet && (
                    <div className="px-3 py-2">
                      <p className="font-mono text-[10px] text-ink-muted line-clamp-2">
                        {turn.text_snippet}
                      </p>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Tool vocabulary */}
      {trace.unique_tools.length > 0 && (
        <div>
          <p className="mb-2 font-display text-[10px] font-semibold uppercase tracking-[0.2em] text-ink-faint">
            Tools used
          </p>
          <div className="flex flex-wrap gap-1.5">
            {trace.unique_tools.map((name) => {
              const cat = toolCategory(name);
              return (
                <span key={name} className={`rounded border px-2 py-0.5 font-mono text-[10px] ${CATEGORY_STYLE[cat]}`}>
                  {name}
                </span>
              );
            })}
          </div>
        </div>
      )}

      {/* Final text snippet */}
      {trace.final_text_snippet && (
        <div>
          <p className="mb-2 font-display text-[10px] font-semibold uppercase tracking-[0.2em] text-ink-faint">
            Final output
          </p>
          <div className="rounded-md border border-hairline bg-surface-1 p-3 shadow-inset-hairline">
            <p className="font-mono text-[11px] leading-relaxed text-ink-muted">
              {trace.final_text_snippet}
            </p>
          </div>
        </div>
      )}
    </div>
  );
}

// ── Main TracePanel ───────────────────────────────────────────────────────────

export function TracePanel({ taskId }: { taskId: string }) {
  const { data: runs, isLoading } = useTaskTraces(taskId);
  const [selectedIndex, setSelectedIndex] = useState<number | null>(null);

  const selectedRun: RunTrace | undefined =
    selectedIndex !== null
      ? runs?.find((r) => r.run_index === selectedIndex)
      : runs?.[0];

  if (isLoading) {
    return (
      <div className="flex flex-1 items-center justify-center p-8">
        <p className="font-mono text-[11px] text-ink-faint">Loading traces…</p>
      </div>
    );
  }

  if (!runs || runs.length === 0) {
    return (
      <div className="flex flex-1 items-center justify-center p-8">
        <p className="font-mono text-[11px] text-ink-faint">
          No traces yet. Run this task to collect execution traces.
        </p>
      </div>
    );
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      {/* Run selector */}
      <div className="flex items-center gap-3 border-b border-hairline bg-surface-2/50 px-4 py-2">
        <span className="font-display text-[10px] uppercase tracking-[0.16em] text-ink-faint">Run</span>
        <select
          value={selectedRun?.run_index ?? runs[0].run_index}
          onChange={(e) => setSelectedIndex(Number(e.target.value))}
          className="rounded border border-hairline-strong bg-canvas px-2 py-1 text-xs font-medium text-ink focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent"
        >
          {runs.map((r) => (
            <option key={r.run_index} value={r.run_index}>
              Run {r.run_index + 1} — {r.exit_reason} — {fmtDuration(r.duration_seconds)}
            </option>
          ))}
        </select>
        {selectedRun && <ExitBadge reason={selectedRun.exit_reason} />}
        {selectedRun && (
          <span className="font-mono text-[10px] text-ink-faint">
            {new Date(selectedRun.started_at).toLocaleString(undefined, {
              month: "short",
              day: "numeric",
              hour: "2-digit",
              minute: "2-digit",
            })}
          </span>
        )}
      </div>

      {selectedRun ? (
        <TraceView trace={selectedRun} />
      ) : (
        <div className="flex flex-1 items-center justify-center p-8">
          <p className="font-mono text-[11px] text-ink-faint">Select a run above.</p>
        </div>
      )}
    </div>
  );
}
