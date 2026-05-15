import { useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  useDeleteTask,
  useReplyToTask,
  useStopTask,
  useTask,
  useUpdateTask,
} from "../hooks/useTasks";
import { STATE_BADGE } from "../state-badges";
import type { AgentMode, AgentModel } from "../types";
import { ChatInput } from "./ChatInput";
import { LiveLog } from "./LiveLog";
import { TaskForm } from "./TaskForm";

interface Props {
  taskId: string;
  onClose: () => void;
}

export function Detail({ taskId, onClose }: Props) {
  const { data: task, isLoading, error } = useTask(taskId);
  const updateTask = useUpdateTask(taskId);
  const deleteTask = useDeleteTask();
  const replyTask = useReplyToTask(taskId);
  const stopTask = useStopTask(taskId);
  const [editing, setEditing] = useState(false);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key !== "Escape" || editing) return;
      const active = document.activeElement;
      if (
        active instanceof HTMLTextAreaElement ||
        active instanceof HTMLInputElement ||
        active instanceof HTMLSelectElement
      ) {
        return;
      }
      onClose();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose, editing]);

  async function onDelete() {
    if (!task) return;
    if (!window.confirm(`Delete "${task.title}"? It will be moved to .trash/.`)) {
      return;
    }
    await deleteTask.mutateAsync(task.id);
    onClose();
  }

  async function onSend(message: string) {
    await replyTask.mutateAsync(message);
  }

  async function onStop() {
    await stopTask.mutateAsync();
  }

  async function onModeChange(mode: AgentMode) {
    if (!task || task.agent_mode === mode) return;
    await updateTask.mutateAsync({ agent_mode: mode });
  }

  async function onModelChange(model: AgentModel) {
    if (!task || task.agent_model === model) return;
    await updateTask.mutateAsync({ agent_model: model });
  }

  const chatError =
    replyTask.error?.message ?? stopTask.error?.message ?? null;

  return (
    <>
      <div
        className="fixed inset-0 z-30 flex items-stretch justify-center bg-slate-900/50 p-0 sm:items-center sm:p-4"
        onClick={onClose}
      >
        <div
          className="flex h-full w-full max-w-3xl flex-col overflow-hidden bg-white shadow-xl sm:h-auto sm:max-h-[90vh] sm:rounded-lg"
          onClick={(e) => e.stopPropagation()}
        >
          {isLoading && <div className="p-6 text-slate-500">Loading…</div>}
          {error && <div className="p-6 text-red-600">Error: {error.message}</div>}
          {task && (
            <>
              <header className="flex items-start justify-between gap-4 border-b border-slate-200 p-4">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <span
                      className={`rounded px-2 py-0.5 text-xs font-medium uppercase tracking-wide ${
                        STATE_BADGE[task.state] ?? STATE_BADGE.backlog
                      }`}
                    >
                      {task.state}
                    </span>
                    <span className="text-xs text-slate-500">{task.id}</span>
                  </div>
                  <h2 className="mt-2 text-xl font-semibold text-slate-900">
                    {task.title}
                  </h2>
                </div>
                <button
                  type="button"
                  onClick={onClose}
                  aria-label="Close"
                  className="rounded p-1 text-slate-500 hover:bg-slate-100"
                >
                  ✕
                </button>
              </header>

              <div className="flex-1 space-y-6 overflow-y-auto p-4">
                <section>
                  <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                    Brief
                  </h3>
                  <div className="prose prose-sm mt-2 max-w-none">
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>{task.brief}</ReactMarkdown>
                  </div>
                </section>

                <section>
                  <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                    History
                  </h3>
                  {task.history ? (
                    <div className="prose prose-sm mt-2 max-w-none">
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>{task.history}</ReactMarkdown>
                    </div>
                  ) : (
                    <p className="mt-2 text-sm text-slate-400">No history yet.</p>
                  )}
                </section>

                {(task.state === "active" || task.state === "waiting") && (
                  <LiveLog taskId={task.id} />
                )}
              </div>

              <ChatInput
                taskState={task.state}
                agentMode={task.agent_mode}
                agentModel={task.agent_model}
                waitingQuestion={task.waiting_question}
                pendingCount={task.pending_messages.length}
                isSending={replyTask.isPending}
                isStopping={stopTask.isPending}
                error={chatError}
                onSend={onSend}
                onStop={onStop}
                onModeChange={onModeChange}
                onModelChange={onModelChange}
              />

              <footer className="flex items-center justify-between gap-2 border-t border-slate-200 p-3">
                <button
                  type="button"
                  onClick={onDelete}
                  disabled={deleteTask.isPending}
                  className="rounded px-3 py-2 text-sm text-red-600 hover:bg-red-50 disabled:opacity-50"
                >
                  Delete
                </button>
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => setEditing(true)}
                    className="rounded bg-slate-800 px-4 py-2 text-sm font-medium text-white hover:bg-slate-900"
                  >
                    Edit
                  </button>
                </div>
              </footer>
            </>
          )}
        </div>
      </div>

      {editing && task && (
        <TaskForm
          heading="Edit task"
          initialTitle={task.title}
          initialBrief={task.brief}
          showModel={false}
          submitting={updateTask.isPending}
          error={updateTask.error?.message ?? null}
          onCancel={() => setEditing(false)}
          onSubmit={async (body) => {
            await updateTask.mutateAsync(body);
            setEditing(false);
          }}
        />
      )}
    </>
  );
}
