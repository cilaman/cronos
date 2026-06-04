import { useTask } from "../../hooks/useTasks";
import { ConversationStream } from "../ConversationStream";

interface ChildTaskDrawerProps {
  child_task_id: string | null;
  onClose?: () => void;
}

export function ChildTaskDrawer({ child_task_id, onClose }: ChildTaskDrawerProps) {
  const { data: task, isLoading } = useTask(child_task_id);

  // Render nothing when no task id is provided (R3 AC-2)
  if (child_task_id === null) return null;

  return (
    <aside
      data-testid="child-task-drawer"
      className="flex h-full w-80 flex-col border-l border-hairline bg-surface-1"
    >
      <div className="flex items-center justify-between border-b border-hairline px-3 py-2">
        <span className="font-display text-[10px] font-semibold uppercase tracking-[0.24em] text-ink-faint">
          Child Task
        </span>
        {onClose && (
          <button
            type="button"
            aria-label="Close drawer"
            onClick={onClose}
            className="rounded p-0.5 text-ink-faint hover:bg-surface-2 hover:text-ink"
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 16 16"
              fill="currentColor"
              className="h-3.5 w-3.5"
              aria-hidden
            >
              <path d="M3.72 3.72a.75.75 0 0 1 1.06 0L8 6.94l3.22-3.22a.75.75 0 1 1 1.06 1.06L9.06 8l3.22 3.22a.75.75 0 1 1-1.06 1.06L8 9.06l-3.22 3.22a.75.75 0 0 1-1.06-1.06L6.94 8 3.72 4.78a.75.75 0 0 1 0-1.06Z" />
            </svg>
          </button>
        )}
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto px-3 py-2">
        {isLoading ? (
          <div
            data-testid="child-task-drawer-skeleton"
            aria-label="Loading task"
            className="space-y-2 animate-pulse"
          >
            <div className="h-3 w-3/4 rounded bg-surface-2" />
            <div className="h-3 w-1/2 rounded bg-surface-2" />
            <div className="h-3 w-5/6 rounded bg-surface-2" />
          </div>
        ) : task ? (
          <ConversationStream task={task} />
        ) : (
          <p className="font-mono text-[11px] text-ink-faint">
            // task not found
          </p>
        )}
      </div>
    </aside>
  );
}
