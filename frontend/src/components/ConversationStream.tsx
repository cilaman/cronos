import { useEffect, useMemo, useRef, useState } from "react";
import { AgentInfo, parseHistory } from "../parse-history";
import { AGENT_TYPE_COLOR } from "./ConversationEntry";
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

interface ActiveSubagentPillProps {
  subtype: string;
}

function ActiveSubagentPill({ subtype }: ActiveSubagentPillProps) {
  const color = AGENT_TYPE_COLOR[subtype] ?? "text-ink-faint";
  return (
    <span
      className={`inline-flex items-center gap-1 font-mono text-[9px] uppercase tracking-[0.18em] ${color}`}
    >
      <span
        aria-hidden
        className="anim-pulse-dot inline-block h-1 w-1 rounded-full bg-current"
      />
      {subtype}
    </span>
  );
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

interface SystemsBlock {
  kind: "systems";
  id: string;
  rows: { text: string; count: number }[];
}

type LiveBlock =
  | { kind: "group"; group: LiveGroup }
  | SystemsBlock
  | { kind: "orphan_result"; result: ToolResultEntry };

interface LiveBucket {
  blocks: LiveBlock[];
  resultByToolUseId: Map<string, ToolResultEntry>;
}

function bucketLive(entries: StreamEntry[]): LiveBucket {
  const blocks: LiveBlock[] = [];
  const resultByToolUseId = new Map<string, ToolResultEntry>();
  const toolCallSeen = new Set<string>();
  let currentGroup: LiveGroup | null = null;

  const lastSystemsBlock = (): SystemsBlock | null => {
    const last = blocks[blocks.length - 1];
    return last && last.kind === "systems" ? last : null;
  };

  const pushSystemRow = (id: string, text: string) => {
    currentGroup = null;
    const existing = lastSystemsBlock();
    if (existing) {
      const lastRow = existing.rows[existing.rows.length - 1];
      if (lastRow && lastRow.text === text) {
        lastRow.count += 1;
      } else {
        existing.rows.push({ text, count: 1 });
      }
    } else {
      blocks.push({ kind: "systems", id, rows: [{ text, count: 1 }] });
    }
  };

  entries.forEach((entry, idx) => {
    if (entry.kind === "system") {
      pushSystemRow(entry.id, entry.text);
      return;
    }
    if (entry.kind === "goal_activity") {
      // Surface goal orchestration (child/subgoal start/end/skip) as system
      // rows so an orchestrating goal's detail view isn't blank.
      const label =
        entry.phase === "start"
          ? `▶ started ${entry.title}`
          : entry.phase === "skipped"
          ? `⤼ skipped ${entry.title} (already done)`
          : `■ ${entry.title} → ${entry.newState ?? "done"}`;
      pushSystemRow(entry.id, label);
      return;
    }
    if (entry.kind === "tool_result") {
      currentGroup = null;
      if (entry.toolUseId) resultByToolUseId.set(entry.toolUseId, entry);
      if (!entry.toolUseId || !toolCallSeen.has(entry.toolUseId)) {
        blocks.push({ kind: "orphan_result", result: entry });
      }
      return;
    }
    if (!currentGroup) {
      currentGroup = { startIndex: idx, text: [], toolCalls: [], thinking: [] };
      blocks.push({ kind: "group", group: currentGroup });
    }
    if (entry.kind === "assistant") currentGroup.text.push(entry.text);
    else if (entry.kind === "tool_call") {
      currentGroup.toolCalls.push(entry);
      toolCallSeen.add(entry.toolUseId);
    } else if (entry.kind === "thinking") currentGroup.thinking.push(entry.text);
  });

  return { blocks, resultByToolUseId };
}

export function ConversationStream({ task }: Props) {
  const streamEnabled = task.state === "active" || task.state === "waiting";
  const { entries: liveEntries, status: liveStatus } = useLiveStream(
    task.id,
    streamEnabled,
  );

  const historyItems = useMemo(() => parseHistory(task.history), [task.history]);
  const bucket = useMemo(() => bucketLive(liveEntries), [liveEntries]);

  // Derive the run index for the live (in-progress) run from the number of
  // completed agent history entries so the badge stays accurate even mid-run.
  const liveRunIndex = useMemo(
    () =>
      historyItems.filter((h) => h.kind === "history" && h.role === "agent")
        .length,
    [historyItems],
  );
  const liveAgentInfo: AgentInfo = {
    runIndex: liveRunIndex,
    model: task.agent_model,
    mode: task.agent_mode,
  };
  const { blocks, resultByToolUseId } = bucket;

  // Derive the currently-running subagent: last Agent tool_call whose toolUseId
  // has no matching tool_result yet in this stream.
  const activeSubagent = useMemo<string | null>(() => {
    if (liveStatus !== "live") return null;
    for (const block of [...blocks].reverse()) {
      if (block.kind !== "group") continue;
      for (const call of [...block.group.toolCalls].reverse()) {
        if (call.name !== "Agent") continue;
        if (resultByToolUseId.has(call.toolUseId)) continue;
        const inp = call.input as Record<string, unknown> | null;
        const subtype =
          inp && typeof inp["subagent_type"] === "string"
            ? (inp["subagent_type"] as string).toLowerCase()
            : null;
        return subtype;
      }
    }
    return null;
  }, [blocks, resultByToolUseId, liveStatus]);

  const lastGroupIdx = useMemo(() => {
    for (let i = blocks.length - 1; i >= 0; i--) {
      if (blocks[i].kind === "group") return i;
    }
    return -1;
  }, [blocks]);

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

  return (
    <section ref={sectionRef} className="relative">
      <div className="sticky top-0 z-10 -mt-1 mb-2 flex items-center justify-between border-b border-hairline/60 bg-surface-1/95 px-1 py-2 backdrop-blur supports-[backdrop-filter]:bg-surface-1/80">
        <h3 className="font-display text-[10px] font-semibold uppercase tracking-[0.24em] text-ink-faint">
          Conversation
        </h3>
        <div className="flex items-center gap-2">
          {activeSubagent && <ActiveSubagentPill subtype={activeSubagent} />}
          {streamEnabled && <StatusPill status={liveStatus} />}
        </div>
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
              agentInfo={item.agentInfo}
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

        {blocks.map((block, bi) => {
          if (block.kind === "group") {
            const group = block.group;
            const text = group.text.join("");
            const isLatest = bi === lastGroupIdx && liveStatus === "live";
            return (
              <EntryShell
                key={`lg:${group.startIndex}`}
                role="agent"
                isStreaming={isLatest}
                enter
                agentInfo={liveAgentInfo}
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
          }
          if (block.kind === "orphan_result") {
            const r = block.result;
            return (
              <EntryShell key={`tr:${r.id}`} role="system" enter>
                <ToolResultBlock output={r.output} isError={r.isError} />
              </EntryShell>
            );
          }
          return (
            <div key={`sys:${block.id}`} className="my-2 space-y-px">
              {block.rows.map((row, ri) => (
                <SystemRow
                  key={`${block.id}:${ri}`}
                  text={row.text}
                  count={row.count}
                />
              ))}
            </div>
          );
        })}

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
