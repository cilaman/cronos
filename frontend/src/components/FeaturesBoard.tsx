import { useCallback, useState } from "react";
import { useSearchParams } from "react-router-dom";
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
import { SortableContext, verticalListSortingStrategy } from "@dnd-kit/sortable";
import {
  FEATURE_LANES,
  canFeatureTransition,
  type FeatureState,
  type TaskSummary,
} from "../types";
import { useFeatureBoard, useTransitionFeatureState } from "../hooks/useFeatures";
import { Lane } from "./Lane";
import { Card } from "./Card";
import { FeatureDetail } from "./FeatureDetail";
import { FeatureForm } from "./FeatureForm";

interface Props {
  spaceId: string;
}

function findFeatureState(
  board: Record<FeatureState, TaskSummary[]>,
  id: string,
): FeatureState | null {
  for (const { state } of FEATURE_LANES) {
    if (board[state].some((t) => t.id === id)) return state;
  }
  return null;
}


export function FeaturesBoard({ spaceId }: Props) {
  const { data, isLoading, error } = useFeatureBoard(spaceId);
  const transition = useTransitionFeatureState(spaceId);
  const [activeTask, setActiveTask] = useState<TaskSummary | null>(null);
  const [hiddenLanes, setHiddenLanes] = useState<Set<FeatureState>>(new Set());
  const [toast, setToast] = useState<{ msg: string; kind: "success" | "error" } | null>(null);
  const [showFeatureForm, setShowFeatureForm] = useState(false);
  const [searchParams, setSearchParams] = useSearchParams();

  function showToast(msg: string, kind: "success" | "error") {
    setToast({ msg, kind });
    setTimeout(() => setToast(null), 3000);
  }
  const openFeatureId = searchParams.get("feature");

  const setOpenFeatureId = (id: string | null) => {
    setSearchParams(
      (prev) => {
        const next = new URLSearchParams(prev);
        if (id) next.set("feature", id);
        else next.delete("feature");
        return next;
      },
      { replace: true },
    );
  };

  const hideLane = useCallback((state: string) => {
    setHiddenLanes((prev) => new Set([...prev, state as FeatureState]));
  }, []);

  const showLane = useCallback((state: FeatureState) => {
    setHiddenLanes((prev) => {
      const next = new Set(prev);
      next.delete(state);
      return next;
    });
  }, []);

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 8 } }),
    useSensor(TouchSensor, { activationConstraint: { delay: 200, tolerance: 8 } }),
  );

  function onDragStart(e: DragStartEvent) {
    if (!data) return;
    const taskId = String(e.active.id);
    for (const { state } of FEATURE_LANES) {
      const found = data[state].find((t) => t.id === taskId);
      if (found) {
        setActiveTask(found);
        return;
      }
    }
  }

  function onDragEnd(e: DragEndEvent) {
    setActiveTask(null);
    if (!e.over || !data) return;

    const taskId = String(e.active.id);
    const overId = String(e.over.id);
    if (taskId === overId) return;

    // (a) read fromState from board data
    const fromState = findFeatureState(data, taskId);
    if (!fromState) return;

    // (b) toState must be a lane id
    const isLaneId = FEATURE_LANES.some((l) => l.state === overId);
    if (!isLaneId) return;

    const toState = overId as FeatureState;

    // (c) guard: canFeatureTransition must pass before calling mutate
    if (!canFeatureTransition(fromState, toState)) return;

    const laneLabel = FEATURE_LANES.find((l) => l.state === toState)?.label ?? toState;

    // (d) call mutate with feedback callbacks
    transition.mutate(
      { taskId, state: toState },
      {
        onSuccess: () => showToast(`Feature moved to ${laneLabel}`, "success"),
        onError: (err) => {
          const msg = (err as Error).message ?? "";
          if (msg.includes("409")) {
            showToast(`Cannot move to ${laneLabel} from current state`, "error");
          } else {
            showToast("Failed to update feature state", "error");
          }
        },
      },
    );
  }

  function onDragCancel() {
    setActiveTask(null);
  }

  if (isLoading) {
    return <p className="p-6 text-ink-muted">Loading features…</p>;
  }
  if (error) {
    return <p className="p-6 text-danger">Error: {error.message}</p>;
  }
  if (!data) return null;

  const visibleLanes = FEATURE_LANES.filter(({ state }) => !hiddenLanes.has(state));
  const hiddenLaneList = FEATURE_LANES.filter(({ state }) => hiddenLanes.has(state));
  const colCount = visibleLanes.length;
  const lgCols =
    colCount === 1 ? "lg:grid-cols-1"
    : colCount === 2 ? "lg:grid-cols-2"
    : colCount === 3 ? "lg:grid-cols-3"
    : colCount === 4 ? "lg:grid-cols-4"
    : "lg:grid-cols-5";

  return (
    <>
    <DndContext
      sensors={sensors}
      collisionDetection={closestCenter}
      onDragStart={onDragStart}
      onDragEnd={onDragEnd}
      onDragCancel={onDragCancel}
    >
      {hiddenLaneList.length > 0 && (
        <div className="flex flex-wrap items-center gap-1.5 px-2 pt-2 lg:px-4">
          <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-ink-faint">
            Hidden:
          </span>
          {hiddenLaneList.map(({ state, label }) => (
            <button
              key={state}
              type="button"
              onClick={() => showLane(state)}
              aria-label={`Show ${label} lane`}
              title={`Show ${label}`}
              className="rounded border border-dashed border-hairline px-2 py-0.5 font-display text-[10px] font-semibold uppercase tracking-[0.14em] text-ink-muted transition hover:border-accent hover:bg-surface-2 hover:text-accent-bright focus:outline-none focus-visible:ring-1 focus-visible:ring-accent"
            >
              + {label}
            </button>
          ))}
        </div>
      )}
      <div className={`grid h-full overflow-hidden grid-rows-[minmax(0,1fr)] grid-cols-1 gap-2 p-2 md:grid-cols-2 ${lgCols} lg:gap-3 lg:p-4`}>
        {visibleLanes.map(({ state, label }) => {
          const isBacklog = state === "backlog";
          const tasks = data[state];
          const taskIds = tasks.map((t) => t.id);

          return (
            <div key={state} className="contents">
              <SortableContext items={taskIds} strategy={verticalListSortingStrategy}>
                <Lane
                  state={state}
                  label={label}
                  tasks={tasks}
                  onOpen={setOpenFeatureId}
                  onAdd={() => setShowFeatureForm(true)}
                  showAdd={isBacklog}
                  onHideLane={hideLane}
                />
              </SortableContext>
            </div>
          );
        })}
      </div>

      <DragOverlay dropAnimation={null}>
        {activeTask ? (
          <Card task={activeTask} onClick={() => {}} />
        ) : null}
      </DragOverlay>
    </DndContext>
    {showFeatureForm && (
      <FeatureForm spaceId={spaceId} onClose={() => setShowFeatureForm(false)} />
    )}
    {openFeatureId && (
      <FeatureDetail
        featureId={openFeatureId}
        onClose={() => setOpenFeatureId(null)}
      />
    )}
    {toast && (
      <div
        role="alert"
        className={`fixed bottom-4 right-4 z-50 rounded-md border px-3 py-2 text-sm shadow-lift ${
          toast.kind === "success"
            ? "border-accent bg-surface-1 text-accent"
            : "border-danger bg-surface-1 text-danger"
        }`}
      >
        {toast.msg}
      </div>
    )}
    </>
  );
}
