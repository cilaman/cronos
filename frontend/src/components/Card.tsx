import { useSortable } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { cn } from "../utils/cn";
import { formatRelative } from "../utils/format";
import { SpaceTag } from "./ui/SpaceTag";
import type { AgentMode, TaskSummary, TaskState, TaskType } from "../types";

function IconGitPR({ className }: { className?: string }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width="12"
      height="12"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden="true"
    >
      <circle cx="18" cy="18" r="3" />
      <circle cx="6" cy="6" r="3" />
      <path d="M13 6h3a2 2 0 0 1 2 2v7" />
      <line x1="6" y1="9" x2="6" y2="21" />
    </svg>
  );
}

function IconFileText({ className }: { className?: string }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width="12"
      height="12"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden="true"
    >
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
      <polyline points="14 2 14 8 20 8" />
      <line x1="16" y1="13" x2="8" y2="13" />
      <line x1="16" y1="17" x2="8" y2="17" />
      <polyline points="10 9 9 9 8 9" />
    </svg>
  );
}

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
  dragDisabled?: boolean;
  onOpenTask?: (id: string) => void;
  blocksCount?: number;
  running?: boolean;
  /** Whether this goal card's child list is expanded. */
  expanded?: boolean;
  /** Called when the user clicks the expand chevron on a goal card. */
  onToggleExpand?: () => void;
}

export function Card({ task, onClick, compact = false, density = "default", isDragOverlay = false, dragDisabled = false, onOpenTask, blocksCount = 0, running = false, expanded = false, onToggleExpand }: Props) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } =
    useSortable({ id: task.id, disabled: isDragOverlay || dragDisabled });

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
  const childrenProgress = task.children_progress;
  const hasChildren = isGoal && (childrenProgress?.total ?? 0) > 0;

  const cardBorderStyle = {
    borderLeftColor: borderColor,
    borderLeftWidth: 3,
    ...(isGoal ? { borderTopWidth: 2 } : {}),
  };

  if (density === "tight") {
    return (
      <div
        ref={setNodeRef}
        style={style}
        {...(!isDragOverlay ? attributes : {})}
        {...(!isDragOverlay && !dragDisabled ? listeners : {})}
        data-task-type={taskType}
        data-density="tight"
        className={cn("group", isDragging && !isDragOverlay && "opacity-40")}
      >
        <button
          type="button"
          onClick={onClick}
          style={cardBorderStyle}
          className={cn(
            "relative flex min-h-[44px] w-full flex-col justify-center rounded-md border border-hairline bg-surface-2 py-2 pl-2.5 pr-3 text-left shadow-inset-hairline transition hover:-translate-y-px hover:border-hairline-strong hover:bg-surface-3 hover:shadow-lift focus:outline-none focus-visible:ring-1 focus-visible:ring-accent focus-visible:ring-offset-1 focus-visible:ring-offset-surface-1",
            isGoal && "border-t-ink",
          )}
        >
          {running && (
            <span
              className="absolute right-2 top-2 h-2 w-2 rounded-full bg-accent-bright anim-pulse-dot"
              aria-label="Running"
            />
          )}
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
            {isGoal && childrenProgress && childrenProgress.total > 0 && (
              <span className="font-mono text-[9px] text-ink-faint">
                {childrenProgress.done}/{childrenProgress.total}
              </span>
            )}
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
      <div
        role="button"
        tabIndex={0}
        onClick={onClick}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            onClick();
          }
        }}
        style={cardBorderStyle}
        className={cn(
          "relative block w-full cursor-pointer border border-hairline bg-surface-2 py-3 pl-2.5 pr-3 text-left shadow-inset-hairline transition hover:-translate-y-px hover:border-hairline-strong hover:bg-surface-3 hover:shadow-lift focus:outline-none focus-visible:ring-1 focus-visible:ring-accent focus-visible:ring-offset-1 focus-visible:ring-offset-surface-1",
          expanded && hasChildren ? "rounded-t-md" : "rounded-md",
          isGoal && "border-t-ink",
        )}
      >
        {running && (
          <span
            className="absolute right-2 top-2 h-2 w-2 rounded-full bg-accent-bright anim-pulse-dot"
            aria-label="Running"
          />
        )}
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

        <div className="mb-1.5 flex flex-wrap items-center gap-1.5">
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
          {task.space_autopilot === "enabled" && (
            <span className="inline-flex items-center rounded border border-hairline bg-surface-2 px-1 py-px font-mono text-[9px] font-semibold uppercase tracking-wide text-ink-faint">
              AUTO
            </span>
          )}
          {task.pr_url && (
            <a
              href={task.pr_url}
              target="_blank"
              rel="noopener noreferrer"
              title="Open pull request"
              onClick={(e) => e.stopPropagation()}
              className="inline-flex items-center text-ink-faint transition hover:text-accent-bright"
            >
              <IconGitPR />
            </a>
          )}
          {!task.pr_url && task.proposed_pr_path && (
            <button
              type="button"
              title="PROPOSED PR (no GitHub remote)"
              onClick={(e) => {
                e.stopPropagation();
                void navigator.clipboard.writeText(task.proposed_pr_path!);
              }}
              className="inline-flex items-center text-ink-faint transition hover:text-ink-muted"
            >
              <IconFileText />
            </button>
          )}
          {/* Expand chevron for goals with children */}
          {hasChildren && (
            <span
              role="button"
              tabIndex={0}
              aria-expanded={expanded}
              aria-label={expanded ? "Collapse children" : "Expand children"}
              onClick={(e) => {
                e.stopPropagation();
                onToggleExpand?.();
              }}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.stopPropagation();
                  onToggleExpand?.();
                }
              }}
              className="ml-auto flex cursor-pointer select-none items-center gap-1 font-mono text-[10px] text-ink-faint hover:text-ink-muted"
            >
              <svg
                width="6"
                height="8"
                viewBox="0 0 6 8"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.75"
                strokeLinecap="round"
                strokeLinejoin="round"
                aria-hidden="true"
                className={cn("transition-transform duration-100", expanded && "rotate-90")}
              >
                <path d="M1.5 1l3 3-3 3" />
              </svg>
              {childrenProgress!.total} children
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
        {isGoal && childrenProgress && childrenProgress.total > 0 && (
          <div className="mt-1.5">
            <span className="font-mono text-[10px] text-ink-faint">
              {childrenProgress.done} / {childrenProgress.total}
            </span>
            <div className="relative mt-1 h-0.5 w-full overflow-hidden rounded-full bg-surface-3">
              <div
                className="absolute inset-y-0 left-0 bg-accent"
                style={{ width: `${(childrenProgress.done / childrenProgress.total) * 100}%` }}
              />
              <div
                className="absolute inset-y-0 bg-amber-500"
                style={{
                  left: `${(childrenProgress.done / childrenProgress.total) * 100}%`,
                  width: `${(childrenProgress.waiting / childrenProgress.total) * 100}%`,
                }}
              />
            </div>
          </div>
        )}
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
      </div>

      {/* Expanded children list — rendered outside the card body div so the inline children look like a panel attached underneath */}
      {expanded && hasChildren && (childrenProgress?.items?.length ?? 0) > 0 && (
        <div
          style={{ borderLeftColor: borderColor, borderLeftWidth: 3 }}
          className="rounded-b-md border border-t-0 border-hairline bg-surface-2 px-2 pb-2 pt-1"
        >
          {childrenProgress!.items!.map((child) => {
            const childPStyle = PRIORITY_STYLES[child.priority] ?? PRIORITY_STYLES[3];
            return (
              <button
                key={child.id}
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  onOpenTask?.(child.id);
                }}
                className="flex w-full items-center gap-1.5 rounded px-1 py-1 text-left transition hover:bg-surface-3 focus:outline-none focus-visible:ring-1 focus-visible:ring-accent"
              >
                <span
                  className={cn("h-1.5 w-1.5 shrink-0 rounded-full", STATE_DOT_STYLES[child.state])}
                  aria-label={child.state}
                />
                <span className="flex-1 truncate text-xs text-ink-muted">{child.title}</span>
                <span className="shrink-0 font-mono text-[9px] text-ink-faint">
                  {formatCompactAge(child.updated_at)}
                </span>
                <span
                  className={cn(
                    "inline-flex shrink-0 items-center rounded border px-1 py-px font-mono text-[9px] font-semibold uppercase tracking-wide",
                    childPStyle.badge,
                  )}
                >
                  P{child.priority}
                </span>
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
