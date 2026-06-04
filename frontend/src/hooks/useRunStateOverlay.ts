/**
 * useRunStateOverlay — coalesces SSE events (live mode) or REST snapshot
 * (replay mode) into a per-node/per-edge status map, flushed via a single
 * requestAnimationFrame per tick to satisfy R7 (no stutter for 10+ concurrent
 * in-progress nodes).
 *
 * IMPORTANT: this hook must use requestAnimationFrame exclusively for batching
 * (not startTransition, not setTimeout) per the design R7 mitigation.
 */

import { useEffect, useRef, useState, useCallback } from "react";
import type { NodeRunStatus, RunStatusOverlayData } from "../components/harness/runStatus";
import { useHarnessRunStream, useHarnessRun } from "./useHarnessRuns";
import type { HarnessRunStreamStatus } from "./useHarnessRuns";

// ---------------------------------------------------------------------------
// Public types
// ---------------------------------------------------------------------------

export type OverlayMode = "live" | "replay";

export interface RunStateOverlayResult {
  /** Per-node overlay data keyed by nodeId. */
  nodeStatuses: Map<string, RunStatusOverlayData>;
  /** Per-edge status keyed by edgeId (edge_chosen events mark edges as 'done'). */
  edgeStatuses: Map<string, NodeRunStatus>;
  /** True when at least one buffer_truncated event was received. */
  bufferTruncated: boolean;
  /** Overall stream status — mirrors HarnessRunStreamStatus; 'ended' for replay. */
  status: HarnessRunStreamStatus;
}

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------

/**
 * Reduce a node_transition event payload into a RunStatusOverlayData update.
 */
function nodeTransitionToOverlay(payload: Record<string, unknown>): RunStatusOverlayData {
  return {
    runStatus: (payload.status as NodeRunStatus) ?? undefined,
    startedAt: (payload.started_at as string) ?? undefined,
    endedAt: (payload.ended_at as string) ?? undefined,
    childTaskId: (payload.child_task_id as string) ?? undefined,
  };
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function useRunStateOverlay(
  runId: string | null,
  mode: OverlayMode,
): RunStateOverlayResult {
  // --- committed state (what React renders) ---
  const [nodeStatuses, setNodeStatuses] = useState<Map<string, RunStatusOverlayData>>(
    () => new Map(),
  );
  const [edgeStatuses, setEdgeStatuses] = useState<Map<string, NodeRunStatus>>(
    () => new Map(),
  );
  const [bufferTruncated, setBufferTruncated] = useState(false);

  // --- pending buffers (accumulated between rAF flushes) ---
  const pendingNodes = useRef<Map<string, RunStatusOverlayData>>(new Map());
  const pendingEdges = useRef<Map<string, NodeRunStatus>>(new Map());
  const pendingTruncated = useRef(false);
  const rafHandle = useRef<number | null>(null);

  // --- track the composite key so we reset when runId or mode changes ---
  const prevKeyRef = useRef<string>("");
  const currentKey = runId === null ? "" : `${mode}:${runId}`;

  // Reset all buffers and committed state when the composite key changes.
  useEffect(() => {
    if (currentKey === prevKeyRef.current) return;
    prevKeyRef.current = currentKey;

    // Cancel any pending rAF flush from prior key.
    if (rafHandle.current !== null) {
      cancelAnimationFrame(rafHandle.current);
      rafHandle.current = null;
    }

    pendingNodes.current = new Map();
    pendingEdges.current = new Map();
    pendingTruncated.current = false;

    setNodeStatuses(new Map());
    setEdgeStatuses(new Map());
    setBufferTruncated(false);
  }, [currentKey]);

  // --- flush function: called from rAF callback ---
  const scheduleFlush = useCallback(() => {
    if (rafHandle.current !== null) return; // already scheduled
    rafHandle.current = requestAnimationFrame(() => {
      rafHandle.current = null;

      const nodesToFlush = pendingNodes.current;
      const edgesToFlush = pendingEdges.current;
      const truncatedToFlush = pendingTruncated.current;

      if (nodesToFlush.size > 0) {
        pendingNodes.current = new Map();
        setNodeStatuses((prev) => {
          const next = new Map(prev);
          for (const [id, data] of nodesToFlush) {
            next.set(id, { ...prev.get(id), ...data });
          }
          return next;
        });
      }

      if (edgesToFlush.size > 0) {
        pendingEdges.current = new Map();
        setEdgeStatuses((prev) => {
          const next = new Map(prev);
          for (const [id, status] of edgesToFlush) {
            next.set(id, status);
          }
          return next;
        });
      }

      if (truncatedToFlush) {
        pendingTruncated.current = false;
        setBufferTruncated(true);
      }
    });
  }, []);

  // Cancel rAF on unmount.
  useEffect(() => {
    return () => {
      if (rafHandle.current !== null) {
        cancelAnimationFrame(rafHandle.current);
        rafHandle.current = null;
      }
    };
  }, []);

  // -------------------------------------------------------------------------
  // Live mode — consume SSE events from useHarnessRunStream
  // -------------------------------------------------------------------------

  const liveRunId = mode === "live" ? runId : null;
  const { events: liveEvents, status: liveStatus } = useHarnessRunStream(liveRunId);

  // Process new live events as they arrive.
  const processedLiveEventCount = useRef(0);

  useEffect(() => {
    if (mode !== "live") {
      processedLiveEventCount.current = 0;
      return;
    }

    const newEvents = liveEvents.slice(processedLiveEventCount.current);
    if (newEvents.length === 0) return;

    processedLiveEventCount.current = liveEvents.length;

    let dirty = false;

    for (const event of newEvents) {
      if (event.type === "node_transition") {
        const nodeId = event.node_id as string | undefined;
        if (nodeId) {
          const update = nodeTransitionToOverlay(event as Record<string, unknown>);
          pendingNodes.current.set(nodeId, {
            ...pendingNodes.current.get(nodeId),
            ...update,
          });
          dirty = true;
        }
      } else if (event.type === "edge_chosen") {
        const edgeId = (event.edge_id ?? `${event.from as string}__${event.to as string}`) as string;
        if (edgeId) {
          pendingEdges.current.set(edgeId, "done");
          dirty = true;
        }
      } else if (event.type === "buffer_truncated") {
        pendingTruncated.current = true;
        dirty = true;
      }
    }

    if (dirty) scheduleFlush();
  }, [liveEvents, mode, scheduleFlush]);

  // Reset processed count when runId/mode key changes.
  useEffect(() => {
    processedLiveEventCount.current = 0;
  }, [currentKey]);

  // -------------------------------------------------------------------------
  // Replay mode — consume snapshot from useHarnessRun
  // -------------------------------------------------------------------------

  const replayRunId = mode === "replay" ? runId : null;
  const { data: runState } = useHarnessRun(replayRunId);

  useEffect(() => {
    if (mode !== "replay" || !runState) return;

    const nodeMap = new Map<string, RunStatusOverlayData>();
    for (const [nodeId, nodeState] of Object.entries(runState.nodes_executed ?? {})) {
      nodeMap.set(nodeId, {
        runStatus: nodeState.status as NodeRunStatus,
        startedAt: nodeState.started_at ?? undefined,
        endedAt: nodeState.ended_at ?? undefined,
        childTaskId: nodeState.child_task_id ?? undefined,
      });
    }

    // Replay sets state directly (no batching needed — snapshot is atomic).
    setNodeStatuses(nodeMap);
    setEdgeStatuses(new Map()); // No edge info in REST snapshot.
    setBufferTruncated(false);
  }, [mode, runState]);

  // -------------------------------------------------------------------------
  // Derive status
  // -------------------------------------------------------------------------

  const status: HarnessRunStreamStatus =
    mode === "live" ? liveStatus : runId === null ? "ended" : "ended";

  return {
    nodeStatuses,
    edgeStatuses,
    bufferTruncated,
    status,
  };
}
