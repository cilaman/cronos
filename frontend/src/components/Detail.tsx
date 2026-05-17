import { useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  useArchiveTask,
  useDeleteTask,
  useReplyToTask,
  useStartTask,
  useStopTask,
  useTask,
  useTransitionTask,
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
import { ConversationStream } from "./ConversationStream";
import { FilesPanel } from "./FilesPanel";
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
  const archiveTask = useArchiveTask(taskId);
  const replyTask = useReplyToTask(taskId);
  const startTask = useStartTask(taskId);
  const stopTask = useStopTask(taskId);
  const transitionTask = useTransitionTask();
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

  async function onArchive() {
    await archiveTask.mutateAsync();
  }

  async function onMarkDone() {
    if (!task) return;
    await transitionTask.mutateAsync({ id: task.id, state: "done" });
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
          className="flex h-full w-full max-w-5xl flex-col overflow-hidden border border-hairline bg-surface-1 shadow-lift sm:h-auto sm:max-h-[90vh] sm:rounded-lg"
          onClick={(e) => e.stopPropagation()}
        >
          {isLoading && <div className="p-6 text-ink-muted">Loading…</div>}
          {error && <div className="p-6 text-danger">Error: {error.message}</div>}
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
                    {task.space_name && (
                      <a
                        href={`/spaces/${task.space_id}`}
                        className="flex items-center gap-1.5 rounded border border-hairline px-2 py-0.5 text-[10px] uppercase tracking-[0.16em] text-ink-muted transition hover:border-hairline-strong hover:text-ink"
                      >
                        <span
                          aria-hidden
                          className="h-2 w-2 rounded-sm"
                          style={{
                            backgroundColor:
                              task.space_color ?? "rgb(var(--color-hairline-strong))",
                          }}
                        />
                        {task.space_icon && <span aria-hidden>{task.space_icon}</span>}
                        {task.space_name}
                      </a>
                    )}
                    <span className="font-mono text-xs text-ink-faint">{task.id}</span>
                  </div>
                  <h2 className="mt-2 text-xl font-semibold leading-tight tracking-tight text-ink">
                    {task.title}
                  </h2>
                  <div className="mt-3 flex flex-wrap items-center gap-4 text-xs">
                    <label className="flex items-center gap-2 text-ink-muted">
                      <span className="font-display text-[10px] uppercase tracking-[0.18em] text-ink-faint">
                        Mode
                      </span>
                      <select
                        value={task.agent_mode}
                        onChange={(e) =>
                          void onModeChange(e.target.value as AgentMode)
                        }
                        className="rounded border border-hairline-strong bg-canvas px-2 py-1 text-xs font-medium text-ink focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent"
                      >
                        {AGENT_MODES.map((m) => (
                          <option key={m.value} value={m.value}>
                            {m.label}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label className="flex items-center gap-2 text-ink-muted">
                      <span className="font-display text-[10px] uppercase tracking-[0.18em] text-ink-faint">
                        Model
                      </span>
                      <select
                        value={task.agent_model}
                        onChange={(e) =>
                          void onModelChange(e.target.value as AgentModel)
                        }
                        className="rounded border border-hairline-strong bg-canvas px-2 py-1 text-xs font-medium text-ink focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent"
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
                  className="rounded p-1 text-ink-muted transition hover:bg-surface-2 hover:text-ink"
                >
                  ✕
                </button>
              </header>

              <TaskActionBar
                taskState={task.state}
                isStarting={startTask.isPending}
                isStopping={stopTask.isPending}
                isDeleting={deleteTask.isPending}
                isArchiving={archiveTask.isPending}
                isMarkingDone={transitionTask.isPending}
                onStart={() => void onStart()}
                onStop={() => void onStop()}
                onEdit={() => setEditing(true)}
                onDelete={() => void onDelete()}
                onArchive={() => void onArchive()}
                onMarkDone={() => void onMarkDone()}
              />

              <div className="flex min-h-0 flex-1 flex-col lg:flex-row">
                <div className="flex min-h-0 min-w-0 flex-1 flex-col">
                  <div className="flex-1 space-y-6 overflow-y-auto overscroll-contain p-4">
                    <section>
                      <h3 className="font-display text-[10px] font-semibold uppercase tracking-[0.2em] text-ink-faint">
                        Brief
                      </h3>
                      <div className="prose prose-sm dark:prose-invert mt-2 max-w-none prose-headings:text-ink prose-p:text-ink prose-strong:text-ink prose-a:text-accent-bright prose-code:text-accent-bright prose-pre:bg-canvas prose-pre:border prose-pre:border-hairline">
                        <ReactMarkdown remarkPlugins={[remarkGfm]}>{task.brief}</ReactMarkdown>
                      </div>
                    </section>

                    <ConversationStream task={task} />
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

                <FilesPanel taskId={task.id} />
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
