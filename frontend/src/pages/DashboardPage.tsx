import { useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useActivity, useImportSpace, useSpaces } from "../hooks/useSpaces";
import { useCreateTask } from "../hooks/useTasks";
import { useGlobalStats } from "../hooks/useStats";
import { useTestReports } from "../hooks/useTestReports";
import { TaskForm } from "../components/TaskForm";
import { EmptyState } from "../components/ui/EmptyState";
import { SpaceTag } from "../components/ui/SpaceTag";
import { api } from "../api";
import { formatRelative } from "../utils/format";
import type { Activity, SpaceSummary, TaskState, TestReportSummary } from "../types";

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

function StatTile({
  label,
  value,
  tone = "ink",
  pulse = false,
  to,
}: {
  label: string;
  value: number | string;
  tone?: "ink" | "accent" | "warning";
  pulse?: boolean;
  to?: string;
}) {
  const valueClass =
    tone === "accent"
      ? "text-accent-bright"
      : tone === "warning"
        ? "text-warning"
        : "text-ink";
  const baseClass =
    "flex h-24 flex-col justify-between rounded-md border border-hairline bg-surface-1 p-4 shadow-inset-hairline";
  const interactiveClass = to
    ? " cursor-pointer transition hover:-translate-y-px hover:border-hairline-strong hover:shadow-lift"
    : "";
  const inner = (
    <>
      <div className="flex items-center justify-between font-display text-[10px] uppercase tracking-[0.2em] text-ink-faint">
        <span>{label}</span>
        {pulse && (
          <span
            aria-hidden
            className="anim-pulse-dot h-2 w-2 rounded-full bg-accent-bright"
          />
        )}
      </div>
      <p className={`font-display text-[28px] font-semibold tabular-nums ${valueClass}`}>
        {value}
      </p>
    </>
  );
  return to ? (
    <Link to={to} className={baseClass + interactiveClass}>
      {inner}
    </Link>
  ) : (
    <div className={baseClass}>{inner}</div>
  );
}

// ── AI stats metric tiles ─────────────────────────────────────────────────────

function MetricTile({
  label,
  value,
  tone = "ink",
  sub,
}: {
  label: string;
  value: string | number;
  tone?: "ink" | "accent" | "warning" | "danger";
  sub?: string;
}) {
  const valueClass =
    tone === "accent"
      ? "text-accent-bright"
      : tone === "warning"
        ? "text-warning"
        : tone === "danger"
          ? "text-danger"
          : "text-ink";

  return (
    <div className="flex h-24 flex-col justify-between rounded-md border border-hairline bg-surface-1 p-4 shadow-inset-hairline">
      <p className="font-display text-[10px] uppercase tracking-[0.2em] text-ink-faint">
        {label}
      </p>
      <div>
        <p className={`font-display text-[24px] font-semibold tabular-nums leading-none ${valueClass}`}>
          {value}
        </p>
        {sub && (
          <p className="mt-1 font-mono text-[10px] tracking-wide text-ink-faint">{sub}</p>
        )}
      </div>
    </div>
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
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-5">
      <div className="flex flex-col gap-0.5 rounded-md border border-hairline bg-surface-1 p-4 shadow-inset-hairline">
        <span className="font-display text-[9px] uppercase tracking-[0.2em] text-ink-faint">Passed</span>
        <span className="font-display text-[24px] font-semibold tabular-nums leading-none text-accent-bright">
          {report.total_passed}
        </span>
      </div>
      <div className="flex flex-col gap-0.5 rounded-md border border-hairline bg-surface-1 p-4 shadow-inset-hairline">
        <span className="font-display text-[9px] uppercase tracking-[0.2em] text-ink-faint">Failed</span>
        <span className={`font-display text-[24px] font-semibold tabular-nums leading-none ${report.total_failed > 0 ? "text-danger" : "text-ink"}`}>
          {report.total_failed}
        </span>
      </div>
      <div className="flex flex-col gap-0.5 rounded-md border border-hairline bg-surface-1 p-4 shadow-inset-hairline">
        <span className="font-display text-[9px] uppercase tracking-[0.2em] text-ink-faint">Errors</span>
        <span className={`font-display text-[24px] font-semibold tabular-nums leading-none ${report.total_errors > 0 ? "text-danger" : "text-ink"}`}>
          {report.total_errors}
        </span>
      </div>
      <div className="flex flex-col gap-0.5 rounded-md border border-hairline bg-surface-1 p-4 shadow-inset-hairline">
        <span className="font-display text-[9px] uppercase tracking-[0.2em] text-ink-faint">Skipped</span>
        <span className="font-display text-[24px] font-semibold tabular-nums leading-none text-ink-muted">
          {report.total_skipped}
        </span>
      </div>
      {report.coverage_pct != null && (
        <div className="flex flex-col gap-0.5 rounded-md border border-hairline bg-surface-1 p-4 shadow-inset-hairline">
          <span className="font-display text-[9px] uppercase tracking-[0.2em] text-ink-faint">Coverage</span>
          <span className={`font-display text-[24px] font-semibold tabular-nums leading-none ${
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

// ── Existing helpers ──────────────────────────────────────────────────────────

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
      className="grid grid-cols-[3.5rem_auto_1fr_5rem] items-center gap-2 border-b border-hairline px-3 py-2 transition hover:bg-surface-2/60"
    >
      <span className="font-mono text-[10px] uppercase tracking-[0.12em] text-ink-faint">
        {formatRelative(event.updated_at)}
      </span>
      <SpaceTag color={space?.color} size="xs" />
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

// ── Main page ─────────────────────────────────────────────────────────────────

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

  const [statsOpen, setStatsOpen] = useState(false);
  const [testsOpen, setTestsOpen] = useState(false);
  const [testsSpaceId, setTestsSpaceId] = useState("");

  const { data: globalStats } = useGlobalStats();
  const { data: testReports, isLoading: testReportsLoading } = useTestReports(
    testsSpaceId || undefined,
  );

  const spaces = spacesData?.spaces ?? [];
  const totals = spacesData?.totals ?? { backlog: 0, active: 0, waiting: 0, done: 0 };
  const lookup = new Map(spaces.map((s) => [s.id, s] as const));

  const totalTasks =
    (totals.backlog ?? 0) +
    (totals.active ?? 0) +
    (totals.waiting ?? 0) +
    (totals.done ?? 0);

  const statsTools = globalStats
    ? Object.entries(globalStats.tool_use_summary).sort(([, a], [, b]) => b - a).slice(0, 5)
    : [];
  const maxTool = statsTools[0]?.[1] ?? 1;

  const latestTestReport =
    testReports && testReports.length > 0 ? testReports[testReports.length - 1] : null;

  async function handleImport(file: File) {
    try {
      const space = await importMutation.mutateAsync({ file });
      navigate(`/spaces/${space.id}`);
    } catch (err) {
      console.error(err);
    }
  }

  if (spacesLoading) {
    return <p className="p-8 text-ink-muted">Loading dashboard…</p>;
  }

  return (
    <div className="mx-auto max-w-[1280px] space-y-8 p-6 lg:p-8">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-ink-faint">
            Cronos · Overview
          </p>
          <h1 className="font-display text-[22px] font-semibold uppercase tracking-[0.14em] text-ink">
            Dashboard
          </h1>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={() => setCreating(true)}
            className="flex h-9 items-center gap-1.5 rounded border border-accent bg-accent px-3 text-[12px] font-medium text-canvas transition hover:bg-accent-bright"
          >
            <span aria-hidden className="text-base leading-none">＋</span>
            New task
          </button>
          <Link
            to="/spaces/new"
            className="flex h-9 items-center rounded border border-hairline-strong bg-surface-1 px-3 text-[12px] text-ink transition hover:border-accent hover:bg-surface-2"
          >
            New space
          </Link>
          <button
            type="button"
            onClick={() => fileRef.current?.click()}
            disabled={importMutation.isPending}
            className="flex h-9 items-center rounded px-3 text-[12px] text-ink-muted transition hover:bg-surface-2 hover:text-ink disabled:opacity-60"
          >
            {importMutation.isPending ? "Importing…" : "Import space"}
          </button>
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
        </div>
      </header>

      <section className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-5">
        <StatTile label="To Do" value={totals.backlog ?? 0} to="/board" />
        <StatTile
          label="Active agents"
          value={totals.active ?? 0}
          tone="accent"
          pulse={(totals.active ?? 0) > 0}
          to="/board"
        />
        <StatTile
          label="Waiting"
          value={totals.waiting ?? 0}
          tone={totals.waiting ? "warning" : "ink"}
          to="/board"
        />
        <StatTile label="Done" value={totals.done ?? 0} to="/board" />
        <StatTile label="Total tasks" value={totalTasks} to="/board" />
      </section>

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
          <div>
            <div className="mb-3 flex items-baseline gap-2">
              <h2 className="font-display text-[11px] font-semibold uppercase tracking-[0.2em] text-ink-muted">
                Spaces
              </h2>
              <span className="font-mono text-[10px] tabular-nums text-ink-faint">
                {String(spaces.length).padStart(2, "0")}
              </span>
            </div>
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

          <div>
            <div className="mb-3 flex items-baseline gap-2">
              <h2 className="font-display text-[11px] font-semibold uppercase tracking-[0.2em] text-ink-muted">
                Activity
              </h2>
              <span className="font-mono text-[10px] tabular-nums text-ink-faint">
                {String(activity?.length ?? 0).padStart(2, "0")}
              </span>
            </div>
            <div className="overflow-hidden rounded-md border border-hairline bg-surface-1 shadow-inset-hairline">
              {!activity || activity.length === 0 ? (
                <EmptyState title="No activity yet" />
              ) : (
                <div>
                  {activity.map((ev) => (
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

      {/* ── AI Performance ─────────────────────────────────────────────────── */}
      <section>
        <div className="mb-3">
          <SectionToggle
            title="AI Performance"
            open={statsOpen}
            onToggle={() => setStatsOpen((o) => !o)}
            badge={globalStats ? `${globalStats.total_runs} runs` : undefined}
          />
        </div>
        {statsOpen && (
          <>
            {!globalStats ? (
              <div className="py-8 text-center font-mono text-[11px] text-ink-faint">
                Loading statistics…
              </div>
            ) : (
              <div className="space-y-6">
                <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                  <MetricTile label="Total runs" value={globalStats.total_runs} />
                  <MetricTile
                    label="Total tokens"
                    value={formatTokens(
                      globalStats.total_input_tokens + globalStats.total_output_tokens,
                    )}
                    tone="accent"
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

                <div className="grid gap-6 lg:grid-cols-[2fr_1fr]">
                  <div>
                    <p className="mb-3 font-display text-[10px] font-semibold uppercase tracking-[0.2em] text-ink-faint">
                      Top tools
                    </p>
                    <div className="rounded-md border border-hairline bg-surface-1 p-4 shadow-inset-hairline">
                      {statsTools.length === 0 ? (
                        <p className="py-4 text-center font-mono text-[11px] text-ink-faint">
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
              </div>
            )}
          </>
        )}
      </section>

      {/* ── Test Health ────────────────────────────────────────────────────── */}
      <section>
        <div className="mb-3">
          <SectionToggle
            title="Test Health"
            open={testsOpen}
            onToggle={() => setTestsOpen((o) => !o)}
            badge={latestTestReport ? `${latestTestReport.total_passed}✓ ${latestTestReport.total_failed + latestTestReport.total_errors}✗` : undefined}
          >
            {testsOpen && spaces.length > 0 && (
              <>
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
                  className="h-8 rounded border border-hairline bg-surface-1 px-2 font-mono text-[12px] text-ink shadow-inset-hairline transition focus:border-accent focus:outline-none"
                >
                  <option value="">Select…</option>
                  {spaces.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.name}
                    </option>
                  ))}
                </select>
              </>
            )}
          </SectionToggle>
        </div>

        {testsOpen && (
          <>
            {!testsSpaceId ? (
              <div className="rounded-md border border-dashed border-hairline bg-surface-1 p-8 text-center shadow-inset-hairline">
                <p className="font-mono text-[11px] text-ink-faint">
                  Select a space above to view test health.
                </p>
              </div>
            ) : testReportsLoading ? (
              <div className="py-8 text-center font-mono text-[11px] text-ink-faint">
                Loading…
              </div>
            ) : !latestTestReport ? (
              <div className="rounded-md border border-dashed border-hairline bg-surface-1 p-8 text-center shadow-inset-hairline">
                <p className="font-mono text-[11px] text-ink-faint">
                  No test reports yet for this space.
                </p>
              </div>
            ) : (
              <div className="space-y-4">
                <SummaryBar report={latestTestReport} />
                <div className="rounded-md border border-hairline bg-surface-1 p-4 shadow-inset-hairline">
                  <p className="mb-3 font-display text-[9px] uppercase tracking-[0.2em] text-ink-faint">
                    Last {Math.min(testReports!.length, 10)} runs
                  </p>
                  <TrendStrip reports={testReports!} />
                </div>
              </div>
            )}
          </>
        )}
      </section>

      {creating && (
        <TaskForm
          heading="New task"
          showSpacePicker
          submitting={isWorking}
          error={workError}
          onCancel={() => { setCreating(false); setWorkError(null); }}
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
  );
}
