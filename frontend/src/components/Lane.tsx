import { useDroppable } from "@dnd-kit/core";
import type { TaskState, TaskSummary } from "../types";
import { Card } from "./Card";

interface Props {
  state: TaskState;
  label: string;
  tasks: TaskSummary[];
  onOpen: (id: string) => void;
  onAdd: () => void;
}

export function Lane({ state, label, tasks, onOpen, onAdd }: Props) {
  const { isOver, setNodeRef } = useDroppable({ id: state });
  return (
    <section
      ref={setNodeRef}
      className={`flex min-h-0 flex-col rounded-lg shadow-inset-hairline transition-colors ${
        isOver
          ? "bg-accent/10 ring-1 ring-accent-bright"
          : "bg-surface-1"
      }`}
    >
      <header className="sticky top-0 z-10 flex items-center justify-between rounded-t-lg border-b border-hairline bg-surface-1/95 px-3 py-2 backdrop-blur">
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
      </header>
      <div className="flex-1 space-y-2 overflow-y-auto p-2">
        {tasks.length === 0 ? (
          <p className="px-2 py-3 text-xs italic text-ink-faint">No tasks</p>
        ) : (
          tasks.map((task) => (
            <Card key={task.id} task={task} onClick={() => onOpen(task.id)} />
          ))
        )}
      </div>
    </section>
  );
}
