import {
  DndContext,
  DragOverlay,
  PointerSensor,
  TouchSensor,
  closestCenter,
  useSensor,
  useSensors,
  type DragEndEvent,
  type DragStartEvent,
} from "@dnd-kit/core";
import { arrayMove } from "@dnd-kit/sortable";
import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useBoard, useReorderTasks, useTransitionTask } from "../hooks/useTasks";
import { useRunning } from "../hooks/useRunning";
import { LANES, type TaskState, type TaskSummary, canUserTransition } from "../types";
import type { BoardSortMode } from "../lib/storage";
import { Detail } from "./Detail";
import { Lane } from "./Lane";
import { Card } from "./Card";

function findTaskState(
  board: Record<TaskState, TaskSummary[]>,
  id: string,
): TaskState | null {
  for (const { state } of LANES) {
    if (board[state].some((t) => t.id === id)) return state;
  }
  return null;
}

interface Props {
  spaceId: string | null;
  onAddTask: () => void;
  compact?: boolean;
  sortMode?: BoardSortMode;
  /** View ID to send to the API (null = use space's default view). */
  viewId?: string | null;
  /** Lane states to render; lanes absent here are hidden (column removed). */
  activeLaneStates?: TaskState[];
  /** Lane states currently visible on the board. Hidden lanes appear as restore chips above the grid. */
  visibleLaneStates?: TaskState[];
  /** Called when the user clicks the × on a lane header. */
  onHideLane?: (state: TaskState) => void;
  /** Called when the user clicks a restore chip for a hidden lane. */
  onShowLane?: (state: TaskState) => void;
  /** Set of goal IDs whose child list is expanded on the board. */
  expandedGoals?: Set<string>;
  /** Called when the user clicks the expand chevron on a goal card. */
  onToggleGoal?: (id: string) => void;
}

export function Board({
  spaceId,
  onAddTask,
  compact = false,
  sortMode = "manual",
  viewId = null,
  activeLaneStates,
  visibleLaneStates,
  onHideLane,
  onShowLane,
  expandedGoals,
  onToggleGoal,
}: Props) {
  const effectiveViewId = spaceId ? (viewId ?? "default") : null;
  const { data, isLoading, error } = useBoard(spaceId, effectiveViewId);
  const transition = useTransitionTask();
  const reorder = useReorderTasks();
  const [searchParams, setSearchParams] = useSearchParams();
  const openId = searchParams.get("task");
  const [activeTask, setActiveTask] = useState<TaskSummary | null>(null);
  const { isRunning, seed } = useRunning(spaceId);

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

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 8 } }),
    useSensor(TouchSensor, { activationConstraint: { delay: 200, tolerance: 8 } }),
  );

  const sortedData = useMemo(() => {
    if (!data) return null;
    if (sortMode === "manual") return data;
    const byPriority = (tasks: TaskSummary[]) =>
      [...tasks].sort((a, b) =>
        a.priority !== b.priority ? a.priority - b.priority : a.manual_order - b.manual_order,
      );
    return {
      ...data,
      backlog: byPriority(data.backlog),
      active: byPriority(data.active),
      waiting: byPriority(data.waiting),
      done: byPriority(data.done),
    };
  }, [data, sortMode]);

  // Seed running set from board data so the pulse appears on first render.
  useEffect(() => {
    if (!sortedData) return;
    const running = LANES.flatMap(({ state }) => sortedData[state])
      .filter((t) => t.is_running)
      .map((t) => t.id);
    seed(running);
  }, [sortedData, seed]);

  const blocksCountMap = useMemo<Record<string, number>>(() => {
    if (!sortedData) return {};
    const allTasks = LANES.flatMap(({ state }) => sortedData[state]);
    const counts: Record<string, number> = {};
    for (const task of allTasks) {
      for (const depId of task.depends_on ?? []) {
        counts[depId] = (counts[depId] ?? 0) + 1;
      }
    }
    return counts;
  }, [sortedData]);

  function onDragStart(e: DragStartEvent) {
    if (!sortedData) return;
    const taskId = String(e.active.id);
    for (const { state } of LANES) {
      const found = sortedData[state].find((t) => t.id === taskId);
      if (found) {
        setActiveTask(found);
        return;
      }
    }
  }

  function onDragEnd(e: DragEndEvent) {
    setActiveTask(null);
    if (!e.over || !sortedData) return;

    const activeId = String(e.active.id);
    const overId = String(e.over.id);
    if (activeId === overId) return;

    const sourceLane = findTaskState(sortedData, activeId);
    if (!sourceLane) return;

    const isLaneId = LANES.some((l) => l.state === overId);

    if (isLaneId) {
      const destLane = overId as TaskState;
      if (sourceLane !== destLane && canUserTransition(sourceLane, destLane)) {
        transition.mutate({ id: activeId, state: destLane });
      }
    } else {
      // Dropped on another task card
      const destLane = findTaskState(sortedData, overId);
      if (!destLane) return;

      if (sourceLane === destLane) {
        // Within-lane reorder
        const tasks = sortedData[sourceLane];
        const oldIndex = tasks.findIndex((t) => t.id === activeId);
        const newIndex = tasks.findIndex((t) => t.id === overId);
        if (oldIndex === newIndex) return;
        const reordered = arrayMove(tasks, oldIndex, newIndex);
        reorder.mutate({ lane: sourceLane, task_ids: reordered.map((t) => t.id) });
      } else if (canUserTransition(sourceLane, destLane)) {
        transition.mutate({ id: activeId, state: destLane });
      }
    }
  }

  function onDragCancel() {
    setActiveTask(null);
  }

  // Always hide tasks whose parent is a goal — they render only inside the goal card's inline children panel.
  // Must be declared before any early returns (hooks-rules).
  const displayData = useMemo(() => {
    if (!sortedData) return null;
    const goalIds = new Set<string>();
    for (const lane of ["backlog", "active", "waiting", "done"] as const) {
      for (const t of sortedData[lane]) if (t.type === "goal") goalIds.add(t.id);
    }
    if (goalIds.size === 0) return sortedData;
    const filterHidden = (tasks: TaskSummary[]) =>
      tasks.filter((t) => !(t.parent_id && goalIds.has(t.parent_id)));
    return {
      ...sortedData,
      backlog: filterHidden(sortedData.backlog),
      active: filterHidden(sortedData.active),
      waiting: filterHidden(sortedData.waiting),
      done: filterHidden(sortedData.done),
    };
  }, [sortedData]);

  if (isLoading) return <p className="p-6 text-ink-muted">Loading board…</p>;
  // Silently ignore 404 for deleted/invalid views — BoardPage resets the URL param.
  if (error && !error.message.startsWith("404 ")) {
    return <p className="p-6 text-danger">Error: {error.message}</p>;
  }
  if (!sortedData || !displayData) return null;

  // Prefer visibleLaneStates (new API) but fall back to activeLaneStates for callers not yet updated.
  const laneStateSet =
    visibleLaneStates !== undefined
      ? new Set(visibleLaneStates)
      : activeLaneStates !== undefined
        ? new Set(activeLaneStates)
        : null;
  const visibleLanes = laneStateSet ? LANES.filter((l) => laneStateSet.has(l.state)) : LANES;
  const hiddenLanes = laneStateSet ? LANES.filter((l) => !laneStateSet.has(l.state)) : [];

  // Dynamic column count so hidden lanes don't leave gaps.
  const colCount = visibleLanes.length;
  const lgCols =
    colCount === 1 ? "lg:grid-cols-1"
    : colCount === 2 ? "lg:grid-cols-2"
    : colCount === 3 ? "lg:grid-cols-3"
    : "lg:grid-cols-4";

  return (
    <>
      <DndContext
        sensors={sensors}
        collisionDetection={closestCenter}
        onDragStart={onDragStart}
        onDragEnd={onDragEnd}
        onDragCancel={onDragCancel}
      >
        {hiddenLanes.length > 0 && (
          <div className="flex flex-wrap items-center gap-1.5 px-2 pt-2 lg:px-4">
            <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-ink-faint">
              Hidden:
            </span>
            {hiddenLanes.map(({ state, label }) => (
              <button
                key={state}
                type="button"
                onClick={() => onShowLane?.(state)}
                aria-label={`Show ${label} lane`}
                title={`Show ${label}`}
                className="rounded border border-dashed border-hairline px-2 py-0.5 font-display text-[10px] font-semibold uppercase tracking-[0.14em] text-ink-muted transition hover:border-accent hover:bg-surface-2 hover:text-accent-bright focus:outline-none focus-visible:ring-1 focus-visible:ring-accent"
              >
                + {label}
              </button>
            ))}
          </div>
        )}
        <div className={`grid h-full grid-cols-1 gap-2 p-2 md:grid-cols-2 ${lgCols} lg:gap-3 lg:p-4`}>
          {visibleLanes.map(({ state, label }) => (
            <Lane
              key={state}
              state={state}
              label={label}
              tasks={displayData[state]}
              onOpen={setOpenId}
              onAdd={onAddTask}
              compact={compact}
              onOpenTask={setOpenId}
              blocksCountMap={blocksCountMap}
              isRunning={isRunning}
              expandedGoals={expandedGoals}
              onToggleGoal={onToggleGoal}
              onHideLane={onHideLane}
            />
          ))}
        </div>

        <DragOverlay dropAnimation={null}>
          {activeTask ? (
            <Card task={activeTask} onClick={() => {}} compact={compact} isDragOverlay />
          ) : null}
        </DragOverlay>
      </DndContext>

      {openId && <Detail taskId={openId} onClose={() => setOpenId(null)} />}
    </>
  );
}
