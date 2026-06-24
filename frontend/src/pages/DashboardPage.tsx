import { useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useActivity, useImportSpace, useSpaces } from "../hooks/useSpaces";
import { useCreateTask } from "../hooks/useTasks";
import { useGlobalStats } from "../hooks/useStats";
import { useTestReports, useLatestTestReport } from "../hooks/useTestReports";
import { TaskForm } from "../components/TaskForm";
import { EmptyState } from "../components/ui/EmptyState";
import { PageContainer } from "../components/ui/PageContainer";
import { PageHeader } from "../components/ui/PageHeader";
import { SpaceTag } from "../components/ui/SpaceTag";
import { Skeleton } from "../components/ui/Skeleton";
import { StatTile } from "../components/ui/StatTile";
import { TestStatusBadge } from "../components/TestStatusBadge";
import { TimeFrameSelector } from "../components/TimeFrameSelector";
import type { TimeFrame } from "../components/TimeFrameSelector";
import { api } from "../api";
import { formatRelative } from "../utils/format";
import type { Activity, SpaceSummary, TaskState, TestReportSummary, TestSuite, TestCase, TestReport } from "../types";

// ── Formatters ────────────────────────────────────────────────────────────────

function formatTokens(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return String(n);
}

function formatDuration(seconds: number): string {
  if (seconds < 60) return `${Math.round(seconds)}s`;
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  if (h > 0) return `${h}h ${m}m`;
  const s = Math.round(seconds % 60);
  return `${m}m ${s}s`;
}

function formatCost(usd: number): string {
  if (usd === 0) return "$0.00";
  if (usd < 0.0001) return "<$0.0001";
  if (usd < 0.01) return `$${usd.toFixed(4)}`;
  if (usd < 1) return `$${usd.toFixed(3)}`;
  return `$${usd.toFixed(2)}`;
}

function fmtDate(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

// ── Task count tiles ──────────────────────────────────────────────────────────
// DashboardStatTile wraps the shared StatTile primitive and adds dashboard-
// specific features: optional Link wrapper (to) and a pulse indicator dot.

type DashboardTone = "neutral" | "info" | "warning";

function DashboardStatTile({
  label,
  value,
  tone = "neutral",
  pulse = false,
  to,
}: {
  label: string;
  value: number | string;
  tone?: DashboardTone;
  pulse?: boolean;
  to?: string;
}) {
  const tile = (
    <div className="relative">
      <StatTile
        label={label}
        value={value}
        tone={tone}
        className={
          to
            ? "h-24 cursor-pointer bg-surface-1 shadow-inset-hairline transition hover:-translate-y-px hover:border-hairline-strong hover:shadow-lift"
            : "h-24 bg-surface-1 shadow-inset-hairline"
        }
      />
      {pulse && (
        <span
          aria-hidden
          className="anim-pulse-dot absolute right-2 top-2 h-2 w-2 rounded-full bg-accent-bright"
        />
      )}
    </div>
  );

  return to ? (
    <Link to={to} className="block">
      {tile}
    </Link>
  ) : (
    tile
  );
}

// ── AI stats metric tiles ─────────────────────────────────────────────────────
// MetricTile uses the shared StatTile primitive; sub text maps to the delta slot.

function MetricTile({
  label,
  value,
  tone = "neutral",
  sub,
}: {
  label: string;
  value: string | number;
  tone?: "neutral" | "info" | "warning" | "danger";
  sub?: string;
}) {
  return (
    <StatTile
      label={label}
      value={value}
      tone={tone}
      delta={sub}
    />
  );
}

// ── AI stats sub-components ───────────────────────────────────────────────────

const EXIT_REASON_STYLE: Record<string, { label: string; cls: string }> = {
  DONE:    { label: "Done",    cls: "text-accent-bright border-accent/30 bg-accent/10" },
  WAIT:    { label: "Wait",    cls: "text-warning border-warning/30 bg-warning/10" },
  BLOCKED: { label: "Blocked", cls: "text-danger border-danger/30 bg-danger/10" },
  STOPPED: { label: "Stopped", cls: "text-ink-muted border-hairline bg-surface-2" },
  CRASHED: { label: "Crashed", cls: "text-danger border-danger/30 bg-danger/10" },
};

function ExitReasonBadge({ reason, count }: { reason: string; count: number }) {
  const style = EXIT_REASON_STYLE[reason] ?? {
    label: reason,
    cls: "text-ink-muted border-hairline bg-surface-2",
  };
  return (
    <div className={`flex items-center gap-2 rounded border px-3 py-2 ${style.cls}`}>
      <span className="font-display text-[10px] uppercase tracking-[0.18em]">
        {style.label}
      </span>
      <span className="ml-auto font-mono text-[13px] font-semibold tabular-nums">
        {count}
      </span>
    </div>
  );
}

function ToolBar({ name, count, max }: { name: string; count: number; max: number }) {
  const pct = max > 0 ? (count / max) * 100 : 0;
  return (
    <div className="grid grid-cols-[7rem_1fr_3.5rem] items-center gap-3">
      <span className="truncate font-mono text-[11px] text-ink-muted">{name}</span>
      <div className="h-1.5 overflow-hidden rounded-full bg-surface-3">
        <div
          className="h-full rounded-full bg-accent transition-all duration-500"
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="text-right font-mono text-[11px] tabular-nums text-ink">
        {count.toLocaleString()}
      </span>
    </div>
  );
}

// ── Test health sub-components ────────────────────────────────────────────────

function SummaryBar({ report }: { report: TestReportSummary }) {
  return (
    <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 lg:grid-cols-5">
      <div className="flex flex-col gap-0.5 rounded-md border border-hairline bg-surface-2 p-3 shadow-inset-hairline">
        <span className="font-display text-[9px] uppercase tracking-[0.2em] text-ink-faint">Passed</span>
        <span className="font-display text-[22px] font-semibold tabular-nums leading-none text-accent-bright">
          {report.total_passed}
        </span>
      </div>
      <div className="flex flex-col gap-0.5 rounded-md border border-hairline bg-surface-2 p-3 shadow-inset-hairline">
        <span className="font-display text-[9px] uppercase tracking-[0.2em] text-ink-faint">Failed</span>
        <span className={`font-display text-[22px] font-semibold tabular-nums leading-none ${report.total_failed > 0 ? "text-danger" : "text-ink"}`}>
          {report.total_failed}
        </span>
      </div>
      <div className="flex flex-col gap-0.5 rounded-md border border-hairline bg-surface-2 p-3 shadow-inset-hairline">
        <span className="font-display text-[9px] uppercase tracking-[0.2em] text-ink-faint">Errors</span>
        <span className={`font-display text-[22px] font-semibold tabular-nums leading-none ${report.total_errors > 0 ? "text-danger" : "text-ink"}`}>
          {report.total_errors}
        </span>
      </div>
      <div className="flex flex-col gap-0.5 rounded-md border border-hairline bg-surface-2 p-3 shadow-inset-hairline">
        <span className="font-display text-[9px] uppercase tracking-[0.2em] text-ink-faint">Skipped</span>
        <span className="font-display text-[22px] font-semibold tabular-nums leading-none text-ink-muted">
          {report.total_skipped}
        </span>
      </div>
      {report.coverage_pct != null && (
        <div className="flex flex-col gap-0.5 rounded-md border border-hairline bg-surface-2 p-3 shadow-inset-hairline">
          <span className="font-display text-[9px] uppercase tracking-[0.2em] text-ink-faint">Coverage</span>
          <span className={`font-display text-[22px] font-semibold tabular-nums leading-none ${
            report.coverage_pct < 40 ? "text-danger" : report.coverage_pct < 70 ? "text-warning" : "text-accent-bright"
          }`}>
            {report.coverage_pct.toFixed(0)}%
          </span>
        </div>
      )}
    </div>
  );
}

function TrendStrip({ reports }: { reports: TestReportSummary[] }) {
  const recent = [...reports].reverse().slice(0, 10);
  const maxTests = Math.max(...recent.map((r) => r.total_tests), 1);

  return (
    <div className="flex h-14 items-end gap-1">
      {recent.map((r) => {
        const total = r.total_tests || 1;
        const passedPct = (r.total_passed / total) * 100;
        const failedPct = ((r.total_failed + r.total_errors) / total) * 100;
        const barH = Math.max((total / maxTests) * 100, 8);

        return (
          <div
            key={r.id}
            title={`${fmtDate(r.started_at)} · ${r.total_passed}✓ ${r.total_failed + r.total_errors}✗`}
            className="relative flex flex-1 flex-col-reverse overflow-hidden rounded-sm bg-surface-3"
            style={{ height: `${barH}%` }}
          >
            <div className="w-full bg-accent/80" style={{ height: `${passedPct}%` }} />
            {failedPct > 0 && (
              <div className="w-full bg-danger/80" style={{ height: `${failedPct}%` }} />
            )}
          </div>
        );
      })}
      {recent.length === 0 && (
        <p className="self-center font-mono text-[11px] text-ink-faint">No reports yet</p>
      )}
    </div>
  );
}

function fmtDuration(seconds: number | null): string {
  if (seconds == null) return "—";
  if (seconds < 60) return `${seconds.toFixed(1)}s`;
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  return `${m}m ${s}s`;
}

function SuiteRow({ suite }: { suite: TestSuite }) {
  const hasFailed = suite.failed > 0 || suite.errors > 0;
  return (
    <details className="group border-b border-hairline last:border-0">
      <summary className="flex cursor-pointer list-none items-center gap-3 px-4 py-2.5 hover:bg-surface-2/40">
        <span className="flex-1 truncate font-mono text-[12px] text-ink">{suite.name}</span>
        <span className="font-mono text-[10px] tabular-nums text-accent-bright">{suite.passed}✓</span>
        {hasFailed && (
          <span className="font-mono text-[10px] tabular-nums text-danger">{suite.failed + suite.errors}✗</span>
        )}
        {suite.skipped > 0 && (
          <span className="font-mono text-[10px] tabular-nums text-ink-faint">{suite.skipped} skip</span>
        )}
        <span className="font-mono text-[10px] text-ink-faint">{fmtDuration(suite.duration_seconds)}</span>
        <span className="ml-1 font-mono text-[10px] text-ink-faint group-open:hidden">▶</span>
        <span className="ml-1 hidden font-mono text-[10px] text-ink-faint group-open:inline">▼</span>
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
    <div className={`flex items-start gap-3 px-4 py-1.5 ${isFailed ? "border-l-2 border-danger" : ""}`}>
      <TestStatusBadge status={tc.status} size="sm" />
      <span className="flex-1 truncate font-mono text-[11px] text-ink" title={tc.name}>
        {tc.name.length > 80 ? tc.name.slice(0, 80) + "…" : tc.name}
      </span>
      <span className="font-mono text-[10px] tabular-nums text-ink-faint">
        {fmtDuration(tc.duration_seconds ?? null)}
      </span>
      {tc.error_message && (
        <details className="col-span-full mt-1 w-full pl-8">
          <summary className="cursor-pointer font-mono text-[10px] text-danger">
            {tc.error_message.slice(0, 60)}{tc.error_message.length > 60 ? "…" : ""}
          </summary>
          <pre className="mt-1 max-h-40 overflow-auto rounded border border-hairline bg-canvas p-2 font-mono text-[10px] text-ink-muted whitespace-pre-wrap">
            {tc.error_message}
          </pre>
        </details>
      )}
    </div>
  );
}

function CoverageBar({ module, pct }: { module: string; pct: number }) {
  const color = pct < 40 ? "bg-danger" : pct < 70 ? "bg-warning" : "bg-accent";
  return (
    <div className="grid grid-cols-[10rem_1fr_3rem] items-center gap-3">
      <span className="truncate font-mono text-[11px] text-ink-muted" title={module}>{module}</span>
      <div className="h-1.5 overflow-hidden rounded-full bg-surface-3">
        <div className={`h-full rounded-full transition-all duration-500 ${color}`} style={{ width: `${Math.min(pct, 100)}%` }} />
      </div>
      <span className="text-right font-mono text-[11px] tabular-nums text-ink">{pct.toFixed(0)}%</span>
    </div>
  );
}

function TestDetails({ report }: { report: TestReport }) {
  const coverageEntries = report.coverage_data
    ? Object.entries(report.coverage_data).sort(([, a], [, b]) => a - b)
    : [];

  return (
    <div className="space-y-4">
      {report.suites.length > 0 && (
        <div className="overflow-hidden rounded-md border border-hairline bg-surface-1 shadow-inset-hairline">
          <p className="border-b border-hairline px-4 py-2 font-display text-[9px] uppercase tracking-[0.2em] text-ink-faint">
            Test Suites
          </p>
          {report.suites.map((suite) => (
            <SuiteRow key={suite.name} suite={suite} />
          ))}
        </div>
      )}
      {coverageEntries.length > 0 && (
        <div className="rounded-md border border-hairline bg-surface-1 p-4 shadow-inset-hairline">
          <p className="mb-3 font-display text-[9px] uppercase tracking-[0.2em] text-ink-faint">
            Coverage by module
          </p>
          <div className="space-y-2">
            {coverageEntries.map(([mod, pct]) => (
              <CoverageBar key={mod} module={mod} pct={pct} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ── Space + activity components ───────────────────────────────────────────────

const LANE_ABBREV: Partial<Record<TaskState, string>> = { backlog: "todo" };

function SpaceCard({ space }: { space: SpaceSummary }) {
  const counts = space.task_counts;
  return (
    <Link
      to={`/spaces/${space.id}`}
      className="group block overflow-hidden rounded-md border border-hairline bg-surface-1 shadow-inset-hairline transition hover:-translate-y-px hover:border-hairline-strong hover:shadow-lift"
    >
      <div className="h-1" style={{ backgroundColor: space.color }} />
      <div className="space-y-3 p-4">
        <div className="flex items-center gap-2">
          <SpaceTag color={space.color} icon={space.icon} size="md" />
          <h3 className="min-w-0 flex-1 truncate text-sm font-semibold text-ink">
            {space.name}
          </h3>
        </div>
        <dl className="grid grid-cols-4 gap-1.5">
          {(["backlog", "active", "waiting", "done"] as TaskState[]).map((s) => (
            <div
              key={s}
              className="rounded border border-hairline bg-surface-2 px-1.5 py-1 text-center"
            >
              <dt className="font-display text-[9px] uppercase tracking-[0.16em] text-ink-faint">
                {LANE_ABBREV[s] ?? s.slice(0, 3)}
              </dt>
              <dd className="font-mono text-[12px] tabular-nums text-ink">
                {String(counts[s] ?? 0).padStart(2, "0")}
              </dd>
            </div>
          ))}
        </dl>
        <p className="font-mono text-[10px] uppercase tracking-[0.14em] text-ink-faint">
          Updated {formatRelative(space.last_activity_at)}
        </p>
      </div>
    </Link>
  );
}

function ActivityRow({
  event,
  spaceLookup,
}: {
  event: Activity;
  spaceLookup: Map<string, SpaceSummary>;
}) {
  const space = spaceLookup.get(event.space_id);
  return (
    <Link
      to={`/spaces/${event.space_id}?task=${encodeURIComponent(event.task_id)}`}
      className="grid grid-cols-[3.5rem_1fr_auto] items-center gap-2 border-b border-hairline px-3 py-1.5 transition hover:bg-surface-2/60"
      style={{ borderLeft: `3px solid ${space?.color ?? "transparent"}` }}
    >
      <span className="font-mono text-[10px] uppercase tracking-[0.12em] text-ink-faint">
        {formatRelative(event.updated_at)}
      </span>
      <span className="truncate text-[12px] text-ink">{event.title}</span>
      <span className="text-right font-mono text-[10px] uppercase tracking-[0.14em] text-ink-muted">
        {event.state}
      </span>
    </Link>
  );
}

// ── Collapsible section header ────────────────────────────────────────────────

function SectionToggle({
  title,
  open,
  onToggle,
  badge,
  children,
}: {
  title: string;
  open: boolean;
  onToggle: () => void;
  badge?: React.ReactNode;
  children?: React.ReactNode;
}) {
  return (
    <div className="flex items-center gap-2">
      <button
        type="button"
        onClick={onToggle}
        className="group flex items-center gap-2 text-left"
      >
        <h2 className="font-display text-[11px] font-semibold uppercase tracking-[0.2em] text-ink-muted transition group-hover:text-ink">
          {title}
        </h2>
        <span className="font-mono text-[9px] text-ink-faint transition group-hover:text-ink-muted">
          {open ? "▲" : "▼"}
        </span>
      </button>
      {badge && <span className="font-mono text-[10px] tabular-nums text-ink-faint">{badge}</span>}
      {children && <div className="ml-auto flex items-center gap-2">{children}</div>}
    </div>
  );
}

// ── Shared section header ─────────────────────────────────────────────────────

function SectionHeader({
  title,
  count,
  right,
}: {
  title: string;
  count?: string | number;
  right?: React.ReactNode;
}) {
  return (
    <div className="mb-3 flex items-center gap-2">
      <h2 className="font-display text-[11px] font-semibold uppercase tracking-[0.2em] text-ink-muted">
        {title}
      </h2>
      {count != null && (
        <span className="font-mono text-[10px] tabular-nums text-ink-faint">
          {typeof count === "number" ? String(count).padStart(2, "0") : count}
        </span>
      )}
      {right && <div className="ml-auto flex items-center gap-2">{right}</div>}
    </div>
  );
}

// ── Pagination controls ───────────────────────────────────────────────────────

function PaginationControls({
  page,
  totalPages,
  onChange,
}: {
  page: number;
  totalPages: number;
  onChange: (p: number) => void;
}) {
  if (totalPages <= 1) return null;
  return (
    <div className="flex items-center gap-1.5">
      <button
        type="button"
        disabled={page === 0}
        onClick={() => onChange(page - 1)}
        className="flex h-6 w-6 items-center justify-center rounded border border-hairline bg-surface-2 font-mono text-[13px] text-ink-muted transition hover:border-hairline-strong hover:text-ink disabled:opacity-30"
        aria-label="Previous page"
      >
        ‹
      </button>
      <span className="font-mono text-[10px] tabular-nums text-ink-faint">
        {page + 1}/{totalPages}
      </span>
      <button
        type="button"
        disabled={page >= totalPages - 1}
        onClick={() => onChange(page + 1)}
        className="flex h-6 w-6 items-center justify-center rounded border border-hairline bg-surface-2 font-mono text-[13px] text-ink-muted transition hover:border-hairline-strong hover:text-ink disabled:opacity-30"
        aria-label="Next page"
      >
        ›
      </button>
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

const ACTIVITY_PAGE_SIZE = 10;

export function DashboardPage() {
  const navigate = useNavigate();
  const { data: spacesData, isLoading: spacesLoading } = useSpaces();
  const { data: activity } = useActivity(50);
  const importMutation = useImportSpace();
  const createTask = useCreateTask();
  const fileRef = useRef<HTMLInputElement>(null);
  const [creating, setCreating] = useState(false);
  const [isWorking, setIsWorking] = useState(false);
  const [workError, setWorkError] = useState<string | null>(null);

  const [activityPage, setActivityPage] = useState(0);
  const [statsOpen, setStatsOpen] = useState(false);
  const [testsSpaceId, setTestsSpaceId] = useState("");
  const [timeFrame, setTimeFrame] = useState<TimeFrame>({ preset: "all" });

  const { data: globalStats } = useGlobalStats(timeFrame);
  const { data: testReports, isLoading: testReportsLoading } = useTestReports(
    testsSpaceId || undefined,
  );
  const { data: latestFullReport } = useLatestTestReport(testsSpaceId || undefined);

  const spaces = spacesData?.spaces ?? [];
  const totals = spacesData?.totals ?? { backlog: 0, active: 0, waiting: 0, done: 0 };
  const lookup = new Map(spaces.map((s) => [s.id, s] as const));

  const totalTasks =
    (totals.backlog ?? 0) +
    (totals.active ?? 0) +
    (totals.waiting ?? 0) +
    (totals.done ?? 0);

  // Auto-select the first space for test health when there's only one
  useEffect(() => {
    if (spaces.length === 1 && !testsSpaceId) {
      setTestsSpaceId(spaces[0].id);
    }
  }, [spaces, testsSpaceId]);

  const statsTools = globalStats
    ? Object.entries(globalStats.tool_use_summary).sort(([, a], [, b]) => b - a).slice(0, 5)
    : [];
  const maxTool = statsTools[0]?.[1] ?? 1;

  const latestTestReport =
    testReports && testReports.length > 0 ? testReports[testReports.length - 1] : null;

  const pagedActivity = activity
    ? activity.slice(activityPage * ACTIVITY_PAGE_SIZE, (activityPage + 1) * ACTIVITY_PAGE_SIZE)
    : [];
  const totalActivityPages = activity ? Math.ceil(activity.length / ACTIVITY_PAGE_SIZE) : 0;

  async function handleImport(file: File) {
    try {
      const space = await importMutation.mutateAsync({ file });
      navigate(`/spaces/${space.id}`);
    } catch (err) {
      console.error(err);
    }
  }

  if (spacesLoading) {
    return (
      <div className="mx-auto max-w-[1280px] space-y-8 p-6 lg:p-8">
        {/* Stat tiles skeleton */}
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-6">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} variant="block" className="h-24" />
          ))}
        </div>
        {/* Analytics cards skeleton */}
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <Skeleton variant="card" className="h-48" />
          <Skeleton variant="card" className="h-48" />
        </div>
      </div>
    );
  }

  return (
    <PageContainer>
      <div className="space-y-8">

      {/* ── Header ─────────────────────────────────────────────────────────── */}
      <PageHeader
        breadcrumbs={[{ label: "Cronos" }, { label: "Overview" }]}
        title="Dashboard"
        actions={[
          <button
            key="new-task"
            type="button"
            onClick={() => setCreating(true)}
            className="flex h-9 items-center gap-1.5 rounded border border-accent bg-accent px-3 text-[12px] font-medium text-canvas transition hover:bg-accent-bright"
          >
            <span aria-hidden className="text-base leading-none">＋</span>
            New task
          </button>,
          <Link
            key="new-space"
            to="/spaces/new"
            className="flex h-9 items-center rounded border border-hairline-strong bg-surface-1 px-3 text-[12px] text-ink transition hover:border-accent hover:bg-surface-2"
          >
            New space
          </Link>,
          <button
            key="import-space"
            type="button"
            onClick={() => fileRef.current?.click()}
            disabled={importMutation.isPending}
            className="flex h-9 items-center rounded px-3 text-[12px] text-ink-muted transition hover:bg-surface-2 hover:text-ink disabled:opacity-60"
          >
            {importMutation.isPending ? "Importing…" : "Import space"}
          </button>,
        ]}
      />
      <input
        ref={fileRef}
        type="file"
        accept=".zip"
        className="hidden"
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) handleImport(file);
          e.target.value = "";
        }}
      />

      {/* ── Zone A: Mission Control ─────────────────────────────────────────── */}

      {/* Stat tiles */}
      <section className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-6">
        <DashboardStatTile label="To Do" value={totals.backlog ?? 0} to="/board" />
        <DashboardStatTile
          label="Active agents"
          value={totals.active ?? 0}
          tone="info"
          pulse={(totals.active ?? 0) > 0}
          to="/board"
        />
        <DashboardStatTile
          label="Waiting"
          value={totals.waiting ?? 0}
          tone={totals.waiting ? "warning" : "neutral"}
          to="/board"
        />
        <DashboardStatTile label="Done" value={totals.done ?? 0} to="/board" />
        <DashboardStatTile label="Total tasks" value={totalTasks} to="/board" />
        <DashboardStatTile label="Features" value={spacesData?.feature_totals?.backlog ?? 0} to="/features" />
      </section>

      {/* Analytics — above the fold, always visible */}
      <section className="grid grid-cols-1 gap-4 lg:grid-cols-2">

        {/* AI Performance card */}
        <div className="overflow-hidden rounded-md border border-hairline bg-surface-1 shadow-inset-hairline">
          <div className="h-[2px] bg-accent" />
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-hairline px-4 py-3">
            <div className="flex items-center gap-2">
              <h2 className="font-display text-[11px] font-semibold uppercase tracking-[0.2em] text-ink-muted">
                AI Performance
              </h2>
              {globalStats && (
                <span className="font-mono text-[10px] tabular-nums text-ink-faint">
                  {globalStats.total_runs} runs
                </span>
              )}
            </div>
            <TimeFrameSelector value={timeFrame} onChange={setTimeFrame} compact />
          </div>
          <div className="p-4">
            {!globalStats ? (
              <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
                <Skeleton variant="block" className="h-16" />
                <Skeleton variant="block" className="h-16" />
                <Skeleton variant="block" className="h-16" />
                <Skeleton variant="block" className="h-16" />
              </div>
            ) : (
              <div className="space-y-4">
                {/* 4-column metric row — avoids 2×2 tall grid */}
                <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
                  <MetricTile label="Runs" value={globalStats.total_runs} />
                  <MetricTile
                    label="Tokens"
                    value={formatTokens(
                      globalStats.total_input_tokens + globalStats.total_output_tokens,
                    )}
                    tone="info"
                  />
                  <MetricTile
                    label="Est. cost"
                    value={formatCost(globalStats.total_cost_usd)}
                  />
                  <MetricTile
                    label="Total time"
                    value={formatDuration(globalStats.total_duration_seconds)}
                  />
                </div>
                <div className="border-t border-hairline pt-3">
                  <SectionToggle
                    title="Details"
                    open={statsOpen}
                    onToggle={() => setStatsOpen((o) => !o)}
                  />
                  {statsOpen && (
                    <div className="mt-4 grid gap-6 sm:grid-cols-2">
                      <div>
                        <p className="mb-3 font-display text-[10px] font-semibold uppercase tracking-[0.2em] text-ink-faint">
                          Top tools
                        </p>
                        {statsTools.length === 0 ? (
                          <p className="py-2 font-mono text-[11px] text-ink-faint">
                            No tool data yet
                          </p>
                        ) : (
                          <div className="space-y-3">
                            {statsTools.map(([name, count]) => (
                              <ToolBar key={name} name={name} count={count} max={maxTool} />
                            ))}
                          </div>
                        )}
                      </div>
                      <div>
                        <p className="mb-3 font-display text-[10px] font-semibold uppercase tracking-[0.2em] text-ink-faint">
                          Exit reasons
                        </p>
                        <div className="space-y-2">
                          {["DONE", "WAIT", "BLOCKED", "STOPPED", "CRASHED"].map((reason) => (
                            <ExitReasonBadge
                              key={reason}
                              reason={reason}
                              count={globalStats.exit_reason_counts[reason] ?? 0}
                            />
                          ))}
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Test Health card */}
        <div className="overflow-hidden rounded-md border border-hairline bg-surface-1 shadow-inset-hairline">
          <div className="h-[2px] bg-warning" />
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-hairline px-4 py-3">
            <div className="flex items-center gap-2">
              <h2 className="font-display text-[11px] font-semibold uppercase tracking-[0.2em] text-ink-muted">
                Test Health
              </h2>
              {latestTestReport && (
                <span className="font-mono text-[10px] tabular-nums text-ink-faint">
                  {latestTestReport.total_passed}✓{" "}
                  {latestTestReport.total_failed + latestTestReport.total_errors}✗
                </span>
              )}
            </div>
            {spaces.length > 0 && (
              <div className="flex items-center gap-2">
                <label
                  htmlFor="tests-space-filter"
                  className="font-display text-[10px] uppercase tracking-[0.18em] text-ink-faint"
                >
                  Space
                </label>
                <select
                  id="tests-space-filter"
                  value={testsSpaceId}
                  onChange={(e) => setTestsSpaceId(e.target.value)}
                  className="h-8 rounded border border-hairline bg-surface-2 px-2 font-mono text-[12px] text-ink shadow-inset-hairline transition focus:border-accent focus:outline-none"
                >
                  <option value="">Select…</option>
                  {spaces.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.name}
                    </option>
                  ))}
                </select>
              </div>
            )}
          </div>
          <div className="p-4">
            {!testsSpaceId ? (
              <div className="flex items-center justify-center py-8">
                <p className="font-mono text-[11px] text-ink-faint">
                  Select a space above to view test health.
                </p>
              </div>
            ) : testReportsLoading ? (
              <Skeleton variant="card" className="h-32" />
            ) : !latestTestReport ? (
              <div className="flex items-center justify-center py-8">
                <p className="font-mono text-[11px] text-ink-faint">
                  No test reports yet for this space.
                </p>
              </div>
            ) : (
              <div className="space-y-4">
                <SummaryBar report={latestTestReport} />
                <div>
                  <p className="mb-3 font-display text-[9px] uppercase tracking-[0.2em] text-ink-faint">
                    Last {Math.min(testReports!.length, 10)} runs
                  </p>
                  <TrendStrip reports={testReports!} />
                </div>
                {latestFullReport && <TestDetails report={latestFullReport} />}
              </div>
            )}
          </div>
        </div>
      </section>

      {/* ── Zone B: Spaces & Activity ───────────────────────────────────────── */}

      {/* Zone divider */}
      <div className="flex items-center gap-3">
        <div className="h-px flex-1 bg-surface-3" />
        <span className="font-display text-[9px] uppercase tracking-[0.28em] text-ink-faint">
          Spaces & Activity
        </span>
        <div className="h-px flex-1 bg-surface-3" />
      </div>

      {spaces.length === 0 ? (
        <section className="rounded-lg border border-dashed border-hairline-strong bg-surface-1 p-10 shadow-inset-hairline">
          <EmptyState
            title="Create your first space"
            description="Spaces group tasks like projects. Each one owns its own tasks, workspaces, and (soon) a bound git repository."
          >
            <Link
              to="/spaces/new"
              className="inline-flex h-9 items-center rounded border border-accent bg-accent px-4 text-[12px] font-medium text-canvas transition hover:bg-accent-bright"
            >
              New space
            </Link>
          </EmptyState>
        </section>
      ) : (
        <section className="grid gap-6 xl:grid-cols-[2fr_1fr]">
          {/* Spaces grid */}
          <div>
            <SectionHeader title="Spaces" count={spaces.length} />
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-2 2xl:grid-cols-3">
              {spaces.map((space) => (
                <SpaceCard key={space.id} space={space} />
              ))}
              <Link
                to="/spaces/new"
                className="flex min-h-[150px] items-center justify-center rounded-md border border-dashed border-hairline-strong bg-surface-1/40 text-[12px] uppercase tracking-[0.2em] text-ink-muted transition hover:border-accent hover:text-accent-bright"
              >
                + New space
              </Link>
            </div>
          </div>

          {/* Activity feed — compact, height-capped, scrollable */}
          <div>
            <SectionHeader
              title="Activity"
              count={activity?.length ?? 0}
              right={
                <PaginationControls
                  page={activityPage}
                  totalPages={totalActivityPages}
                  onChange={setActivityPage}
                />
              }
            />
            <div className="overflow-hidden rounded-md border border-hairline bg-surface-1 shadow-inset-hairline">
              {!activity || activity.length === 0 ? (
                <EmptyState title="No activity yet" />
              ) : (
                <div className="max-h-[340px] overflow-y-auto">
                  {pagedActivity.map((ev) => (
                    <ActivityRow
                      key={ev.task_id + ev.updated_at}
                      event={ev}
                      spaceLookup={lookup}
                    />
                  ))}
                </div>
              )}
            </div>
          </div>
        </section>
      )}

      {/* ── TaskForm modal ─────────────────────────────────────────────────── */}
      {creating && (
        <TaskForm
          heading="New task"
          showSpacePicker
          submitting={isWorking}
          error={workError}
          onCancel={() => {
            setCreating(false);
            setWorkError(null);
          }}
          onSubmit={async (body) => {
            if (!body.space_id) return;
            setIsWorking(true);
            setWorkError(null);
            try {
              const task = await createTask.mutateAsync({
                space_id: body.space_id,
                title: body.title,
                brief: body.brief,
                agent_model: body.agent_model,
                agent_mode: body.agent_mode,
              });
              for (const file of body.files) {
                await api.uploadTaskFile(task.id, file);
              }
              if (body.startImmediately) {
                await api.start(task.id);
              }
              setCreating(false);
            } catch (err) {
              setWorkError(err instanceof Error ? err.message : String(err));
            } finally {
              setIsWorking(false);
            }
          }}
        />
      )}
      </div>
    </PageContainer>
  );
}
