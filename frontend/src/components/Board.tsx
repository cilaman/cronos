import {
  DndContext,
  PointerSensor,
  TouchSensor,
  useSensor,
  useSensors,
  type DragEndEvent,
} from "@dnd-kit/core";
import { useSearchParams } from "react-router-dom";
import { useBoard, useTransitionTask } from "../hooks/useTasks";
import { LANES, type TaskState, canUserTransition } from "../types";
import { Detail } from "./Detail";
import { Lane } from "./Lane";

function findTaskState(board: ReturnType<typeof useBoard>["data"], id: string): TaskState | null {
  if (!board) return null;
  for (const { state } of LANES) {
    if (board[state].some((t) => t.id === id)) return state;
  }
  return null;
}

interface Props {
  spaceId: string | null;
  onAddTask: () => void;
}

export function Board({ spaceId, onAddTask }: Props) {
  const { data, isLoading, error } = useBoard(spaceId);
  const transition = useTransitionTask();
  const [searchParams, setSearchParams] = useSearchParams();
  const openId = searchParams.get("task");

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

  function onDragEnd(e: DragEndEvent) {
    if (!e.over) return;
    const taskId = String(e.active.id);
    const dest = e.over.id as TaskState;
    const current = findTaskState(data, taskId);
    if (current && canUserTransition(current, dest)) {
      transition.mutate({ id: taskId, state: dest });
    }
  }

  if (isLoading) return <p className="p-6 text-ink-muted">Loading board…</p>;
  if (error) return <p className="p-6 text-danger">Error: {error.message}</p>;
  if (!data) return null;

  return (
    <>
      <DndContext sensors={sensors} onDragEnd={onDragEnd}>
        <div className="grid h-[calc(100vh-3rem)] grid-cols-1 gap-2 p-2 md:grid-cols-2 lg:grid-cols-4 lg:gap-3 lg:p-4">
          {LANES.map(({ state, label }) => (
            <Lane
              key={state}
              state={state}
              label={label}
              tasks={data[state]}
              onOpen={setOpenId}
              onAdd={onAddTask}
            />
          ))}
        </div>
      </DndContext>

      {openId && <Detail taskId={openId} onClose={() => setOpenId(null)} />}
    </>
  );
}
