import { useState } from "react";
import type { ReactNode } from "react";
import type { FeatureRead, FeatureState, Task } from "../../types";
import { STATE_BADGE } from "../../state-badges";
import { Modal } from "./Modal";

// ── Shared loading skeleton ────────────────────────────────────────────────────

export function DetailShellSkeleton() {
  return (
    <div className="animate-pulse p-6 space-y-4">
      <div className="flex gap-2">
        <div className="h-5 w-16 rounded bg-surface-3" />
        <div className="h-5 w-24 rounded bg-surface-3" />
      </div>
      <div className="h-7 w-2/3 rounded bg-surface-3" />
      <div className="space-y-2 pt-2">
        <div className="h-4 w-full rounded bg-surface-3" />
        <div className="h-4 w-5/6 rounded bg-surface-3" />
        <div className="h-4 w-4/6 rounded bg-surface-3" />
      </div>
    </div>
  );
}

// ── Feature state badge map (moved from FeatureDetail.tsx) ────────────────────

export const FEATURE_STATE_BADGE: Record<FeatureState, string> = {
  backlog: "bg-surface-2 text-ink-muted ring-1 ring-hairline",
  processing:
    "bg-violet-100 text-violet-800 ring-1 ring-violet-300 dark:bg-violet-400/10 dark:text-violet-300 dark:ring-violet-400/40",
  planned:
    "bg-indigo-100 text-indigo-800 ring-1 ring-indigo-300 dark:bg-indigo-400/10 dark:text-indigo-300 dark:ring-indigo-400/40",
  waiting:
    "bg-amber-100 text-amber-800 ring-1 ring-amber-300 dark:bg-amber-400/10 dark:text-amber-300 dark:ring-amber-400/40",
  done:
    "bg-sky-100 text-sky-800 ring-1 ring-sky-300 dark:bg-sky-400/10 dark:text-sky-300 dark:ring-sky-400/40",
};

// ── Props ─────────────────────────────────────────────────────────────────────

interface BaseProps {
  isLoading?: boolean;
  error?: Error | null;
  onRetry?: () => void;
  onClose: () => void;
  /** Extra elements rendered inside the header after the badges/title row. */
  headerActions?: ReactNode;
  /** Body content rendered below the header. */
  footer?: ReactNode;
}

export interface TaskDetailShellProps extends BaseProps {
  variant: "task";
  entity?: Task | null;
}

export interface FeatureDetailShellProps extends BaseProps {
  variant: "feature";
  entity?: FeatureRead | null;
}

export type DetailShellProps = TaskDetailShellProps | FeatureDetailShellProps;

// ── Component ─────────────────────────────────────────────────────────────────

export function DetailShell({
  variant,
  entity,
  isLoading = false,
  error,
  onRetry,
  onClose,
  headerActions,
  footer,
}: DetailShellProps) {
  const [detailsCollapsed, setDetailsCollapsed] = useState(false);
  const maxWidthCls = variant === "task" ? "max-w-6xl" : "max-w-3xl";
  const heightCls = variant === "task" ? "min-h-[60svh]" : "";

  return (
    <Modal onClose={onClose} hideDefaultClose panelClassName={maxWidthCls}>
      <div
        className={`flex max-h-[90svh] w-full ${maxWidthCls} ${heightCls} flex-col overflow-hidden rounded-lg border border-hairline bg-surface-1 shadow-lift glass-pane`}
        onClick={(e) => e.stopPropagation()}
      >
        {isLoading && <DetailShellSkeleton />}

        {!isLoading && error && (
          <div className="flex flex-col items-center gap-3 p-10 text-center">
            <p className="rounded border border-danger/40 bg-danger/15 px-4 py-3 text-sm text-danger">
              {error.message}
            </p>
            {onRetry && (
              <button
                type="button"
                onClick={onRetry}
                className="rounded border border-hairline-strong bg-canvas px-3 py-1.5 text-xs text-ink-muted transition hover:bg-surface-2 hover:text-ink"
              >
                Retry
              </button>
            )}
          </div>
        )}

        {!isLoading && !error && entity && (
          <>
            <header className="flex items-start justify-between gap-4 border-b border-hairline p-4">
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  {variant === "task" ? (
                    <>
                      <span
                        className={`rounded px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.18em] ${
                          STATE_BADGE[entity.state] ?? STATE_BADGE.backlog
                        }`}
                      >
                        {entity.state}
                      </span>
                      <span className="font-mono text-xs text-ink-faint">{entity.id}</span>
                    </>
                  ) : (
                    <>
                      {(entity as FeatureRead).feature_state && (
                        <span
                          className={`rounded px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.18em] ${
                            FEATURE_STATE_BADGE[(entity as FeatureRead).feature_state!]
                          }`}
                        >
                          {(entity as FeatureRead).feature_state}
                        </span>
                      )}
                      <span
                        className={`rounded px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.18em] ${
                          (entity as FeatureRead).type === "fix"
                            ? "bg-rose-100 text-rose-800 ring-1 ring-rose-300 dark:bg-rose-400/10 dark:text-rose-300 dark:ring-rose-400/40"
                            : "bg-emerald-100 text-emerald-800 ring-1 ring-emerald-300 dark:bg-emerald-400/10 dark:text-emerald-300 dark:ring-emerald-400/40"
                        }`}
                      >
                        {(entity as FeatureRead).type}
                      </span>
                      {(entity as FeatureRead).feature_key && (
                        <span className="font-mono text-xs text-ink-faint">
                          {(entity as FeatureRead).feature_key}
                        </span>
                      )}
                      <span className="font-mono text-xs text-ink-faint">{entity.id}</span>
                    </>
                  )}
                </div>

                <h2 className="mt-2 text-xl font-semibold leading-tight tracking-tight text-ink">
                  {entity.title}
                </h2>

                {headerActions && (
                  <div className={`mt-3 ${detailsCollapsed ? "hidden md:block" : "block"}`}>
                    {headerActions}
                  </div>
                )}
              </div>

              <div className="flex items-start gap-1">
                <button
                  type="button"
                  onClick={() => setDetailsCollapsed((v) => !v)}
                  aria-expanded={!detailsCollapsed}
                  aria-label={detailsCollapsed ? "Expand header" : "Collapse header"}
                  className="rounded p-1 text-ink-muted transition hover:bg-surface-2 hover:text-ink md:hidden"
                >
                  <span
                    aria-hidden
                    className={`inline-block transition-transform ${detailsCollapsed ? "" : "rotate-90"}`}
                  >
                    ▸
                  </span>
                </button>
                <button
                  type="button"
                  onClick={onClose}
                  aria-label="Close"
                  className="rounded p-1 text-ink-muted transition hover:bg-surface-2 hover:text-ink"
                >
                  ✕
                </button>
              </div>
            </header>

            <div className="flex flex-1 min-h-0 flex-col overflow-hidden">
              {footer}
            </div>
          </>
        )}
      </div>
    </Modal>
  );
}
