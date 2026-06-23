import MDEditor from "@uiw/react-md-editor";
import "@uiw/react-md-editor/markdown-editor.css";
import { useEffect, useState } from "react";
import { useTheme } from "../hooks/useTheme";
import type { TaskFile } from "../types";
import { cn } from "../utils/cn";
import { Button } from "./ui/Button";
import { IconButton } from "./ui/IconButton";

type PreviewMode = "edit" | "preview" | "live";

function isMobile() {
  return window.innerWidth < 768;
}

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
  const [previewMode, setPreviewMode] = useState<PreviewMode>(() =>
    isMobile() ? "preview" : "live"
  );

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
        <div className="flex shrink-0 items-center justify-between gap-2 border-b border-hairline px-4 py-3">
          <span className="min-w-0 truncate font-mono text-sm text-ink">
            {file.path}
          </span>
          <div className="flex shrink-0 items-center gap-2">
            {/* Mode toggle */}
            <div className="flex rounded border border-hairline overflow-hidden">
              {(["edit", "preview", "live"] as PreviewMode[]).map((mode) => (
                <Button
                  key={mode}
                  type="button"
                  archetype="segmented"
                  variant={previewMode === mode ? "secondary" : "ghost"}
                  size="sm"
                  onClick={() => setPreviewMode(mode)}
                  className={cn(
                    "text-[10px] uppercase tracking-wide px-2 py-1",
                    mode === "live" ? "hidden sm:flex" : "",
                  )}
                >
                  {mode === "live" ? "Split" : mode.charAt(0).toUpperCase() + mode.slice(1)}
                </Button>
              ))}
            </div>

            {dirty && (
              <span className="hidden text-[10px] text-ink-muted sm:inline">Unsaved</span>
            )}
            {saveError && (
              <span className="max-w-xs truncate text-[10px] text-danger">{saveError}</span>
            )}
            {onSave && (
              <Button
                type="button"
                variant="secondary"
                size="sm"
                onClick={() => void handleSave()}
                disabled={savePending || !dirty || content === null}
                loading={savePending}
              >
                {savePending ? "Saving…" : "Save"}
              </Button>
            )}
            <IconButton
              type="button"
              variant="default"
              onClick={onClose}
              aria-label="Close editor"
              size="compact"
            >
              ✕
            </IconButton>
          </div>
        </div>

        {/* Editor body */}
        <div className="cronos-md-editor min-h-0 flex-1 overflow-hidden" data-color-mode={theme}>
          {error ? (
            <p className="p-4 text-sm text-danger">{error}</p>
          ) : content === null ? (
            <p className="p-4 text-sm text-ink-muted">Loading…</p>
          ) : previewMode === "preview" ? (
            // Pure preview: use the bare markdown renderer so we own the
            // scroll container and avoid MDEditor's height/toolbar quirks.
            <div className="h-full overflow-y-auto">
              <MDEditor.Markdown source={content} />
            </div>
          ) : (
            <MDEditor
              value={content}
              onChange={handleChange}
              height="100%"
              visibleDragbar={false}
              preview={previewMode}
            />
          )}
        </div>
      </div>
    </div>
  );
}
