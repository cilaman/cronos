import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, harnessRunStreamUrl } from "../api";
import type { HarnessRunState, RunSummary, TriggerRunResponse } from "../api";

export type { HarnessRunState, RunSummary, TriggerRunResponse };

export type HarnessRunStreamStatus = "connecting" | "live" | "ended" | "error";

export interface HarnessRunEvent {
  type: "node_transition" | "edge_chosen" | "run_status" | "buffer_truncated" | string;
  [key: string]: unknown;
}

export interface HarnessRunStream {
  events: HarnessRunEvent[];
  status: HarnessRunStreamStatus;
}

// --- query hooks ---

export function useHarnessRuns(spaceId: string, name: string) {
  return useQuery({
    queryKey: ["harness-runs", spaceId, name],
    queryFn: () => api.listHarnessRuns(spaceId, name),
    refetchInterval: 5_000,
  });
}

export function useHarnessRun(runId: string | null) {
  return useQuery({
    queryKey: ["harness-run", runId],
    queryFn: () => api.getHarnessRun(runId!),
    enabled: runId !== null,
    refetchInterval: 3_000,
  });
}

// --- mutation hooks ---

export function useTriggerHarnessRun() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ spaceId, name }: { spaceId: string; name: string }) =>
      api.triggerHarnessRun(spaceId, name),
    onSuccess: (_data, { spaceId, name }) => {
      qc.invalidateQueries({ queryKey: ["harness-runs", spaceId, name] });
    },
  });
}

export function useCancelHarnessRun() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (runId: string) => api.cancelHarnessRun(runId),
    onSuccess: (_data, runId) => {
      qc.invalidateQueries({ queryKey: ["harness-run", runId] });
      // Invalidate all harness-runs lists (we don't know spaceId/name from runId alone)
      qc.invalidateQueries({
        predicate: (q) =>
          Array.isArray(q.queryKey) && q.queryKey[0] === "harness-runs",
      });
    },
  });
}

// --- SSE stream hook ---

/**
 * Opens an EventSource SSE connection to the harness run stream endpoint.
 * Uses named-event listeners (node_transition, edge_chosen, run_status,
 * buffer_truncated) matching the discriminated envelope from I6.
 * Returns null and creates no EventSource when runId is null.
 */
export function useHarnessRunStream(runId: string | null): HarnessRunStream {
  const [events, setEvents] = useState<HarnessRunEvent[]>([]);
  const [status, setStatus] = useState<HarnessRunStreamStatus>("connecting");
  const esRef = useRef<EventSource | null>(null);

  useEffect(() => {
    if (runId === null) {
      setEvents([]);
      setStatus("ended");
      return;
    }

    setEvents([]);
    setStatus("connecting");

    const url = harnessRunStreamUrl(runId);
    const es = new EventSource(url);
    esRef.current = es;

    es.onopen = () => setStatus("live");
    es.onerror = () => setStatus("error");

    function handleNamedEvent(eventType: string) {
      return (e: MessageEvent) => {
        let payload: HarnessRunEvent;
        try {
          payload = { ...JSON.parse(e.data), type: eventType } as HarnessRunEvent;
        } catch {
          payload = { type: eventType, raw: e.data };
        }
        setEvents((prev) => [...prev, payload]);
      };
    }

    const HARNESS_EVENT_TYPES = [
      "node_transition",
      "edge_chosen",
      "run_status",
      "buffer_truncated",
    ] as const;

    const handlers: Array<[string, (e: MessageEvent) => void]> = HARNESS_EVENT_TYPES.map(
      (t) => [t, handleNamedEvent(t)],
    );

    for (const [type, handler] of handlers) {
      es.addEventListener(type, handler as EventListener);
    }

    // Generic onmessage catches any data-only frames that lack an event: field
    es.onmessage = (e) => {
      let payload: HarnessRunEvent;
      try {
        payload = JSON.parse(e.data) as HarnessRunEvent;
      } catch {
        return;
      }
      if (!payload.type) return; // skip malformed
      setEvents((prev) => [...prev, payload]);
    };

    const endHandler = () => {
      setStatus("ended");
      es.close();
    };
    es.addEventListener("end", endHandler as EventListener);

    return () => {
      for (const [type, handler] of handlers) {
        es.removeEventListener(type, handler as EventListener);
      }
      es.removeEventListener("end", endHandler as EventListener);
      es.close();
      esRef.current = null;
    };
  }, [runId]);

  return { events, status };
}
