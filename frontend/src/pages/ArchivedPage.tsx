import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Detail } from "../components/Detail";
import { SpaceFilterDropdown } from "../components/SpaceFilterDropdown";
import { EmptyState } from "../components/ui/EmptyState";
import { IconButton } from "../components/ui/IconButton";
import { SpaceTag } from "../components/ui/SpaceTag";
import { StickyToolbar } from "../components/ui/StickyToolbar";
import { useDeleteTask, useArchivedTasks, useUnarchiveTask } from "../hooks/useTasks";
import { formatRelative } from "../utils/format";
import type { TaskSummary } from "../types";

interface RowProps {
  task: TaskSummary;
  onOpen: (id: string) => void;
  unarchivePending: boolean;
  deletePending: boolean;
  onUnarchive: () => void;
  onDelete: () => void;
}

function ArchivedRow({ task, onOpen, unarchivePending, deletePending, onUnarchive, onDelete }: RowProps) {
  const borderColor = task.space_color ?? "rgb(var(--color-hairline-strong))";

  return (
    <div className="group flex items-stretch border-b border-hairline transition-colors hover:bg-surface-1 last:border-b-0">
      <div
        className="w-0.5 shrink-0 self-stretch rounded-l"
        style={{ backgroundColor: borderColor }}
        aria-hidden
      />
      <button
        type="button"
        onClick={() => onOpen(task.id)}
        className="min-w-0 flex-1 py-3 pl-3 pr-2 text-left focus:outline-none focus-visible:ring-1 focus-visible:ring-inset focus-visible:ring-accent"
      >
        <div className="flex flex-wrap items-center gap-2">
          <span className="min-w-0 truncate text-sm font-medium text-ink-muted group-hover:text-ink">
            {task.title}
          </span>
          {task.space_name && (
            <span className="flex shrink-0 items-center rounded border border-hairline px-1.5 py-px">
              <SpaceTag
                color={task.space_color}
                icon={task.space_icon}
                name={task.space_name}
                size="xs"
              />
            </span>
          )}
        </div>
        {task.brief_preview && (
          <p className="mt-0.5 truncate text-xs text-ink-faint">{task.brief_preview}</p>
        )}
      </button>
      <div className="flex shrink-0 items-center gap-1 py-2 pr-3">
        <span className="hidden font-mono text-[10px] uppercase tracking-[0.14em] text-ink-faint sm:block">
          {formatRelative(task.updated_at)}
        </span>
        <IconButton
          size="sm"
          variant="default"
          onClick={onUnarchive}
          disabled={unarchivePending}
          loading={unarchivePending}
          title="Unarchive — move to To Do"
          aria-label="Unarchive task"
        >
          ↑
        </IconButton>
        <IconButton
          size="sm"
          variant="danger-hover"
          onClick={onDelete}
          disabled={deletePending}
          loading={deletePending}
          title="Delete task permanently"
          aria-label="Delete task"
        >
          ⊘
        </IconButton>
      </div>
    </div>
  );
}

interface RowState {
  unarchiving: boolean;
  deleting: boolean;
}

export function ArchivedPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const openId = searchParams.get("task");
  const [spaceFilter, setSpaceFilter] = useState<string | null>(null);
  const [rowState, setRowState] = useState<Record<string, RowState>>({});

  const { data: tasks, isLoading, error } = useArchivedTasks(spaceFilter);
  const unarchive = useUnarchiveTask();
  const deleteTask = useDeleteTask();

  const setOpenId = (id: string | null) => {
    setSearchParams(
      (prev) => {
        const next = new URLSearchParams(prev);
        if (id) next.set("task", id);
        else next.delete("task");
        return next;
      },
      { replace: true },
    );
  };

  async function handleUnarchive(id: string) {
    setRowState((s) => ({ ...s, [id]: { ...s[id], unarchiving: true } }));
    try {
      await unarchive.mutateAsync(id);
    } finally {
      setRowState((s) => ({ ...s, [id]: { ...s[id], unarchiving: false } }));
    }
  }

  async function handleDelete(id: string, title: string) {
    if (!window.confirm(`Delete "${title}"? It will be moved to .trash/.`)) return;
    setRowState((s) => ({ ...s, [id]: { ...s[id], deleting: true } }));
    try {
      await deleteTask.mutateAsync(id);
    } finally {
      setRowState((s) => ({ ...s, [id]: { ...s[id], deleting: false } }));
    }
  }

  const count = tasks?.length ?? 0;

  return (
    <>
      <StickyToolbar>
        <div className="flex items-baseline gap-3">
          <h1 className="font-display text-[13px] font-semibold uppercase tracking-[0.18em] text-ink">
            Archived
          </h1>
          {!isLoading && (
            <span className="font-mono text-xs tabular-nums text-ink-faint">
              {String(count).padStart(2, "0")}
            </span>
          )}
        </div>
        <SpaceFilterDropdown value={spaceFilter} onChange={setSpaceFilter} />
      </StickyToolbar>

      <div className="mx-auto max-w-3xl px-4 py-6">
        {isLoading && (
          <p className="py-12 text-center text-sm text-ink-faint">Loading…</p>
        )}
        {error && (
          <p className="py-12 text-center text-sm text-danger">
            Error: {error.message}
          </p>
        )}
        {!isLoading && !error && count === 0 && (
          <EmptyState
            icon="↓"
            title="No archived tasks"
            description="Done tasks are archived automatically after 7 days, or you can archive them manually from the board."
          />
        )}
        {!isLoading && !error && count > 0 && (
          <div className="overflow-hidden rounded-lg border border-hairline bg-canvas shadow-inset-hairline">
            {tasks!.map((task: TaskSummary) => (
              <ArchivedRow
                key={task.id}
                task={task}
                onOpen={setOpenId}
                unarchivePending={rowState[task.id]?.unarchiving ?? false}
                deletePending={rowState[task.id]?.deleting ?? false}
                onUnarchive={() => void handleUnarchive(task.id)}
                onDelete={() => void handleDelete(task.id, task.title)}
              />
            ))}
          </div>
        )}
      </div>

      {openId && <Detail taskId={openId} onClose={() => setOpenId(null)} />}
    </>
  );
}
