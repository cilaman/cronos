import { useState } from "react";
import { useDiscoverySources, useDiscoveryTools, useDiscoveryRefresh } from "../hooks/useSpaces";
import { cn } from "../utils/cn";
import type { DiscoveredTool, ToolSource } from "../types";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const KIND_LABELS: Record<string, string> = {
  agent: "Agents",
  skill: "Skills",
  command: "Commands",
  hook: "Hooks",
};

const KIND_ICON: Record<string, string> = {
  agent: "🤖",
  skill: "⚡",
  command: "⌘",
  hook: "🪝",
};

const KIND_ORDER = ["agent", "skill", "command", "hook"];

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function SourceBadge({ slug }: { slug: string }) {
  return (
    <span className="shrink-0 rounded border border-hairline bg-surface-2 px-1.5 py-0.5 font-mono text-[9px] uppercase tracking-[0.12em] text-ink-muted">
      {slug}
    </span>
  );
}

function SourceRow({
  source,
  onRefresh,
  isRefreshing,
}: {
  source: ToolSource;
  onRefresh: () => void;
  isRefreshing: boolean;
}) {
  const label = source.label ?? source.url.replace(/^https?:\/\//, "").replace(/\.git$/, "");
  return (
    <div className="flex items-center justify-between gap-3 border-b border-hairline px-4 py-2.5 last:border-b-0">
      <div className="min-w-0 flex-1">
        <p className="truncate font-display text-[12px] font-medium text-ink">{label}</p>
        <p className="truncate font-mono text-[10px] text-ink-faint">{source.url}</p>
      </div>
      <div className="flex shrink-0 items-center gap-2">
        {source.branch && (
          <span className="rounded border border-hairline bg-surface-2 px-1.5 py-0.5 font-mono text-[10px] text-ink-muted">
            {source.branch}
          </span>
        )}
        {!source.enabled && (
          <span className="rounded border border-hairline px-1.5 py-0.5 font-mono text-[10px] text-ink-faint">
            disabled
          </span>
        )}
        <button
          type="button"
          onClick={onRefresh}
          disabled={isRefreshing}
          className={cn(
            "rounded border px-2.5 py-1 font-display text-[11px] font-medium transition",
            isRefreshing
              ? "border-hairline bg-surface-2 text-ink-faint"
              : "border-accent/30 bg-accent/10 text-accent-bright hover:bg-accent/20",
          )}
        >
          {isRefreshing ? "Refreshing…" : "Refresh"}
        </button>
      </div>
    </div>
  );
}

function DiscoveredToolCard({ tool }: { tool: DiscoveredTool }) {
  const icon = KIND_ICON[tool.kind] ?? "📄";
  return (
    <div className="rounded-md border border-hairline bg-surface-1 p-4 shadow-inset-hairline transition hover:-translate-y-px hover:border-hairline-strong hover:shadow-lift">
      <div className="mb-2 flex items-start justify-between gap-2">
        <div className="flex min-w-0 items-center gap-2">
          <span className="shrink-0 text-[18px] leading-none" aria-hidden>
            {icon}
          </span>
          <span className="truncate font-display text-[13px] font-semibold tracking-[0.04em] text-ink">
            {tool.name}
          </span>
        </div>
        <SourceBadge slug={tool.source_slug} />
      </div>
      <p className="line-clamp-2 text-[12px] leading-relaxed text-ink-muted">
        {tool.description ?? (
          <span className="italic text-ink-faint">No description</span>
        )}
      </p>
      <div className="mt-3 truncate font-mono text-[10px] text-ink-faint">
        {tool.relative_path}
      </div>
    </div>
  );
}

function KindGroup({ kind, tools }: { kind: string; tools: DiscoveredTool[] }) {
  return (
    <section>
      <div className="mb-3 flex items-baseline gap-2">
        <h2 className="font-display text-[11px] font-semibold uppercase tracking-[0.2em] text-ink-muted">
          {KIND_LABELS[kind] ?? kind}
        </h2>
        <span className="font-mono text-[10px] tabular-nums text-ink-faint">
          {String(tools.length).padStart(2, "0")}
        </span>
      </div>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {tools.map((t) => (
          <DiscoveredToolCard key={`${t.source_slug}:${t.kind}:${t.name}`} tool={t} />
        ))}
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Panel
// ---------------------------------------------------------------------------

export function DiscoveryPanel() {
  const [kindFilter, setKindFilter] = useState<string>("all");
  const [search, setSearch] = useState("");

  const { data: sources = [], isLoading: sourcesLoading } = useDiscoverySources();
  const { data: allTools = [], isLoading: toolsLoading } = useDiscoveryTools();
  const refreshMutation = useDiscoveryRefresh();

  const isRefreshing = refreshMutation.isPending;

  function handleRefresh() {
    refreshMutation.mutate();
  }

  // Derived state
  const filteredTools = allTools.filter((t) => {
    if (kindFilter !== "all" && t.kind !== kindFilter) return false;
    if (search.trim()) {
      const q = search.toLowerCase();
      return (
        t.name.toLowerCase().includes(q) ||
        (t.description ?? "").toLowerCase().includes(q) ||
        t.source_slug.toLowerCase().includes(q)
      );
    }
    return true;
  });

  const grouped = KIND_ORDER.map((kind) => ({
    kind,
    tools: filteredTools.filter((t) => t.kind === kind),
  })).filter((g) => g.tools.length > 0);

  const noSourcesConfigured = !sourcesLoading && sources.length === 0;
  const hasActiveFilters = kindFilter !== "all" || search.trim().length > 0;

  // Empty state: no sources configured at all
  if (noSourcesConfigured) {
    return (
      <div className="rounded-lg border border-dashed border-hairline-strong bg-surface-1 p-10 shadow-inset-hairline">
        <div className="mx-auto max-w-sm text-center">
          <p className="font-display text-[13px] font-semibold uppercase tracking-[0.14em] text-ink">
            No tool sources configured
          </p>
          <p className="mt-2 text-[12px] text-ink-muted">
            Add URLs to{" "}
            <code className="font-mono text-[11px]">/data/tool_sources.yml</code> to
            start discovering tools from external repositories.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Sources */}
      <section>
        <div className="mb-3 flex items-baseline gap-2">
          <h2 className="font-display text-[11px] font-semibold uppercase tracking-[0.2em] text-ink-muted">
            Sources
          </h2>
          <span className="font-mono text-[10px] tabular-nums text-ink-faint">
            {String(sources.length).padStart(2, "0")}
          </span>
        </div>
        <div className="overflow-hidden rounded-md border border-hairline bg-surface-1 shadow-inset-hairline">
          {sourcesLoading ? (
            <p className="px-4 py-3 text-[12px] text-ink-muted">Loading sources…</p>
          ) : (
            sources.map((s, i) => (
              <SourceRow
                key={i}
                source={s}
                onRefresh={handleRefresh}
                isRefreshing={isRefreshing}
              />
            ))
          )}
        </div>
        {refreshMutation.isError && (
          <p className="mt-2 text-[11px] text-danger">
            Refresh failed.{" "}
            {(refreshMutation.error as Error)?.message ?? "Unknown error"}
          </p>
        )}
      </section>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-2">
        <select
          value={kindFilter}
          onChange={(e) => setKindFilter(e.target.value)}
          aria-label="Filter by kind"
          className="h-8 rounded border border-hairline-strong bg-surface-1 px-2 text-[12px] text-ink transition hover:border-accent focus:border-accent focus:outline-none"
        >
          <option value="all">All kinds</option>
          {KIND_ORDER.map((k) => (
            <option key={k} value={k}>
              {KIND_LABELS[k]}
            </option>
          ))}
        </select>
        <input
          type="search"
          placeholder="Search tools…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          aria-label="Search tools"
          className="h-8 min-w-[180px] rounded border border-hairline-strong bg-surface-1 px-3 text-[12px] text-ink placeholder:text-ink-faint transition hover:border-accent focus:border-accent focus:outline-none"
        />
        {allTools.length > 0 && (
          <span className="ml-auto font-mono text-[11px] text-ink-faint">
            {filteredTools.length} / {allTools.length}
          </span>
        )}
      </div>

      {/* Tool groups or empty states */}
      {toolsLoading ? (
        <p className="text-[12px] text-ink-muted">Loading discovered tools…</p>
      ) : allTools.length === 0 ? (
        <div className="rounded-md border border-dashed border-hairline bg-surface-1/40 px-4 py-8 text-center">
          <p className="font-display text-[11px] uppercase tracking-[0.18em] text-ink-faint">
            No tools discovered yet
          </p>
          <p className="mt-1 text-[11px] text-ink-faint">
            Click Refresh on a source above to index its tools.
          </p>
        </div>
      ) : grouped.length === 0 && hasActiveFilters ? (
        <div className="rounded-md border border-dashed border-hairline bg-surface-1/40 px-4 py-8 text-center">
          <p className="font-display text-[11px] uppercase tracking-[0.18em] text-ink-faint">
            No matching tools
          </p>
          <p className="mt-1 text-[11px] text-ink-faint">
            Try a different kind or search term.
          </p>
        </div>
      ) : (
        <div className="space-y-8">
          {grouped.map(({ kind, tools }) => (
            <KindGroup key={kind} kind={kind} tools={tools} />
          ))}
        </div>
      )}
    </div>
  );
}
