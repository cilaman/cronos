import { useEffect, useMemo, useRef, useState } from "react";
import { parseHistory } from "../parse-history";
import {
  LiveStatus,
  StreamEntry,
  ToolCallEntry,
  ToolResultEntry,
  useLiveStream,
} from "../hooks/useLiveStream";
import type { Task } from "../types";
import {
  EntryShell,
  MarkdownBody,
  SystemRow,
  ThinkingBlock,
} from "./ConversationEntry";
import { ToolCallBlock, ToolResultBlock } from "./ToolBlock";

interface Props {
  task: Task;
}

function StatusPill({ status }: { status: LiveStatus }) {
  const map: Record<LiveStatus, { dot: string; text: string; label: string }> = {
    connecting: {
      dot: "bg-warning",
      text: "text-warning",
      label: "connecting",
    },
    live: {
      dot: "bg-accent-bright anim-pulse-dot",
      text: "text-accent-bright",
      label: "live",
    },
    ended: {
      dot: "bg-ink-faint",
      text: "text-ink-faint",
      label: "ended",
    },
    error: {
      dot: "bg-danger",
      text: "text-danger",
      label: "stream error",
    },
  };
  const tone = map[status];
  return (
    <span
      className={`inline-flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-[0.22em] ${tone.text}`}
    >
      <span aria-hidden className={`h-1.5 w-1.5 rounded-full ${tone.dot}`} />
      {tone.label}
    </span>
  );
}

interface LiveGroup {
  startIndex: number;
  text: string[];
  toolCalls: ToolCallEntry[];
  thinking: string[];
}

interface LiveBucket {
  groups: LiveGroup[];
  systems: { id: string; text: string }[];
  results: ToolResultEntry[];
}

function bucketLive(entries: StreamEntry[]): LiveBucket {
  const groups: LiveGroup[] = [];
  const systems: { id: string; text: string }[] = [];
  const results: ToolResultEntry[] = [];
  let current: LiveGroup | null = null;
  entries.forEach((entry, idx) => {
    if (entry.kind === "system") {
      systems.push({ id: entry.id, text: entry.text });
      current = null;
      return;
    }
    if (entry.kind === "tool_result") {
      results.push(entry);
      current = null;
      return;
    }
    if (!current) {
      current = { startIndex: idx, text: [], toolCalls: [], thinking: [] };
      groups.push(current);
    }
    if (entry.kind === "assistant") current.text.push(entry.text);
    else if (entry.kind === "tool_call") current.toolCalls.push(entry);
    else if (entry.kind === "thinking") current.thinking.push(entry.text);
  });
  return { groups, systems, results };
}

export function ConversationStream({ task }: Props) {
  const streamEnabled = task.state === "active" || task.state === "waiting";
  const { entries: liveEntries, status: liveStatus } = useLiveStream(
    task.id,
    streamEnabled,
  );

  const historyItems = useMemo(() => parseHistory(task.history), [task.history]);
  const bucket = useMemo(() => bucketLive(liveEntries), [liveEntries]);

  const resultByToolUseId = useMemo(() => {
    const map = new Map<string, ToolResultEntry>();
    for (const r of bucket.results) {
      if (r.toolUseId) map.set(r.toolUseId, r);
    }
    return map;
  }, [bucket.results]);

  // Bottom sentinel — used to auto-stick to bottom and to surface the
  // "new activity" pill when the user has scrolled away.
  const endRef = useRef<HTMLDivElement>(null);
  const sectionRef = useRef<HTMLElement>(null);
  const [atBottom, setAtBottom] = useState(true);
  const [hasNewBelow, setHasNewBelow] = useState(false);

  // Observe the bottom sentinel against its nearest scrolling ancestor.
  useEffect(() => {
    const target = endRef.current;
    if (!target) return;
    const observer = new IntersectionObserver(
      (entries) => {
        const entry = entries[0];
        const visible = entry.isIntersecting;
        setAtBottom(visible);
        if (visible) setHasNewBelow(false);
      },
      { threshold: 0, rootMargin: "0px 0px 0px 0px" },
    );
    observer.observe(target);
    return () => observer.disconnect();
  }, []);

  // On new content: if the user is at the bottom, snap to bottom. Otherwise
  // surface the "new activity" pill (only when live content arrives — pure
  // history reloads shouldn't pop the pill).
  const lastCountsRef = useRef({ history: 0, live: 0 });
  useEffect(() => {
    const prev = lastCountsRef.current;
    const liveGrew = liveEntries.length > prev.live;
    lastCountsRef.current = { history: historyItems.length, live: liveEntries.length };

    if (atBottom) {
      endRef.current?.scrollIntoView({ block: "end" });
    } else if (liveGrew) {
      setHasNewBelow(true);
    }
  }, [historyItems.length, liveEntries.length, atBottom]);

  function scrollToBottom() {
    endRef.current?.scrollIntoView({ block: "end", behavior: "smooth" });
    setHasNewBelow(false);
  }

  const isEmpty = historyItems.length === 0 && liveEntries.length === 0;
  const lastGroupIdx = bucket.groups.length - 1;

  // Orphaned tool results (whose tool_use_id never matched a tool_call).
  const orphanResults = useMemo(
    () =>
      bucket.results.filter(
        (r) =>
          !r.toolUseId ||
          !bucket.groups.some((g) =>
            g.toolCalls.some((c) => c.toolUseId === r.toolUseId),
          ),
      ),
    [bucket],
  );

  return (
    <section ref={sectionRef} className="relative">
      <div className="sticky top-0 z-10 -mt-1 mb-2 flex items-center justify-between border-b border-hairline/60 bg-surface-1/95 px-1 py-2 backdrop-blur supports-[backdrop-filter]:bg-surface-1/80">
        <h3 className="font-display text-[10px] font-semibold uppercase tracking-[0.24em] text-ink-faint">
          Conversation
        </h3>
        {streamEnabled && <StatusPill status={liveStatus} />}
      </div>

      <div className="rounded border border-hairline bg-canvas/40 px-3 py-1 shadow-inset-hairline">
        {isEmpty && (
          <div className="flex items-center justify-center py-10">
            <p className="font-mono text-[11px] text-ink-faint">
              // no exchanges yet — send the first message below
            </p>
          </div>
        )}

        {historyItems.map((item, idx) => {
          if (item.kind === "unparsed") {
            return (
              <EntryShell key={`h:${idx}`} role="system">
                <pre className="whitespace-pre-wrap font-mono text-[11px] text-ink-muted">
                  {item.body}
                </pre>
              </EntryShell>
            );
          }
          return (
            <EntryShell
              key={`h:${idx}`}
              role={item.role}
              timestamp={item.timestamp}
            >
              <MarkdownBody source={item.body} />
            </EntryShell>
          );
        })}

        {task.pending_messages.map((msg, idx) => (
          <EntryShell key={`p:${idx}`} role="user" enter>
            <div className="mb-1 font-mono text-[9px] uppercase tracking-[0.22em] text-warning">
              queued
            </div>
            <MarkdownBody source={msg} />
          </EntryShell>
        ))}

        {bucket.groups.map((group, gi) => {
          const text = group.text.join("");
          const isLatest = gi === lastGroupIdx && liveStatus === "live";
          return (
            <EntryShell
              key={`lg:${group.startIndex}`}
              role="agent"
              isStreaming={isLatest}
              enter
            >
              <div className="space-y-2">
                {group.thinking.map((t, ti) => (
                  <ThinkingBlock key={`th:${ti}`} text={t} />
                ))}
                {text && <MarkdownBody source={text} />}
                {group.toolCalls.length > 0 && (
                  <div className="space-y-1.5">
                    {group.toolCalls.map((call) => {
                      const r = resultByToolUseId.get(call.toolUseId);
                      return (
                        <ToolCallBlock
                          key={call.id}
                          name={call.name}
                          input={call.input}
                          matchedResult={
                            r ? { output: r.output, isError: r.isError } : null
                          }
                        />
                      );
                    })}
                  </div>
                )}
              </div>
            </EntryShell>
          );
        })}

        {orphanResults.map((r) => (
          <EntryShell key={`tr:${r.id}`} role="system" enter>
            <ToolResultBlock output={r.output} isError={r.isError} />
          </EntryShell>
        ))}

        {bucket.systems.length > 0 && (
          <div className="mt-2 space-y-px">
            {bucket.systems.map((s) => (
              <SystemRow key={s.id} text={s.text} />
            ))}
          </div>
        )}

        <div ref={endRef} aria-hidden className="h-px w-full" />
      </div>

      {hasNewBelow && (
        <div className="sticky bottom-2 z-10 mt-2 flex justify-center">
          <button
            type="button"
            onClick={scrollToBottom}
            className="inline-flex items-center gap-1.5 rounded-full border border-accent/40 bg-canvas px-3 py-1.5 font-mono text-[10px] uppercase tracking-[0.22em] text-accent-bright shadow-accent-glow transition hover:bg-surface-2"
          >
            ↓ new activity
          </button>
        </div>
      )}
    </section>
  );
}
