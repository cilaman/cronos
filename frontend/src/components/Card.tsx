import { useSortable } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { cn } from "../utils/cn";
import { formatRelative } from "../utils/format";
import { SpaceTag } from "./ui/SpaceTag";
import type { AgentMode, TaskSummary } from "../types";

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

interface Props {
  task: TaskSummary;
  onClick: () => void;
  compact?: boolean;
  isDragOverlay?: boolean;
}

export function Card({ task, onClick, compact = false, isDragOverlay = false }: Props) {
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

  return (
    <div
      ref={setNodeRef}
      style={style}
      {...(!isDragOverlay ? attributes : {})}
      className={cn("group", isDragging && !isDragOverlay && "opacity-40")}
    >
      <button
        type="button"
        onClick={onClick}
        style={{ borderLeftColor: borderColor, borderLeftWidth: 3 }}
        className="relative block w-full rounded-md border border-hairline bg-surface-2 py-3 pl-2.5 pr-3 text-left shadow-inset-hairline transition hover:-translate-y-px hover:border-hairline-strong hover:bg-surface-3 hover:shadow-lift focus:outline-none focus-visible:ring-1 focus-visible:ring-accent focus-visible:ring-offset-1 focus-visible:ring-offset-surface-1"
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
        <p className="mt-2 font-mono text-[10px] uppercase tracking-[0.15em] text-ink-faint">
          {formatRelative(task.updated_at)}
        </p>
      </button>
    </div>
  );
}
