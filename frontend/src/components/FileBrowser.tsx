import { useEffect, useRef, useState } from "react";
import type { FileCategory, TaskFile } from "../types";

// ---------------------------------------------------------------------------
// Category metadata
// ---------------------------------------------------------------------------

const CATEGORY_ICON: Record<FileCategory | "directory", string> = {
  directory: "▸",
  agent:     "🤖",
  skill:     "⚡",
  command:   "⌘",
  context:   "📖",
  image:     "🖼",
  text:      "📄",
  code:      "💻",
  document:  "📑",
  archive:   "🗜",
  binary:    "⬛",
};

const CATEGORY_LABEL: Record<FileCategory | "directory", string> = {
  directory: "Folder",
  agent:     "Agent",
  skill:     "Skill",
  command:   "Command",
  context:   "Context",
  image:     "Image",
  text:      "Text",
  code:      "Code",
  document:  "Document",
  archive:   "Archive",
  binary:    "Binary",
};

const VIEWABLE_CATEGORIES = new Set<FileCategory>(
  ["image", "text", "code", "agent", "skill", "command", "context"]
);

function formatBytes(bytes: number): string {
  if (bytes === 0) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(1024));
  return `${(bytes / 1024 ** i).toFixed(i === 0 ? 0 : 1)} ${units[i]}`;
}

// ---------------------------------------------------------------------------
// FileViewerModal
// ---------------------------------------------------------------------------

interface ViewerProps {
  file: TaskFile;
  fileUrl: string;
  downloadUrl: string;
  onClose: () => void;
}

function FileViewerModal({ file, fileUrl, downloadUrl, onClose }: ViewerProps) {
  const [content, setContent] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (file.category === "image") return;
    fetch(fileUrl)
      .then((r) => {
        if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
        return r.text();
      })
      .then(setContent)
      .catch((e: unknown) => setError(e instanceof Error ? e.message : String(e)));
  }, [fileUrl, file.category]);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-4 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        className="flex max-h-[90vh] w-full max-w-4xl flex-col overflow-hidden rounded-lg border border-hairline bg-surface-1 shadow-lift"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex shrink-0 items-center justify-between gap-4 border-b border-hairline px-4 py-3">
          <span className="min-w-0 truncate font-mono text-sm text-ink">
            {file.path}
          </span>
          <div className="flex shrink-0 items-center gap-2">
            <a
              href={downloadUrl}
              download
              className="rounded border border-hairline px-3 py-1 text-xs text-ink-muted transition hover:border-hairline-strong hover:text-ink"
            >
              Download
            </a>
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

        {/* Body */}
        <div className="min-h-0 flex-1 overflow-auto">
          {file.category === "image" ? (
            <div className="flex items-center justify-center p-4">
              <img
                src={fileUrl}
                alt={file.name}
                className="max-h-[70vh] max-w-full object-contain"
              />
            </div>
          ) : error ? (
            <p className="p-4 text-sm text-danger">{error}</p>
          ) : content === null ? (
            <p className="p-4 text-sm text-ink-muted">Loading…</p>
          ) : (
            <pre className="whitespace-pre-wrap break-all p-4 font-mono text-xs leading-relaxed text-ink">
              {content}
            </pre>
          )}
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// FileBrowser
// ---------------------------------------------------------------------------

export interface FileBrowserProps {
  files: TaskFile[];
  isLoading: boolean;
  fileUrlBuilder: (path: string, download?: boolean) => string;
  onUpload?: (file: File, subdir: string) => Promise<void>;
  uploadPending?: boolean;
}

export function FileBrowser({
  files,
  isLoading,
  fileUrlBuilder,
  onUpload,
  uploadPending,
}: FileBrowserProps) {
  const [viewing, setViewing] = useState<TaskFile | null>(null);
  const [uploadOpen, setUploadOpen] = useState(false);
  const [subdir, setSubdir] = useState("");
  const [uploadError, setUploadError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  function handleOpen(file: TaskFile) {
    if (file.is_dir) return;
    const cat = file.category as FileCategory;
    if (cat === "document") {
      window.open(fileUrlBuilder(file.path), "_blank");
      return;
    }
    if (cat === "archive" || cat === "binary") {
      const a = document.createElement("a");
      a.href = fileUrlBuilder(file.path, true);
      a.download = file.name;
      a.click();
      return;
    }
    if (VIEWABLE_CATEGORIES.has(cat)) {
      setViewing(file);
    }
  }

  async function handleUpload(e: React.FormEvent) {
    e.preventDefault();
    if (!onUpload || !fileInputRef.current?.files?.[0]) return;
    setUploadError(null);
    try {
      await onUpload(fileInputRef.current.files[0], subdir.trim());
      setSubdir("");
      if (fileInputRef.current) fileInputRef.current.value = "";
      setUploadOpen(false);
    } catch (err: unknown) {
      setUploadError(err instanceof Error ? err.message : String(err));
    }
  }

  return (
    <>
      <div className="flex flex-1 flex-col overflow-hidden">
        {/* File list */}
        <div className="min-h-0 flex-1 overflow-x-hidden overflow-y-auto">
          {isLoading ? (
            <p className="px-4 py-3 text-sm text-ink-muted">Loading…</p>
          ) : files.length === 0 ? (
            <p className="px-4 py-3 text-sm text-ink-muted">No files yet.</p>
          ) : (
            <ul className="divide-y divide-hairline">
              {files.map((file) => {
                const icon = CATEGORY_ICON[file.category as FileCategory | "directory"] ?? "📄";
                const label = CATEGORY_LABEL[file.category as FileCategory | "directory"] ?? file.category;
                const canView = !file.is_dir && VIEWABLE_CATEGORIES.has(file.category as FileCategory);
                const depth = file.path.split("/").length - 1;

                return (
                  <li
                    key={file.path}
                    className={`flex items-center gap-2 px-3 py-2 text-sm ${
                      file.is_dir
                        ? "bg-surface-1/50 text-ink-muted"
                        : "hover:bg-surface-2/50"
                    }`}
                    style={{ paddingLeft: `${0.75 + depth * 1}rem` }}
                  >
                    <span className="shrink-0 text-base leading-none" title={label}>
                      {icon}
                    </span>
                    <span
                      className={`min-w-0 flex-1 truncate font-mono text-xs ${
                        file.is_dir ? "font-medium text-ink-muted" : "text-ink"
                      }`}
                      title={file.path}
                    >
                      {file.name}
                    </span>
                    {!file.is_dir && (
                      <span className="shrink-0 text-[10px] text-ink-faint">
                        {formatBytes(file.size)}
                      </span>
                    )}
                    {!file.is_dir && (
                      <div className="flex shrink-0 items-center gap-1">
                        {canView && (
                          <button
                            type="button"
                            onClick={() => handleOpen(file)}
                            className="rounded px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-accent-bright transition hover:bg-surface-2"
                          >
                            Open
                          </button>
                        )}
                        <a
                          href={fileUrlBuilder(file.path, true)}
                          download={file.name}
                          className="rounded px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-ink-muted transition hover:bg-surface-2 hover:text-ink"
                          onClick={(e) => e.stopPropagation()}
                        >
                          ↓
                        </a>
                      </div>
                    )}
                  </li>
                );
              })}
            </ul>
          )}
        </div>

        {/* Upload section */}
        {onUpload && (
          <div className="shrink-0 border-t border-hairline">
            <button
              type="button"
              onClick={() => setUploadOpen((v) => !v)}
              className="flex w-full items-center gap-2 px-3 py-2 text-left text-xs text-ink-muted transition hover:text-ink"
            >
              <span className={`transition-transform ${uploadOpen ? "rotate-90" : ""}`}>▸</span>
              Upload file
            </button>

            {uploadOpen && (
              <form onSubmit={(e) => void handleUpload(e)} className="px-3 pb-3 space-y-2">
                <input
                  ref={fileInputRef}
                  type="file"
                  required
                  className="block w-full text-xs text-ink-muted file:mr-2 file:rounded file:border file:border-hairline file:bg-canvas file:px-2 file:py-1 file:text-xs file:text-ink"
                />
                <input
                  type="text"
                  value={subdir}
                  onChange={(e) => setSubdir(e.target.value)}
                  placeholder="Subdirectory (e.g. src/) — optional"
                  className="block w-full rounded border border-hairline bg-canvas px-2 py-1 text-xs text-ink placeholder:text-ink-faint focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent"
                />
                {uploadError && (
                  <p className="text-xs text-danger">{uploadError}</p>
                )}
                <button
                  type="submit"
                  disabled={uploadPending}
                  className="rounded border border-hairline bg-canvas px-3 py-1 text-xs text-ink transition hover:border-hairline-strong hover:bg-surface-2 disabled:opacity-50"
                >
                  {uploadPending ? "Uploading…" : "Upload"}
                </button>
              </form>
            )}
          </div>
        )}
      </div>

      {viewing && (
        <FileViewerModal
          file={viewing}
          fileUrl={fileUrlBuilder(viewing.path)}
          downloadUrl={fileUrlBuilder(viewing.path, true)}
          onClose={() => setViewing(null)}
        />
      )}
    </>
  );
}
