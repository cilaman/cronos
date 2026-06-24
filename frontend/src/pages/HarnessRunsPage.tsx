import { useParams, useSearchParams } from "react-router-dom";
import { useHarnessRuns, useTriggerHarnessRun } from "../hooks/useHarnessRuns";
import type { RunSummary } from "../api";
import { HarnessRunPanel } from "../components/HarnessRunPanel";
import { Badge } from "../components/ui/Badge";
import { getToneRunStatus } from "../utils/badgeTone";
import { PageContainer } from "../components/ui/PageContainer";
import { PageHeader } from "../components/ui/PageHeader";
import { cn } from "../utils/cn";

// ---------------------------------------------------------------------------
// Status badge
// ---------------------------------------------------------------------------

type RunStatus = RunSummary["status"];

function RunStatusBadge({ status }: { status: RunStatus }) {
  return (
    <span data-testid={`run-badge-${status}`}>
      <Badge tone={getToneRunStatus(status)}>{status}</Badge>
    </span>
  );
}

// ---------------------------------------------------------------------------
// Run row in the list
// ---------------------------------------------------------------------------

function formatRelativeTime(iso: string): string {
  try {
    const diff = Date.now() - new Date(iso).getTime();
    const seconds = Math.floor(diff / 1000);
    if (seconds < 60) return `${seconds}s ago`;
    const minutes = Math.floor(seconds / 60);
    if (minutes < 60) return `${minutes}m ago`;
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return `${hours}h ago`;
    return new Date(iso).toLocaleDateString();
  } catch {
    return iso;
  }
}

function RunListRow({
  summary,
  isSelected,
  onClick,
}: {
  summary: RunSummary;
  isSelected: boolean;
  onClick: () => void;
}) {
  return (
    <div
      role="button"
      tabIndex={0}
      onClick={onClick}
      onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && onClick()}
      className={cn(
        "flex cursor-pointer items-center gap-3 border-b border-hairline px-4 py-3 last:border-b-0 transition",
        isSelected
          ? "bg-accent/5 hover:bg-accent/8"
          : "hover:bg-surface-2/40",
      )}
      data-testid={`run-row-${summary.run_id}`}
      aria-selected={isSelected}
    >
      <div className="min-w-0 flex-1">
        <p className="truncate font-mono text-[11px] text-ink" title={summary.run_id}>
          {summary.run_id}
        </p>
        <p className="font-mono text-[10px] text-ink-faint">
          {formatRelativeTime(summary.triggered_at)}
        </p>
      </div>
      <RunStatusBadge status={summary.status} />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export function HarnessRunsPage() {
  const { spaceId, name } = useParams<{ spaceId: string; name: string }>();
  const [searchParams, setSearchParams] = useSearchParams();

  const safeSpaceId = spaceId ?? "";
  const safeName = name ?? "";

  const { data: runs, isLoading, isError } = useHarnessRuns(safeSpaceId, safeName);
  const triggerMutation = useTriggerHarnessRun();

  // Selected run is tracked via query param ?run=<run_id>
  const selectedRunId = searchParams.get("run");

  function selectRun(runId: string) {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      next.set("run", runId);
      return next;
    });
  }

  function handleTrigger() {
    triggerMutation.mutate(
      { spaceId: safeSpaceId, name: safeName },
      {
        onSuccess: (data) => {
          // Auto-focus the newly triggered run
          setSearchParams((prev) => {
            const next = new URLSearchParams(prev);
            next.set("run", data.run_id);
            return next;
          });
        },
      },
    );
  }

  // Sort runs newest-first
  const sortedRuns = [...(runs ?? [])].sort(
    (a, b) => new Date(b.triggered_at).getTime() - new Date(a.triggered_at).getTime(),
  );

  return (
    <PageContainer>
      <div className="space-y-6">
      {/* Page header */}
      <PageHeader
        breadcrumbs={[{ label: "Cronos" }, { label: "Harnesses" }]}
        title={safeName}
        actions={[
          <button
            key="run-now"
            type="button"
            onClick={handleTrigger}
            disabled={triggerMutation.isPending}
            className="rounded border border-accent/30 bg-accent/10 px-4 py-2 font-display text-[12px] font-medium text-accent-bright transition hover:bg-accent/20 disabled:opacity-60"
            data-testid="run-now-button"
          >
            {triggerMutation.isPending ? "Starting…" : "Run now"}
          </button>,
        ]}
      />

      {/* Error banner for trigger */}
      {triggerMutation.isError && (
        <div className="rounded-md border border-danger/20 bg-danger/5 px-4 py-3 text-[12px] text-danger">
          Failed to trigger run.
        </div>
      )}

      {/* Main layout: list + detail panel */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[320px_1fr]">
        {/* Run list */}
        <div className="overflow-hidden rounded-md border border-hairline bg-surface-1 shadow-inset-hairline">
          <div className="flex items-center gap-2 border-b border-hairline bg-surface-2/50 px-4 py-2">
            <span className="font-display text-[11px] font-semibold uppercase tracking-[0.18em] text-ink-muted">
              Runs
            </span>
            {!isLoading && (
              <span className="font-mono text-[10px] tabular-nums text-ink-faint">
                {String(sortedRuns.length).padStart(2, "0")}
              </span>
            )}
          </div>

          {/* Loading */}
          {isLoading && (
            <div className="px-4 py-6 text-center" data-testid="runs-loading">
              <p className="font-mono text-[11px] text-ink-faint">Loading runs…</p>
            </div>
          )}

          {/* Error */}
          {isError && (
            <div
              className="px-4 py-3 text-[12px] text-danger"
              data-testid="runs-error"
            >
              Failed to load run history.
            </div>
          )}

          {/* Empty state */}
          {!isLoading && !isError && sortedRuns.length === 0 && (
            <div
              className="px-4 py-8 text-center"
              data-testid="runs-empty"
            >
              <p className="font-display text-[11px] uppercase tracking-[0.18em] text-ink-faint">
                No runs yet
              </p>
              <p className="mt-1 text-[11px] text-ink-faint">
                Click "Run now" to start the first run.
              </p>
            </div>
          )}

          {/* Run rows */}
          {!isLoading && !isError && sortedRuns.length > 0 && (
            <div>
              {sortedRuns.map((run) => (
                <RunListRow
                  key={run.run_id}
                  summary={run}
                  isSelected={run.run_id === selectedRunId}
                  onClick={() => selectRun(run.run_id)}
                />
              ))}
            </div>
          )}
        </div>

        {/* Detail panel */}
        <div>
          {selectedRunId ? (
            <HarnessRunPanel
              runId={selectedRunId}
              spaceId={safeSpaceId}
              harnessId={safeName}
            />
          ) : (
            <div
              className="flex items-center justify-center rounded-md border border-dashed border-hairline bg-surface-1/40 p-10"
              data-testid="no-run-selected"
            >
              <p className="font-display text-[12px] uppercase tracking-[0.14em] text-ink-faint">
                Select a run to view details
              </p>
            </div>
          )}
        </div>
      </div>
      </div>
    </PageContainer>
  );
}
