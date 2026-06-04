import { useQueryClient } from "@tanstack/react-query";
import {
  useHarnessRun,
  useHarnessRunStream,
  useCancelHarnessRun,
} from "../hooks/useHarnessRuns";
import type { NodeState } from "../api";
import { cn } from "../utils/cn";

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

export interface HarnessRunPanelProps {
  runId: string;
  spaceId: string;
  harnessId: string;
}

// ---------------------------------------------------------------------------
// Status badge colours
// ---------------------------------------------------------------------------

type NodeStatus = NodeState["status"];
type RunStatus = "running" | "done" | "failed" | "cancelled";

const NODE_STATUS_STYLE: Record<NodeStatus, string> = {
  pending: "border-hairline bg-surface-2 text-ink-muted",
  in_progress: "border-amber-400/40 bg-amber-400/10 text-amber-600 dark:text-amber-400",
  done: "border-accent/30 bg-accent/10 text-accent-bright",
  failed: "border-danger/30 bg-danger/10 text-danger",
  skipped: "border-hairline bg-surface-2 text-ink-faint",
};

const RUN_STATUS_STYLE: Record<RunStatus, string> = {
  running: "border-amber-400/40 bg-amber-400/10 text-amber-600 dark:text-amber-400",
  done: "border-accent/30 bg-accent/10 text-accent-bright",
  failed: "border-danger/30 bg-danger/10 text-danger",
  cancelled: "border-hairline bg-surface-2 text-ink-muted",
};

function NodeStatusBadge({ status }: { status: NodeStatus }) {
  return (
    <span
      className={cn(
        "rounded border px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-[0.12em]",
        NODE_STATUS_STYLE[status],
      )}
      data-testid={`node-status-${status}`}
    >
      {status.replace("_", " ")}
    </span>
  );
}

function RunStatusBadge({ status }: { status: RunStatus }) {
  return (
    <span
      className={cn(
        "rounded border px-2 py-0.5 font-mono text-[11px] uppercase tracking-[0.12em]",
        RUN_STATUS_STYLE[status],
      )}
      data-testid={`run-status-${status}`}
    >
      {status}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Timing display
// ---------------------------------------------------------------------------

function formatTimestamp(iso: string | null): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString(undefined, {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  } catch {
    return iso;
  }
}

// ---------------------------------------------------------------------------
// Live indicator
// ---------------------------------------------------------------------------

function LiveIndicator() {
  return (
    <span className="flex items-center gap-1.5" data-testid="live-indicator">
      <span className="relative flex h-2 w-2">
        <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-accent opacity-75" />
        <span className="relative inline-flex h-2 w-2 rounded-full bg-accent" />
      </span>
      <span className="font-mono text-[10px] uppercase tracking-[0.12em] text-accent-bright">
        Live
      </span>
    </span>
  );
}

// ---------------------------------------------------------------------------
// Node row
// ---------------------------------------------------------------------------

function NodeRow({
  nodeId,
  node,
}: {
  nodeId: string;
  node: NodeState;
}) {
  return (
    <div
      className="flex items-start gap-3 border-b border-hairline px-4 py-2.5 last:border-b-0 hover:bg-surface-2/40"
      data-testid={`node-row-${nodeId}`}
    >
      <span className="min-w-[6rem] truncate font-mono text-[11px] text-ink">
        {nodeId}
      </span>
      <NodeStatusBadge status={node.status} />
      <div className="ml-auto flex gap-4 text-[10px] text-ink-faint">
        {node.started_at && (
          <span title={`Started: ${node.started_at}`}>
            &#9656; {formatTimestamp(node.started_at)}
          </span>
        )}
        {node.ended_at && (
          <span title={`Ended: ${node.ended_at}`}>
            &#9670; {formatTimestamp(node.ended_at)}
          </span>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main panel
// ---------------------------------------------------------------------------

export function HarnessRunPanel({ runId, spaceId, harnessId }: HarnessRunPanelProps) {
  const qc = useQueryClient();
  const { data: run, isLoading, isError } = useHarnessRun(runId);
  const { status: streamStatus, events } = useHarnessRunStream(
    run?.status === "running" ? runId : null,
  );

  const cancelMutation = useCancelHarnessRun();

  // Invalidate React Query cache on each SSE event
  const prevEventCount = events.length;
  if (prevEventCount > 0) {
    qc.invalidateQueries({ queryKey: ["harness-run", runId] });
    qc.invalidateQueries({ queryKey: ["harness-runs", spaceId] });
  }

  // Check for buffer_truncated synthetic event
  const hasBufferTruncated = events.some((e) => e.type === "buffer_truncated");

  function handleCancel() {
    cancelMutation.mutate(runId);
  }

  // Loading state
  if (isLoading) {
    return (
      <div
        className="flex items-center justify-center rounded-md border border-hairline bg-surface-1 p-8"
        data-testid="run-panel-loading"
      >
        <p className="font-mono text-[11px] text-ink-faint">Loading run…</p>
      </div>
    );
  }

  // Error state
  if (isError || !run) {
    return (
      <div
        className="rounded-md border border-danger/20 bg-danger/5 px-4 py-3 text-[12px] text-danger"
        data-testid="run-panel-error"
      >
        Failed to load run state.
      </div>
    );
  }

  const isRunning = run.status === "running";
  const nodes = Object.entries(run.nodes_executed);

  return (
    <div
      className="overflow-hidden rounded-md border border-hairline bg-surface-1 shadow-inset-hairline"
      data-testid="harness-run-panel"
    >
      {/* Header */}
      <div className="flex flex-wrap items-center gap-3 border-b border-hairline bg-surface-2/50 px-4 py-3">
        <div className="min-w-0 flex-1">
          <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-ink-faint">
            {harnessId}
          </p>
          <p className="mt-0.5 truncate font-mono text-[12px] text-ink-muted" title={runId}>
            {runId}
          </p>
        </div>

        <div className="flex items-center gap-3">
          {isRunning && <LiveIndicator />}
          <RunStatusBadge status={run.status} />

          {isRunning && (
            <button
              type="button"
              onClick={handleCancel}
              disabled={cancelMutation.isPending}
              aria-label="Cancel run"
              className="rounded border border-danger/30 bg-danger/10 px-2.5 py-1 font-display text-[11px] font-medium text-danger transition hover:bg-danger/20 disabled:opacity-60"
              data-testid="cancel-button"
            >
              {cancelMutation.isPending ? "Cancelling…" : "Cancel"}
            </button>
          )}
        </div>
      </div>

      {/* Buffer truncated warning */}
      {hasBufferTruncated && (
        <div
          className="flex items-center gap-2 border-b border-warning/20 bg-warning/5 px-4 py-2 text-[11px] text-warning"
          data-testid="buffer-truncated-badge"
        >
          <span>History truncated — early events may be missing</span>
        </div>
      )}

      {/* Node list */}
      {nodes.length === 0 ? (
        <div className="px-4 py-6 text-center">
          <p className="font-mono text-[11px] text-ink-faint">
            No nodes executed yet.
          </p>
        </div>
      ) : (
        <div>
          <div className="flex items-center gap-2 bg-surface-2/30 px-4 py-1.5">
            <span className="font-display text-[10px] uppercase tracking-[0.18em] text-ink-faint">
              Nodes
            </span>
            <span className="font-mono text-[10px] tabular-nums text-ink-faint">
              {String(nodes.length).padStart(2, "0")}
            </span>
          </div>
          <div className="divide-y divide-hairline">
            {nodes.map(([nodeId, node]) => (
              <NodeRow key={nodeId} nodeId={nodeId} node={node} />
            ))}
          </div>
        </div>
      )}

      {/* SSE stream status footer (debug/info, only shown when not idle) */}
      {isRunning && streamStatus === "error" && (
        <div
          className="border-t border-hairline px-4 py-2 text-[10px] text-ink-faint"
          data-testid="stream-error"
        >
          Stream disconnected — data may be stale.
        </div>
      )}
    </div>
  );
}
