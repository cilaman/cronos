import { useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  useArchiveTask,
  useBoard,
  useDeleteTask,
  usePromoteTask,
  useReplyToTask,
  useRoutePreview,
  useSetDependsOn,
  useSetParent,
  useStartTask,
  useStopTask,
  useTask,
  useTransitionTask,
  useUpdateTask,
} from "../hooks/useTasks";
import { useTaskStats } from "../hooks/useStats";
import { useTaskTestReportLatest } from "../hooks/useTestReports";
import {
  AGENT_MODELS,
  AGENT_MODES,
  type AgentMode,
  type AgentModel,
  type RunStats,
  type Task,
  type TaskStats,
  type TaskSummary,
  type TaskType,
} from "../types";
import { ChatInput } from "./ChatInput";
import { ConversationStream } from "./ConversationStream";
import { FilesPanel } from "./FilesPanel";
import { GoalDependencyGraph } from "./GoalDependencyGraph";
import { TaskActionBar } from "./TaskActionBar";
import { TaskForm } from "./TaskForm";
import { TracePanel } from "./TracePanel";
import { DetailShell } from "./ui/DetailShell";
import { useLiveStream, type ToolCallEntry } from "../hooks/useLiveStream";
import activeAnimatedSvgUrl from "../assets/cronos-state-active-animated.svg";
import { SpaceTag } from "./ui/SpaceTag";

// ── Stat formatting helpers ───────────────────────────────────────────────────

function fmtTokens(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return String(n);
}

function fmtDuration(seconds: number): string {
  if (seconds < 60) return `${Math.round(seconds)}s`;
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  if (h > 0) return `${h}h ${m}m`;
  const s = Math.round(seconds % 60);
  return `${m}m ${s}s`;
}

function fmtCost(usd: number): string {
  if (usd === 0) return "$0.00";
  if (usd < 0.0001) return "<$0.0001";
  if (usd < 0.01) return `$${usd.toFixed(4)}`;
  if (usd < 1) return `$${usd.toFixed(3)}`;
  return `$${usd.toFixed(2)}`;
}

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

// ── Stats panel ───────────────────────────────────────────────────────────────

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

function MiniBar({ name, count, max }: { name: string; count: number; max: number }) {
  const pct = max > 0 ? (count / max) * 100 : 0;
  return (
    <div className="grid grid-cols-[6rem_1fr_2.5rem] items-center gap-2">
      <span className="truncate font-mono text-[10px] text-ink-muted">{name}</span>
      <div className="h-1 overflow-hidden rounded-full bg-surface-3">
        <div
          className="h-full rounded-full bg-accent transition-all duration-500"
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="text-right font-mono text-[10px] tabular-nums text-ink">
        {count}
      </span>
    </div>
  );
}

function StatsPanel({ taskId }: { taskId: string }) {
  const { data: stats, isLoading } = useTaskStats(taskId);

  if (isLoading) {
    return (
      <div className="flex flex-1 items-center justify-center p-8">
        <p className="font-mono text-[11px] text-ink-faint">Loading stats…</p>
      </div>
    );
  }

  const s: TaskStats = stats ?? {
    task_id: taskId,
    space_id: "",
    title: "",
    runs: [],
    total_runs: 0,
    total_input_tokens: 0,
    total_output_tokens: 0,
    total_cache_tokens: 0,
    total_cost_usd: 0,
    total_duration_seconds: 0,
    tool_use_summary: {},
    exit_reason_counts: {},
    avg_tokens_per_run: 0,
    crash_rate: 0,
  };

  const totalTokens = s.total_input_tokens + s.total_output_tokens;
  const sortedRuns = [...s.runs].reverse();
  const tools = Object.entries(s.tool_use_summary)
    .sort(([, a], [, b]) => b - a)
    .slice(0, 8);
  const maxTool = tools[0]?.[1] ?? 1;

  return (
    <div className="flex-1 space-y-5 overflow-y-auto overscroll-contain p-4">
      {/* Summary chips */}
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        <StatChip label="Runs" value={String(s.total_runs)} />
        <StatChip label="Tokens" value={fmtTokens(totalTokens)} />
        <StatChip label="Est. cost" value={fmtCost(s.total_cost_usd)} />
        <StatChip label="Duration" value={fmtDuration(s.total_duration_seconds)} />
      </div>

      {/* Run history */}
      <div>
        <p className="mb-2 font-display text-[10px] font-semibold uppercase tracking-[0.2em] text-ink-faint">
          Run history
        </p>
        <div className="overflow-hidden rounded-md border border-hairline bg-surface-1 shadow-inset-hairline">
          {sortedRuns.length === 0 ? (
            <p className="px-4 py-6 text-center font-mono text-[11px] text-ink-faint">
              No runs recorded yet. Start this task to collect statistics.
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[540px]">
                <thead>
                  <tr className="border-b border-hairline bg-surface-2">
                    {["#", "Started", "Duration", "Tokens", "Cost", "Model", "Mode", "Exit"].map((h) => (
                      <th
                        key={h}
                        className="px-3 py-2 text-left font-display text-[9px] uppercase tracking-[0.16em] text-ink-faint"
                      >
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {sortedRuns.map((run: RunStats) => {
                    const started = new Date(run.started_at).toLocaleString(undefined, {
                      month: "short",
                      day: "numeric",
                      hour: "2-digit",
                      minute: "2-digit",
                    });
                    return (
                      <tr
                        key={run.run_index}
                        className="border-b border-hairline last:border-0 hover:bg-surface-2/50"
                      >
                        <td className="px-3 py-2 font-mono text-[10px] tabular-nums text-ink-faint">
                          {run.run_index + 1}
                        </td>
                        <td className="px-3 py-2 font-mono text-[10px] text-ink-muted">
                          {started}
                        </td>
                        <td className="px-3 py-2 font-mono text-[10px] tabular-nums text-ink-muted">
                          {fmtDuration(run.duration_seconds)}
                        </td>
                        <td className="px-3 py-2 font-mono text-[10px] tabular-nums text-ink-muted">
                          {fmtTokens(run.input_tokens + run.output_tokens)}
                        </td>
                        <td className="px-3 py-2 font-mono text-[10px] tabular-nums text-ink-muted">
                          {fmtCost(run.cost_usd)}
                        </td>
                        <td className="px-3 py-2 font-mono text-[10px] text-ink-muted">
                          {run.real_model ? (
                            <span title={run.real_model} className="cursor-default">
                              {run.real_model.replace(/^claude-/, "").replace(/-\d{8}$/, "")}
                            </span>
                          ) : (
                            run.model
                          )}
                        </td>
                        <td className="px-3 py-2 font-mono text-[10px] text-ink-muted">
                          {run.mode}
                        </td>
                        <td className="px-3 py-2">
                          <ExitBadge reason={run.exit_reason} />
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>

      {/* Tool usage */}
      {tools.length > 0 && (
        <div>
          <p className="mb-2 font-display text-[10px] font-semibold uppercase tracking-[0.2em] text-ink-faint">
            Tool usage
          </p>
          <div className="rounded-md border border-hairline bg-surface-1 p-3 shadow-inset-hairline">
            <div className="space-y-2.5">
              {tools.map(([name, count]) => (
                <MiniBar key={name} name={name} count={count} max={maxTool} />
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Token breakdown */}
      {s.total_runs > 0 && (
        <div>
          <p className="mb-2 font-display text-[10px] font-semibold uppercase tracking-[0.2em] text-ink-faint">
            Token breakdown
          </p>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            <StatChip label="Input" value={fmtTokens(s.total_input_tokens)} />
            <StatChip label="Output" value={fmtTokens(s.total_output_tokens)} />
            <StatChip label="Cache read" value={fmtTokens(s.total_cache_tokens)} />
            <StatChip label="Avg / run" value={fmtTokens(s.avg_tokens_per_run)} />
          </div>
        </div>
      )}
    </div>
  );
}

// ── Priority badge ────────────────────────────────────────────────────────────

const PRIORITY_BADGE_STYLES: Record<number, string> = {
  1: "border-danger/30 bg-danger/10 text-danger dark:border-red-400/30 dark:bg-red-400/10 dark:text-red-400",
  2: "border-warning/40 bg-warning/15 text-warning dark:border-orange-400/30 dark:bg-orange-400/10 dark:text-orange-400",
  3: "border-warning/30 bg-warning/10 text-warning dark:border-amber-400/30 dark:bg-amber-400/10 dark:text-amber-400",
  4: "border-hairline bg-surface-2 text-ink-muted dark:border-teal-400/30 dark:bg-teal-400/10 dark:text-teal-400",
  5: "border-hairline bg-surface-2 text-ink-faint",
};

function PriorityBadge({ priority }: { priority: number }) {
  const cls = PRIORITY_BADGE_STYLES[priority] ?? PRIORITY_BADGE_STYLES[3];
  return (
    <span className={`rounded border px-1.5 py-0.5 font-mono text-[10px] font-semibold uppercase tracking-wide ${cls}`}>
      P{priority}
    </span>
  );
}

// ── Test result mini-badge ────────────────────────────────────────────────────

function TaskTestBadge({ taskId }: { taskId: string }) {
  const { data: report } = useTaskTestReportLatest(taskId);
  if (!report) return null;
  const hasFail = report.total_failed > 0 || report.total_errors > 0;
  return (
    <Link
      to={`/tests`}
      className={`inline-flex items-center gap-1 rounded border px-2 py-0.5 font-mono text-[10px] transition hover:opacity-80 ${
        hasFail
          ? "border-danger/30 bg-danger/10 text-danger"
          : "border-accent/30 bg-accent/10 text-accent-bright"
      }`}
      title="View test reports"
    >
      <span>{report.total_passed}✓</span>
      {hasFail && <span>{report.total_failed + report.total_errors}✗</span>}
    </Link>
  );
}

// ── Hierarchy helpers ─────────────────────────────────────────────────────────

export function extractDetail(msg: string): string {
  try {
    const idx = msg.indexOf("{");
    if (idx >= 0) {
      const obj = JSON.parse(msg.slice(idx)) as { detail?: string };
      if (obj.detail) return obj.detail;
    }
  } catch {
    // fall through
  }
  return msg;
}

export function getDescendantIds(tasks: TaskSummary[], rootId: string): Set<string> {
  const result = new Set<string>();
  const queue = [rootId];
  while (queue.length > 0) {
    const current = queue.shift()!;
    for (const t of tasks) {
      if (t.parent_id === current && !result.has(t.id)) {
        result.add(t.id);
        queue.push(t.id);
      }
    }
  }
  return result;
}

const TYPE_BADGE_STYLES: Partial<Record<TaskType, string>> = {
  goal: "border-[rgb(var(--cat-goal)/0.4)] bg-[rgb(var(--cat-goal)/0.1)] text-[rgb(var(--cat-goal))] dark:border-violet-400/30 dark:bg-violet-400/10 dark:text-violet-400",
  issue: "border-warning/30 bg-warning/10 text-warning dark:border-orange-400/30 dark:bg-orange-400/10 dark:text-orange-400",
};

export function TypeBadge({ type }: { type: TaskType }) {
  const cls =
    TYPE_BADGE_STYLES[type] ?? "border-hairline bg-surface-2 text-ink-muted";
  return (
    <span
      className={`rounded border px-1.5 py-0.5 font-mono text-[10px] font-semibold uppercase tracking-wide ${cls}`}
    >
      {type}
    </span>
  );
}

// ── Parent picker ─────────────────────────────────────────────────────────────

interface ParentPickerProps {
  currentParentId: string | null;
  currentParentTitle: string | null;
  candidates: TaskSummary[];
  onSelect: (parentId: string | null) => Promise<unknown>;
  isPending: boolean;
  error: string | null;
  onOpenTask: (id: string) => void;
}

function ParentPicker({
  currentParentId,
  currentParentTitle,
  candidates,
  onSelect,
  isPending,
  error,
  onOpenTask,
}: ParentPickerProps) {
  const [editing, setEditing] = useState(false);
  const [search, setSearch] = useState("");

  const filtered = candidates
    .filter(
      (t) =>
        t.title.toLowerCase().includes(search.toLowerCase()) ||
        t.id.includes(search),
    )
    .slice(0, 8);

  async function handleSelect(id: string | null) {
    try {
      await onSelect(id);
      setEditing(false);
      setSearch("");
    } catch {
      // error shown via error prop
    }
  }

  return (
    <div>
      <p className="font-display text-[10px] uppercase tracking-[0.18em] text-ink-faint">
        Parent
      </p>
      {currentParentId && !editing ? (
        <div className="mt-1 flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={() => onOpenTask(currentParentId)}
            className="flex items-center gap-1 rounded border border-hairline bg-surface-2 px-2 py-1 font-mono text-[11px] text-ink-muted transition hover:border-hairline-strong hover:text-ink"
          >
            <span className="text-ink-faint">↑</span>
            <span className="max-w-[200px] truncate">
              {currentParentTitle ?? currentParentId}
            </span>
          </button>
          <button
            type="button"
            onClick={() => setEditing(true)}
            className="rounded border border-hairline px-2 py-1 text-[11px] text-ink-muted transition hover:border-hairline-strong hover:text-ink"
          >
            Change
          </button>
          <button
            type="button"
            onClick={() => void handleSelect(null)}
            disabled={isPending}
            className="rounded border border-hairline px-2 py-1 text-[11px] text-ink-muted transition hover:border-danger/50 hover:text-danger disabled:opacity-50"
          >
            Remove
          </button>
        </div>
      ) : (
        <div className="relative mt-1">
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            onFocus={() => setEditing(true)}
            onBlur={() =>
              setTimeout(() => {
                setEditing(false);
                setSearch("");
              }, 150)
            }
            autoFocus={editing && !currentParentId}
            placeholder={
              candidates.length === 0 ? "No tasks available" : "Search tasks…"
            }
            className="w-full rounded border border-hairline-strong bg-canvas px-2 py-1 text-xs text-ink placeholder-ink-faint focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent"
          />
          {editing && filtered.length > 0 && (
            <div className="absolute z-10 mt-0.5 w-full overflow-hidden rounded border border-hairline-strong bg-surface-1 shadow-lift">
              {filtered.map((t) => (
                <button
                  key={t.id}
                  type="button"
                  onMouseDown={() => void handleSelect(t.id)}
                  className="flex w-full items-center justify-between gap-2 px-3 py-1.5 text-left text-xs hover:bg-surface-2"
                >
                  <span className="truncate text-ink">{t.title}</span>
                  <span className="shrink-0 font-mono text-[10px] text-ink-faint">
                    {t.id}
                  </span>
                </button>
              ))}
            </div>
          )}
          {currentParentId && editing && (
            <button
              type="button"
              onMouseDown={() => {
                setEditing(false);
                setSearch("");
              }}
              className="mt-1 text-[11px] text-ink-muted transition hover:text-ink"
            >
              Cancel
            </button>
          )}
        </div>
      )}
      {error && (
        <p className="mt-1 rounded border border-danger/30 bg-danger/10 px-2 py-1 text-[11px] text-danger">
          {error}
        </p>
      )}
    </div>
  );
}

// ── Dependency picker ─────────────────────────────────────────────────────────

interface DependencyPickerProps {
  currentDeps: string[];
  allTasks: TaskSummary[];
  candidates: TaskSummary[];
  onUpdate: (ids: string[]) => Promise<unknown>;
  isPending: boolean;
  error: string | null;
  onOpenTask: (id: string) => void;
}

function DependencyPicker({
  currentDeps,
  allTasks,
  candidates,
  onUpdate,
  isPending,
  error,
  onOpenTask,
}: DependencyPickerProps) {
  const [search, setSearch] = useState("");

  const taskMap = useMemo(
    () => new Map(allTasks.map((t) => [t.id, t])),
    [allTasks],
  );

  const filtered = candidates
    .filter(
      (t) =>
        !currentDeps.includes(t.id) &&
        (t.title.toLowerCase().includes(search.toLowerCase()) ||
          t.id.includes(search)),
    )
    .slice(0, 8);

  async function handleAdd(id: string) {
    try {
      await onUpdate([...currentDeps, id]);
      setSearch("");
    } catch {
      // error shown via error prop
    }
  }

  async function handleRemove(id: string) {
    try {
      await onUpdate(currentDeps.filter((d) => d !== id));
    } catch {
      // error shown via error prop
    }
  }

  return (
    <div>
      <p className="font-display text-[10px] uppercase tracking-[0.18em] text-ink-faint">
        Depends on
      </p>
      <div className="mt-1 space-y-2">
        {currentDeps.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            {currentDeps.map((depId) => {
              const dep = taskMap.get(depId);
              return (
                <div
                  key={depId}
                  className="flex items-center gap-1 rounded border border-hairline-strong bg-surface-2 px-2 py-0.5"
                >
                  <button
                    type="button"
                    onClick={() => onOpenTask(depId)}
                    className="font-mono text-[11px] text-ink-muted transition hover:text-ink"
                  >
                    {dep?.title ?? depId}
                  </button>
                  <button
                    type="button"
                    onClick={() => void handleRemove(depId)}
                    disabled={isPending}
                    aria-label="Remove dependency"
                    className="ml-0.5 text-ink-faint transition hover:text-danger"
                  >
                    <span className="text-[10px]">✕</span>
                  </button>
                </div>
              );
            })}
          </div>
        )}
        <div className="relative">
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            onBlur={() => setTimeout(() => setSearch(""), 150)}
            placeholder="Add dependency…"
            className="w-full rounded border border-hairline-strong bg-canvas px-2 py-1 text-xs text-ink placeholder-ink-faint focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent"
          />
          {search && filtered.length > 0 && (
            <div className="absolute z-10 mt-0.5 w-full overflow-hidden rounded border border-hairline-strong bg-surface-1 shadow-lift">
              {filtered.map((t) => (
                <button
                  key={t.id}
                  type="button"
                  onMouseDown={() => void handleAdd(t.id)}
                  className="flex w-full items-center justify-between gap-2 px-3 py-1.5 text-left text-xs hover:bg-surface-2"
                >
                  <span className="truncate text-ink">{t.title}</span>
                  <span className="shrink-0 font-mono text-[10px] text-ink-faint">
                    {t.id}
                  </span>
                </button>
              ))}
            </div>
          )}
        </div>
      </div>
      {error && (
        <p className="mt-1 rounded border border-danger/30 bg-danger/10 px-2 py-1 text-[11px] text-danger">
          {error}
        </p>
      )}
    </div>
  );
}

// ── Hierarchy section ─────────────────────────────────────────────────────────

export function HierarchySection({ task }: { task: Task }) {
  const [, setSearchParams] = useSearchParams();
  const promote = usePromoteTask(task.id);
  const setParent = useSetParent(task.id);
  const setDependsOn = useSetDependsOn(task.id);
  const { data: board } = useBoard(task.space_id);
  const [promoteToast, setPromoteToast] = useState(false);

  const allTasks = useMemo(
    () =>
      board
        ? [
            ...board.backlog,
            ...board.active,
            ...board.waiting,
            ...board.done,
          ]
        : [],
    [board],
  );

  const descendantIds = useMemo(
    () => getDescendantIds(allTasks, task.id),
    [allTasks, task.id],
  );

  const parentCandidates = useMemo(
    () =>
      allTasks.filter((t) => t.id !== task.id && !descendantIds.has(t.id)),
    [allTasks, task.id, descendantIds],
  );

  const depCandidates = useMemo(
    () => allTasks.filter((t) => t.id !== task.id),
    [allTasks, task.id],
  );

  const children = useMemo(
    () => allTasks.filter((t) => t.parent_id === task.id),
    [allTasks, task.id],
  );

  const runningIds = useMemo(
    () => new Set(children.filter((c) => c.state === "active").map((c) => c.id)),
    [children],
  );

  function openTask(id: string) {
    setSearchParams(
      (prev) => {
        const next = new URLSearchParams(prev);
        next.set("task", id);
        return next;
      },
      { replace: true },
    );
  }

  async function handlePromote() {
    try {
      await promote.mutateAsync();
      setPromoteToast(true);
      setTimeout(() => setPromoteToast(false), 3000);
    } catch {
      // error shown via promote.error
    }
  }

  return (
    <section>
      <h3 className="font-display text-[10px] font-semibold uppercase tracking-[0.2em] text-ink-faint">
        Hierarchy
      </h3>
      <div className="mt-2 space-y-4">
        <div className="flex flex-wrap items-center gap-3">
          <TypeBadge type={task.type ?? "task"} />
          {(task.type ?? "task") !== "goal" && (
            <button
              type="button"
              onClick={() => void handlePromote()}
              disabled={promote.isPending}
              className="rounded border border-hairline px-2 py-0.5 text-[11px] text-ink-muted transition hover:border-violet-300 hover:text-violet-600 disabled:cursor-not-allowed disabled:opacity-50 dark:hover:border-violet-400/50 dark:hover:text-violet-400"
            >
              {promote.isPending ? "Promoting…" : "Promote to Goal"}
            </button>
          )}
          {promoteToast && (
            <span className="text-[11px] text-accent-bright">
              Promoted to goal
            </span>
          )}
          {promote.error && (
            <span className="text-[11px] text-danger">
              {extractDetail(promote.error.message)}
            </span>
          )}
        </div>

        <ParentPicker
          currentParentId={task.parent_id ?? null}
          currentParentTitle={task.parent_title ?? null}
          candidates={parentCandidates}
          onSelect={(parentId) => setParent.mutateAsync(parentId)}
          isPending={setParent.isPending}
          error={
            setParent.error
              ? extractDetail(setParent.error.message)
              : null
          }
          onOpenTask={openTask}
        />

        <DependencyPicker
          currentDeps={task.depends_on ?? []}
          allTasks={allTasks}
          candidates={depCandidates}
          onUpdate={(ids) => setDependsOn.mutateAsync(ids)}
          isPending={setDependsOn.isPending}
          error={
            setDependsOn.error
              ? extractDetail(setDependsOn.error.message)
              : null
          }
          onOpenTask={openTask}
        />

        {task.type === "goal" && children.length > 0 && (
          <div>
            <p className="font-display text-[10px] uppercase tracking-[0.18em] text-ink-faint">
              Progress
            </p>
            <p className="mt-1 font-mono text-sm text-ink">
              {children.filter((c) => c.state === "done").length} / {children.length}
              {children.filter((c) => c.state === "waiting").length > 0 && (
                <span className="ml-2 text-ink-muted">
                  — {children.filter((c) => c.state === "waiting").length} waiting
                </span>
              )}
            </p>
          </div>
        )}
        {task.type === "goal" && children.length > 0 && (
          <div>
            <p className="font-display text-[10px] uppercase tracking-[0.18em] text-ink-faint">
              Children
            </p>
            <div className="mt-2">
              <GoalDependencyGraph
                goal={task}
                children={children}
                onOpenTask={openTask}
                runningIds={runningIds}
              />
            </div>
          </div>
        )}
      </div>
    </section>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

interface Props {
  taskId: string;
  onClose: () => void;
}

export function Detail({ taskId, onClose }: Props) {
  const { data: task, isLoading, error, refetch } = useTask(taskId);
  const updateTask = useUpdateTask(taskId);
  const deleteTask = useDeleteTask();
  const archiveTask = useArchiveTask(taskId);
  const replyTask = useReplyToTask(taskId);
  const startTask = useStartTask(taskId);
  const stopTask = useStopTask(taskId);
  const transitionTask = useTransitionTask();
  const { data: routePreviewData } = useRoutePreview(
    task?.type === "goal" ? taskId : null
  );
  const [editing, setEditing] = useState(false);
  const [activeTab, setActiveTab] = useState<"details" | "stats" | "trace" | "files">("details");
  const [mobilePaneTab, setMobilePaneTab] = useState<"context" | "conversation">("conversation");
  const [routeToast, setRouteToast] = useState<string | null>(null);

  const { entries: liveEntries } = useLiveStream(taskId, task?.state === "active");
  const liveToolName = useMemo(() => {
    const lastToolCall = [...liveEntries].reverse().find((e): e is ToolCallEntry => e.kind === "tool_call");
    return lastToolCall?.name ?? null;
  }, [liveEntries]);
  const liveStepCount = useMemo(
    () => liveEntries.filter((e) => e.kind === "tool_call" || e.kind === "assistant").length,
    [liveEntries],
  );

  async function onDelete() {
    if (!task) return;
    if (!window.confirm(`Delete "${task.title}"? It will be moved to .trash/.`)) {
      return;
    }
    await deleteTask.mutateAsync(task.id);
    onClose();
  }

  async function onSend(message: string, verdict?: "approve" | "reject") {
    const result = await replyTask.mutateAsync({ message, verdict });
    if (result.routed_to) {
      setRouteToast(`Sent to ${result.routed_to.title}`);
      setTimeout(() => setRouteToast(null), 3000);
    }
  }

  async function onStart() {
    await startTask.mutateAsync();
  }

  async function onStop() {
    await stopTask.mutateAsync();
  }

  async function onArchive() {
    await archiveTask.mutateAsync();
  }

  async function onMarkDone() {
    if (!task) return;
    await transitionTask.mutateAsync({ id: task.id, state: "done" });
  }

  async function onSendToBacklog() {
    if (!task) return;
    await transitionTask.mutateAsync({ id: task.id, state: "backlog" });
  }

  async function onModeChange(mode: AgentMode) {
    if (!task || task.agent_mode === mode) return;
    await updateTask.mutateAsync({ agent_mode: mode });
  }

  async function onModelChange(model: AgentModel) {
    if (!task || task.agent_model === model) return;
    await updateTask.mutateAsync({ agent_model: model });
  }

  const chatError =
    replyTask.error?.message ??
    startTask.error?.message ??
    stopTask.error?.message ??
    null;

  return (
    <>
      <DetailShell
        variant="task"
        entity={task}
        isLoading={isLoading}
        error={error}
        onRetry={() => void refetch()}
        onClose={editing ? () => {} : onClose}
        headerActions={
          task ? (
            <div className="flex flex-wrap items-center gap-2">
              <PriorityBadge priority={task.priority ?? 3} />
              {task.space_name && (
                <a
                  href={`/spaces/${task.space_id}`}
                  className="flex items-center rounded border border-hairline px-2 py-0.5 transition hover:border-hairline-strong hover:text-ink"
                >
                  <SpaceTag
                    color={task.space_color}
                    icon={task.space_icon}
                    name={task.space_name}
                    size="xs"
                  />
                </a>
              )}
              <TaskTestBadge taskId={task.id} />
              <div className="flex flex-wrap items-center gap-4 text-xs">
                <label className="flex items-center gap-2 text-ink-muted">
                  <span className="font-display text-[10px] uppercase tracking-[0.18em] text-ink-faint">
                    Priority
                  </span>
                  <select
                    value={task.priority ?? 3}
                    onChange={(e) =>
                      void updateTask.mutateAsync({ priority: Number(e.target.value) })
                    }
                    className="rounded border border-hairline-strong bg-canvas px-2 py-1 text-xs font-medium text-ink focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent"
                  >
                    <option value={1}>P1 — Highest</option>
                    <option value={2}>P2 — High</option>
                    <option value={3}>P3 — Medium</option>
                    <option value={4}>P4 — Low</option>
                    <option value={5}>P5 — Lowest</option>
                  </select>
                </label>
                <label className="flex items-center gap-2 text-ink-muted">
                  <span className="font-display text-[10px] uppercase tracking-[0.18em] text-ink-faint">
                    Mode
                  </span>
                  <select
                    value={task.agent_mode}
                    onChange={(e) =>
                      void onModeChange(e.target.value as AgentMode)
                    }
                    className="rounded border border-hairline-strong bg-canvas px-2 py-1 text-xs font-medium text-ink focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent"
                  >
                    {AGENT_MODES.map((m) => (
                      <option key={m.value} value={m.value}>{m.label}</option>
                    ))}
                  </select>
                </label>
                <label className="flex items-center gap-2 text-ink-muted">
                  <span className="font-display text-[10px] uppercase tracking-[0.18em] text-ink-faint">
                    Model
                  </span>
                  <select
                    value={task.agent_model}
                    onChange={(e) =>
                      void onModelChange(e.target.value as AgentModel)
                    }
                    className="rounded border border-hairline-strong bg-canvas px-2 py-1 text-xs font-medium text-ink focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent"
                  >
                    {AGENT_MODELS.map((m) => (
                      <option key={m.value} value={m.value}>{m.label}</option>
                    ))}
                  </select>
                </label>
              </div>
            </div>
          ) : null
        }
        footer={
          task ? (
            <>
              <TaskActionBar
                taskState={task.state}
                isStarting={startTask.isPending}
                isStopping={stopTask.isPending}
                isDeleting={deleteTask.isPending}
                isArchiving={archiveTask.isPending}
                isMarkingDone={transitionTask.isPending}
                isSendingToBacklog={transitionTask.isPending}
                onStart={() => void onStart()}
                onStop={() => void onStop()}
                onEdit={() => setEditing(true)}
                onDelete={() => void onDelete()}
                onArchive={() => void onArchive()}
                onMarkDone={() => void onMarkDone()}
                onSendToBacklog={() => void onSendToBacklog()}
              />

              {/* Tab bar */}
              <div className="flex border-b border-hairline bg-surface-1 px-4">
                {(["details", "stats", "trace"] as const).map((tab) => (
                  <button
                    key={tab}
                    type="button"
                    onClick={() => setActiveTab(tab)}
                    className={[
                      "relative mr-4 pb-2.5 pt-2 font-display text-[10px] uppercase tracking-[0.18em] transition",
                      activeTab === tab
                        ? "text-ink after:absolute after:inset-x-0 after:bottom-0 after:h-[2px] after:rounded-t after:bg-accent"
                        : "text-ink-faint hover:text-ink-muted",
                    ].join(" ")}
                  >
                    {tab}
                  </button>
                ))}
                <button
                  type="button"
                  onClick={() => setActiveTab("files")}
                  className={[
                    "relative mr-4 pb-2.5 pt-2 font-display text-[10px] uppercase tracking-[0.18em] transition",
                    activeTab === "files"
                      ? "text-ink after:absolute after:inset-x-0 after:bottom-0 after:h-[2px] after:rounded-t after:bg-accent"
                      : "text-ink-faint hover:text-ink-muted",
                  ].join(" ")}
                >
                  files
                </button>
              </div>

              {/* Tab content */}
              {activeTab === "details" ? (
                <>
                  {/* Mobile sub-tab bar: Context / Conversation — hidden ≥md */}
                  <div className="flex border-b border-hairline bg-surface-1 px-4 md:hidden">
                    {(["context", "conversation"] as const).map((pane) => (
                      <button
                        key={pane}
                        type="button"
                        onClick={() => setMobilePaneTab(pane)}
                        className={[
                          "relative mr-4 pb-2.5 pt-2 font-display text-[10px] uppercase tracking-[0.18em] transition",
                          mobilePaneTab === pane
                            ? "text-ink after:absolute after:inset-x-0 after:bottom-0 after:h-[2px] after:rounded-t after:bg-accent"
                            : "text-ink-faint hover:text-ink-muted",
                        ].join(" ")}
                      >
                        {pane}
                      </button>
                    ))}
                  </div>

                  {/* Two-pane workspace */}
                  <div className="flex flex-1 min-h-0 flex-col md:flex-row">
                    {/* Left pane: Context (Brief + PR + Hierarchy) */}
                    <div
                      data-testid="context-pane"
                      className={[
                        "flex-1 min-h-0 overflow-y-auto overscroll-contain space-y-6 p-4",
                        "border-b border-hairline md:border-b-0 md:border-r",
                        mobilePaneTab === "conversation" ? "hidden md:block" : "",
                      ].filter(Boolean).join(" ")}
                    >
                      <section>
                        <h3 className="font-display text-[10px] font-semibold uppercase tracking-[0.2em] text-ink-faint">
                          Brief
                        </h3>
                        <div className="prose prose-sm dark:prose-invert mt-2 max-w-none prose-headings:text-ink prose-p:text-ink prose-strong:text-ink prose-a:text-accent-bright prose-code:text-accent-bright prose-pre:bg-canvas prose-pre:border prose-pre:border-hairline prose-pre:overflow-x-auto">
                          <ReactMarkdown remarkPlugins={[remarkGfm]}>{task.brief}</ReactMarkdown>
                        </div>
                      </section>

                      {task.state === "done" && (task.pr_url || task.proposed_pr_path) && (
                        <section>
                          <h3 className="font-display text-[10px] font-semibold uppercase tracking-[0.2em] text-ink-faint">
                            Pull Request
                          </h3>
                          <div className="mt-2">
                            {task.pr_url ? (
                              <a
                                href={task.pr_url}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="inline-flex items-center gap-1.5 rounded border border-hairline bg-surface-2 px-3 py-1.5 text-[12px] text-ink-muted transition hover:border-accent hover:text-accent-bright"
                              >
                                <svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                                  <circle cx="18" cy="18" r="3" /><circle cx="6" cy="6" r="3" />
                                  <path d="M13 6h3a2 2 0 0 1 2 2v7" /><line x1="6" y1="9" x2="6" y2="21" />
                                </svg>
                                {task.pr_url}
                              </a>
                            ) : task.proposed_pr_path ? (
                              <div className="flex items-center gap-2">
                                <code className="break-all rounded border border-hairline bg-canvas px-2 py-1 font-mono text-[11px] text-ink">
                                  {task.proposed_pr_path}
                                </code>
                                <button
                                  type="button"
                                  onClick={() => void navigator.clipboard.writeText(task.proposed_pr_path!)}
                                  className="shrink-0 rounded border border-hairline-strong bg-surface-2 px-2 py-1 text-[11px] text-ink-muted transition hover:border-hairline-strong hover:text-ink"
                                >
                                  Copy path
                                </button>
                              </div>
                            ) : null}
                          </div>
                        </section>
                      )}

                      <HierarchySection task={task} />
                    </div>

                    {/* Right pane: Conversation */}
                    <div
                      className={[
                        "flex flex-1 min-h-0 flex-col",
                        mobilePaneTab === "context" ? "hidden md:flex" : "",
                      ].filter(Boolean).join(" ")}
                    >
                      {/* NOW running card — sticky at top of right pane when task is active */}
                      {task.state === "active" && (
                        <div
                          data-testid="now-running-card"
                          className="flex shrink-0 items-center gap-3 border-b border-hairline bg-surface-1 px-4 py-2"
                        >
                          <img
                            src={activeAnimatedSvgUrl}
                            alt=""
                            aria-hidden="true"
                            className="h-5 w-5 shrink-0"
                          />
                          <span className="font-display text-[10px] uppercase tracking-[0.18em] text-accent-bright">
                            NOW running
                          </span>
                          {liveToolName && (
                            <span
                              data-testid="now-tool-name"
                              className="truncate font-mono text-[10px] text-ink-muted"
                            >
                              {liveToolName}
                            </span>
                          )}
                          <span
                            data-testid="now-step-count"
                            className="ml-auto shrink-0 font-mono text-[10px] text-ink-faint"
                          >
                            {liveStepCount} steps
                          </span>
                        </div>
                      )}
                      <div
                        data-testid="conversation-pane"
                        className="flex-1 min-h-0 overflow-y-auto overscroll-contain"
                      >
                        <ConversationStream task={task} />
                      </div>
                      <ChatInput
                        taskState={task.state}
                        waitingQuestion={task.waiting_question}
                        waitingKind={task.waiting_kind}
                        pendingCount={task.pending_messages.length}
                        isSending={replyTask.isPending}
                        error={chatError}
                        onSend={onSend}
                        routeHint={
                          routePreviewData?.routed_to
                            ? `→ will route to: ${routePreviewData.routed_to.title}`
                            : undefined
                        }
                        routeToast={routeToast}
                      />
                    </div>
                  </div>
                </>
              ) : activeTab === "stats" ? (
                <div className="flex min-h-0 flex-1 flex-col">
                  <StatsPanel taskId={task.id} />
                </div>
              ) : activeTab === "trace" ? (
                <div className="flex min-h-0 flex-1 flex-col">
                  <TracePanel taskId={task.id} />
                </div>
              ) : (
                <div className="flex min-h-0 flex-1 flex-col">
                  <FilesPanel
                    taskId={task.id}
                    className="flex flex-1 flex-col overflow-hidden"
                  />
                </div>
              )}
            </>
          ) : null
        }
      />

      {editing && task && (
        <TaskForm
          heading="Edit task"
          initialTitle={task.title}
          initialBrief={task.brief}
          initialModel={task.agent_model}
          initialMode={task.agent_mode}
          initialPriority={task.priority ?? 3}
          submitting={updateTask.isPending}
          error={updateTask.error?.message ?? null}
          onCancel={() => setEditing(false)}
          onSubmit={async (body) => {
            await updateTask.mutateAsync({
              title: body.title,
              brief: body.brief,
              agent_model: body.agent_model,
              agent_mode: body.agent_mode,
              priority: body.priority,
            });
            setEditing(false);
          }}
        />
      )}
    </>
  );
}
