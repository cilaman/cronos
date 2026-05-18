export type HistoryRole = "user" | "agent";

export interface AgentInfo {
  runIndex: number;
  model: string;
  mode: string;
}

export interface HistoryEntry {
  kind: "history";
  role: HistoryRole;
  timestamp: string;
  body: string;
  agentInfo?: AgentInfo;
}

export interface UnparsedEntry {
  kind: "unparsed";
  body: string;
}

export type ParsedHistoryItem = HistoryEntry | UnparsedEntry;

// Matches the leading line of each block: an ISO-8601 timestamp, [user] or [agent],
// and an optional metadata string (e.g. "run=2 model=claude-sonnet-4-6 mode=auto").
const HEADER = /^(\S+)\s+\[(user|agent)\](?:\s+(.+))?\s*$/;

// Backend writes each turn as `\`\`\`\nTIMESTAMP [role]\nbody\n\`\`\``, with
// entries joined by `\n\n`. We split on the boundary between two entries
// (closing fence + blank line + opening fence + timestamp lookahead) so the
// body — which may legitimately contain its own ```code fences``` — survives
// intact.
const BOUNDARY = /\n```\n\n```\n(?=\S+\s+\[(?:user|agent)\])/;

function stripWrappingFences(segment: string): string {
  let s = segment;
  if (s.startsWith("```\n")) s = s.slice(4);
  else if (s.startsWith("```")) s = s.slice(3).replace(/^\n/, "");
  if (s.endsWith("\n```")) s = s.slice(0, -4);
  else if (s.endsWith("```")) s = s.slice(0, -3);
  return s;
}

function parseAgentMeta(meta: string): AgentInfo | undefined {
  const parts: Record<string, string> = {};
  for (const pair of meta.trim().split(/\s+/)) {
    const eqIdx = pair.indexOf("=");
    if (eqIdx > 0) parts[pair.slice(0, eqIdx)] = pair.slice(eqIdx + 1);
  }
  const runStr = parts["run"];
  const model = parts["model"];
  const mode = parts["mode"];
  if (runStr === undefined || !model || !mode) return undefined;
  const runIndex = parseInt(runStr, 10);
  if (isNaN(runIndex)) return undefined;
  return { runIndex, model, mode };
}

export function parseHistory(raw: string): ParsedHistoryItem[] {
  const trimmed = raw?.trim();
  if (!trimmed) return [];

  const segments = trimmed.split(BOUNDARY);
  const items: ParsedHistoryItem[] = [];

  for (const segment of segments) {
    const inner = stripWrappingFences(segment).replace(/^\n+|\n+$/g, "");
    const newlineIdx = inner.indexOf("\n");
    const headerLine = newlineIdx === -1 ? inner : inner.slice(0, newlineIdx);
    const body = newlineIdx === -1 ? "" : inner.slice(newlineIdx + 1);

    const match = headerLine.match(HEADER);
    if (!match) {
      items.push({ kind: "unparsed", body: segment.trim() });
      continue;
    }

    const agentInfo =
      match[2] === "agent" && match[3] ? parseAgentMeta(match[3]) : undefined;

    items.push({
      kind: "history",
      role: match[2] as HistoryRole,
      timestamp: match[1],
      body,
      agentInfo,
    });
  }

  return items;
}

export function formatClock(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  const hh = d.getHours().toString().padStart(2, "0");
  const mm = d.getMinutes().toString().padStart(2, "0");
  const ss = d.getSeconds().toString().padStart(2, "0");
  return `${hh}:${mm}:${ss}`;
}

export function formatFullTimestamp(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString();
}
