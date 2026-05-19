import { ReactNode } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { AgentInfo, formatClock, formatFullTimestamp } from "../parse-history";

export const conversationProseClasses =
  "prose prose-sm dark:prose-invert max-w-none " +
  "prose-headings:text-ink prose-headings:font-semibold prose-headings:tracking-tight " +
  "prose-p:text-ink prose-p:leading-relaxed " +
  "prose-strong:text-ink " +
  "prose-a:text-accent-bright prose-a:no-underline hover:prose-a:underline " +
  "prose-li:text-ink " +
  "prose-blockquote:border-l-accent prose-blockquote:bg-canvas/40 prose-blockquote:not-italic prose-blockquote:text-ink-muted " +
  "prose-code:rounded prose-code:bg-canvas prose-code:px-1 prose-code:py-px prose-code:text-[0.85em] prose-code:font-mono prose-code:text-accent-bright prose-code:before:hidden prose-code:after:hidden " +
  "prose-pre:bg-canvas prose-pre:border prose-pre:border-hairline prose-pre:rounded prose-pre:text-[12px] prose-pre:leading-relaxed prose-pre:overflow-x-auto " +
  "prose-hr:border-hairline";

interface EntryShellProps {
  role: "user" | "agent" | "system";
  timestamp?: string;
  isStreaming?: boolean;
  enter?: boolean;
  agentInfo?: AgentInfo;
  children: ReactNode;
}

function shortenModel(model: string): string {
  const lower = model.toLowerCase();
  if (lower.includes("opus")) return "opus";
  if (lower.includes("haiku")) return "haiku";
  if (lower.includes("sonnet")) return "sonnet";
  return model;
}

const MODEL_COLOR: Record<string, string> = {
  opus: "text-purple-400",
  sonnet: "text-accent-bright",
  haiku: "text-emerald-400",
};

export const AGENT_TYPE_COLOR: Record<string, string> = {
  explore: "text-sky-400",
  plan: "text-purple-400",
  "test-architect": "text-emerald-400",
  tester: "text-emerald-300",
  "security-officer": "text-rose-400",
  "general-purpose": "text-amber-400",
  claude: "text-accent-bright",
};

function RoleTag({
  role,
  streaming,
}: {
  role: "user" | "agent" | "system";
  streaming?: boolean;
}) {
  const label =
    role === "user" ? "USER" : role === "agent" ? "AGENT" : "SYSTEM";
  const color =
    role === "agent"
      ? "text-accent-bright"
      : role === "user"
      ? "text-ink"
      : "text-ink-faint";
  return (
    <span
      className={`inline-flex items-center gap-1.5 font-mono text-[10px] font-medium uppercase tracking-[0.22em] ${color}`}
    >
      {label}
      {streaming && (
        <span
          aria-hidden
          className="anim-pulse-dot inline-block h-1.5 w-1.5 rounded-full bg-accent-bright"
        />
      )}
    </span>
  );
}

function AgentBadge({ info }: { info: AgentInfo }) {
  const short = shortenModel(info.model);
  const modelColor = MODEL_COLOR[short] ?? "text-ink-faint";
  return (
    <div className="mt-0.5 flex flex-col gap-0.5">
      <span className="inline-flex items-center gap-1 font-mono text-[9px] tabular-nums text-ink-faint">
        <span className="rounded bg-accent/15 px-1 py-px font-semibold text-accent-bright">
          #{info.runIndex + 1}
        </span>
        <span className={modelColor}>{short}</span>
      </span>
      <span className="font-mono text-[9px] uppercase tracking-[0.14em] text-ink-faint/70">
        {info.mode}
      </span>
      {info.agents && info.agents.length > 0 && (
        <div className="flex flex-col gap-px">
          {info.agents.map((agent) => {
            const color = AGENT_TYPE_COLOR[agent] ?? "text-ink-faint";
            return (
              <span
                key={agent}
                className={`font-mono text-[8px] tracking-[0.10em] ${color}`}
              >
                ↳ {agent}
              </span>
            );
          })}
        </div>
      )}
    </div>
  );
}

export function EntryShell({
  role,
  timestamp,
  isStreaming,
  enter,
  agentInfo,
  children,
}: EntryShellProps) {
  return (
    <article
      className={`grid border-t border-hairline pt-3 sm:grid-cols-[112px_minmax(0,1fr)] sm:gap-x-4 ${
        enter ? "anim-enter" : ""
      }`}
    >
      <header className="flex flex-row items-center gap-3 pb-2 sm:flex-col sm:items-start sm:gap-1 sm:pb-0">
        {timestamp ? (
          <time
            dateTime={timestamp}
            title={formatFullTimestamp(timestamp)}
            className="font-mono text-[11px] tabular-nums text-ink-faint"
          >
            {formatClock(timestamp)}
          </time>
        ) : (
          <span className="font-mono text-[11px] text-ink-faint">—</span>
        )}
        <RoleTag role={role} streaming={isStreaming} />
        {role === "agent" && agentInfo && <AgentBadge info={agentInfo} />}
        {role === "agent" && !agentInfo && (
          <span
            aria-hidden
            className="hidden h-px w-6 bg-accent-bright/40 sm:block"
          />
        )}
      </header>
      <div className="min-w-0 pb-4">{children}</div>
    </article>
  );
}

export function MarkdownBody({ source }: { source: string }) {
  return (
    <div className={conversationProseClasses}>
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{source}</ReactMarkdown>
    </div>
  );
}

export function ThinkingBlock({ text }: { text: string }) {
  return (
    <details className="group rounded border border-hairline/60 bg-canvas/40 open:bg-canvas/60">
      <summary className="cursor-pointer select-none px-3 py-1.5 font-mono text-[10px] uppercase tracking-[0.22em] text-ink-faint transition hover:text-ink-muted">
        <span className="mr-2">▸</span>thinking
      </summary>
      <div className="border-t border-hairline/60 px-3 py-2 font-mono text-[11px] leading-relaxed text-ink-muted">
        <pre className="whitespace-pre-wrap">{text}</pre>
      </div>
    </details>
  );
}

export function SystemRow({ text, count }: { text: string; count?: number }) {
  return (
    <div className="flex items-center gap-3 border-t border-hairline/40 py-1.5 font-mono text-[10px] uppercase tracking-[0.18em] text-ink-faint">
      <span aria-hidden>::</span>
      <span>{text}</span>
      {count && count > 1 ? (
        <span className="text-ink-muted">×{count}</span>
      ) : null}
    </div>
  );
}
