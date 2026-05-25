import { useCallback, useEffect, useState } from "react";

type RunEvent = { type: string; task_id?: string };

function parseRunEvent(data: string): RunEvent | null {
  try {
    return JSON.parse(data) as RunEvent;
  } catch {
    return null;
  }
}

/**
 * Tracks which tasks are actively executing in a space.
 *
 * Opens a persistent SSE connection to /api/spaces/{spaceId}/stream and
 * maintains a Set of currently-running task IDs. Call `seed(ids)` once
 * after the board loads to populate the initial state without waiting for
 * the next SSE event.
 */
export function useRunning(spaceId: string | null): {
  isRunning: (id: string) => boolean;
  seed: (ids: readonly string[]) => void;
} {
  const [runningIds, setRunningIds] = useState<ReadonlySet<string>>(new Set());

  useEffect(() => {
    if (!spaceId) {
      setRunningIds(new Set());
      return;
    }

    const es = new EventSource(`/api/spaces/${spaceId}/stream`);

    es.onmessage = (e: MessageEvent<string>) => {
      const event = parseRunEvent(e.data);
      if (!event || typeof event.task_id !== "string") return;
      const id = event.task_id;
      if (event.type === "run_start") {
        setRunningIds((prev) => {
          const next = new Set(prev);
          next.add(id);
          return next;
        });
      } else if (event.type === "run_end") {
        setRunningIds((prev) => {
          const next = new Set(prev);
          next.delete(id);
          return next;
        });
      }
    };

    return () => {
      es.close();
      setRunningIds(new Set());
    };
  }, [spaceId]);

  const seed = useCallback((ids: readonly string[]) => {
    if (ids.length === 0) return;
    setRunningIds((prev) => {
      const next = new Set(prev);
      for (const id of ids) next.add(id);
      return next;
    });
  }, []);

  const isRunning = useCallback(
    (id: string) => runningIds.has(id),
    [runningIds],
  );

  return { isRunning, seed };
}
