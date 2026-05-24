import { useSortable } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { cn } from "../utils/cn";
import { formatRelative } from "../utils/format";
import { SpaceTag } from "./ui/SpaceTag";
import type { AgentMode, TaskSummary, TaskState, TaskType } from "../types";

const PRIORITY_STYLES: Record<number, { badge: string; dot: string }> = {
  1: {
    badge: "border-red-200 bg-red-50 text-red-600 dark:border-red-400/30 dark:bg-red-400/10 dark:text-red-400",
    dot: "bg-red-500",
  },
  2: {
    badge: "border-orange-200 bg-orange-50 text-orange-600 dark:border-orange-400/30 dark:bg-orange-400/10 dark:text-orange-400",
    dot: "bg-orange-500",
  },
  3: {
    badge: "border-amber-200 bg-amber-50 text-amber-600 dark:border-amber-400/30 dark:bg-amber-400/10 dark:text-amber-400",
    dot: "bg-amber-500",
  },
  4: {
    badge: "border-teal-200 bg-teal-50 text-teal-600 dark:border-teal-400/30 dark:bg-teal-400/10 dark:text-teal-400",
    dot: "bg-teal-500",
  },
  5: {
    badge: "border-hairline bg-surface-2 text-ink-faint",
    dot: "bg-ink-faint",
  },
};

const MODE_STYLES: Record<AgentMode, string> = {
  plan: "border-indigo-200 bg-indigo-50 text-indigo-600 dark:border-indigo-400/30 dark:bg-indigo-400/10 dark:text-indigo-400",
  auto: "border-hairline bg-surface-2 text-ink-faint",
  ask: "border-violet-200 bg-violet-50 text-violet-600 dark:border-violet-400/30 dark:bg-violet-400/10 dark:text-violet-400",
};

const MODE_LABELS: Record<AgentMode, string> = {
  plan: "Plan",
  auto: "Auto",
  ask: "Ask",
};

const TYPE_BADGE_STYLES: Partial<Record<TaskType, string>> = {
  goal: "border-violet-200 bg-violet-50 text-violet-700 dark:border-violet-400/30 dark:bg-violet-400/10 dark:text-violet-400",
  issue: "border-orange-200 bg-orange-50 text-orange-600 dark:border-orange-400/30 dark:bg-orange-400/10 dark:text-orange-400",
};

const STATE_DOT_STYLES: Record<TaskState, string> = {
  backlog: "bg-ink-faint",
  active: "bg-emerald-500",
  waiting: "bg-amber-500",
  done: "bg-sky-500",
  archived: "bg-ink-faint/40",
};

function formatCompactAge(iso: string | null | undefined): string {
  if (!iso) return "—";
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "—";
  const seconds = Math.round((Date.now() - then) / 1000);
  const abs = Math.abs(seconds);
  if (abs < 60) return "now";
  if (abs < 3600) return `${Math.round(seconds / 60)}m`;
  if (abs < 86_400) return `${Math.round(seconds / 3600)}h`;
  if (abs < 86_400 * 30) return `${Math.round(seconds / 86_400)}d`;
  if (abs < 86_400 * 365) return `${Math.round(seconds / (86_400 * 30))}mo`;
  return `${Math.round(seconds / (86_400 * 365))}y`;
}

interface Props {
  task: TaskSummary;
  onClick: () => void;
  compact?: boolean;
  density?: "default" | "compact" | "tight";
  isDragOverlay?: boolean;
  onOpenTask?: (id: string) => void;
  blocksCount?: number;
}

export function Card({ task, onClick, compact = false, density = "default", isDragOverlay = false, onOpenTask, blocksCount = 0 }: Props) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } =
    useSortable({ id: task.id, disabled: isDragOverlay });

  const style =
    !isDragOverlay
      ? {
          transform: CSS.Transform.toString(transform),
          transition,
        }
      : undefined;

  const borderColor = task.space_color ?? "rgb(var(--color-hairline-strong))";
  const priority = task.priority ?? 3;
  const pStyle = PRIORITY_STYLES[priority] ?? PRIORITY_STYLES[3];
  const mode = task.agent_mode ?? "auto";
  const showModeBadge = !compact || mode !== "auto";
  const taskType = task.type ?? "task";
  const isGoal = taskType === "goal";
  const typeBadgeStyle = TYPE_BADGE_STYLES[taskType];
  const blockedBy = task.unmet_dependencies ?? [];

  if (density === "tight") {
    return (
      <div
        ref={setNodeRef}
        style={style}
        {...(!isDragOverlay ? attributes : {})}
        data-task-type={taskType}
        data-density="tight"
        className={cn("group", isDragging && !isDragOverlay && "opacity-40")}
      >
        <button
          type="button"
          onClick={onClick}
          style={{
            borderLeftColor: borderColor,
            borderLeftWidth: 3,
            ...(isGoal ? { borderTopWidth: 2 } : {}),
          }}
          className={cn(
            "relative flex min-h-[44px] w-full flex-col justify-center rounded-md border border-hairline bg-surface-2 py-2 pl-2.5 pr-3 text-left shadow-inset-hairline transition hover:-translate-y-px hover:border-hairline-strong hover:bg-surface-3 hover:shadow-lift focus:outline-none focus-visible:ring-1 focus-visible:ring-accent focus-visible:ring-offset-1 focus-visible:ring-offset-surface-1",
            isGoal && "border-t-ink",
          )}
        >
          <h3 className="truncate text-sm font-semibold leading-snug text-ink">{task.title}</h3>
          <div className="mt-0.5 flex flex-wrap items-center gap-x-1.5 gap-y-0.5">
            <span
              className={cn("h-1.5 w-1.5 shrink-0 rounded-full", STATE_DOT_STYLES[task.state])}
              aria-label={task.state}
            />
            <span
              className={cn("h-1.5 w-1.5 shrink-0 rounded-full", pStyle.dot)}
              aria-label={`priority ${priority}`}
            />
            <span className="font-mono text-[9px] uppercase tracking-[0.1em] text-ink-faint">
              {formatCompactAge(task.updated_at)}
            </span>
            {typeBadgeStyle && (
              <span
                className={cn(
                  "inline-flex items-center rounded border px-1 py-px font-mono text-[9px] font-semibold uppercase tracking-wide",
                  typeBadgeStyle,
                )}
              >
                {taskType}
              </span>
            )}
            {blockedBy.length > 0 && (
              <span
                title={blockedBy.map((d) => d.title).join(", ")}
                className="inline-flex items-center rounded border border-amber-200 bg-amber-50 px-1 py-px font-mono text-[9px] font-semibold uppercase tracking-wide text-amber-700 dark:border-amber-400/30 dark:bg-amber-400/10 dark:text-amber-400"
              >
                Blocked by {blockedBy.length}
              </span>
            )}
            {blocksCount > 0 && (
              <span className="inline-flex items-center rounded border border-hairline bg-surface-2 px-1 py-px font-mono text-[9px] font-semibold uppercase tracking-wide text-ink-muted">
                Blocks {blocksCount}
              </span>
            )}
          </div>
        </button>
      </div>
    );
  }

  return (
    <div
      ref={setNodeRef}
      style={style}
      {...(!isDragOverlay ? attributes : {})}
      data-task-type={taskType}
      data-density={density}
      className={cn("group", isDragging && !isDragOverlay && "opacity-40")}
    >
      <button
        type="button"
        onClick={onClick}
        style={{
          borderLeftColor: borderColor,
          borderLeftWidth: 3,
          ...(isGoal ? { borderTopWidth: 2 } : {}),
        }}
        className={cn(
          "relative block w-full rounded-md border border-hairline bg-surface-2 py-3 pl-2.5 pr-3 text-left shadow-inset-hairline transition hover:-translate-y-px hover:border-hairline-strong hover:bg-surface-3 hover:shadow-lift focus:outline-none focus-visible:ring-1 focus-visible:ring-accent focus-visible:ring-offset-1 focus-visible:ring-offset-surface-1",
          isGoal && "border-t-ink",
        )}
      >
        <span
          {...(!isDragOverlay ? listeners : {})}
          className="absolute right-1.5 top-1.5 touch-none cursor-grab rounded p-0.5 text-ink-faint opacity-0 transition-opacity group-hover:opacity-100 active:cursor-grabbing"
          aria-label="Drag"
          onClick={(e) => e.stopPropagation()}
        >
          <svg width="10" height="14" viewBox="0 0 10 14" fill="currentColor" aria-hidden="true">
            <circle cx="2" cy="2" r="1.5"/><circle cx="8" cy="2" r="1.5"/>
            <circle cx="2" cy="7" r="1.5"/><circle cx="8" cy="7" r="1.5"/>
            <circle cx="2" cy="12" r="1.5"/><circle cx="8" cy="12" r="1.5"/>
          </svg>
        </span>

        <div className="mb-1.5 flex items-center gap-1.5">
          <span
            className={cn(
              "inline-flex items-center rounded border px-1 py-px font-mono text-[9px] font-semibold uppercase tracking-wide",
              pStyle.badge,
            )}
          >
            P{priority}
          </span>
          {typeBadgeStyle && (
            <span
              className={cn(
                "inline-flex items-center rounded border px-1 py-px font-mono text-[9px] font-semibold uppercase tracking-wide",
                typeBadgeStyle,
              )}
            >
              {taskType}
            </span>
          )}
          {task.space_name && (
            <SpaceTag
              color={task.space_color}
              icon={task.space_icon}
              name={task.space_name}
              size="xs"
            />
          )}
          {showModeBadge && (
            <span
              className={cn(
                "inline-flex items-center rounded border px-1 py-px font-mono text-[9px] font-semibold uppercase tracking-wide",
                MODE_STYLES[mode],
              )}
            >
              {MODE_LABELS[mode]}
            </span>
          )}
        </div>

        {task.parent_id && task.parent_title && (
          <span
            role="button"
            tabIndex={0}
            onClick={(e) => {
              e.stopPropagation();
              onOpenTask?.(task.parent_id!);
            }}
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === " ") {
                e.stopPropagation();
                onOpenTask?.(task.parent_id!);
              }
            }}
            className="mb-1 block cursor-pointer truncate font-mono text-[10px] uppercase tracking-[0.1em] text-ink-faint hover:text-ink-muted"
          >
            ↑ {task.parent_title}
          </span>
        )}

        <h3 className="text-sm font-semibold leading-snug text-ink">{task.title}</h3>
        {task.brief_preview && !compact && (
          <p className="mt-1.5 hidden text-xs leading-relaxed text-ink-muted line-clamp-3 sm:block">
            {task.brief_preview}
          </p>
        )}
        {task.waiting_question && !compact && (
          <p className="mt-2 hidden rounded border border-amber-300 bg-amber-50 px-2 py-1 text-xs text-amber-800 sm:block dark:border-amber-400/30 dark:bg-amber-400/10 dark:text-amber-300">
            <span className="font-semibold uppercase tracking-wide text-[10px]">Q&nbsp;</span>
            {task.waiting_question}
          </p>
        )}

        {(blockedBy.length > 0 || blocksCount > 0) && (
          <div className="mt-1.5 flex flex-wrap gap-1">
            {blockedBy.length > 0 && (
              <span
                title={blockedBy.map((d) => d.title).join(", ")}
                className="inline-flex items-center rounded border border-amber-200 bg-amber-50 px-1 py-px font-mono text-[9px] font-semibold uppercase tracking-wide text-amber-700 dark:border-amber-400/30 dark:bg-amber-400/10 dark:text-amber-400"
              >
                Blocked by {blockedBy.length}
              </span>
            )}
            {blocksCount > 0 && (
              <span className="inline-flex items-center rounded border border-hairline bg-surface-2 px-1 py-px font-mono text-[9px] font-semibold uppercase tracking-wide text-ink-muted">
                Blocks {blocksCount}
              </span>
            )}
          </div>
        )}

        <p className="mt-2 font-mono text-[10px] uppercase tracking-[0.15em] text-ink-faint">
          {formatRelative(task.updated_at)}
        </p>
      </button>
    </div>
  );
}
