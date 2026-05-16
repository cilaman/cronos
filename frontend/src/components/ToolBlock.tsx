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
    name: "text-bone",
    bracket: "text-bone-faint",
    rule: "border-bone-faint/40",
  },
  write: {
    name: "text-moss-bright",
    bracket: "text-moss",
    rule: "border-moss/50",
  },
  shell: {
    name: "text-brass",
    bracket: "text-brass/70",
    rule: "border-brass/50",
  },
  web: {
    name: "text-sky-300",
    bracket: "text-sky-400/70",
    rule: "border-sky-400/50",
  },
  task: {
    name: "text-bone",
    bracket: "text-bone-faint",
    rule: "border-hairline-strong",
  },
  other: {
    name: "text-bone-muted",
    bracket: "text-bone-faint",
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
      className={`border-l-2 ${hasError ? "border-oxblood/80" : tone.rule}`}
    >
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center gap-2 px-2 py-1 text-left font-mono text-[11px] transition hover:bg-pitch-100/40 focus:outline-none focus-visible:bg-pitch-100/60"
        aria-expanded={open}
      >
        <span className={tone.bracket}>{open ? "▾" : "▸"}</span>
        <span className={`font-medium ${tone.name}`}>{name}</span>
        {argSummary && (
          <span className="truncate text-bone-faint">
            {summarize(argSummary, 96)}
          </span>
        )}
        {hasError && (
          <span className="ml-auto rounded-sm bg-oxblood/20 px-1 py-px text-[9px] uppercase tracking-[0.18em] text-oxblood">
            error
          </span>
        )}
      </button>

      {open && (
        <div className="flex flex-col gap-2 px-2 pb-2">
          <div>
            <div className="mb-1 font-mono text-[9px] uppercase tracking-[0.22em] text-bone-faint">
              input
            </div>
            <pre className="max-h-64 overflow-auto whitespace-pre-wrap rounded border border-hairline bg-pitch/80 p-3 font-mono text-[11px] leading-relaxed text-bone">
              {formatInput(input)}
            </pre>
          </div>
          {matched && (
            <div>
              <div className="mb-1 flex items-center justify-between font-mono text-[9px] uppercase tracking-[0.22em] text-bone-faint">
                <span>{hasError ? "error" : "output"}</span>
                {shouldTruncate && (
                  <button
                    type="button"
                    onClick={() => setExpandedOutput((v) => !v)}
                    className="cursor-pointer rounded px-1 text-bone-muted transition hover:text-bone"
                  >
                    {expandedOutput
                      ? "collapse"
                      : `show all (${outputLines.length} lines)`}
                  </button>
                )}
              </div>
              <pre className="max-h-96 overflow-auto whitespace-pre-wrap rounded border border-hairline bg-pitch/80 p-3 font-mono text-[11px] leading-relaxed text-bone">
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
        isError ? "border-oxblood/70" : "border-hairline-strong"
      }`}
    >
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center gap-2 px-2 py-1 text-left font-mono text-[11px] transition hover:bg-pitch-100/40 focus:outline-none focus-visible:bg-pitch-100/60"
        aria-expanded={open}
      >
        <span className="text-bone-faint">{open ? "▾" : "▸"}</span>
        <span className="uppercase tracking-[0.18em] text-bone-faint">
          {isError ? "tool error" : "tool result"}
        </span>
        {preview && <span className="truncate text-bone-faint">{preview}</span>}
      </button>
      {open && (
        <pre className="mx-2 mb-2 max-h-80 overflow-auto whitespace-pre-wrap rounded border border-hairline bg-pitch/80 p-3 font-mono text-[11px] leading-relaxed text-bone">
          {output || "(empty)"}
        </pre>
      )}
    </div>
  );
}
