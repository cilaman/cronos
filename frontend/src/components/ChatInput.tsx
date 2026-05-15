import { useEffect, useRef, useState } from "react";
import {
  AGENT_MODELS,
  AGENT_MODES,
  type AgentMode,
  type AgentModel,
  type TaskState,
} from "../types";
import { STATE_BADGE } from "../state-badges";

interface Props {
  taskState: TaskState;
  agentMode: AgentMode;
  agentModel: AgentModel;
  waitingQuestion: string | null;
  pendingCount: number;
  isSending: boolean;
  isStopping: boolean;
  error: string | null;
  onSend: (message: string) => Promise<void>;
  onStop: () => Promise<void>;
  onModeChange: (mode: AgentMode) => Promise<void>;
  onModelChange: (model: AgentModel) => Promise<void>;
}

function placeholderFor(state: TaskState): string {
  switch (state) {
    case "backlog":
      return "Type a starting prompt or press Send to begin…";
    case "waiting":
      return "Reply to the agent…";
    case "active":
      return "Queue a follow-up message…";
    case "done":
      return "Message the agent to resume this task…";
  }
}

export function ChatInput({
  taskState,
  agentMode,
  agentModel,
  waitingQuestion,
  pendingCount,
  isSending,
  isStopping,
  error,
  onSend,
  onStop,
  onModeChange,
  onModelChange,
}: Props) {
  const [draft, setDraft] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Auto-grow the textarea (capped by max-height).
  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 192) + "px";
  }, [draft]);

  async function handleSend() {
    const message = draft.trim();
    if (!message || isSending) return;
    await onSend(message);
    setDraft("");
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
      e.preventDefault();
      void handleSend();
    }
  }

  const isActive = taskState === "active";

  return (
    <div className="border-t border-slate-200 bg-slate-50">
      {waitingQuestion && taskState === "waiting" && (
        <div className="border-b border-amber-200 bg-amber-50 px-4 py-2 text-sm text-amber-900">
          <span className="mr-2 font-semibold uppercase tracking-wide text-[10px]">
            Agent asks
          </span>
          {waitingQuestion}
        </div>
      )}
      <div className="flex flex-col gap-2 p-3">
        <div className="flex flex-wrap items-center gap-2 text-xs">
          <span
            className={`rounded px-2 py-0.5 font-medium uppercase tracking-wide ${STATE_BADGE[taskState]}`}
          >
            {taskState}
          </span>
          <label className="flex items-center gap-1 rounded border border-slate-300 bg-white px-2 py-0.5 text-slate-700">
            <span className="text-[10px] uppercase tracking-wide text-slate-500">
              Mode
            </span>
            <select
              value={agentMode}
              onChange={(e) => void onModeChange(e.target.value as AgentMode)}
              className="bg-transparent text-xs font-medium focus:outline-none"
            >
              {AGENT_MODES.map((m) => (
                <option key={m.value} value={m.value}>
                  {m.label}
                </option>
              ))}
            </select>
          </label>
          <label className="flex items-center gap-1 rounded border border-slate-300 bg-white px-2 py-0.5 text-slate-700">
            <span className="text-[10px] uppercase tracking-wide text-slate-500">
              Model
            </span>
            <select
              value={agentModel}
              onChange={(e) => void onModelChange(e.target.value as AgentModel)}
              className="bg-transparent text-xs font-medium focus:outline-none"
            >
              {AGENT_MODELS.map((m) => (
                <option key={m.value} value={m.value}>
                  {m.label}
                </option>
              ))}
            </select>
          </label>
          {pendingCount > 0 && (
            <span className="rounded bg-slate-200 px-2 py-0.5 text-slate-700">
              queued {pendingCount}
            </span>
          )}
          <span className="ml-auto text-[11px] text-slate-500">
            <kbd className="rounded bg-slate-200 px-1 font-mono">⌘⏎</kbd> to send
          </span>
        </div>

        <div className="flex items-end gap-2 rounded-lg border border-slate-300 bg-white px-3 py-2 shadow-sm focus-within:border-slate-500 focus-within:ring-1 focus-within:ring-slate-500">
          <textarea
            ref={textareaRef}
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={handleKeyDown}
            rows={1}
            placeholder={placeholderFor(taskState)}
            className="block w-full resize-none bg-transparent text-sm text-slate-900 placeholder:text-slate-400 focus:outline-none"
          />
          <div className="flex items-center gap-1">
            {isActive && (
              <button
                type="button"
                onClick={() => void onStop()}
                disabled={isStopping}
                aria-label="Stop running agent"
                title="Stop running agent"
                className="rounded bg-red-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-red-700 disabled:cursor-not-allowed disabled:bg-slate-300"
              >
                {isStopping ? "Stopping…" : "Stop"}
              </button>
            )}
            <button
              type="button"
              onClick={() => void handleSend()}
              disabled={!draft.trim() || isSending}
              className="rounded bg-slate-900 px-3 py-1.5 text-xs font-medium text-white hover:bg-slate-700 disabled:cursor-not-allowed disabled:bg-slate-300"
            >
              {isSending ? "Sending…" : "Send"}
            </button>
          </div>
        </div>

        {error && <p className="text-xs text-red-700">{error}</p>}
      </div>
    </div>
  );
}
