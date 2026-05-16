import type { TaskState } from "../types";

interface Props {
  taskState: TaskState;
  isStarting: boolean;
  isStopping: boolean;
  isDeleting: boolean;
  onStart: () => void;
  onStop: () => void;
  onEdit: () => void;
  onDelete: () => void;
}

const ICON_BUTTON =
  "flex h-8 w-8 items-center justify-center rounded border text-sm transition disabled:cursor-not-allowed disabled:opacity-50";

export function TaskActionBar({
  taskState,
  isStarting,
  isStopping,
  isDeleting,
  onStart,
  onStop,
  onEdit,
  onDelete,
}: Props) {
  const showStart = taskState === "backlog";
  const showStop = taskState === "active";

  return (
    <div className="flex items-center gap-1 border-b border-hairline bg-pitch-50/40 px-3 py-2">
      {showStart && (
        <button
          type="button"
          onClick={onStart}
          disabled={isStarting}
          title="Start agent"
          aria-label="Start agent"
          className={`${ICON_BUTTON} border-moss bg-moss text-bone hover:bg-moss-bright hover:shadow-moss-glow`}
        >
          {isStarting ? "…" : "▶"}
        </button>
      )}
      {showStop && (
        <button
          type="button"
          onClick={onStop}
          disabled={isStopping}
          title="Stop agent"
          aria-label="Stop agent"
          className={`${ICON_BUTTON} border-oxblood bg-oxblood text-bone hover:bg-oxblood/80`}
        >
          {isStopping ? "…" : "■"}
        </button>
      )}
      <button
        type="button"
        onClick={onEdit}
        title="Edit task"
        aria-label="Edit task"
        className={`${ICON_BUTTON} border-hairline-strong bg-pitch text-bone-muted hover:bg-pitch-100 hover:text-bone`}
      >
        ✎
      </button>
      <button
        type="button"
        onClick={onDelete}
        disabled={isDeleting}
        title="Delete task"
        aria-label="Delete task"
        className={`${ICON_BUTTON} border-hairline-strong bg-pitch text-bone-muted hover:border-oxblood hover:bg-oxblood/15 hover:text-oxblood`}
      >
        ⊘
      </button>
    </div>
  );
}
