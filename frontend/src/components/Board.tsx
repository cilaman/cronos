import {
  DndContext,
  PointerSensor,
  TouchSensor,
  useSensor,
  useSensors,
  type DragEndEvent,
} from "@dnd-kit/core";
import { useState } from "react";
import { useBoard, useCreateTask, useTransitionTask } from "../hooks/useTasks";
import { LANES, type TaskState, canUserTransition } from "../types";
import { Detail } from "./Detail";
import { Lane } from "./Lane";
import { TaskForm } from "./TaskForm";

function findTaskState(board: ReturnType<typeof useBoard>["data"], id: string): TaskState | null {
  if (!board) return null;
  for (const { state } of LANES) {
    if (board[state].some((t) => t.id === id)) return state;
  }
  return null;
}

export function Board() {
  const { data, isLoading, error } = useBoard();
  const transition = useTransitionTask();
  const createTask = useCreateTask();
  const [openId, setOpenId] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 8 } }),
    useSensor(TouchSensor, { activationConstraint: { delay: 200, tolerance: 8 } }),
  );

  function onDragEnd(e: DragEndEvent) {
    if (!e.over) return;
    const taskId = String(e.active.id);
    const dest = e.over.id as TaskState;
    const current = findTaskState(data, taskId);
    if (current && canUserTransition(current, dest)) {
      transition.mutate({ id: taskId, state: dest });
    }
  }

  if (isLoading) return <p className="p-6 text-bone-muted">Loading board…</p>;
  if (error) return <p className="p-6 text-oxblood">Error: {error.message}</p>;
  if (!data) return null;

  return (
    <>
      <DndContext sensors={sensors} onDragEnd={onDragEnd}>
        <div className="grid h-[calc(100vh-4rem)] grid-cols-1 gap-2 p-2 md:grid-cols-2 lg:grid-cols-4 lg:gap-3 lg:p-4">
          {LANES.map(({ state, label }) => (
            <Lane
              key={state}
              state={state}
              label={label}
              tasks={data[state]}
              onOpen={setOpenId}
              onAdd={() => setCreating(true)}
            />
          ))}
        </div>
      </DndContext>

      {openId && <Detail taskId={openId} onClose={() => setOpenId(null)} />}

      {creating && (
        <TaskForm
          heading="New task"
          submitting={createTask.isPending}
          error={createTask.error?.message ?? null}
          onCancel={() => setCreating(false)}
          onSubmit={async (body) => {
            await createTask.mutateAsync(body);
            setCreating(false);
          }}
        />
      )}
    </>
  );
}
