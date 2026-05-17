import { useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useActivity, useImportSpace, useSpaces } from "../hooks/useSpaces";
import { useCreateTask } from "../hooks/useTasks";
import { TaskForm } from "../components/TaskForm";
import { EmptyState } from "../components/ui/EmptyState";
import { SpaceTag } from "../components/ui/SpaceTag";
import { api } from "../api";
import { formatRelative } from "../utils/format";
import type { Activity, SpaceSummary, TaskState } from "../types";

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

  const spaces = spacesData?.spaces ?? [];
  const totals = spacesData?.totals ?? { backlog: 0, active: 0, waiting: 0, done: 0 };
  const lookup = new Map(spaces.map((s) => [s.id, s] as const));

  const totalTasks =
    (totals.backlog ?? 0) +
    (totals.active ?? 0) +
    (totals.waiting ?? 0) +
    (totals.done ?? 0);

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
