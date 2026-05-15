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
      className={`flex min-h-0 flex-col rounded-lg ${
        isOver ? "bg-emerald-50 ring-2 ring-emerald-300" : "bg-slate-100"
      }`}
    >
      <header className="sticky top-0 z-10 flex items-center justify-between rounded-t-lg bg-slate-100/95 px-3 py-2 backdrop-blur">
        <div className="flex items-center gap-2">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-600">
            {label}
          </h2>
          <span className="rounded-full bg-slate-200 px-2 py-0.5 text-xs font-medium text-slate-700">
            {tasks.length}
          </span>
        </div>
        {state === "backlog" && (
          <button
            type="button"
            onClick={onAdd}
            aria-label="New task"
            className="rounded p-1 text-slate-500 hover:bg-slate-200 hover:text-slate-800"
          >
            <span aria-hidden className="text-lg leading-none">＋</span>
          </button>
        )}
      </header>
      <div className="flex-1 space-y-2 overflow-y-auto p-2">
        {tasks.length === 0 ? (
          <p className="px-2 py-3 text-xs text-slate-400">No tasks</p>
        ) : (
          tasks.map((task) => (
            <Card key={task.id} task={task} onClick={() => onOpen(task.id)} />
          ))
        )}
      </div>
    </section>
  );
}
