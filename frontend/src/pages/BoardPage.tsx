import { useEffect, useMemo, useState } from "react";
import { useParams, useSearchParams } from "react-router-dom";
import { Board } from "../components/Board";
import { BoardToolbar } from "../components/BoardToolbar";
import { TaskForm } from "../components/TaskForm";
import { ViewEditor } from "../components/ViewEditor";
import { useSpaces } from "../hooks/useSpaces";
import { useCreateTask } from "../hooks/useTasks";
import { useViews } from "../hooks/useViews";
import { api } from "../api";
import type { TaskState } from "../types";
import {
  readBoardSpaceFilter,
  writeBoardSpaceFilter,
  readCardViewMode,
  writeCardViewMode,
  readBoardSortMode,
  writeBoardSortMode,
  type BoardSortMode,
} from "../lib/storage";

export function BoardPage() {
  const { spaceId: routeSpaceId } = useParams();
  const scoped = routeSpaceId ?? null;

  const [searchParams, setSearchParams] = useSearchParams();
  const [filter, setFilter] = useState<string | null>(() =>
    scoped ?? readBoardSpaceFilter(),
  );
  const [compact, setCompact] = useState(() => readCardViewMode() === "minimal");
  const [sortMode, setSortMode] = useState<BoardSortMode>(() => readBoardSortMode());
  const [creating, setCreating] = useState(false);
  const [managingViews, setManagingViews] = useState(false);
  const [isWorking, setIsWorking] = useState(false);
  const [workError, setWorkError] = useState<string | null>(null);
  const { data: spacesData } = useSpaces();
  const createTask = useCreateTask();

  // The space the board is actually scoped to.
  const boardSpaceId = scoped ?? filter;

  // View ID from URL — null means "use the space's default view".
  const urlViewId = searchParams.get("view");

  // Load views for the current space (only when scoped to one space).
  const { data: views } = useViews(boardSpaceId);

  // Resolve the active view object for lane visibility.
  const activeView = useMemo(() => {
    if (!views || !boardSpaceId) return null;
    if (urlViewId !== null) {
      return views.find((v) => v.id === urlViewId) ?? views.find((v) => v.default) ?? null;
    }
    return views.find((v) => v.default) ?? views[0] ?? null;
  }, [views, boardSpaceId, urlViewId]);

  // Lane states the board should render (hide others).
  const activeLaneStates = useMemo<TaskState[] | undefined>(() => {
    if (!activeView) return undefined;
    return activeView.lanes;
  }, [activeView]);

  // Keep filter aligned with the URL when navigating between scoped/unscoped.
  useEffect(() => {
    if (scoped) {
      setFilter(scoped);
    } else {
      setFilter(readBoardSpaceFilter());
    }
  }, [scoped]);

  // Persist when the user changes filter on the unscoped /board view.
  useEffect(() => {
    if (!scoped) writeBoardSpaceFilter(filter);
  }, [scoped, filter]);

  // Silently reset to default when the bookmarked view no longer exists.
  useEffect(() => {
    if (urlViewId && views && !views.find((v) => v.id === urlViewId)) {
      setSearchParams(
        (prev) => {
          const next = new URLSearchParams(prev);
          next.delete("view");
          return next;
        },
        { replace: true },
      );
    }
  }, [urlViewId, views, setSearchParams]);

  function handleViewChange(newViewId: string | null) {
    setSearchParams(
      (prev) => {
        const next = new URLSearchParams(prev);
        if (newViewId) {
          next.set("view", newViewId);
        } else {
          next.delete("view");
        }
        return next;
      },
      { replace: false },
    );
  }

  const initialSpaceForCreate = useMemo(() => {
    return (
      scoped ?? filter ?? spacesData?.spaces[0]?.id ?? null
    );
  }, [scoped, filter, spacesData]);

  return (
    <div className="flex h-full min-h-0 flex-col">
      <BoardToolbar
        spaceId={filter}
        onSpaceChange={(next) => setFilter(next)}
        filterLocked={!!scoped}
        onNewTask={() => setCreating(true)}
        compact={compact}
        onCompactToggle={() => {
          const next = !compact;
          setCompact(next);
          writeCardViewMode(next ? "minimal" : "full");
        }}
        sortMode={sortMode}
        onSortModeToggle={() => {
          const next: BoardSortMode = sortMode === "manual" ? "priority" : "manual";
          setSortMode(next);
          writeBoardSortMode(next);
        }}
        viewId={urlViewId}
        onViewChange={scoped ? handleViewChange : undefined}
        onManageViews={boardSpaceId ? () => setManagingViews(true) : undefined}
      />
      <div className="min-h-0 flex-1">
        <Board
          spaceId={filter}
          onAddTask={() => setCreating(true)}
          compact={compact}
          sortMode={sortMode}
          viewId={urlViewId}
          activeLaneStates={activeLaneStates}
        />
      </div>

      {managingViews && boardSpaceId && (
        <ViewEditor
          spaceId={boardSpaceId}
          currentViewId={urlViewId}
          onClose={() => setManagingViews(false)}
          onViewChange={(viewId) => {
            setManagingViews(false);
            handleViewChange(viewId);
          }}
        />
      )}

      {creating && (
        <TaskForm
          heading="New task"
          showSpacePicker
          initialSpaceId={initialSpaceForCreate}
          lockedSpaceId={scoped}
          submitting={isWorking}
          error={workError}
          onCancel={() => { setCreating(false); setWorkError(null); }}
          onSubmit={async (body) => {
            if (!body.space_id) return;
            setIsWorking(true);
            setWorkError(null);
            try {
              const task = await createTask.mutateAsync({
                space_id: body.space_id,
                title: body.title,
                brief: body.brief,
                agent_model: body.agent_model,
                agent_mode: body.agent_mode,
                priority: body.priority,
              });
              for (const file of body.files) {
                await api.uploadTaskFile(task.id, file);
              }
              if (body.startImmediately) {
                await api.start(task.id);
              }
              setCreating(false);
            } catch (err) {
              setWorkError(err instanceof Error ? err.message : String(err));
            } finally {
              setIsWorking(false);
            }
          }}
        />
      )}
    </div>
  );
}
