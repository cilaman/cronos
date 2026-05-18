import MDEditor from "@uiw/react-md-editor";
import "@uiw/react-md-editor/markdown-editor.css";
import { useEffect, useState } from "react";
import { useTheme } from "../hooks/useTheme";
import type { TaskFile } from "../types";

interface Props {
  file: TaskFile;
  fileUrl: string;
  onSave?: (file: TaskFile, content: string) => Promise<void>;
  savePending?: boolean;
  onClose: () => void;
}

export function MarkdownEditorModal({ file, fileUrl, onSave, savePending, onClose }: Props) {
  const [theme] = useTheme();
  const [content, setContent] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [dirty, setDirty] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  useEffect(() => {
    fetch(fileUrl)
      .then((r) => {
        if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
        return r.text();
      })
      .then((text) => {
        setContent(text);
        setDirty(false);
      })
      .catch((e: unknown) =>
        setError(e instanceof Error ? e.message : String(e))
      );
  }, [fileUrl]);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") {
        onClose();
        return;
      }
      if (e.key === "s" && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        if (onSave && dirty && content !== null && !savePending) {
          void handleSave();
        }
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [onClose, onSave, dirty, content, savePending]);

  async function handleSave() {
    if (!onSave || content === null) return;
    setSaveError(null);
    try {
      await onSave(file, content);
      setDirty(false);
    } catch (e: unknown) {
      setSaveError(e instanceof Error ? e.message : String(e));
    }
  }

  function handleChange(value: string | undefined) {
    setContent(value ?? "");
    setDirty(true);
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-4 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        className="flex max-h-[92vh] w-full max-w-6xl flex-col overflow-hidden rounded-lg border border-hairline bg-surface-1 shadow-lift"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex shrink-0 items-center justify-between gap-4 border-b border-hairline px-4 py-3">
          <span className="min-w-0 truncate font-mono text-sm text-ink">
            {file.path}
          </span>
          <div className="flex shrink-0 items-center gap-2">
            {dirty && (
              <span className="text-[10px] text-ink-muted">Unsaved changes</span>
            )}
            {saveError && (
              <span className="max-w-xs truncate text-[10px] text-danger">{saveError}</span>
            )}
            {onSave && (
              <button
                type="button"
                onClick={() => void handleSave()}
                disabled={savePending || !dirty || content === null}
                className="rounded border border-hairline px-3 py-1 text-xs text-ink-muted transition hover:border-hairline-strong hover:text-ink disabled:opacity-40"
              >
                {savePending ? "Saving…" : "Save"}
              </button>
            )}
            <button
              type="button"
              onClick={onClose}
              aria-label="Close"
              className="rounded p-1 text-ink-muted transition hover:bg-surface-2 hover:text-ink"
            >
              ✕
            </button>
          </div>
        </div>

        {/* Editor body */}
        <div className="cronos-md-editor min-h-0 flex-1 overflow-hidden" data-color-mode={theme}>
          {error ? (
            <p className="p-4 text-sm text-danger">{error}</p>
          ) : content === null ? (
            <p className="p-4 text-sm text-ink-muted">Loading…</p>
          ) : (
            <MDEditor
              value={content}
              onChange={handleChange}
              height="100%"
              visibleDragbar={false}
              preview="live"
            />
          )}
        </div>
      </div>
    </div>
  );
}
