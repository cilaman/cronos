import { useEffect, useRef, useState } from "react";
import type { TaskState } from "../types";

interface Props {
  taskState: TaskState;
  waitingQuestion: string | null;
  pendingCount: number;
  isSending: boolean;
  error: string | null;
  onSend: (message: string) => Promise<void>;
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
  waitingQuestion,
  pendingCount,
  isSending,
  error,
  onSend,
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

  return (
    <div className="border-t border-hairline bg-canvas">
      {waitingQuestion && taskState === "waiting" && (
        <div className="border-b border-amber-300 bg-amber-50 px-4 py-2 text-sm text-amber-800 dark:border-amber-400/30 dark:bg-amber-400/10 dark:text-amber-300">
          <span className="mr-2 font-display font-semibold uppercase tracking-[0.18em] text-[10px]">
            Agent asks
          </span>
          {waitingQuestion}
        </div>
      )}
      <div className="flex flex-col gap-2 p-3">
        <div className="flex items-end gap-2 rounded-lg border border-hairline-strong bg-surface-1 px-3 py-2 shadow-inset-hairline transition focus-within:border-accent focus-within:ring-1 focus-within:ring-accent">
          <textarea
            ref={textareaRef}
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={handleKeyDown}
            rows={1}
            placeholder={placeholderFor(taskState)}
            className="block w-full resize-none bg-transparent text-sm text-ink placeholder:text-ink-faint focus:outline-none"
          />
          <button
            type="button"
            onClick={() => void handleSend()}
            disabled={!draft.trim() || isSending}
            className="rounded border border-accent bg-accent px-3 py-1.5 text-xs font-medium text-canvas transition hover:bg-accent-bright hover:shadow-accent-glow disabled:cursor-not-allowed disabled:border-hairline disabled:bg-surface-2 disabled:text-ink-faint disabled:shadow-none"
          >
            {isSending ? "Sending…" : "Send"}
          </button>
        </div>

        <div className="flex items-center gap-3 text-[11px] text-ink-faint">
          <span>
            <kbd className="rounded bg-surface-2 px-1 font-mono text-ink-muted ring-1 ring-hairline">
              ⌘⏎
            </kbd>{" "}
            to send
          </span>
          {pendingCount > 0 && (
            <span className="rounded bg-surface-2 px-2 py-0.5 text-ink-muted ring-1 ring-hairline">
              queued {pendingCount}
            </span>
          )}
        </div>

        {error && <p className="text-xs text-danger">{error}</p>}
      </div>
    </div>
  );
}
