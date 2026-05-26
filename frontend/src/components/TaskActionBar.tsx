import { IconButton } from "./ui/IconButton";
import type { TaskState } from "../types";

interface Props {
  taskState: TaskState;
  isStarting: boolean;
  isStopping: boolean;
  isDeleting: boolean;
  isArchiving: boolean;
  isMarkingDone: boolean;
  isSendingToBacklog: boolean;
  onStart: () => void;
  onStop: () => void;
  onEdit: () => void;
  onDelete: () => void;
  onArchive: () => void;
  onMarkDone: () => void;
  onSendToBacklog: () => void;
}

export function TaskActionBar({
  taskState,
  isStarting,
  isStopping,
  isDeleting,
  isArchiving,
  isMarkingDone,
  isSendingToBacklog,
  onStart,
  onStop,
  onEdit,
  onDelete,
  onArchive,
  onMarkDone,
  onSendToBacklog,
}: Props) {
  const showStart = taskState === "backlog";
  const showStop = taskState === "active";
  const showArchive = taskState === "done" || taskState === "waiting";
  const showMarkDone = taskState === "waiting" || taskState === "archived";
  const showSendToBacklog =
    taskState === "waiting" || taskState === "done" || taskState === "archived";
  const archiveLabel = taskState === "waiting" ? "Cancel task (archive)" : "Archive task";

  return (
    <div className="flex items-center gap-1 border-b border-hairline bg-surface-1/40 px-3 py-2">
      {showStart && (
        <IconButton
          variant="accent"
          onClick={onStart}
          disabled={isStarting}
          loading={isStarting}
          title="Start agent"
          aria-label="Start agent"
        >
          ▶
        </IconButton>
      )}
      {showStop && (
        <IconButton
          variant="danger"
          onClick={onStop}
          disabled={isStopping}
          loading={isStopping}
          title="Stop agent"
          aria-label="Stop agent"
        >
          ■
        </IconButton>
      )}
      {showMarkDone && (
        <IconButton
          variant="accent-soft"
          onClick={onMarkDone}
          disabled={isMarkingDone}
          loading={isMarkingDone}
          title="Mark as done"
          aria-label="Mark task as done"
        >
          ✓
        </IconButton>
      )}
      {showSendToBacklog && (
        <IconButton
          variant="default"
          onClick={onSendToBacklog}
          disabled={isSendingToBacklog}
          loading={isSendingToBacklog}
          title="Send to backlog"
          aria-label="Send task to backlog"
        >
          ↩
        </IconButton>
      )}
      {showArchive && (
        <IconButton
          variant="default"
          onClick={onArchive}
          disabled={isArchiving}
          loading={isArchiving}
          title={archiveLabel}
          aria-label={archiveLabel}
        >
          ↓
        </IconButton>
      )}
      <IconButton
        variant="default"
        onClick={onEdit}
        title="Edit task"
        aria-label="Edit task"
      >
        ✎
      </IconButton>
      <IconButton
        variant="danger-hover"
        onClick={onDelete}
        disabled={isDeleting}
        loading={isDeleting}
        title="Delete task"
        aria-label="Delete task"
      >
        ⊘
      </IconButton>
    </div>
  );
}
