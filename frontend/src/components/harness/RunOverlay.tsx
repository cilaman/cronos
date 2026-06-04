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

import { useEffect } from 'react';
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
