import { useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  useDeleteTask,
  useReplyToTask,
  useStartTask,
  useTask,
  useUpdateTask,
} from "../hooks/useTasks";
import { LiveLog } from "./LiveLog";
import { TaskForm } from "./TaskForm";

const STATE_BADGE: Record<string, string> = {
  backlog: "bg-slate-200 text-slate-800",
  active: "bg-emerald-200 text-emerald-900",
  waiting: "bg-amber-200 text-amber-900",
  done: "bg-blue-200 text-blue-900",
};

interface Props {
  taskId: string;
  onClose: () => void;
}

export function Detail({ taskId, onClose }: Props) {
  const { data: task, isLoading, error } = useTask(taskId);
  const updateTask = useUpdateTask(taskId);
  const deleteTask = useDeleteTask();
  const startTask = useStartTask();
  const replyTask = useReplyToTask(taskId);
  const [editing, setEditing] = useState(false);
  const [reply, setReply] = useState("");

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape" && !editing) onClose();
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

  async function onStart() {
    if (!task) return;
    await startTask.mutateAsync(task.id);
  }

  async function onSendReply() {
    if (!task || !reply.trim()) return;
    await replyTask.mutateAsync(reply.trim());
    setReply("");
  }

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
                {task.state === "waiting" && (
                  <section className="rounded border border-amber-200 bg-amber-50 p-3">
                    <h3 className="text-xs font-semibold uppercase tracking-wide text-amber-900">
                      Waiting on your reply
                    </h3>
                    {task.waiting_question && (
                      <p className="mt-1 text-sm text-amber-900">{task.waiting_question}</p>
                    )}
                    <textarea
                      value={reply}
                      onChange={(e) => setReply(e.target.value)}
                      rows={3}
                      placeholder="Type your reply…"
                      className="mt-2 block w-full rounded border border-amber-300 bg-white px-3 py-2 text-sm focus:border-amber-500 focus:outline-none focus:ring-1 focus:ring-amber-500"
                    />
                    <div className="mt-2 flex items-center justify-end gap-2">
                      {replyTask.error && (
                        <span className="mr-auto text-xs text-red-700">
                          {replyTask.error.message}
                        </span>
                      )}
                      <button
                        type="button"
                        onClick={onSendReply}
                        disabled={!reply.trim() || replyTask.isPending}
                        className="rounded bg-amber-600 px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-amber-700 disabled:cursor-not-allowed disabled:bg-slate-300"
                      >
                        {replyTask.isPending ? "Sending…" : "Send reply"}
                      </button>
                    </div>
                  </section>
                )}

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

                {task.state === "active" && <LiveLog taskId={task.id} />}
              </div>

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
                  {task.state === "backlog" && (
                    <button
                      type="button"
                      onClick={onStart}
                      disabled={startTask.isPending}
                      className="rounded bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-700 disabled:opacity-50"
                    >
                      {startTask.isPending ? "Starting…" : "Start agent"}
                    </button>
                  )}
                </div>
              </footer>
              {startTask.error && (
                <p className="border-t border-red-100 bg-red-50 px-4 py-2 text-sm text-red-700">
                  {startTask.error.message}
                </p>
              )}
            </>
          )}
        </div>
      </div>

      {editing && task && (
        <TaskForm
          heading="Edit task"
          initialTitle={task.title}
          initialBrief={task.brief}
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
