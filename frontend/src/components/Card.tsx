import { useDraggable } from "@dnd-kit/core";
import type { TaskSummary } from "../types";

function formatRelative(iso: string): string {
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "";
  const seconds = Math.round((Date.now() - then) / 1000);
  const abs = Math.abs(seconds);
  if (abs < 60) return "just now";
  if (abs < 3600) return `${Math.round(seconds / 60)}m ago`;
  if (abs < 86_400) return `${Math.round(seconds / 3600)}h ago`;
  return `${Math.round(seconds / 86_400)}d ago`;
}

interface Props {
  task: TaskSummary;
  onClick: () => void;
}

export function Card({ task, onClick }: Props) {
  const { attributes, listeners, setNodeRef, transform, isDragging } =
    useDraggable({ id: task.id });

  const style = transform
    ? {
        transform: `translate3d(${transform.x}px, ${transform.y}px, 0)`,
        zIndex: 20,
      }
    : undefined;

  return (
    <div
      ref={setNodeRef}
      style={style}
      {...listeners}
      {...attributes}
      className={`touch-none ${isDragging ? "opacity-50" : ""}`}
    >
      <button
        type="button"
        onClick={onClick}
        className="block w-full rounded-md border border-slate-200 bg-white p-3 text-left shadow-sm hover:border-slate-300 hover:shadow focus:outline-none focus:ring-2 focus:ring-emerald-500"
      >
        <h3 className="text-sm font-semibold text-slate-900">{task.title}</h3>
        {task.brief_preview && (
          <p className="mt-1 text-xs text-slate-600 line-clamp-3">{task.brief_preview}</p>
        )}
        {task.waiting_question && (
          <p className="mt-2 rounded bg-amber-50 px-2 py-1 text-xs text-amber-900">
            <span className="font-medium">Q:</span> {task.waiting_question}
          </p>
        )}
        <p className="mt-2 text-[10px] uppercase tracking-wide text-slate-400">
          {formatRelative(task.updated_at)}
        </p>
      </button>
    </div>
  );
}
