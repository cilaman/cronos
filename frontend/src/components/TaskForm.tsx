import { useEffect, useState } from "react";
import { AGENT_MODELS, type AgentModel } from "../types";

interface Props {
  title?: string;
  heading: string;
  initialTitle?: string;
  initialBrief?: string;
  initialModel?: AgentModel;
  showModel?: boolean;
  submitting?: boolean;
  error?: string | null;
  onSubmit: (body: {
    title: string;
    brief: string;
    agent_model?: AgentModel;
  }) => void;
  onCancel: () => void;
}

export function TaskForm({
  heading,
  initialTitle = "",
  initialBrief = "",
  initialModel = "default",
  showModel = true,
  submitting = false,
  error = null,
  onSubmit,
  onCancel,
}: Props) {
  const [title, setTitle] = useState(initialTitle);
  const [brief, setBrief] = useState(initialBrief);
  const [model, setModel] = useState<AgentModel>(initialModel);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onCancel();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onCancel]);

  const canSubmit = title.trim().length > 0 && !submitting;

  return (
    <div
      className="fixed inset-0 z-40 flex items-stretch justify-center bg-black/70 p-0 backdrop-blur-sm sm:items-center sm:p-4"
      onClick={onCancel}
    >
      <form
        onClick={(e) => e.stopPropagation()}
        onSubmit={(e) => {
          e.preventDefault();
          if (!canSubmit) return;
          const body: { title: string; brief: string; agent_model?: AgentModel } = {
            title: title.trim(),
            brief: brief.trim(),
          };
          if (showModel) body.agent_model = model;
          onSubmit(body);
        }}
        className="flex h-full w-full max-w-2xl flex-col overflow-hidden border border-hairline bg-pitch-50 shadow-lift sm:h-auto sm:max-h-[90vh] sm:rounded-lg"
      >
        <header className="flex items-center justify-between border-b border-hairline p-4">
          <h2 className="text-lg font-semibold tracking-tight text-bone">{heading}</h2>
          <button
            type="button"
            onClick={onCancel}
            aria-label="Close"
            className="rounded p-1 text-bone-muted transition hover:bg-pitch-100 hover:text-bone"
          >
            ✕
          </button>
        </header>
        <div className="flex-1 space-y-4 overflow-y-auto p-4">
          <div className="flex flex-col gap-3 sm:flex-row">
            <label className="block flex-1">
              <span className="text-[10px] font-semibold uppercase tracking-[0.2em] text-bone-faint">
                Title
              </span>
              <input
                autoFocus
                type="text"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                maxLength={200}
                required
                className="mt-1 block w-full rounded border border-hairline-strong bg-pitch px-3 py-2 text-sm text-bone placeholder:text-bone-faint focus:border-moss focus:outline-none focus:ring-1 focus:ring-moss"
              />
            </label>
            {showModel && (
              <label className="block sm:w-40">
                <span className="text-[10px] font-semibold uppercase tracking-[0.2em] text-bone-faint">
                  Model
                </span>
                <select
                  value={model}
                  onChange={(e) => setModel(e.target.value as AgentModel)}
                  className="mt-1 block w-full rounded border border-hairline-strong bg-pitch px-3 py-2 text-sm text-bone focus:border-moss focus:outline-none focus:ring-1 focus:ring-moss"
                >
                  {AGENT_MODELS.map((m) => (
                    <option key={m.value} value={m.value}>
                      {m.label}
                    </option>
                  ))}
                </select>
              </label>
            )}
          </div>
          <label className="block">
            <span className="text-[10px] font-semibold uppercase tracking-[0.2em] text-bone-faint">
              Brief
            </span>
            <textarea
              value={brief}
              onChange={(e) => setBrief(e.target.value)}
              rows={10}
              placeholder="Describe what the agent should do. Markdown supported."
              className="mt-1 block w-full rounded border border-hairline-strong bg-pitch px-3 py-2 font-mono text-sm text-bone placeholder:text-bone-faint focus:border-moss focus:outline-none focus:ring-1 focus:ring-moss"
            />
          </label>
          {error && (
            <p className="rounded border border-oxblood/40 bg-oxblood/15 px-3 py-2 text-sm text-oxblood">
              {error}
            </p>
          )}
        </div>
        <footer className="flex items-center justify-end gap-2 border-t border-hairline p-3">
          <button
            type="button"
            onClick={onCancel}
            className="rounded px-3 py-2 text-sm text-bone-muted transition hover:bg-pitch-100 hover:text-bone"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={!canSubmit}
            className="rounded border border-moss bg-moss px-4 py-2 text-sm font-medium text-bone transition hover:bg-moss-bright hover:shadow-moss-glow disabled:cursor-not-allowed disabled:border-hairline disabled:bg-pitch-100 disabled:text-bone-faint disabled:shadow-none"
          >
            {submitting ? "Saving…" : "Save"}
          </button>
        </footer>
      </form>
    </div>
  );
}
