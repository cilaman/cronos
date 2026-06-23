import { useDroppable } from "@dnd-kit/core";
import { SortableContext, verticalListSortingStrategy } from "@dnd-kit/sortable";
import { cn } from "../utils/cn";
import { EmptyState } from "./ui/EmptyState";
import { StickyToolbar } from "./ui/StickyToolbar";
import { IconButton } from "./ui/IconButton";
import { Card } from "./Card";
import type { TaskSummary } from "../types";

interface Props {
  /**
   * The state identifier for this lane. Must come from exactly one lane-system
   * constant — use `LANES[n].state` for the Tasks board, or `FEATURE_LANES[n].state`
   * for the Features board. Never mix values across lane systems.
   *
   * Widened to `string` (from `TaskState`) so the same component can serve both
   * the Tasks board (TaskState values) and the Features board (FeatureState values).
   */
  state: string;
  label: string;
  tasks: TaskSummary[];
  onOpen: (id: string) => void;
  onAdd: () => void;
  compact?: boolean;
  /**
   * Whether to show the "+ New task" add button in the lane header.
   * Defaults to `true` when `state === "backlog"`, preserving the existing
   * Tasks-board behaviour at all existing call-sites.
   */
  showAdd?: boolean;
  onOpenTask?: (id: string) => void;
  blocksCountMap?: Record<string, number>;
  isRunning?: (id: string) => boolean;
  expandedGoals?: Set<string>;
  onToggleGoal?: (id: string) => void;
  onHideLane?: (state: string) => void;
}

export function Lane({ state, label, tasks, onOpen, onAdd, compact = false, showAdd, onOpenTask, blocksCountMap, isRunning, expandedGoals, onToggleGoal, onHideLane }: Props) {
  const { isOver, setNodeRef } = useDroppable({ id: state });
  const taskIds = tasks.map((t) => t.id);
  const anyRunning = isRunning !== undefined && tasks.some((t) => isRunning(t.id));

  // Default: show the add button on the backlog lane (backward-compatible with Tasks board).
  const shouldShowAdd = showAdd !== undefined ? showAdd : state === "backlog";

  return (
    <section
      ref={setNodeRef}
      className={cn(
        "group/lane flex min-h-0 flex-col rounded-lg shadow-inset-hairline transition-colors",
        isOver ? "bg-accent/10 ring-1 ring-accent-bright" : "bg-surface-1",
      )}
    >
      <StickyToolbar className="z-10 h-10 rounded-t-lg px-3">
        <div className="flex items-center gap-2">
          <h2 className="font-display text-[11px] font-semibold uppercase tracking-[0.18em] text-ink-muted">
            {label}
          </h2>
          <span className="font-mono text-xs tabular-nums text-ink-faint">
            {String(tasks.length).padStart(2, "0")}
          </span>
          {anyRunning && (
            <span
              className="h-2 w-2 rounded-full bg-accent-bright anim-pulse-dot"
              aria-label="Task running"
            />
          )}
        </div>
        <div className="ml-auto flex items-center gap-1">
          {shouldShowAdd && (
            <IconButton
              aria-label="New task"
              size="compact"
              onClick={onAdd}
            >
              <span aria-hidden className="text-lg leading-none">＋</span>
            </IconButton>
          )}
          {onHideLane && (
            <IconButton
              aria-label={`Hide ${label} lane`}
              title={`Hide ${label}`}
              size="compact"
              onClick={() => onHideLane(state)}
            >
              <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" aria-hidden="true">
                <line x1="3" y1="3" x2="9" y2="9" />
                <line x1="9" y1="3" x2="3" y2="9" />
              </svg>
            </IconButton>
          )}
        </div>
      </StickyToolbar>
      <div className="flex-1 space-y-2 overflow-x-hidden overflow-y-auto p-2">
        <SortableContext items={taskIds} strategy={verticalListSortingStrategy}>
          {tasks.length === 0 ? (
            <EmptyState title="No tasks" />
          ) : (
            tasks.map((task) => (
              <Card
                key={task.id}
                task={task}
                onClick={() => onOpen(task.id)}
                compact={compact}
                onOpenTask={onOpenTask}
                blocksCount={blocksCountMap?.[task.id] ?? 0}
                running={isRunning?.(task.id)}
                expanded={expandedGoals?.has(task.id) ?? false}
                onToggleExpand={onToggleGoal ? () => onToggleGoal(task.id) : undefined}
              />
            ))
          )}
        </SortableContext>
      </div>
    </section>
  );
}
