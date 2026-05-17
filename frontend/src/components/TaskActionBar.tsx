import type { TaskState } from "../types";

interface Props {
  taskState: TaskState;
  isStarting: boolean;
  isStopping: boolean;
  isDeleting: boolean;
  isArchiving: boolean;
  isMarkingDone: boolean;
  onStart: () => void;
  onStop: () => void;
  onEdit: () => void;
  onDelete: () => void;
  onArchive: () => void;
  onMarkDone: () => void;
}

const ICON_BUTTON =
  "flex h-8 w-8 items-center justify-center rounded border text-sm transition disabled:cursor-not-allowed disabled:opacity-50";

export function TaskActionBar({
  taskState,
  isStarting,
  isStopping,
  isDeleting,
  isArchiving,
  isMarkingDone,
  onStart,
  onStop,
  onEdit,
  onDelete,
  onArchive,
  onMarkDone,
}: Props) {
  const showStart = taskState === "backlog";
  const showStop = taskState === "active";
  const showArchive = taskState === "done" || taskState === "waiting";
  const showMarkDone = taskState === "waiting";
  const archiveLabel = taskState === "waiting" ? "Cancel task (archive)" : "Archive task";

  return (
    <div className="flex items-center gap-1 border-b border-hairline bg-surface-1/40 px-3 py-2">
      {showStart && (
        <button
          type="button"
          onClick={onStart}
          disabled={isStarting}
          title="Start agent"
          aria-label="Start agent"
          className={`${ICON_BUTTON} border-accent bg-accent text-canvas hover:bg-accent-bright hover:shadow-accent-glow`}
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
          className={`${ICON_BUTTON} border-danger bg-danger text-ink hover:bg-danger/80`}
        >
          {isStopping ? "…" : "■"}
        </button>
      )}
      {showMarkDone && (
        <button
          type="button"
          onClick={onMarkDone}
          disabled={isMarkingDone}
          title="Mark as done"
          aria-label="Mark task as done"
          className={`${ICON_BUTTON} border-accent bg-accent/15 text-accent-bright hover:bg-accent/25`}
        >
          {isMarkingDone ? "…" : "✓"}
        </button>
      )}
      {showArchive && (
        <button
          type="button"
          onClick={onArchive}
          disabled={isArchiving}
          title={archiveLabel}
          aria-label={archiveLabel}
          className={`${ICON_BUTTON} border-hairline-strong bg-canvas text-ink-muted hover:bg-surface-2 hover:text-ink`}
        >
          {isArchiving ? "…" : "↓"}
        </button>
      )}
      <button
        type="button"
        onClick={onEdit}
        title="Edit task"
        aria-label="Edit task"
        className={`${ICON_BUTTON} border-hairline-strong bg-canvas text-ink-muted hover:bg-surface-2 hover:text-ink`}
      >
        ✎
      </button>
      <button
        type="button"
        onClick={onDelete}
        disabled={isDeleting}
        title="Delete task"
        aria-label="Delete task"
        className={`${ICON_BUTTON} border-hairline-strong bg-canvas text-ink-muted hover:border-danger hover:bg-danger/15 hover:text-danger`}
      >
        ⊘
      </button>
    </div>
  );
}
