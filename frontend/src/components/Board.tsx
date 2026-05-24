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
import { useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useBoard, useReorderTasks, useTransitionTask } from "../hooks/useTasks";
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
}

export function Board({ spaceId, onAddTask, compact = false, sortMode = "manual" }: Props) {
  const { data, isLoading, error } = useBoard(spaceId);
  const transition = useTransitionTask();
  const reorder = useReorderTasks();
  const [searchParams, setSearchParams] = useSearchParams();
  const openId = searchParams.get("task");
  const [activeTask, setActiveTask] = useState<TaskSummary | null>(null);

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

  if (isLoading) return <p className="p-6 text-ink-muted">Loading board…</p>;
  if (error) return <p className="p-6 text-danger">Error: {error.message}</p>;
  if (!sortedData) return null;

  return (
    <>
      <DndContext
        sensors={sensors}
        collisionDetection={closestCenter}
        onDragStart={onDragStart}
        onDragEnd={onDragEnd}
        onDragCancel={onDragCancel}
      >
        <div className="grid h-full grid-cols-1 gap-2 p-2 md:grid-cols-2 lg:grid-cols-4 lg:gap-3 lg:p-4">
          {LANES.map(({ state, label }) => (
            <Lane
              key={state}
              state={state}
              label={label}
              tasks={sortedData[state]}
              onOpen={setOpenId}
              onAdd={onAddTask}
              compact={compact}
              onOpenTask={setOpenId}
              blocksCountMap={blocksCountMap}
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
