import { useDroppable } from "@dnd-kit/core";
import { SortableContext, verticalListSortingStrategy } from "@dnd-kit/sortable";
import { cn } from "../utils/cn";
import { EmptyState } from "./ui/EmptyState";
import { StickyToolbar } from "./ui/StickyToolbar";
import { Card } from "./Card";
import type { TaskState, TaskSummary } from "../types";

interface Props {
  state: TaskState;
  label: string;
  tasks: TaskSummary[];
  onOpen: (id: string) => void;
  onAdd: () => void;
  compact?: boolean;
  onOpenTask?: (id: string) => void;
  blocksCountMap?: Record<string, number>;
}

export function Lane({ state, label, tasks, onOpen, onAdd, compact = false, onOpenTask, blocksCountMap }: Props) {
  const { isOver, setNodeRef } = useDroppable({ id: state });
  const taskIds = tasks.map((t) => t.id);

  return (
    <section
      ref={setNodeRef}
      className={cn(
        "flex min-h-0 flex-col rounded-lg shadow-inset-hairline transition-colors",
        isOver ? "bg-accent/10 ring-1 ring-accent-bright" : "bg-surface-1",
      )}
    >
      <StickyToolbar className="z-10 h-10 rounded-t-lg px-3">
        <div className="flex items-baseline gap-2">
          <h2 className="font-display text-[11px] font-semibold uppercase tracking-[0.18em] text-ink-muted">
            {label}
          </h2>
          <span className="font-mono text-xs tabular-nums text-ink-faint">
            {String(tasks.length).padStart(2, "0")}
          </span>
        </div>
        {state === "backlog" && (
          <button
            type="button"
            onClick={onAdd}
            aria-label="New task"
            className="rounded p-1 text-ink-muted transition hover:bg-surface-2 hover:text-accent-bright focus:outline-none focus-visible:ring-1 focus-visible:ring-accent"
          >
            <span aria-hidden className="text-lg leading-none">＋</span>
          </button>
        )}
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
              />
            ))
          )}
        </SortableContext>
      </div>
    </section>
  );
}
