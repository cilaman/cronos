import { useCallback, useRef, useState } from "react";
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
import { useFeatureBoard, useTransitionFeatureState, useCreateFeature } from "../hooks/useFeatures";
import { Lane } from "./Lane";
import { Card } from "./Card";
import { FeatureDetail } from "./FeatureDetail";

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

interface ComposerProps {
  spaceId: string;
  inputRef?: React.RefObject<HTMLInputElement>;
}

function FeatureComposer({ spaceId, inputRef }: ComposerProps) {
  const [title, setTitle] = useState("");
  const [type, setType] = useState<"feature" | "fix">("feature");
  const [formError, setFormError] = useState<string | null>(null);
  const createFeature = useCreateFeature(spaceId);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const trimmed = title.trim();
    if (!trimmed) return;
    setFormError(null);
    createFeature.mutate(
      { title: trimmed, type },
      {
        onSuccess: () => {
          setTitle("");
        },
        onError: (err) => {
          const msg = (err as Error).message ?? "";
          if (msg.includes("400")) {
            setFormError(
              "This space must be linked to a git repository to create features.",
            );
          } else {
            setFormError("Failed to create feature.");
          }
        },
      },
    );
  }

  return (
    <form onSubmit={handleSubmit} className="p-2 space-y-2">
      <div className="flex gap-1">
        <label className="flex items-center gap-1 cursor-pointer">
          <input
            type="radio"
            name={`feature-type-${spaceId}`}
            value="feature"
            checked={type === "feature"}
            onChange={() => setType("feature")}
            className="sr-only"
            aria-label="Feature"
          />
          <span
            className={`rounded px-2 py-0.5 text-xs font-semibold border transition ${
              type === "feature"
                ? "bg-emerald-100 border-emerald-300 text-emerald-700 dark:bg-emerald-400/20 dark:border-emerald-400/50 dark:text-emerald-300"
                : "border-hairline bg-surface-2 text-ink-muted"
            }`}
          >
            Feature
          </span>
        </label>
        <label className="flex items-center gap-1 cursor-pointer">
          <input
            type="radio"
            name={`feature-type-${spaceId}`}
            value="fix"
            checked={type === "fix"}
            onChange={() => setType("fix")}
            className="sr-only"
            aria-label="Fix"
          />
          <span
            className={`rounded px-2 py-0.5 text-xs font-semibold border transition ${
              type === "fix"
                ? "bg-rose-100 border-rose-300 text-rose-700 dark:bg-rose-400/20 dark:border-rose-400/50 dark:text-rose-300"
                : "border-hairline bg-surface-2 text-ink-muted"
            }`}
          >
            Fix
          </span>
        </label>
      </div>
      <div className="flex gap-1">
        <input
          ref={inputRef}
          type="text"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="New feature title…"
          aria-label="Feature title"
          className="min-w-0 flex-1 rounded border border-hairline bg-surface-1 px-2 py-1 text-sm text-ink placeholder:text-ink-faint focus:border-accent focus:outline-none focus-visible:ring-1 focus-visible:ring-accent"
        />
        <button
          type="submit"
          disabled={!title.trim() || createFeature.isPending}
          aria-label="Add feature"
          className="rounded border border-hairline bg-surface-2 px-2 py-1 text-xs font-semibold text-ink-muted transition hover:bg-accent hover:text-white disabled:opacity-40 focus:outline-none focus-visible:ring-1 focus-visible:ring-accent"
        >
          Add
        </button>
      </div>
      {formError && (
        <p role="alert" className="text-xs text-danger">
          {formError}
        </p>
      )}
    </form>
  );
}

export function FeaturesBoard({ spaceId }: Props) {
  const { data, isLoading, error } = useFeatureBoard(spaceId);
  const transition = useTransitionFeatureState(spaceId);
  const [activeTask, setActiveTask] = useState<TaskSummary | null>(null);
  const [hiddenLanes, setHiddenLanes] = useState<Set<FeatureState>>(new Set());
  const [toast, setToast] = useState<{ msg: string; kind: "success" | "error" } | null>(null);
  const composerInputRef = useRef<HTMLInputElement>(null);
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
      <div className={`grid h-full grid-cols-1 gap-2 p-2 md:grid-cols-2 ${lgCols} lg:gap-3 lg:p-4`}>
        {visibleLanes.map(({ state, label }) => {
          const isBacklog = state === "backlog";
          const tasks = data[state];
          const taskIds = tasks.map((t) => t.id);

          return (
            <div key={state} className="flex min-h-0 flex-col">
              <SortableContext items={taskIds} strategy={verticalListSortingStrategy}>
                <Lane
                  state={state}
                  label={label}
                  tasks={tasks}
                  onOpen={setOpenFeatureId}
                  onAdd={() => composerInputRef.current?.focus()}
                  showAdd={isBacklog}
                  onHideLane={hideLane}
                />
              </SortableContext>
              {isBacklog && <FeatureComposer spaceId={spaceId} inputRef={composerInputRef} />}
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
