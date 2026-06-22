import { useState } from "react";
import { useSpaces } from "../hooks/useSpaces";
import { useConfirmMemory, useMemoryItems, useRejectMemory } from "../hooks/useMemory";
import type { MemoryItem, MemoryKind } from "../types";
import { cn } from "../utils/cn";
import { PageContainer } from "../components/ui/PageContainer";
import { PageHeader } from "../components/ui/PageHeader";

// ── Constants ─────────────────────────────────────────────────────────────────

const KIND_STYLE: Record<MemoryKind, { label: string; cls: string }> = {
  fact:        { label: "Fact",        cls: "text-accent-bright border-accent/30 bg-accent/10" },
  procedure:   { label: "Procedure",   cls: "text-warning border-warning/30 bg-warning/10" },
  observation: { label: "Observation", cls: "text-ink-muted border-hairline bg-surface-2" },
  reference:   { label: "Reference",   cls: "text-ink border-hairline bg-surface-3" },
};

const ALL_KINDS: MemoryKind[] = ["fact", "procedure", "observation", "reference"];

// ── Sub-components ────────────────────────────────────────────────────────────

function KindBadge({ kind }: { kind: MemoryKind }) {
  const s = KIND_STYLE[kind] ?? { label: kind, cls: "text-ink-muted border-hairline bg-surface-2" };
  return (
    <span
      className={cn(
        "inline-flex items-center rounded border px-1.5 py-0.5 font-mono text-[9px] uppercase tracking-[0.14em]",
        s.cls,
      )}
    >
      {s.label}
    </span>
  );
}

function ScoreBar({ value }: { value: number }) {
  const pct = Math.round(Math.max(0, Math.min(1, value)) * 100);
  return (
    <div className="flex items-center gap-1.5">
      <div className="h-1 w-16 overflow-hidden rounded-full bg-surface-3">
        <div
          className="h-full rounded-full bg-accent-bright/60 transition-all"
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="font-mono text-[10px] tabular-nums text-ink-faint">{pct}</span>
    </div>
  );
}

function MemoryRow({
  item,
  scope,
}: {
  item: MemoryItem;
  scope: string;
}) {
  const [expanded, setExpanded] = useState(false);
  const confirm = useConfirmMemory(scope);
  const reject = useRejectMemory(scope);

  return (
    <div
      className={cn(
        "rounded-md border border-hairline bg-surface-1 shadow-inset-hairline transition",
        !item.confirmed && "border-warning/30 bg-warning/5",
      )}
    >
      <div
        className="flex cursor-pointer select-none items-start gap-3 p-3"
        onClick={() => setExpanded((v) => !v)}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => e.key === "Enter" && setExpanded((v) => !v)}
        aria-expanded={expanded}
      >
        {/* Expand chevron */}
        <span
          className={cn(
            "mt-0.5 shrink-0 font-mono text-[10px] text-ink-faint transition-transform",
            expanded && "rotate-90",
          )}
          aria-hidden
        >
          ▶
        </span>

        <div className="min-w-0 flex-1 space-y-1">
          <div className="flex flex-wrap items-center gap-2">
            <KindBadge kind={item.kind} />
            {!item.confirmed && (
              <span className="inline-flex items-center rounded border border-warning/40 bg-warning/10 px-1.5 py-0.5 font-mono text-[9px] uppercase tracking-[0.14em] text-warning">
                Unconfirmed
              </span>
            )}
            <span className="min-w-0 flex-1 truncate font-display text-[13px] font-medium text-ink">
              {item.title}
            </span>
          </div>
          <div className="flex flex-wrap items-center gap-4">
            <div className="flex items-center gap-1">
              <span className="font-mono text-[10px] text-ink-faint">score</span>
              <ScoreBar value={item.score} />
            </div>
            <div className="flex items-center gap-1">
              <span className="font-mono text-[10px] text-ink-faint">conf</span>
              <ScoreBar value={item.confidence} />
            </div>
            <span className="font-mono text-[10px] tabular-nums text-ink-faint">
              ×{item.ref_count}
            </span>
          </div>
        </div>

        {/* Actions */}
        <div className="flex shrink-0 items-center gap-1.5" onClick={(e) => e.stopPropagation()}>
          {!item.confirmed && (
            <button
              type="button"
              disabled={confirm.isPending}
              onClick={() => confirm.mutate(item.id)}
              className="rounded border border-accent/40 bg-accent/10 px-2 py-1 font-mono text-[10px] uppercase tracking-[0.14em] text-accent-bright transition hover:bg-accent/20 disabled:opacity-50"
            >
              {confirm.isPending ? "…" : "Confirm"}
            </button>
          )}
          <button
            type="button"
            disabled={reject.isPending}
            onClick={() => reject.mutate(item.id)}
            className="rounded border border-danger/40 bg-danger/10 px-2 py-1 font-mono text-[10px] uppercase tracking-[0.14em] text-danger transition hover:bg-danger/20 disabled:opacity-50"
          >
            {reject.isPending ? "…" : item.confirmed ? "Delete" : "Reject"}
          </button>
        </div>
      </div>

      {/* Expanded body */}
      {expanded && (
        <div className="border-t border-hairline px-4 pb-3 pt-2 text-[12px] text-ink-muted">
          {item.body ? (
            <p className="whitespace-pre-wrap">{item.body}</p>
          ) : (
            <p className="italic text-ink-faint">No body.</p>
          )}
          {item.sources.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-1">
              {item.sources.map((s) => (
                <span
                  key={s}
                  className="rounded bg-surface-2 px-1.5 py-0.5 font-mono text-[10px] text-ink-faint"
                >
                  {s}
                </span>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export function MemoryPage() {
  const { data: spacesData } = useSpaces();
  const spaces = spacesData?.spaces ?? [];

  const [scope, setScope] = useState<string>("global");
  const [kindFilter, setKindFilter] = useState<MemoryKind | "all">("all");
  const [confirmedFilter, setConfirmedFilter] = useState<"all" | "confirmed" | "unconfirmed">("all");

  const { data: items, isLoading } = useMemoryItems(scope);

  const filtered = (items ?? []).filter((item) => {
    if (kindFilter !== "all" && item.kind !== kindFilter) return false;
    if (confirmedFilter === "confirmed" && !item.confirmed) return false;
    if (confirmedFilter === "unconfirmed" && item.confirmed) return false;
    return true;
  });

  const unconfirmedCount = (items ?? []).filter((i) => !i.confirmed).length;

  return (
    <PageContainer width="reading" className="space-y-6">
      <PageHeader
        title="Memory Browser"
        actions={
          unconfirmedCount > 0
            ? [
                <span
                  key="unconfirmed"
                  className="rounded border border-warning/40 bg-warning/10 px-2.5 py-1 font-mono text-[11px] text-warning"
                >
                  {unconfirmedCount} unconfirmed
                </span>,
              ]
            : undefined
        }
      />

      {/* Filters row */}
      <div className="flex flex-wrap items-center gap-3">
        {/* Scope selector */}
        <div className="flex items-center gap-2">
          <label className="font-mono text-[10px] uppercase tracking-[0.14em] text-ink-faint">
            Scope
          </label>
          <select
            value={scope}
            onChange={(e) => setScope(e.target.value)}
            className="rounded border border-hairline bg-surface-1 px-2 py-1 font-mono text-[11px] text-ink shadow-inset-hairline focus:outline-none focus:ring-1 focus:ring-accent"
          >
            <option value="global">Global</option>
            {spaces.map((s) => (
              <option key={s.id} value={`space:${s.id}`}>
                {s.icon ? `${s.icon} ` : ""}{s.name}
              </option>
            ))}
          </select>
        </div>

        {/* Kind filter */}
        <div className="flex items-center gap-1.5">
          <button
            type="button"
            onClick={() => setKindFilter("all")}
            className={cn(
              "rounded border px-2 py-1 font-mono text-[10px] uppercase tracking-[0.14em] transition",
              kindFilter === "all"
                ? "border-accent/40 bg-accent/10 text-accent-bright"
                : "border-hairline bg-surface-1 text-ink-muted hover:text-ink",
            )}
          >
            All kinds
          </button>
          {ALL_KINDS.map((k) => (
            <button
              key={k}
              type="button"
              onClick={() => setKindFilter(kindFilter === k ? "all" : k)}
              className={cn(
                "rounded border px-2 py-1 font-mono text-[10px] uppercase tracking-[0.14em] transition",
                kindFilter === k
                  ? KIND_STYLE[k].cls + " border-current"
                  : "border-hairline bg-surface-1 text-ink-muted hover:text-ink",
              )}
            >
              {KIND_STYLE[k].label}
            </button>
          ))}
        </div>

        {/* Confirmed filter */}
        <div className="flex items-center gap-1.5">
          {(["all", "confirmed", "unconfirmed"] as const).map((f) => (
            <button
              key={f}
              type="button"
              onClick={() => setConfirmedFilter(f)}
              className={cn(
                "rounded border px-2 py-1 font-mono text-[10px] uppercase tracking-[0.14em] transition",
                confirmedFilter === f
                  ? "border-accent/40 bg-accent/10 text-accent-bright"
                  : "border-hairline bg-surface-1 text-ink-muted hover:text-ink",
              )}
            >
              {f}
            </button>
          ))}
        </div>
      </div>

      {/* Item list */}
      {isLoading ? (
        <div className="py-12 text-center font-mono text-[11px] text-ink-faint">Loading…</div>
      ) : filtered.length === 0 ? (
        <div className="rounded-md border border-hairline bg-surface-1 p-8 text-center shadow-inset-hairline">
          <p className="font-mono text-[11px] text-ink-faint">
            {(items ?? []).length === 0 ? "No memory items in this scope." : "No items match the current filters."}
          </p>
        </div>
      ) : (
        <div className="space-y-2">
          <p className="font-mono text-[10px] text-ink-faint">
            {filtered.length} item{filtered.length !== 1 ? "s" : ""}
          </p>
          {filtered.map((item) => (
            <MemoryRow key={item.id} item={item} scope={scope} />
          ))}
        </div>
      )}
    </PageContainer>
  );
}
