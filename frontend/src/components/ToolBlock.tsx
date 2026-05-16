import { useState } from "react";

type ToolFamily = "read" | "write" | "shell" | "web" | "task" | "other";

const READ_TOOLS = new Set(["Read", "Grep", "Glob", "LS", "NotebookRead"]);
const WRITE_TOOLS = new Set(["Edit", "Write", "MultiEdit", "NotebookEdit"]);
const SHELL_TOOLS = new Set(["Bash", "BashOutput", "KillShell", "KillBash"]);
const WEB_TOOLS = new Set(["WebFetch", "WebSearch"]);
const TASK_TOOLS = new Set(["Task", "TodoWrite", "ExitPlanMode"]);

function familyOf(name: string): ToolFamily {
  if (READ_TOOLS.has(name)) return "read";
  if (WRITE_TOOLS.has(name)) return "write";
  if (SHELL_TOOLS.has(name)) return "shell";
  if (WEB_TOOLS.has(name)) return "web";
  if (TASK_TOOLS.has(name)) return "task";
  return "other";
}

const FAMILY_TONE: Record<
  ToolFamily,
  { name: string; bracket: string; rule: string }
> = {
  read: {
    name: "text-ink",
    bracket: "text-ink-faint",
    rule: "border-ink-faint/40",
  },
  write: {
    name: "text-accent-bright",
    bracket: "text-accent",
    rule: "border-accent/50",
  },
  shell: {
    name: "text-warning",
    bracket: "text-warning/70",
    rule: "border-warning/50",
  },
  web: {
    name: "text-sky-700 dark:text-sky-300",
    bracket: "text-sky-600/80 dark:text-sky-400/70",
    rule: "border-sky-500/40 dark:border-sky-400/50",
  },
  task: {
    name: "text-ink",
    bracket: "text-ink-faint",
    rule: "border-hairline-strong",
  },
  other: {
    name: "text-ink-muted",
    bracket: "text-ink-faint",
    rule: "border-hairline-strong",
  },
};

const OUTPUT_LINE_LIMIT = 60;

function pickArgKey(input: unknown): string | null {
  if (!input || typeof input !== "object") return null;
  const obj = input as Record<string, unknown>;
  const preferred = [
    "file_path",
    "path",
    "command",
    "pattern",
    "url",
    "query",
    "description",
    "prompt",
  ];
  for (const key of preferred) {
    const v = obj[key];
    if (typeof v === "string" && v.length > 0) return v;
  }
  const firstString = Object.values(obj).find(
    (v): v is string => typeof v === "string" && v.length > 0,
  );
  return firstString ?? null;
}

function summarize(value: string, max = 80): string {
  const cleaned = value.replace(/\s+/g, " ").trim();
  if (cleaned.length <= max) return cleaned;
  return cleaned.slice(0, max - 1).trimEnd() + "…";
}

function formatInput(input: unknown): string {
  if (input === undefined) return "(no input)";
  try {
    return JSON.stringify(input, null, 2);
  } catch {
    return String(input);
  }
}

export interface ToolCallBlockProps {
  name: string;
  input: unknown;
  matchedResult?: {
    output: string;
    isError: boolean;
  } | null;
}

export function ToolCallBlock({
  name,
  input,
  matchedResult,
}: ToolCallBlockProps) {
  const [open, setOpen] = useState(false);
  const [expandedOutput, setExpandedOutput] = useState(false);

  const family = familyOf(name);
  const tone = FAMILY_TONE[family];
  const argSummary = pickArgKey(input);
  const matched = matchedResult ?? null;
  const hasError = matched?.isError ?? false;

  const outputLines = matched ? matched.output.split("\n") : [];
  const shouldTruncate = outputLines.length > OUTPUT_LINE_LIMIT;
  const displayedOutput = matched
    ? shouldTruncate && !expandedOutput
      ? outputLines.slice(0, OUTPUT_LINE_LIMIT).join("\n")
      : matched.output
    : "";

  return (
    <div
      className={`border-l-2 ${hasError ? "border-danger/80" : tone.rule}`}
    >
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center gap-2 px-2 py-1 text-left font-mono text-[11px] transition hover:bg-surface-2/40 focus:outline-none focus-visible:bg-surface-2/60"
        aria-expanded={open}
      >
        <span className={tone.bracket}>{open ? "▾" : "▸"}</span>
        <span className={`font-medium ${tone.name}`}>{name}</span>
        {argSummary && (
          <span className="truncate text-ink-faint">
            {summarize(argSummary, 96)}
          </span>
        )}
        {hasError && (
          <span className="ml-auto rounded-sm bg-danger/20 px-1 py-px text-[9px] uppercase tracking-[0.18em] text-danger">
            error
          </span>
        )}
      </button>

      {open && (
        <div className="flex flex-col gap-2 px-2 pb-2">
          <div>
            <div className="mb-1 font-mono text-[9px] uppercase tracking-[0.22em] text-ink-faint">
              input
            </div>
            <pre className="max-h-64 overflow-auto whitespace-pre-wrap rounded border border-hairline bg-canvas/80 p-3 font-mono text-[11px] leading-relaxed text-ink">
              {formatInput(input)}
            </pre>
          </div>
          {matched && (
            <div>
              <div className="mb-1 flex items-center justify-between font-mono text-[9px] uppercase tracking-[0.22em] text-ink-faint">
                <span>{hasError ? "error" : "output"}</span>
                {shouldTruncate && (
                  <button
                    type="button"
                    onClick={() => setExpandedOutput((v) => !v)}
                    className="cursor-pointer rounded px-1 text-ink-muted transition hover:text-ink"
                  >
                    {expandedOutput
                      ? "collapse"
                      : `show all (${outputLines.length} lines)`}
                  </button>
                )}
              </div>
              <pre className="max-h-96 overflow-auto whitespace-pre-wrap rounded border border-hairline bg-canvas/80 p-3 font-mono text-[11px] leading-relaxed text-ink">
                {displayedOutput || "(empty)"}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export interface ToolResultBlockProps {
  output: string;
  isError: boolean;
}

export function ToolResultBlock({ output, isError }: ToolResultBlockProps) {
  const [open, setOpen] = useState(false);
  const previewLine = output.split("\n", 1)[0] ?? "";
  const preview = summarize(previewLine, 96);
  return (
    <div
      className={`border-l-2 ${
        isError ? "border-danger/70" : "border-hairline-strong"
      }`}
    >
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center gap-2 px-2 py-1 text-left font-mono text-[11px] transition hover:bg-surface-2/40 focus:outline-none focus-visible:bg-surface-2/60"
        aria-expanded={open}
      >
        <span className="text-ink-faint">{open ? "▾" : "▸"}</span>
        <span className="uppercase tracking-[0.18em] text-ink-faint">
          {isError ? "tool error" : "tool result"}
        </span>
        {preview && <span className="truncate text-ink-faint">{preview}</span>}
      </button>
      {open && (
        <pre className="mx-2 mb-2 max-h-80 overflow-auto whitespace-pre-wrap rounded border border-hairline bg-canvas/80 p-3 font-mono text-[11px] leading-relaxed text-ink">
          {output || "(empty)"}
        </pre>
      )}
    </div>
  );
}
