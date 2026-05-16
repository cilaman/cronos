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
        className="block w-full rounded-md border border-hairline bg-surface-2 p-3 text-left shadow-inset-hairline transition hover:-translate-y-px hover:border-hairline-strong hover:bg-surface-3 hover:shadow-lift focus:outline-none focus-visible:ring-1 focus-visible:ring-accent focus-visible:ring-offset-1 focus-visible:ring-offset-surface-1"
      >
        <h3 className="text-sm font-semibold leading-snug text-ink">{task.title}</h3>
        {task.brief_preview && (
          <p className="mt-1.5 text-xs leading-relaxed text-ink-muted line-clamp-3">
            {task.brief_preview}
          </p>
        )}
        {task.waiting_question && (
          <p className="mt-2 rounded border border-amber-400/30 bg-amber-400/10 px-2 py-1 text-xs text-amber-300">
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
