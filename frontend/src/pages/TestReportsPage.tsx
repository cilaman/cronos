import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useTestReport, useTestReports } from "../hooks/useTestReports";
import { useSpaces } from "../hooks/useSpaces";
import { TestStatusBadge } from "../components/TestStatusBadge";
import type { TestReportSummary, TestSuite, TestCase } from "../types";

// ── Helpers ───────────────────────────────────────────────────────────────────

function fmtDate(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function fmtDuration(seconds: number | null): string {
  if (seconds == null) return "—";
  if (seconds < 60) return `${seconds.toFixed(1)}s`;
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  return `${m}m ${s}s`;
}

function truncate(s: string, max = 80): string {
  return s.length > max ? s.slice(0, max) + "…" : s;
}

// ── Coverage bar ──────────────────────────────────────────────────────────────

function CoverageBar({ module, pct }: { module: string; pct: number }) {
  const color =
    pct < 40 ? "bg-danger" : pct < 70 ? "bg-warning" : "bg-accent";
  return (
    <div className="grid grid-cols-[10rem_1fr_3rem] items-center gap-3">
      <span className="truncate font-mono text-[11px] text-ink-muted" title={module}>
        {module}
      </span>
      <div className="h-1.5 overflow-hidden rounded-full bg-surface-3">
        <div
          className={`h-full rounded-full transition-all duration-500 ${color}`}
          style={{ width: `${Math.min(pct, 100)}%` }}
        />
      </div>
      <span className="text-right font-mono text-[11px] tabular-nums text-ink">
        {pct.toFixed(0)}%
      </span>
    </div>
  );
}

// ── Trend strip ───────────────────────────────────────────────────────────────

function TrendStrip({
  reports,
  selectedId,
  onSelect,
}: {
  reports: TestReportSummary[];
  selectedId: string | null;
  onSelect: (id: string) => void;
}) {
  const recent = [...reports].reverse().slice(0, 10);
  const maxTests = Math.max(...recent.map((r) => r.total_tests), 1);

  return (
    <div className="flex h-14 items-end gap-1">
      {recent.map((r) => {
        const total = r.total_tests || 1;
        const passedPct = (r.total_passed / total) * 100;
        const failedPct = ((r.total_failed + r.total_errors) / total) * 100;
        const isSelected = r.id === selectedId;
        const barH = Math.max((total / maxTests) * 100, 8);

        return (
          <button
            key={r.id}
            type="button"
            onClick={() => onSelect(r.id)}
            title={`${fmtDate(r.started_at)} · ${r.total_passed}✓ ${r.total_failed + r.total_errors}✗`}
            className={`relative flex flex-1 flex-col-reverse overflow-hidden rounded-sm transition ${
              isSelected
                ? "ring-1 ring-accent"
                : "opacity-70 hover:opacity-100"
            }`}
            style={{ height: `${barH}%` }}
          >
            <div
              className="w-full bg-accent/80"
              style={{ height: `${passedPct}%` }}
            />
            {failedPct > 0 && (
              <div
                className="w-full bg-danger/80"
                style={{ height: `${failedPct}%` }}
              />
            )}
          </button>
        );
      })}
      {recent.length === 0 && (
        <p className="self-center font-mono text-[11px] text-ink-faint">No reports yet</p>
      )}
    </div>
  );
}

// ── Suite detail ──────────────────────────────────────────────────────────────

function SuiteRow({ suite }: { suite: TestSuite }) {
  const hasFailed = suite.failed > 0 || suite.errors > 0;
  return (
    <details className="group border-b border-hairline last:border-0">
      <summary className="flex cursor-pointer list-none items-center gap-3 px-4 py-2.5 hover:bg-surface-2/40">
        <span className="flex-1 font-mono text-[12px] text-ink">{suite.name}</span>
        <span className="font-mono text-[10px] tabular-nums text-accent-bright">
          {suite.passed}✓
        </span>
        {hasFailed && (
          <span className="font-mono text-[10px] tabular-nums text-danger">
            {suite.failed + suite.errors}✗
          </span>
        )}
        {suite.skipped > 0 && (
          <span className="font-mono text-[10px] tabular-nums text-ink-faint">
            {suite.skipped} skip
          </span>
        )}
        <span className="font-mono text-[10px] text-ink-faint">
          {fmtDuration(suite.duration_seconds)}
        </span>
        <span className="ml-1 font-mono text-[10px] text-ink-faint group-open:hidden">▶</span>
        <span className="ml-1 font-mono text-[10px] text-ink-faint hidden group-open:inline">▼</span>
      </summary>
      <div className="pb-1">
        {suite.tests.map((tc: TestCase) => (
          <TestCaseRow key={tc.id} tc={tc} />
        ))}
      </div>
    </details>
  );
}

function TestCaseRow({ tc }: { tc: TestCase }) {
  const isFailed = tc.status === "failed" || tc.status === "error";
  return (
    <div
      className={`flex items-start gap-3 px-4 py-1.5 ${
        isFailed ? "border-l-2 border-danger" : ""
      }`}
    >
      <TestStatusBadge status={tc.status} size="sm" />
      <span
        className="flex-1 font-mono text-[11px] text-ink"
        title={tc.name}
      >
        {truncate(tc.name)}
      </span>
      <span className="font-mono text-[10px] tabular-nums text-ink-faint">
        {fmtDuration(tc.duration_seconds)}
      </span>
      {tc.error_message && (
        <details className="w-full col-span-full mt-1 pl-8">
          <summary className="cursor-pointer font-mono text-[10px] text-danger">
            {truncate(tc.error_message, 60)}
          </summary>
          <pre className="mt-1 max-h-40 overflow-auto rounded bg-canvas p-2 font-mono text-[10px] text-ink-muted whitespace-pre-wrap border border-hairline">
            {tc.error_message}
          </pre>
        </details>
      )}
    </div>
  );
}

// ── Summary bar ───────────────────────────────────────────────────────────────

function SummaryBar({ report }: { report: TestReportSummary }) {
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-5">
      <div className="flex flex-col gap-0.5 rounded-md border border-hairline bg-surface-1 p-4 shadow-inset-hairline">
        <span className="font-display text-[9px] uppercase tracking-[0.2em] text-ink-faint">
          Passed
        </span>
        <span className="font-display text-[28px] font-semibold tabular-nums leading-none text-accent-bright">
          {report.total_passed}
        </span>
      </div>
      <div className="flex flex-col gap-0.5 rounded-md border border-hairline bg-surface-1 p-4 shadow-inset-hairline">
        <span className="font-display text-[9px] uppercase tracking-[0.2em] text-ink-faint">
          Failed
        </span>
        <span className={`font-display text-[28px] font-semibold tabular-nums leading-none ${report.total_failed > 0 ? "text-danger" : "text-ink"}`}>
          {report.total_failed}
        </span>
      </div>
      <div className="flex flex-col gap-0.5 rounded-md border border-hairline bg-surface-1 p-4 shadow-inset-hairline">
        <span className="font-display text-[9px] uppercase tracking-[0.2em] text-ink-faint">
          Errors
        </span>
        <span className={`font-display text-[28px] font-semibold tabular-nums leading-none ${report.total_errors > 0 ? "text-danger" : "text-ink"}`}>
          {report.total_errors}
        </span>
      </div>
      <div className="flex flex-col gap-0.5 rounded-md border border-hairline bg-surface-1 p-4 shadow-inset-hairline">
        <span className="font-display text-[9px] uppercase tracking-[0.2em] text-ink-faint">
          Skipped
        </span>
        <span className="font-display text-[28px] font-semibold tabular-nums leading-none text-ink-muted">
          {report.total_skipped}
        </span>
      </div>
      {report.coverage_pct != null && (
        <div className="flex flex-col gap-0.5 rounded-md border border-hairline bg-surface-1 p-4 shadow-inset-hairline">
          <span className="font-display text-[9px] uppercase tracking-[0.2em] text-ink-faint">
            Coverage
          </span>
          <span className={`font-display text-[28px] font-semibold tabular-nums leading-none ${
            report.coverage_pct < 40 ? "text-danger" : report.coverage_pct < 70 ? "text-warning" : "text-accent-bright"
          }`}>
            {report.coverage_pct.toFixed(0)}%
          </span>
        </div>
      )}
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export function TestReportsPage() {
  const { spaceId: paramSpaceId } = useParams<{ spaceId?: string }>();
  const [selectedSpaceId, setSelectedSpaceId] = useState<string>(paramSpaceId ?? "");
  const [selectedReportId, setSelectedReportId] = useState<string | null>(null);

  const { data: spacesData } = useSpaces();
  const spaces = spacesData?.spaces ?? [];

  const { data: reports, isLoading: reportsLoading } = useTestReports(selectedSpaceId || undefined);
  const activeReportId = selectedReportId ?? (reports && reports.length > 0 ? reports[reports.length - 1].id : null);
  const { data: activeReport, isLoading: reportLoading } = useTestReport(
    selectedSpaceId || undefined,
    activeReportId ?? undefined,
  );

  const activeSpace = spaces.find((s) => s.id === selectedSpaceId);

  return (
    <div className="mx-auto max-w-[1280px] space-y-8 p-6 lg:p-8">
      {/* Page header */}
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-ink-faint">
            Cronos · Tests
          </p>
          <h1 className="font-display text-[22px] font-semibold uppercase tracking-[0.14em] text-ink">
            Test Reports
          </h1>
        </div>

        {spaces.length > 0 && (
          <div className="flex items-center gap-2">
            <label
              htmlFor="space-filter"
              className="font-display text-[10px] uppercase tracking-[0.18em] text-ink-faint"
            >
              Space
            </label>
            <select
              id="space-filter"
              value={selectedSpaceId}
              onChange={(e) => {
                setSelectedSpaceId(e.target.value);
                setSelectedReportId(null);
              }}
              className="h-9 rounded border border-hairline bg-surface-1 px-3 font-mono text-[12px] text-ink shadow-inset-hairline transition focus:border-accent focus:outline-none"
            >
              <option value="">Select a space…</option>
              {spaces.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </select>
          </div>
        )}
      </header>

      {/* No space selected */}
      {!selectedSpaceId && (
        <div className="rounded-md border border-dashed border-hairline bg-surface-1 p-12 text-center shadow-inset-hairline">
          <p className="font-mono text-[12px] text-ink-faint">Select a space above to view test reports.</p>
        </div>
      )}

      {selectedSpaceId && (
        <>
          {/* Latest summary */}
          {reportsLoading ? (
            <div className="py-8 text-center font-mono text-[11px] text-ink-faint">Loading…</div>
          ) : !reports || reports.length === 0 ? (
            <div className="rounded-md border border-dashed border-hairline bg-surface-1 p-12 text-center shadow-inset-hairline">
              <p className="font-mono text-[12px] text-ink-faint">
                No test reports yet{activeSpace ? ` for ${activeSpace.name}` : ""}.
              </p>
              <p className="mt-1 font-mono text-[10px] text-ink-faint">
                Run tests and POST a report to the API to get started.
              </p>
            </div>
          ) : (
            <>
              {/* Summary from most recent report */}
              {(() => {
                const latest = reports[reports.length - 1];
                return (
                  <section>
                    <div className="mb-3 flex items-baseline gap-2">
                      <h2 className="font-display text-[11px] font-semibold uppercase tracking-[0.2em] text-ink-muted">
                        Latest run
                      </h2>
                      <span className="font-mono text-[10px] text-ink-faint">
                        {fmtDate(latest.started_at)}
                        {latest.framework ? ` · ${latest.framework}` : ""}
                      </span>
                    </div>
                    <SummaryBar report={latest} />
                  </section>
                );
              })()}

              {/* Trend strip */}
              <section>
                <div className="mb-3 flex items-baseline gap-2">
                  <h2 className="font-display text-[11px] font-semibold uppercase tracking-[0.2em] text-ink-muted">
                    Trend
                  </h2>
                  <span className="font-mono text-[10px] text-ink-faint">last {Math.min(reports.length, 10)} runs · click to inspect</span>
                </div>
                <div className="rounded-md border border-hairline bg-surface-1 p-4 shadow-inset-hairline">
                  <TrendStrip
                    reports={reports}
                    selectedId={activeReportId}
                    onSelect={(id) => setSelectedReportId(id)}
                  />
                </div>
              </section>

              {/* Report detail */}
              {activeReport && (
                <section>
                  <div className="mb-3 flex items-baseline gap-3">
                    <h2 className="font-display text-[11px] font-semibold uppercase tracking-[0.2em] text-ink-muted">
                      Report detail
                    </h2>
                    <span className="font-mono text-[10px] text-ink-faint">
                      {fmtDate(activeReport.started_at)}
                      {activeReport.framework ? ` · ${activeReport.framework}` : ""}
                      {activeReport.triggered_by ? ` · by ${activeReport.triggered_by}` : ""}
                    </span>
                    {activeReport.exit_code != null && (
                      <span className={`font-mono text-[10px] rounded border px-1.5 py-0.5 ${
                        activeReport.exit_code === 0
                          ? "border-accent/30 bg-accent/10 text-accent-bright"
                          : "border-danger/30 bg-danger/10 text-danger"
                      }`}>
                        exit {activeReport.exit_code}
                      </span>
                    )}
                    {activeReport.task_id && (
                      <Link
                        to={`/?task=${encodeURIComponent(activeReport.task_id)}`}
                        className="font-mono text-[10px] text-accent-bright hover:underline"
                      >
                        view task →
                      </Link>
                    )}
                  </div>

                  {reportLoading ? (
                    <div className="py-8 text-center font-mono text-[11px] text-ink-faint">Loading report…</div>
                  ) : (
                    <div className="space-y-4">
                      {/* Suite list */}
                      {activeReport.suites && activeReport.suites.length > 0 ? (
                        <div className="overflow-hidden rounded-md border border-hairline bg-surface-1 shadow-inset-hairline">
                          {activeReport.suites.map((suite: TestSuite) => (
                            <SuiteRow key={suite.name} suite={suite} />
                          ))}
                        </div>
                      ) : (
                        <div className="rounded-md border border-hairline bg-surface-1 p-8 text-center shadow-inset-hairline">
                          <p className="font-mono text-[11px] text-ink-faint">No suite details in this report.</p>
                        </div>
                      )}

                      {/* Coverage */}
                      {activeReport.coverage_data && Object.keys(activeReport.coverage_data).length > 0 && (
                        <div>
                          <p className="mb-2 font-display text-[10px] font-semibold uppercase tracking-[0.2em] text-ink-faint">
                            Coverage by module
                          </p>
                          <div className="rounded-md border border-hairline bg-surface-1 p-4 shadow-inset-hairline">
                            <div className="space-y-2.5">
                              {Object.entries(activeReport.coverage_data)
                                .sort(([, a], [, b]) => a - b)
                                .map(([mod, pct]) => (
                                  <CoverageBar key={mod} module={mod} pct={pct} />
                                ))}
                            </div>
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </section>
              )}
            </>
          )}
        </>
      )}
    </div>
  );
}
