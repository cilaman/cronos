import { useEffect, useRef, useState } from "react";

export type LiveStatus = "connecting" | "live" | "ended" | "error";

export interface AssistantTextEntry {
  id: string;
  kind: "assistant";
  text: string;
}

export interface ToolCallEntry {
  id: string;
  kind: "tool_call";
  toolUseId: string;
  name: string;
  input: unknown;
}

export interface ToolResultEntry {
  id: string;
  kind: "tool_result";
  toolUseId: string | null;
  output: string;
  isError: boolean;
}

export interface ThinkingEntry {
  id: string;
  kind: "thinking";
  text: string;
}

export interface SystemEntry {
  id: string;
  kind: "system";
  text: string;
}

export type StreamEntry =
  | AssistantTextEntry
  | ToolCallEntry
  | ToolResultEntry
  | ThinkingEntry
  | SystemEntry;

type RawEvent = Record<string, unknown> & { type?: string };

function isRecord(x: unknown): x is Record<string, unknown> {
  return typeof x === "object" && x !== null;
}

function extractBlocks(event: RawEvent): unknown[] {
  const msg = (event as { message?: unknown }).message;
  if (!isRecord(msg)) return [];
  const content = (msg as { content?: unknown }).content;
  return Array.isArray(content) ? content : [];
}

function blockToolResultText(block: Record<string, unknown>): string {
  const content = block.content;
  if (typeof content === "string") return content;
  if (Array.isArray(content)) {
    const parts: string[] = [];
    for (const inner of content) {
      if (isRecord(inner)) {
        if (typeof inner.text === "string") parts.push(inner.text);
      } else if (typeof inner === "string") {
        parts.push(inner);
      }
    }
    return parts.join("");
  }
  return "";
}

function parseAssistantEvent(event: RawEvent, idBase: string): StreamEntry[] {
  const out: StreamEntry[] = [];
  let i = 0;
  for (const block of extractBlocks(event)) {
    if (!isRecord(block)) continue;
    const type = block.type;
    const id = `${idBase}:${i++}`;
    if (type === "text" && typeof block.text === "string") {
      out.push({ id, kind: "assistant", text: block.text });
    } else if (type === "thinking" && typeof block.thinking === "string") {
      out.push({ id, kind: "thinking", text: block.thinking });
    } else if (type === "tool_use") {
      const name = typeof block.name === "string" ? block.name : "tool";
      const toolUseId = typeof block.id === "string" ? block.id : id;
      out.push({
        id,
        kind: "tool_call",
        toolUseId,
        name,
        input: block.input,
      });
    }
  }
  return out;
}

function parseUserEvent(event: RawEvent, idBase: string): StreamEntry[] {
  const out: StreamEntry[] = [];
  let i = 0;
  for (const block of extractBlocks(event)) {
    if (!isRecord(block)) continue;
    if (block.type !== "tool_result") continue;
    const id = `${idBase}:${i++}`;
    const toolUseId =
      typeof block.tool_use_id === "string" ? block.tool_use_id : null;
    const isError = block.is_error === true;
    out.push({
      id,
      kind: "tool_result",
      toolUseId,
      output: blockToolResultText(block),
      isError,
    });
  }
  return out;
}

export interface LiveStream {
  entries: StreamEntry[];
  status: LiveStatus;
}

export function useLiveStream(taskId: string, enabled: boolean): LiveStream {
  const [entries, setEntries] = useState<StreamEntry[]>([]);
  const [status, setStatus] = useState<LiveStatus>("connecting");
  const counter = useRef(0);

  useEffect(() => {
    if (!enabled) {
      setEntries([]);
      setStatus("ended");
      return;
    }

    setEntries([]);
    setStatus("connecting");
    counter.current = 0;
    const es = new EventSource(`/api/tasks/${taskId}/stream`);

    es.onopen = () => setStatus("live");
    es.onerror = () => setStatus("error");

    es.onmessage = (e) => {
      let event: RawEvent;
      try {
        event = JSON.parse(e.data);
      } catch {
        return;
      }
      const seq = counter.current++;
      const idBase = `${seq}`;
      let next: StreamEntry[] = [];

      if (event.type === "assistant") {
        next = parseAssistantEvent(event, idBase);
      } else if (event.type === "user") {
        next = parseUserEvent(event, idBase);
      } else if (event.type === "system" || event.type === "result") {
        const subtype = (event as { subtype?: string }).subtype;
        next = [
          {
            id: idBase,
            kind: "system",
            text: `${event.type}${subtype ? `/${subtype}` : ""}`,
          },
        ];
      }

      if (next.length) setEntries((prev) => [...prev, ...next]);
    };

    const endHandler = () => {
      setStatus("ended");
      es.close();
    };
    es.addEventListener("end", endHandler);

    return () => {
      es.removeEventListener("end", endHandler);
      es.close();
    };
  }, [taskId, enabled]);

  return { entries, status };
}
