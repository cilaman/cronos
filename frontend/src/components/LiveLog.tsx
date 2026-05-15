import { useEffect, useRef, useState } from "react";

type AnyEvent = Record<string, unknown> & { type?: string };

function extractAssistantText(event: AnyEvent): string | null {
  if (event.type !== "assistant") return null;
  const msg = (event as { message?: unknown }).message;
  if (!msg || typeof msg !== "object") return null;
  const content = (msg as { content?: unknown }).content;
  if (!Array.isArray(content)) return null;
  const parts: string[] = [];
  for (const block of content) {
    if (
      block &&
      typeof block === "object" &&
      (block as { type?: unknown }).type === "text" &&
      typeof (block as { text?: unknown }).text === "string"
    ) {
      parts.push((block as { text: string }).text);
    }
  }
  return parts.length ? parts.join("") : null;
}

interface Props {
  taskId: string;
}

export function LiveLog({ taskId }: Props) {
  const [entries, setEntries] = useState<
    { kind: "assistant" | "tool" | "system"; text: string }[]
  >([]);
  const [status, setStatus] = useState<"connecting" | "live" | "ended" | "error">(
    "connecting",
  );
  const scrollerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setEntries([]);
    setStatus("connecting");
    const es = new EventSource(`/api/tasks/${taskId}/stream`);

    es.onopen = () => setStatus("live");
    es.onerror = () => setStatus("error");

    es.onmessage = (e) => {
      let event: AnyEvent;
      try {
        event = JSON.parse(e.data);
      } catch {
        return;
      }
      const text = extractAssistantText(event);
      if (text) {
        setEntries((prev) => [...prev, { kind: "assistant", text }]);
        return;
      }
      if (event.type === "user") {
        // Tool result. Short summary.
        setEntries((prev) => [
          ...prev,
          { kind: "tool", text: "(tool result)" },
        ]);
        return;
      }
      if (event.type === "system" || event.type === "result") {
        const subtype = (event as { subtype?: string }).subtype;
        setEntries((prev) => [
          ...prev,
          { kind: "system", text: `${event.type}${subtype ? `/${subtype}` : ""}` },
        ]);
      }
    };

    es.addEventListener("end", () => {
      setStatus("ended");
      es.close();
    });

    return () => es.close();
  }, [taskId]);

  useEffect(() => {
    if (scrollerRef.current) {
      scrollerRef.current.scrollTop = scrollerRef.current.scrollHeight;
    }
  }, [entries.length]);

  return (
    <section>
      <div className="flex items-center justify-between">
        <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">
          Live
        </h3>
        <span
          className={`text-xs ${
            status === "live"
              ? "text-emerald-700"
              : status === "ended"
              ? "text-slate-500"
              : status === "error"
              ? "text-red-600"
              : "text-amber-700"
          }`}
        >
          {status}
        </span>
      </div>
      <div
        ref={scrollerRef}
        className="mt-2 max-h-[40vh] overflow-y-auto rounded border border-slate-200 bg-slate-900 p-3 font-mono text-xs leading-relaxed text-slate-100"
      >
        {entries.length === 0 ? (
          <p className="text-slate-500">
            {status === "ended"
              ? "No live activity. The agent has finished."
              : "Waiting for agent output…"}
          </p>
        ) : (
          entries.map((e, i) => (
            <div
              key={i}
              className={
                e.kind === "tool"
                  ? "text-slate-400 italic"
                  : e.kind === "system"
                  ? "text-slate-500"
                  : "whitespace-pre-wrap"
              }
            >
              {e.text}
            </div>
          ))
        )}
      </div>
    </section>
  );
}
