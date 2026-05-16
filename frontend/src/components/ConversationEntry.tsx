import { ReactNode } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { formatClock, formatFullTimestamp } from "../parse-history";

export const conversationProseClasses =
  "prose prose-sm prose-invert max-w-none " +
  "prose-headings:text-bone prose-headings:font-semibold prose-headings:tracking-tight " +
  "prose-p:text-bone prose-p:leading-relaxed " +
  "prose-strong:text-bone " +
  "prose-a:text-moss-bright prose-a:no-underline hover:prose-a:underline " +
  "prose-li:text-bone " +
  "prose-blockquote:border-l-moss prose-blockquote:bg-pitch/40 prose-blockquote:not-italic prose-blockquote:text-bone-muted " +
  "prose-code:rounded prose-code:bg-pitch prose-code:px-1 prose-code:py-px prose-code:text-[0.85em] prose-code:font-mono prose-code:text-moss-bright prose-code:before:hidden prose-code:after:hidden " +
  "prose-pre:bg-pitch prose-pre:border prose-pre:border-hairline prose-pre:rounded prose-pre:text-[12px] prose-pre:leading-relaxed " +
  "prose-hr:border-hairline";

interface EntryShellProps {
  role: "user" | "agent" | "system";
  timestamp?: string;
  isStreaming?: boolean;
  enter?: boolean;
  children: ReactNode;
}

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
      ? "text-moss-bright"
      : role === "user"
      ? "text-bone"
      : "text-bone-faint";
  return (
    <span
      className={`inline-flex items-center gap-1.5 font-mono text-[10px] font-medium uppercase tracking-[0.22em] ${color}`}
    >
      {label}
      {streaming && (
        <span
          aria-hidden
          className="anim-pulse-dot inline-block h-1.5 w-1.5 rounded-full bg-moss-bright"
        />
      )}
    </span>
  );
}

export function EntryShell({
  role,
  timestamp,
  isStreaming,
  enter,
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
            className="font-mono text-[11px] tabular-nums text-bone-faint"
          >
            {formatClock(timestamp)}
          </time>
        ) : (
          <span className="font-mono text-[11px] text-bone-faint">—</span>
        )}
        <RoleTag role={role} streaming={isStreaming} />
        {role === "agent" && (
          <span
            aria-hidden
            className="hidden h-px w-6 bg-moss-bright/40 sm:block"
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
    <details className="group rounded border border-hairline/60 bg-pitch/40 open:bg-pitch/60">
      <summary className="cursor-pointer select-none px-3 py-1.5 font-mono text-[10px] uppercase tracking-[0.22em] text-bone-faint transition hover:text-bone-muted">
        <span className="mr-2">▸</span>thinking
      </summary>
      <div className="border-t border-hairline/60 px-3 py-2 font-mono text-[11px] leading-relaxed text-bone-muted">
        <pre className="whitespace-pre-wrap">{text}</pre>
      </div>
    </details>
  );
}

export function SystemRow({ text }: { text: string }) {
  return (
    <div className="flex items-center gap-3 border-t border-hairline/40 py-1.5 font-mono text-[10px] uppercase tracking-[0.18em] text-bone-faint">
      <span aria-hidden>::</span>
      <span>{text}</span>
    </div>
  );
}
