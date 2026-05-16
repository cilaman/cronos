import { useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  useDeleteTask,
  useReplyToTask,
  useStartTask,
  useStopTask,
  useTask,
  useUpdateTask,
} from "../hooks/useTasks";
import { STATE_BADGE } from "../state-badges";
import {
  AGENT_MODELS,
  AGENT_MODES,
  type AgentMode,
  type AgentModel,
} from "../types";
import { ChatInput } from "./ChatInput";
import { FilesPanel } from "./FilesPanel";
import { LiveLog } from "./LiveLog";
import { TaskActionBar } from "./TaskActionBar";
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
  const startTask = useStartTask(taskId);
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

  async function onStart() {
    await startTask.mutateAsync();
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
    replyTask.error?.message ??
    startTask.error?.message ??
    stopTask.error?.message ??
    null;

  return (
    <>
      <div
        className="fixed inset-0 z-30 flex items-stretch justify-center bg-black/70 p-0 backdrop-blur-sm sm:items-center sm:p-4"
        onClick={onClose}
      >
        <div
          className="flex h-full w-full max-w-5xl flex-col overflow-hidden border border-hairline bg-pitch-50 shadow-lift sm:h-auto sm:max-h-[90vh] sm:rounded-lg"
          onClick={(e) => e.stopPropagation()}
        >
          {isLoading && <div className="p-6 text-bone-muted">Loading…</div>}
          {error && <div className="p-6 text-oxblood">Error: {error.message}</div>}
          {task && (
            <>
              <header className="flex items-start justify-between gap-4 border-b border-hairline p-4">
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span
                      className={`rounded px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.18em] ${
                        STATE_BADGE[task.state] ?? STATE_BADGE.backlog
                      }`}
                    >
                      {task.state}
                    </span>
                    <span className="font-mono text-xs text-bone-faint">{task.id}</span>
                  </div>
                  <h2 className="mt-2 text-xl font-semibold leading-tight tracking-tight text-bone">
                    {task.title}
                  </h2>
                  <div className="mt-3 flex flex-wrap items-center gap-4 text-xs">
                    <label className="flex items-center gap-2 text-bone-muted">
                      <span className="text-[10px] uppercase tracking-[0.15em] text-bone-faint">
                        Mode
                      </span>
                      <select
                        value={task.agent_mode}
                        onChange={(e) =>
                          void onModeChange(e.target.value as AgentMode)
                        }
                        className="rounded border border-hairline-strong bg-pitch px-2 py-1 text-xs font-medium text-bone focus:border-moss focus:outline-none focus:ring-1 focus:ring-moss"
                      >
                        {AGENT_MODES.map((m) => (
                          <option key={m.value} value={m.value}>
                            {m.label}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label className="flex items-center gap-2 text-bone-muted">
                      <span className="text-[10px] uppercase tracking-[0.15em] text-bone-faint">
                        Model
                      </span>
                      <select
                        value={task.agent_model}
                        onChange={(e) =>
                          void onModelChange(e.target.value as AgentModel)
                        }
                        className="rounded border border-hairline-strong bg-pitch px-2 py-1 text-xs font-medium text-bone focus:border-moss focus:outline-none focus:ring-1 focus:ring-moss"
                      >
                        {AGENT_MODELS.map((m) => (
                          <option key={m.value} value={m.value}>
                            {m.label}
                          </option>
                        ))}
                      </select>
                    </label>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={onClose}
                  aria-label="Close"
                  className="rounded p-1 text-bone-muted transition hover:bg-pitch-100 hover:text-bone"
                >
                  ✕
                </button>
              </header>

              <TaskActionBar
                taskState={task.state}
                isStarting={startTask.isPending}
                isStopping={stopTask.isPending}
                isDeleting={deleteTask.isPending}
                onStart={() => void onStart()}
                onStop={() => void onStop()}
                onEdit={() => setEditing(true)}
                onDelete={() => void onDelete()}
              />

              <div className="flex min-h-0 flex-1 flex-col lg:flex-row">
                <div className="flex min-w-0 flex-1 flex-col">
                  <div className="flex-1 space-y-6 overflow-y-auto p-4">
                    <section>
                      <h3 className="text-[10px] font-semibold uppercase tracking-[0.2em] text-bone-faint">
                        Brief
                      </h3>
                      <div className="prose prose-sm prose-invert mt-2 max-w-none prose-headings:text-bone prose-p:text-bone prose-strong:text-bone prose-a:text-moss-bright prose-code:text-moss-bright prose-pre:bg-pitch prose-pre:border prose-pre:border-hairline">
                        <ReactMarkdown remarkPlugins={[remarkGfm]}>{task.brief}</ReactMarkdown>
                      </div>
                    </section>

                    <section>
                      <h3 className="text-[10px] font-semibold uppercase tracking-[0.2em] text-bone-faint">
                        History
                      </h3>
                      {task.history ? (
                        <div className="prose prose-sm prose-invert mt-2 max-w-none prose-headings:text-bone prose-p:text-bone prose-strong:text-bone prose-a:text-moss-bright prose-code:text-moss-bright prose-pre:bg-pitch prose-pre:border prose-pre:border-hairline">
                          <ReactMarkdown remarkPlugins={[remarkGfm]}>{task.history}</ReactMarkdown>
                        </div>
                      ) : (
                        <p className="mt-2 text-sm italic text-bone-faint">No history yet.</p>
                      )}
                    </section>

                    {(task.state === "active" || task.state === "waiting") && (
                      <LiveLog taskId={task.id} />
                    )}
                  </div>

                  <ChatInput
                    taskState={task.state}
                    waitingQuestion={task.waiting_question}
                    pendingCount={task.pending_messages.length}
                    isSending={replyTask.isPending}
                    error={chatError}
                    onSend={onSend}
                  />
                </div>

                <FilesPanel />
              </div>
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
