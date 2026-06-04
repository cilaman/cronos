/**
 * runStatus.ts — Single source of truth for node-and-edge run-status styling.
 *
 * All downstream iterators (I2–I7) must import types and the mapper from here.
 * Field names on RunStatusOverlayData are FIXED — do not rename across iterations.
 */

/**
 * The five possible run-statuses a harness node can carry during or after execution.
 * Mirrors the backend HarnessRun / child-task lifecycle states.
 */
export type NodeRunStatus = 'pending' | 'in_progress' | 'done' | 'failed' | 'skipped';

/**
 * Shape merged onto `node.data` by useRunStateOverlay (I3).
 * All fields are optional so legacy harness fixtures without overlay data render
 * exactly as before (R8 invariant — no className diff on un-annotated harnesses).
 */
export interface RunStatusOverlayData {
  /** Current execution status of this node. Undefined means "no overlay active". */
  runStatus?: NodeRunStatus;
  /** ISO-8601 timestamp when the child task started (or the run reached this node). */
  startedAt?: string;
  /** ISO-8601 timestamp when the child task finished. Undefined while still running. */
  endedAt?: string;
  /**
   * ID of the Cronos task spawned for this node's agent execution.
   * Used by ChildTaskDrawer (I6) to fetch the full Task and stream logs.
   */
  childTaskId?: string;
}

/**
 * Maps a NodeRunStatus to a Tailwind class string that the node wrapper div
 * should append to its existing className.
 *
 * Styling intent (from design spec):
 *   in_progress — node pulses to signal active execution
 *   done        — node shows a completed (green-tinted) state
 *   failed      — node desaturates to signal an error path
 *   skipped     — node dims to indicate it was bypassed
 *   pending     — node remains at default appearance (no extra class)
 *
 * Returns an empty string for `undefined` / unknown statuses so callers can
 * safely spread the result without conditional logic.
 */
export function runStatusClassName(status: NodeRunStatus | undefined): string {
  switch (status) {
    case 'in_progress':
      return 'animate-pulse ring-2 ring-blue-400 ring-offset-1';
    case 'done':
      return 'ring-2 ring-green-500 ring-offset-1';
    case 'failed':
      return 'grayscale ring-2 ring-red-400 ring-offset-1';
    case 'skipped':
      return 'opacity-40';
    case 'pending':
      return '';
    default:
      return '';
  }
}
