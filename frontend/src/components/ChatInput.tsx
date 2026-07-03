import { useEffect, useRef, useState } from "react";
import type { TaskState } from "../types";

interface Props {
  taskState: TaskState;
  waitingQuestion: string | null;
  /** Structured wait kind (backend waiting_kind). 'signoff' shows the
   * explicit Approve / Reject controls for delivery sign-off waits. */
  waitingKind?: string | null;
  pendingCount: number;
  isSending: boolean;
  error: string | null;
  onSend: (message: string, verdict?: "approve" | "reject") => Promise<void>;
  routeHint?: string;
  routeToast?: string | null;
}

function placeholderFor(state: TaskState, isSignoff: boolean): string {
  if (isSignoff) {
    return "Optional note — or feedback required to reject…";
  }
  switch (state) {
    case "backlog":
      return "Type a starting prompt or press Send to begin…";
    case "waiting":
      return "Reply to the agent…";
    case "active":
      return "Queue a follow-up message…";
    case "done":
      return "Message the agent to resume this task…";
    case "archived":
      return "This task is archived.";
  }
}

export function ChatInput({
  taskState,
  waitingQuestion,
  waitingKind,
  pendingCount,
  isSending,
  error,
  onSend,
  routeHint,
  routeToast,
}: Props) {
  const [draft, setDraft] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const isSignoff = taskState === "waiting" && waitingKind === "signoff";

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

  async function handleVerdict(verdict: "approve" | "reject") {
    if (isSending) return;
    const message = draft.trim();
    // Rejecting without feedback is meaningless — the button is disabled,
    // but guard anyway. Approving without a note sends a default.
    if (verdict === "reject" && !message) return;
    await onSend(message || "Approved.", verdict);
    setDraft("");
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
      e.preventDefault();
      if (isSignoff) {
        void handleVerdict("approve");
      } else {
        void handleSend();
      }
    }
  }

  return (
    <div className="shrink-0 border-t border-hairline bg-canvas">
      {waitingQuestion && taskState === "waiting" && (
        <div className="border-b border-amber-300 bg-amber-50 px-4 py-2 text-sm text-amber-800 dark:border-amber-400/30 dark:bg-amber-400/10 dark:text-amber-300">
          <span className="mr-2 font-display font-semibold uppercase tracking-[0.18em] text-[10px]">
            {isSignoff ? "Sign-off requested" : "Agent asks"}
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
            placeholder={placeholderFor(taskState, isSignoff)}
            className="block w-full resize-none bg-transparent text-sm text-ink placeholder:text-ink-faint focus:outline-none"
          />
          {isSignoff ? (
            <>
              <button
                type="button"
                onClick={() => void handleVerdict("reject")}
                disabled={!draft.trim() || isSending}
                title={
                  draft.trim()
                    ? "Reject the sign-off — your feedback is routed back into the workflow"
                    : "Type feedback to reject"
                }
                className="rounded border border-danger px-3 py-1.5 text-xs font-medium text-danger transition hover:bg-danger hover:text-canvas disabled:cursor-not-allowed disabled:border-hairline disabled:bg-surface-2 disabled:text-ink-faint"
              >
                Reject
              </button>
              <button
                type="button"
                onClick={() => void handleVerdict("approve")}
                disabled={isSending}
                className="rounded border border-accent bg-accent px-3 py-1.5 text-xs font-medium text-canvas transition hover:bg-accent-bright hover:shadow-accent-glow disabled:cursor-not-allowed disabled:border-hairline disabled:bg-surface-2 disabled:text-ink-faint disabled:shadow-none"
              >
                {isSending ? "Sending…" : "Approve"}
              </button>
            </>
          ) : (
            <button
              type="button"
              onClick={() => void handleSend()}
              disabled={!draft.trim() || isSending}
              className="rounded border border-accent bg-accent px-3 py-1.5 text-xs font-medium text-canvas transition hover:bg-accent-bright hover:shadow-accent-glow disabled:cursor-not-allowed disabled:border-hairline disabled:bg-surface-2 disabled:text-ink-faint disabled:shadow-none"
            >
              {isSending ? "Sending…" : "Send"}
            </button>
          )}
        </div>

        <div className="flex items-center gap-3 text-[11px] text-ink-faint">
          <span>
            <kbd className="rounded bg-surface-2 px-1 font-mono text-ink-muted ring-1 ring-hairline">
              ⌘⏎
            </kbd>{" "}
            {isSignoff ? "to approve" : "to send"}
          </span>
          {pendingCount > 0 && (
            <span className="rounded bg-surface-2 px-2 py-0.5 text-ink-muted ring-1 ring-hairline">
              queued {pendingCount}
            </span>
          )}
          {routeHint && (
            <span className="rounded bg-surface-2 px-2 py-0.5 text-ink-muted ring-1 ring-hairline">
              {routeHint}
            </span>
          )}
        </div>

        {routeToast && (
          <p className="text-xs text-accent">{routeToast}</p>
        )}
        {error && <p className="text-xs text-danger">{error}</p>}
      </div>
    </div>
  );
}
