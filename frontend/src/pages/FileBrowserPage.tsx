import { useState } from "react";
import { useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api, taskFileUrl } from "../api";
import { useBoard } from "../hooks/useTasks";
import { useSpace } from "../hooks/useSpaces";
import { FileBrowser } from "../components/FileBrowser";
import type { TaskSummary } from "../types";

export function FileBrowserPage() {
  const { spaceId } = useParams<{ spaceId: string }>();
  const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null);
  const [expandedGoals, setExpandedGoals] = useState<Set<string>>(new Set());

  const { data: boardData, isLoading: boardLoading, isError: boardError } = useBoard(
    spaceId ?? null,
  );
  const { data: spaceData } = useSpace(spaceId ?? null);
  const spaceName = spaceData?.name ?? spaceId ?? "Space";

  const {
    data: taskFiles = [],
    isLoading: filesLoading,
    isError: filesError,
  } = useQuery({
    queryKey: ["task-files", selectedTaskId],
    queryFn: () => api.taskFiles(selectedTaskId!),
    enabled: selectedTaskId !== null,
  });

  const allTasks: TaskSummary[] = boardData
    ? [
        ...boardData.backlog,
        ...boardData.active,
        ...boardData.waiting,
        ...boardData.done,
      ]
    : [];

  const goals = allTasks.filter((t) => t.type === "goal");

  const childrenByParent: Record<string, TaskSummary[]> = {};
  for (const task of allTasks) {
    if (task.parent_id) {
      if (!childrenByParent[task.parent_id]) {
        childrenByParent[task.parent_id] = [];
      }
      childrenByParent[task.parent_id].push(task);
    }
  }

  const rootTasks = allTasks.filter((t) => !t.parent_id && t.type !== "goal");

  const selectedTask = allTasks.find((t) => t.id === selectedTaskId);
  const breadcrumb = selectedTask
    ? `Space ${spaceName} / ${selectedTask.title}`
    : `Space ${spaceName}`;

  function toggleGoal(goalId: string) {
    setExpandedGoals((prev) => {
      const next = new Set(prev);
      if (next.has(goalId)) next.delete(goalId);
      else next.add(goalId);
      return next;
    });
  }

  return (
    <div className="flex h-full flex-col overflow-hidden md:flex-row">
      {/* Task tree panel */}
      <div className="w-full shrink-0 overflow-y-auto border-b border-hairline bg-surface-1 md:w-72 md:border-b-0 md:border-r">
        <div className="border-b border-hairline px-4 py-3">
          <h1 className="font-display text-sm font-semibold uppercase tracking-[0.18em] text-ink">
            File Browser
          </h1>
          {spaceData && (
            <p className="mt-0.5 truncate text-[11px] text-ink-muted">{spaceName}</p>
          )}
        </div>

        {boardLoading ? (
          <p className="px-4 py-3 text-sm text-ink-muted">Loading tasks…</p>
        ) : boardError ? (
          <p className="px-4 py-3 text-sm text-danger">Failed to load tasks.</p>
        ) : (
          <ul className="py-2">
            {goals.map((goal) => (
              <li key={goal.id}>
                <button
                  type="button"
                  onClick={() => toggleGoal(goal.id)}
                  className="flex w-full items-center gap-1.5 px-4 py-1.5 text-left text-[12px] font-medium text-ink-muted transition hover:bg-surface-2/50"
                >
                  <span
                    aria-hidden
                    className={`text-[9px] transition-transform ${
                      expandedGoals.has(goal.id) ? "rotate-90" : ""
                    }`}
                  >
                    ▶
                  </span>
                  <span className="min-w-0 flex-1 truncate">{goal.title}</span>
                </button>
                {expandedGoals.has(goal.id) &&
                  childrenByParent[goal.id]?.map((child) => (
                    <button
                      key={child.id}
                      type="button"
                      onClick={() => setSelectedTaskId(child.id)}
                      className={`flex w-full items-center gap-1.5 py-1.5 pl-8 pr-4 text-left text-[12px] transition ${
                        selectedTaskId === child.id
                          ? "bg-surface-2 text-ink"
                          : "text-ink-muted hover:bg-surface-2/50"
                      }`}
                    >
                      <span className="min-w-0 flex-1 truncate">{child.title}</span>
                    </button>
                  ))}
              </li>
            ))}
            {rootTasks.map((task) => (
              <li key={task.id}>
                <button
                  type="button"
                  onClick={() => setSelectedTaskId(task.id)}
                  className={`flex w-full items-center gap-1.5 px-4 py-1.5 text-left text-[12px] transition ${
                    selectedTaskId === task.id
                      ? "bg-surface-2 text-ink"
                      : "text-ink-muted hover:bg-surface-2/50"
                  }`}
                >
                  <span className="min-w-0 flex-1 truncate">{task.title}</span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>

      {/* Files panel */}
      <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
        {selectedTaskId === null ? (
          <div className="flex flex-1 items-center justify-center">
            <p className="text-sm text-ink-muted">Select a task to browse its files.</p>
          </div>
        ) : filesError ? (
          <p className="px-4 py-3 text-sm text-danger">Failed to load files.</p>
        ) : (
          <FileBrowser
            files={taskFiles}
            isLoading={filesLoading}
            fileUrlBuilder={(path, dl) => taskFileUrl(selectedTaskId, path, dl)}
            breadcrumb={breadcrumb}
          />
        )}
      </div>
    </div>
  );
}
