import { useEffect, useState } from "react";

interface Props {
  title?: string;
  heading: string;
  initialTitle?: string;
  initialBrief?: string;
  submitting?: boolean;
  error?: string | null;
  onSubmit: (body: { title: string; brief: string }) => void;
  onCancel: () => void;
}

export function TaskForm({
  heading,
  initialTitle = "",
  initialBrief = "",
  submitting = false,
  error = null,
  onSubmit,
  onCancel,
}: Props) {
  const [title, setTitle] = useState(initialTitle);
  const [brief, setBrief] = useState(initialBrief);

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
      className="fixed inset-0 z-40 flex items-stretch justify-center bg-slate-900/50 p-0 sm:items-center sm:p-4"
      onClick={onCancel}
    >
      <form
        onClick={(e) => e.stopPropagation()}
        onSubmit={(e) => {
          e.preventDefault();
          if (canSubmit) onSubmit({ title: title.trim(), brief: brief.trim() });
        }}
        className="flex h-full w-full max-w-2xl flex-col overflow-hidden bg-white shadow-xl sm:h-auto sm:max-h-[90vh] sm:rounded-lg"
      >
        <header className="flex items-center justify-between border-b border-slate-200 p-4">
          <h2 className="text-lg font-semibold text-slate-900">{heading}</h2>
          <button
            type="button"
            onClick={onCancel}
            aria-label="Close"
            className="rounded p-1 text-slate-500 hover:bg-slate-100"
          >
            ✕
          </button>
        </header>
        <div className="flex-1 space-y-4 overflow-y-auto p-4">
          <label className="block">
            <span className="text-xs font-semibold uppercase tracking-wide text-slate-500">
              Title
            </span>
            <input
              autoFocus
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              maxLength={200}
              required
              className="mt-1 block w-full rounded border border-slate-300 px-3 py-2 text-sm focus:border-emerald-500 focus:outline-none focus:ring-1 focus:ring-emerald-500"
            />
          </label>
          <label className="block">
            <span className="text-xs font-semibold uppercase tracking-wide text-slate-500">
              Brief
            </span>
            <textarea
              value={brief}
              onChange={(e) => setBrief(e.target.value)}
              rows={10}
              placeholder="Describe what the agent should do. Markdown supported."
              className="mt-1 block w-full rounded border border-slate-300 px-3 py-2 font-mono text-sm focus:border-emerald-500 focus:outline-none focus:ring-1 focus:ring-emerald-500"
            />
          </label>
          {error && (
            <p className="rounded bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>
          )}
        </div>
        <footer className="flex items-center justify-end gap-2 border-t border-slate-200 p-3">
          <button
            type="button"
            onClick={onCancel}
            className="rounded px-3 py-2 text-sm text-slate-600 hover:bg-slate-100"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={!canSubmit}
            className="rounded bg-emerald-600 px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-emerald-700 disabled:cursor-not-allowed disabled:bg-slate-300"
          >
            {submitting ? "Saving…" : "Save"}
          </button>
        </footer>
      </form>
    </div>
  );
}
