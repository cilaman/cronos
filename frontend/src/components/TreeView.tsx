import { useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Tree, type TreeHandle } from "./Tree";
import { TreeToolbar } from "./TreeToolbar";
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
      />
      <div className="min-h-0 flex-1 overflow-y-auto px-4 py-3 sm:px-6">
        {isLoading ? (
          <p className="py-8 text-center text-sm text-ink-faint">Loading…</p>
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
