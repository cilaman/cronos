import { useEffect } from "react";
import { useToolContent } from "../hooks/useSpaces";
import { cn } from "../utils/cn";
import { formatRelative } from "../utils/format";
import type { AiToolEntry } from "../types";

export interface ToolDetailPanelProps {
  tool: AiToolEntry & { category: "agent" | "command" | "skill" | "context" };
  spaceId: string;
  onClose: () => void;
}

const CATEGORY_ICON: Record<string, string> = {
  agent: "🤖",
  command: "⌘",
  skill: "⚡",
  context: "📖",
};

const CATEGORY_STYLE: Record<
  string,
  { headerBg: string; iconBox: string; titleColor: string }
> = {
  agent: {
    headerBg: "bg-accent/5",
    iconBox: "bg-accent/10 border-accent/20",
    titleColor: "text-accent-bright",
  },
  command: {
    headerBg: "bg-warning/5",
    iconBox: "bg-warning/10 border-warning/20",
    titleColor: "text-warning",
  },
  skill: {
    headerBg: "bg-emerald-500/5",
    iconBox: "bg-emerald-500/10 border-emerald-500/20",
    titleColor: "text-emerald-400",
  },
  context: {
    headerBg: "bg-surface-2/60",
    iconBox: "bg-surface-2 border-hairline",
    titleColor: "text-ink",
  },
};

function ScopeBadge({ scope }: { scope: "space" | "global" }) {
  return (
    <span
      className={cn(
        "shrink-0 rounded border px-1.5 py-0.5 font-mono text-[9px] uppercase tracking-[0.14em]",
        scope === "space"
          ? "border-accent/20 bg-accent/10 text-accent-bright"
          : "border-hairline bg-surface-2 text-ink-muted",
      )}
    >
      {scope}
    </span>
  );
}

function Spinner() {
  return (
    <svg
      className="h-4 w-4 animate-spin text-ink-faint"
      xmlns="http://www.w3.org/2000/svg"
      fill="none"
      viewBox="0 0 24 24"
      aria-hidden
    >
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path
        className="opacity-75"
        fill="currentColor"
        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
      />
    </svg>
  );
}

export function ToolDetailPanel({ tool, spaceId, onClose }: ToolDetailPanelProps) {
  const { data, isLoading, isError } = useToolContent(spaceId, tool.path, tool.scope);
  const style = CATEGORY_STYLE[tool.category] ?? CATEGORY_STYLE.context;

  useEffect(() => {
    function handleKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    document.addEventListener("keydown", handleKey);
    return () => document.removeEventListener("keydown", handleKey);
  }, [onClose]);

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 z-40 bg-canvas/60 backdrop-blur-sm"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Slide-over panel */}
      <div
        role="dialog"
        aria-modal="true"
        aria-label={`Tool details: ${tool.name}`}
        className="fixed inset-y-0 right-0 z-50 flex w-[520px] max-w-[92vw] flex-col border-l border-hairline-strong bg-surface-1 shadow-lift"
      >
        {/* Header */}
        <div className={cn("border-b border-hairline px-5 py-4", style.headerBg)}>
          <div className="flex items-start justify-between gap-3">
            <div className="flex items-center gap-3">
              <span
                className={cn(
                  "flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border text-[22px] leading-none",
                  style.iconBox,
                )}
                aria-hidden="true"
              >
                {CATEGORY_ICON[tool.category] ?? "📄"}
              </span>
              <div className="min-w-0">
                <p className="font-mono text-[9px] uppercase tracking-[0.2em] text-ink-faint">
                  {tool.category}
                </p>
                <h2
                  className={cn(
                    "truncate font-display text-[16px] font-semibold tracking-[0.04em]",
                    style.titleColor,
                  )}
                >
                  {tool.name}
                </h2>
              </div>
            </div>
            <div className="flex shrink-0 items-center gap-2">
              <ScopeBadge scope={tool.scope} />
              <button
                onClick={onClose}
                className="flex h-7 w-7 items-center justify-center rounded border border-hairline bg-surface-2 text-ink-faint transition hover:border-hairline-strong hover:text-ink"
                aria-label="Close panel"
              >
                <svg width="11" height="11" viewBox="0 0 11 11" fill="none" aria-hidden="true">
                  <path
                    d="M1 1l9 9M10 1L1 10"
                    stroke="currentColor"
                    strokeWidth="1.5"
                    strokeLinecap="round"
                  />
                </svg>
              </button>
            </div>
          </div>
        </div>

        {/* Scrollable body */}
        <div className="flex-1 overflow-y-auto">
          {/* Metadata row */}
          <div className="border-b border-hairline bg-surface-2/40 px-5 py-3">
            <dl className="grid grid-cols-[5rem_1fr] gap-x-3 gap-y-1.5 text-[11px]">
              <dt className="font-mono uppercase tracking-[0.12em] text-ink-faint">Path</dt>
              <dd className="truncate font-mono text-ink-muted" title={tool.path}>
                {tool.path}
              </dd>
              <dt className="font-mono uppercase tracking-[0.12em] text-ink-faint">Modified</dt>
              <dd className="font-mono text-ink-muted">{formatRelative(tool.modified_at)}</dd>
              <dt className="font-mono uppercase tracking-[0.12em] text-ink-faint">Scope</dt>
              <dd className="font-mono capitalize text-ink-muted">{tool.scope}</dd>
            </dl>
          </div>

          {/* Description */}
          <div className="border-b border-hairline px-5 py-4">
            <p className="mb-2 font-mono text-[9px] uppercase tracking-[0.2em] text-ink-faint">
              Description
            </p>
            {tool.description ? (
              <p className="text-[13px] leading-relaxed text-ink">{tool.description}</p>
            ) : (
              <p className="text-[12px] italic text-ink-faint">No description</p>
            )}
          </div>

          {/* File content */}
          <div className="px-5 py-4">
            <p className="mb-3 font-mono text-[9px] uppercase tracking-[0.2em] text-ink-faint">
              Content
            </p>
            {isLoading && (
              <div className="flex items-center gap-2 py-4 text-[12px] text-ink-faint">
                <Spinner />
                <span>Loading file…</span>
              </div>
            )}
            {isError && (
              <div className="rounded border border-danger/20 bg-danger/5 px-3 py-2.5 text-[12px] text-danger">
                Failed to load file content.
              </div>
            )}
            {data && (
              <pre className="overflow-x-auto rounded-md border border-hairline bg-canvas p-4 font-mono text-[11px] leading-relaxed text-ink-muted">
                <code className="whitespace-pre-wrap break-words">{data.content}</code>
              </pre>
            )}
          </div>
        </div>
      </div>
    </>
  );
}
