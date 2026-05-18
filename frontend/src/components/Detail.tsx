import { useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  useArchiveTask,
  useDeleteTask,
  useReplyToTask,
  useStartTask,
  useStopTask,
  useTask,
  useTransitionTask,
  useUpdateTask,
} from "../hooks/useTasks";
import { useTaskStats } from "../hooks/useStats";
import { STATE_BADGE } from "../state-badges";
import {
  AGENT_MODELS,
  AGENT_MODES,
  type AgentMode,
  type AgentModel,
  type RunStats,
  type TaskStats,
} from "../types";
import { ChatInput } from "./ChatInput";
import { ConversationStream } from "./ConversationStream";
import { FilesPanel } from "./FilesPanel";
import { TaskActionBar } from "./TaskActionBar";
import { TaskForm } from "./TaskForm";
import { TracePanel } from "./TracePanel";
import { Modal } from "./ui/Modal";
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
                          {run.model}
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

// ── Main component ────────────────────────────────────────────────────────────

interface Props {
  taskId: string;
  onClose: () => void;
}

function DetailSkeleton() {
  return (
    <div className="animate-pulse p-6 space-y-4">
      <div className="flex gap-2">
        <div className="h-5 w-16 rounded bg-surface-3" />
        <div className="h-5 w-24 rounded bg-surface-3" />
      </div>
      <div className="h-7 w-2/3 rounded bg-surface-3" />
      <div className="space-y-2 pt-2">
        <div className="h-4 w-full rounded bg-surface-3" />
        <div className="h-4 w-5/6 rounded bg-surface-3" />
        <div className="h-4 w-4/6 rounded bg-surface-3" />
      </div>
    </div>
  );
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
  const [editing, setEditing] = useState(false);
  const [activeTab, setActiveTab] = useState<"details" | "stats" | "trace">("details");

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key !== "Escape" || editing) return;
      const active = document.activeElement;
      if (
        active instanceof HTMLTextAreaElement ||
        active instanceof HTMLInputElement ||
        active instanceof HTMLSelectElement
      ) {
        return;
      }
      onClose();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose, editing]);

  async function onDelete() {
    if (!task) return;
    if (!window.confirm(`Delete "${task.title}"? It will be moved to .trash/.`)) {
      return;
    }
    await deleteTask.mutateAsync(task.id);
    onClose();
  }

  async function onSend(message: string) {
    await replyTask.mutateAsync(message);
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
      <Modal onClose={onClose} className="z-30">
        <div
          className="flex h-full w-full max-w-5xl flex-col overflow-hidden border border-hairline bg-surface-1 shadow-lift sm:h-auto sm:max-h-[90vh] sm:rounded-lg"
          onClick={(e) => e.stopPropagation()}
        >
          {isLoading && <DetailSkeleton />}
          {error && (
            <div className="flex flex-col items-center gap-3 p-10 text-center">
              <p className="rounded border border-danger/40 bg-danger/15 px-4 py-3 text-sm text-danger">
                {error.message}
              </p>
              <button
                type="button"
                onClick={() => void refetch()}
                className="rounded border border-hairline-strong bg-canvas px-3 py-1.5 text-xs text-ink-muted transition hover:bg-surface-2 hover:text-ink"
              >
                Retry
              </button>
            </div>
          )}
          {task && (
            <>
              <header className="flex items-start justify-between gap-4 border-b border-hairline p-4">
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span
                      className={`rounded px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.18em] ${
                        STATE_BADGE[task.state] ?? STATE_BADGE.backlog
                      }`}
                    >
                      {task.state}
                    </span>
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
                    <span className="font-mono text-xs text-ink-faint">{task.id}</span>
                  </div>
                  <h2 className="mt-2 text-xl font-semibold leading-tight tracking-tight text-ink">
                    {task.title}
                  </h2>
                  <div className="mt-3 flex flex-wrap items-center gap-4 text-xs">
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
                <button
                  type="button"
                  onClick={onClose}
                  aria-label="Close"
                  className="rounded p-1 text-ink-muted transition hover:bg-surface-2 hover:text-ink"
                >
                  ✕
                </button>
              </header>

              <TaskActionBar
                taskState={task.state}
                isStarting={startTask.isPending}
                isStopping={stopTask.isPending}
                isDeleting={deleteTask.isPending}
                isArchiving={archiveTask.isPending}
                isMarkingDone={transitionTask.isPending}
                onStart={() => void onStart()}
                onStop={() => void onStop()}
                onEdit={() => setEditing(true)}
                onDelete={() => void onDelete()}
                onArchive={() => void onArchive()}
                onMarkDone={() => void onMarkDone()}
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
              </div>

              {/* Tab content */}
              {activeTab === "details" ? (
                <div className="flex min-h-0 flex-1 flex-col lg:flex-row">
                  <div className="flex min-h-0 min-w-0 flex-1 flex-col">
                    <div className="flex-1 space-y-6 overflow-x-hidden overflow-y-auto overscroll-contain p-4">
                      <section>
                        <h3 className="font-display text-[10px] font-semibold uppercase tracking-[0.2em] text-ink-faint">
                          Brief
                        </h3>
                        <div className="prose prose-sm dark:prose-invert mt-2 max-w-none prose-headings:text-ink prose-p:text-ink prose-strong:text-ink prose-a:text-accent-bright prose-code:text-accent-bright prose-pre:bg-canvas prose-pre:border prose-pre:border-hairline prose-pre:overflow-x-auto">
                          <ReactMarkdown remarkPlugins={[remarkGfm]}>{task.brief}</ReactMarkdown>
                        </div>
                      </section>

                      <ConversationStream task={task} />
                    </div>

                    <ChatInput
                      taskState={task.state}
                      waitingQuestion={task.waiting_question}
                      pendingCount={task.pending_messages.length}
                      isSending={replyTask.isPending}
                      error={chatError}
                      onSend={onSend}
                    />
                  </div>

                  <FilesPanel taskId={task.id} />
                </div>
              ) : activeTab === "stats" ? (
                <div className="flex min-h-0 flex-1 flex-col">
                  <StatsPanel taskId={task.id} />
                </div>
              ) : (
                <div className="flex min-h-0 flex-1 flex-col">
                  <TracePanel taskId={task.id} />
                </div>
              )}
            </>
          )}
        </div>
      </Modal>

      {editing && task && (
        <TaskForm
          heading="Edit task"
          initialTitle={task.title}
          initialBrief={task.brief}
          initialModel={task.agent_model}
          initialMode={task.agent_mode}
          submitting={updateTask.isPending}
          error={updateTask.error?.message ?? null}
          onCancel={() => setEditing(false)}
          onSubmit={async (body) => {
            await updateTask.mutateAsync({
              title: body.title,
              brief: body.brief,
              agent_model: body.agent_model,
              agent_mode: body.agent_mode,
            });
            setEditing(false);
          }}
        />
      )}
    </>
  );
}
