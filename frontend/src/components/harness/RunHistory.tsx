import { useHarnessRuns } from "../../hooks/useHarnessRuns";
import type { RunSummary } from "../../hooks/useHarnessRuns";

export interface RunHistoryProps {
  spaceId: string;
  name: string;
  onSelectRun: (runId: string, mode: "live" | "replay") => void;
}

function statusPillClass(status: RunSummary["status"]): string {
  switch (status) {
    case "running":
      return "bg-blue-100 text-blue-700";
    case "done":
      return "bg-green-100 text-green-700";
    case "failed":
      return "bg-red-100 text-red-700";
    case "cancelled":
      return "bg-gray-100 text-gray-600";
    default:
      return "bg-gray-100 text-gray-600";
  }
}

function formatTimestamp(iso: string): string {
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

export function RunHistory({ spaceId, name, onSelectRun }: RunHistoryProps) {
  const { data: runs, isLoading, isError } = useHarnessRuns(spaceId, name);

  if (isLoading) {
    return (
      <div className="text-xs text-ink opacity-50 p-3" data-testid="run-history-loading">
        Loading…
      </div>
    );
  }

  if (isError) {
    return (
      <div className="text-xs text-red-600 p-3" data-testid="run-history-error">
        Failed to load runs.
      </div>
    );
  }

  const sorted = runs
    ? [...runs].sort(
        (a, b) =>
          new Date(b.triggered_at).getTime() - new Date(a.triggered_at).getTime(),
      )
    : [];

  if (sorted.length === 0) {
    return (
      <div className="text-xs text-ink opacity-50 p-3" data-testid="run-history-empty">
        No runs yet.
      </div>
    );
  }

  return (
    <ul className="flex flex-col gap-1 p-2" data-testid="run-history-list">
      {sorted.map((run) => {
        const isLive = run.status === "running";
        const mode: "live" | "replay" = isLive ? "live" : "replay";
        return (
          <li key={run.run_id}>
            <button
              className="w-full text-left rounded px-2 py-1.5 hover:bg-surface-3 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 flex items-center gap-2"
              onClick={() => onSelectRun(run.run_id, mode)}
              data-testid={`run-item-${run.run_id}`}
            >
              <span
                className={`shrink-0 rounded-full px-1.5 py-0.5 text-[10px] font-semibold uppercase ${statusPillClass(run.status)}`}
                data-testid={`run-status-pill-${run.run_id}`}
              >
                {run.status}
              </span>
              <span className="text-xs text-ink truncate flex-1">
                {formatTimestamp(run.triggered_at)}
              </span>
            </button>
          </li>
        );
      })}
    </ul>
  );
}
