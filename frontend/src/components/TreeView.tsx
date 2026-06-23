import { useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Tree, type TreeHandle } from "./Tree";
import { TreeToolbar, type TreeViewMode } from "./TreeToolbar";
import { Detail } from "./Detail";
import { useBoard, useArchivedTasks } from "../hooks/useTasks";
import {
  readBoardSpaceFilter,
  writeBoardSpaceFilter,
  readBoardSortMode,
  writeBoardSortMode,
  type BoardSortMode,
} from "../lib/storage";
import { LANES } from "../types";

interface TreeViewProps {
  spaceId?: string | null;
  archivedOnly?: boolean;
}

export function TreeView({ spaceId, archivedOnly = false }: TreeViewProps) {
  const scoped = spaceId ?? null;

  const [filter, setFilter] = useState<string | null>(() =>
    scoped ?? readBoardSpaceFilter(),
  );
  const [sortMode, setSortMode] = useState<BoardSortMode>(() => readBoardSortMode());
  const [viewMode, setViewMode] = useState<TreeViewMode>("tree");
  const [searchParams, setSearchParams] = useSearchParams();
  const openTaskId = searchParams.get("task");

  const treeRef = useRef<TreeHandle>(null);

  useEffect(() => {
    if (scoped) {
      setFilter(scoped);
    } else {
      setFilter(readBoardSpaceFilter());
    }
  }, [scoped]);

  useEffect(() => {
    if (!scoped) writeBoardSpaceFilter(filter);
  }, [scoped, filter]);

  const { data: boardData, isLoading: boardLoading } = useBoard(
    archivedOnly ? null : filter,
    null,
  );
  const { data: archivedData, isLoading: archivedLoading } = useArchivedTasks(
    archivedOnly ? filter : null,
  );

  const isLoading = archivedOnly ? archivedLoading : boardLoading;

  const allTasks = useMemo(() => {
    if (archivedOnly) {
      return archivedData ?? [];
    }
    if (!boardData) return [];
    return LANES.flatMap(({ state }) => boardData[state]);
  }, [archivedOnly, boardData, archivedData]);

  const setOpenTaskId = (id: string | null) => {
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

  const boardLink = scoped
    ? `/spaces/${scoped}`
    : filter
      ? `/spaces/${filter}`
      : "/board";

  return (
    <div className="flex h-full min-h-0 flex-col">
      <TreeToolbar
        spaceId={filter}
        onSpaceChange={(next) => setFilter(next)}
        filterLocked={!!scoped}
        sortMode={sortMode}
        onSortModeToggle={() => {
          const next: BoardSortMode = sortMode === "manual" ? "priority" : "manual";
          setSortMode(next);
          writeBoardSortMode(next);
        }}
        onExpandAll={() => treeRef.current?.expandAll()}
        onCollapseAll={() => treeRef.current?.collapseAll()}
        boardLink={boardLink}
        viewMode={viewMode}
        onViewModeToggle={() =>
          setViewMode((prev) => (prev === "tree" ? "dag" : "tree"))
        }
      />
      <div className="min-h-0 flex-1 overflow-y-auto px-4 py-3 sm:px-6">
        {isLoading ? (
          <p className="py-8 text-center text-sm text-ink-faint">Loading…</p>
        ) : viewMode === "dag" ? (
          <div className="space-y-2 py-2">
            {allTasks.length === 0 ? (
              <p className="py-8 text-center text-sm text-ink-faint">No tasks to display.</p>
            ) : (
              <div className="rounded border border-hairline bg-surface-1 p-4">
                <p className="mb-3 font-display text-[10px] uppercase tracking-[0.18em] text-ink-faint">
                  Dependency DAG — {allTasks.length} tasks
                </p>
                <ul className="space-y-1">
                  {allTasks
                    .filter((t) => (t.depends_on ?? []).length > 0)
                    .map((t) => (
                      <li
                        key={t.id}
                        className="flex items-center gap-2 text-xs text-ink-muted"
                      >
                        <button
                          type="button"
                          onClick={() => setOpenTaskId(t.id)}
                          className="truncate font-semibold text-ink hover:text-accent-bright"
                        >
                          {t.title}
                        </button>
                        <span className="text-ink-faint">←</span>
                        <span className="font-mono text-ink-faint">
                          {(t.depends_on ?? []).join(", ")}
                        </span>
                      </li>
                    ))}
                  {allTasks.filter((t) => (t.depends_on ?? []).length > 0).length === 0 && (
                    <li className="py-4 text-center text-sm text-ink-faint">
                      No dependency edges found.
                    </li>
                  )}
                </ul>
              </div>
            )}
          </div>
        ) : (
          <Tree
            ref={treeRef}
            tasks={allTasks}
            spaceId={filter}
            onOpenTask={(id) => setOpenTaskId(id)}
          />
        )}
      </div>

      {openTaskId && (
        <Detail taskId={openTaskId} onClose={() => setOpenTaskId(null)} />
      )}
    </div>
  );
}
