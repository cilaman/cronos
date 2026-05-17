import { useEffect, useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import { Board } from "../components/Board";
import { BoardToolbar } from "../components/BoardToolbar";
import { TaskForm } from "../components/TaskForm";
import { useSpaces } from "../hooks/useSpaces";
import { useCreateTask } from "../hooks/useTasks";
import { api } from "../api";
import {
  readBoardSpaceFilter,
  writeBoardSpaceFilter,
} from "../lib/storage";

export function BoardPage() {
  const { spaceId: routeSpaceId } = useParams();
  const scoped = routeSpaceId ?? null;

  const [filter, setFilter] = useState<string | null>(() =>
    scoped ?? readBoardSpaceFilter(),
  );
  const [creating, setCreating] = useState(false);
  const [isWorking, setIsWorking] = useState(false);
  const [workError, setWorkError] = useState<string | null>(null);
  const { data: spacesData } = useSpaces();
  const createTask = useCreateTask();

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
      />
      <div className="min-h-0 flex-1">
        <Board spaceId={filter} onAddTask={() => setCreating(true)} />
      </div>

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
