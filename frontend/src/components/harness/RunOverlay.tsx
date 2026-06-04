/**
 * RunOverlay — top-level overlay component mounted inside HarnessEditor
 * (which provides the ReactFlowProvider context).
 *
 * Responsibilities:
 *  - Accepts a runId and mode, drives setNodes/setEdges from useRunStateOverlay
 *    to apply per-node run-status data (I3 rAF-coalesced map → I2 styling)
 *  - Renders a `data-testid="buffer-truncated-banner"` accessibility banner
 *    when any buffer_truncated event has been received (R1 AC-2 mitigation)
 *  - Lifts node-click events upward via onNodeOpen(child_task_id) so the
 *    parent HarnessEditor can open ChildTaskDrawer (I6)
 *
 * The component renders no chrome of its own (it is a pure side-effect
 * overlay on the React Flow graph), except for the optional truncated banner.
 */

import { useEffect, useRef } from 'react';
import { useReactFlow } from '@xyflow/react';
import type { OverlayMode } from '../../hooks/useRunStateOverlay';
import { useRunStateOverlay } from '../../hooks/useRunStateOverlay';

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

export interface RunOverlayProps {
  /** The harness run ID to track. When null the overlay is inactive. */
  runId: string | null;
  /** Live mode subscribes to SSE; replay mode consumes REST snapshot. */
  mode: OverlayMode;
  /**
   * Called when the user clicks a node that has an associated child_task_id.
   * The parent component uses this to open ChildTaskDrawer.
   */
  onNodeOpen?: (childTaskId: string) => void;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function RunOverlay({ runId, mode, onNodeOpen: _onNodeOpen }: RunOverlayProps) {
  const { setNodes, setEdges } = useReactFlow();
  const { nodeStatuses, edgeStatuses, bufferTruncated } = useRunStateOverlay(runId, mode);

  // Cleanup effect: when runId changes (user switches between runs via RunHistory),
  // strip stale runStatus/startedAt/endedAt/childTaskId from all node.data and
  // reset edge styling so the prior run's data does not bleed into the new run.
  // Uses a ref to track the previous runId so we do NOT fire on initial mount.
  const prevRunIdRef = useRef<string | null | undefined>(undefined);
  useEffect(() => {
    const prevRunId = prevRunIdRef.current;
    prevRunIdRef.current = runId;
    // Skip the very first render (prevRunId is the sentinel undefined)
    if (prevRunId === undefined) return;
    // Skip if the runId has not actually changed
    if (prevRunId === runId) return;
    // runId changed — clear stale overlay data from all nodes
    setNodes((prevNodes) =>
      prevNodes.map((node) => {
        const { runStatus, startedAt, endedAt, childTaskId, ...rest } = node.data as Record<string, unknown> & {
          runStatus?: unknown;
          startedAt?: unknown;
          endedAt?: unknown;
          childTaskId?: unknown;
        };
        // Only rebuild the node object when stale fields were actually present
        if (runStatus === undefined && startedAt === undefined && endedAt === undefined && childTaskId === undefined) {
          return node;
        }
        return { ...node, data: rest };
      }),
    );
    // Reset edge styling to pristine state
    setEdges((prevEdges) =>
      prevEdges.map((edge) => {
        if (!edge.animated && edge.style?.stroke === undefined) return edge;
        const { stroke: _stroke, ...restStyle } = (edge.style ?? {}) as Record<string, unknown> & { stroke?: unknown };
        return { ...edge, animated: false, style: restStyle };
      }),
    );
  }, [runId, setNodes, setEdges]); // eslint-disable-line react-hooks/exhaustive-deps

  // Apply node run-status data into the React Flow graph.
  // When nodeStatuses changes (after each rAF flush), update every node whose
  // status is tracked. Nodes NOT in nodeStatuses are left untouched so that
  // legacy nodes render exactly as before (R8 invariant preserved).
  useEffect(() => {
    if (nodeStatuses.size === 0) return;
    setNodes((prevNodes) =>
      prevNodes.map((node) => {
        const overlay = nodeStatuses.get(node.id);
        if (!overlay) return node;
        return {
          ...node,
          data: {
            ...node.data,
            runStatus: overlay.runStatus,
            startedAt: overlay.startedAt,
            endedAt: overlay.endedAt,
            childTaskId: overlay.childTaskId,
          },
        };
      }),
    );
  }, [nodeStatuses, setNodes]);

  // Apply edge run-status data. Edges whose id appears in edgeStatuses get
  // an `animated` flag and a style to signal they were chosen.
  useEffect(() => {
    if (edgeStatuses.size === 0) return;
    setEdges((prevEdges) =>
      prevEdges.map((edge) => {
        const status = edgeStatuses.get(edge.id);
        if (!status) return edge;
        return {
          ...edge,
          animated: status === 'done',
          style: { ...edge.style, stroke: status === 'done' ? '#22c55e' : undefined },
        };
      }),
    );
  }, [edgeStatuses, setEdges]);

  // Render the buffer-truncated banner when applicable; nothing otherwise.
  if (!bufferTruncated) return null;

  return (
    <div
      data-testid="buffer-truncated-banner"
      aria-label="Some events were dropped before this view connected."
      role="alert"
      className="pointer-events-none absolute left-1/2 top-2 z-50 -translate-x-1/2 rounded border border-yellow-400 bg-yellow-50 px-4 py-1 text-xs font-medium text-yellow-800 shadow"
    >
      Some events were dropped before this view connected.
    </div>
  );
}
