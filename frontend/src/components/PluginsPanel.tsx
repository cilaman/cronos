import { useState } from "react";
import {
  usePlugins,
  useInstallPlugin,
  useUninstallPlugin,
  useEnablePlugin,
  useDisablePlugin,
  useAddMarketplace,
  useRemoveMarketplace,
} from "../hooks/usePlugins";
import type { PluginEntry, MarketplacePluginEntry, MarketplaceEntry } from "../types";

// ---------------------------------------------------------------------------
// Icons
// ---------------------------------------------------------------------------

const KIND_ICON: Record<string, string> = {
  agent: "🤖",
  skill: "⚡",
  command: "⌘",
};

// ---------------------------------------------------------------------------
// Local section layout helpers (NOT imported from DiscoveryPanel — those
// helpers are module-local in DiscoveryPanel and not exported)
// ---------------------------------------------------------------------------

function SectionHeader({ title, count }: { title: string; count: number }) {
  return (
    <div className="mb-3 flex items-baseline gap-2">
      <h2 className="font-display text-[11px] font-semibold uppercase tracking-[0.2em] text-ink-muted">
        {title}
      </h2>
      <span className="font-mono text-[10px] tabular-nums text-ink-faint">
        {String(count).padStart(2, "0")}
      </span>
    </div>
  );
}

function SectionEmptyState({ message }: { message: string }) {
  return (
    <div className="rounded-md border border-dashed border-hairline bg-surface-1/40 px-4 py-8 text-center">
      <p className="font-display text-[11px] uppercase tracking-[0.18em] text-ink-faint">
        {message}
      </p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// InstalledPluginCard
// ---------------------------------------------------------------------------

function InstalledPluginCard({ entry }: { entry: PluginEntry }) {
  const [expanded, setExpanded] = useState(false);
  const enableMutation = useEnablePlugin();
  const disableMutation = useDisablePlugin();
  const uninstallMutation = useUninstallPlugin();

  const togglePending = enableMutation.isPending || disableMutation.isPending;

  function handleToggle() {
    if (togglePending) return;
    if (entry.enabled) {
      disableMutation.mutate(entry.id);
    } else {
      enableMutation.mutate(entry.id);
    }
  }

  function handleUninstall() {
    if (window.confirm(`Uninstall plugin "${entry.name}"? This cannot be undone.`)) {
      uninstallMutation.mutate(entry.id);
    }
  }

  return (
    <div className="rounded-md border border-hairline bg-surface-1 p-4 shadow-inset-hairline">
      <div className="mb-2 flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <p className="truncate font-display text-[13px] font-semibold tracking-[0.04em] text-ink">
            {entry.name}
          </p>
          {entry.marketplace && (
            <p className="font-mono text-[10px] text-ink-faint">{entry.marketplace}</p>
          )}
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <button
            type="button"
            onClick={handleToggle}
            disabled={togglePending}
            aria-pressed={entry.enabled}
            aria-label={entry.enabled ? `Disable ${entry.name}` : `Enable ${entry.name}`}
            className={`rounded border px-2 py-0.5 font-display text-[10px] font-medium uppercase tracking-[0.1em] transition disabled:cursor-not-allowed disabled:opacity-50 ${
              entry.enabled
                ? "border-accent/30 bg-accent/10 text-accent-bright hover:bg-accent/20"
                : "border-hairline bg-surface-2 text-ink-muted hover:border-hairline-strong"
            }`}
          >
            {entry.enabled ? "Enabled" : "Disabled"}
          </button>
          <button
            type="button"
            onClick={handleUninstall}
            disabled={uninstallMutation.isPending}
            aria-label={`Uninstall ${entry.name}`}
            className="rounded border border-hairline px-2 py-0.5 font-display text-[10px] font-medium uppercase tracking-[0.1em] text-ink-muted transition hover:border-danger/40 hover:bg-danger/10 hover:text-danger disabled:cursor-not-allowed disabled:opacity-50"
          >
            {uninstallMutation.isPending ? "Removing…" : "Uninstall"}
          </button>
        </div>
      </div>

      <div className="mb-2 flex flex-wrap gap-2">
        {entry.version && (
          <span className="rounded border border-hairline bg-surface-2 px-1.5 py-0.5 font-mono text-[9px] text-ink-muted">
            v{entry.version}
          </span>
        )}
        <span className="rounded border border-hairline bg-surface-2 px-1.5 py-0.5 font-mono text-[9px] uppercase tracking-[0.1em] text-ink-faint">
          {entry.scope}
        </span>
      </div>

      {(entry.installPath || entry.installedAt || !entry.marketplace) && (
        <div className="mb-2 space-y-0.5">
          {!entry.marketplace && (
            <p className="font-mono text-[10px] italic text-ink-faint/60">source unknown</p>
          )}
          {entry.installPath && (
            <p className="truncate font-mono text-[10px] text-ink-faint" title={entry.installPath}>
              <span className="text-ink-muted">path:</span> {entry.installPath}
            </p>
          )}
          {entry.installedAt && (
            <p className="font-mono text-[10px] text-ink-faint">
              <span className="text-ink-muted">installed:</span>{" "}
              {new Date(entry.installedAt).toLocaleDateString()}
            </p>
          )}
        </div>
      )}

      {entry.components.length > 0 && (
        <div>
          <button
            type="button"
            onClick={() => setExpanded((v) => !v)}
            aria-expanded={expanded}
            aria-label={`${expanded ? "Collapse" : "Expand"} components for ${entry.name}`}
            className="flex items-center gap-1 font-mono text-[10px] text-ink-muted transition hover:text-ink"
          >
            <span className={`inline-block transition-transform ${expanded ? "rotate-90" : ""}`} aria-hidden>
              ▶
            </span>
            {entry.components.length} component{entry.components.length !== 1 ? "s" : ""}
          </button>
          {expanded && (
            <ul className="mt-2 space-y-1 pl-4" role="list">
              {entry.components.map((comp, i) => (
                <li key={i} className="flex items-center gap-2">
                  <span aria-hidden className="shrink-0 text-[13px]">{KIND_ICON[comp.kind] ?? "📄"}</span>
                  <span className="font-mono text-[11px] text-ink-muted">{comp.name}</span>
                  <span className="font-mono text-[9px] uppercase tracking-[0.1em] text-ink-faint">{comp.kind}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// AvailablePluginCard
// ---------------------------------------------------------------------------

function AvailablePluginCard({ entry }: { entry: MarketplacePluginEntry }) {
  const installMutation = useInstallPlugin();
  return (
    <div className="rounded-md border border-hairline bg-surface-1 p-4 shadow-inset-hairline transition hover:-translate-y-px hover:border-hairline-strong hover:shadow-lift">
      <div className="mb-2 flex items-start justify-between gap-2">
        <div className="min-w-0 flex-1">
          <p className="truncate font-display text-[13px] font-semibold tracking-[0.04em] text-ink">{entry.name}</p>
          {entry.marketplaceName && (
            <p className="font-mono text-[10px] text-ink-faint">{entry.marketplaceName}</p>
          )}
        </div>
        <button
          type="button"
          onClick={() => installMutation.mutate({ pluginId: entry.pluginId })}
          disabled={installMutation.isPending}
          aria-label={`Install ${entry.name}`}
          className="shrink-0 rounded border border-accent/30 bg-accent/10 px-2.5 py-1 font-display text-[11px] font-medium text-accent-bright transition hover:bg-accent/20 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {installMutation.isPending ? "Installing…" : "Install"}
        </button>
      </div>
      {entry.description && (
        <p className="line-clamp-2 text-[12px] leading-relaxed text-ink-muted">{entry.description}</p>
      )}
      <div className="mt-2 flex items-center justify-between gap-2">
        {entry.source && (
          <p className="truncate font-mono text-[10px] text-ink-faint">{entry.source}</p>
        )}
        <span className="ml-auto shrink-0 font-mono text-[10px] text-ink-faint">
          {entry.installCount.toLocaleString()} installs
        </span>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// MarketplaceRow
// ---------------------------------------------------------------------------

function MarketplaceRow({ entry }: { entry: MarketplaceEntry }) {
  const removeMutation = useRemoveMarketplace();
  return (
    <div className="flex items-center justify-between gap-3 border-b border-hairline px-4 py-2.5 last:border-b-0">
      <div className="min-w-0 flex-1">
        <p className="truncate font-display text-[12px] font-medium text-ink">{entry.name}</p>
        <p className="truncate font-mono text-[10px] text-ink-faint">{entry.source}</p>
      </div>
      <button
        type="button"
        onClick={() => removeMutation.mutate(entry.name)}
        disabled={removeMutation.isPending}
        aria-label={`Remove marketplace ${entry.name}`}
        className="shrink-0 rounded border border-hairline px-2 py-0.5 font-display text-[10px] font-medium uppercase tracking-[0.1em] text-ink-muted transition hover:border-danger/40 hover:bg-danger/10 hover:text-danger disabled:cursor-not-allowed disabled:opacity-50"
      >
        {removeMutation.isPending ? "Removing…" : "Remove"}
      </button>
    </div>
  );
}

// ---------------------------------------------------------------------------
// AddMarketplaceForm
// ---------------------------------------------------------------------------

function AddMarketplaceForm() {
  const [url, setUrl] = useState("");
  const addMutation = useAddMarketplace();

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const trimmed = url.trim();
    if (!trimmed) return;
    addMutation.mutate(trimmed, { onSuccess: () => setUrl("") });
  }

  return (
    <form onSubmit={handleSubmit} className="mt-3 flex gap-2">
      <label htmlFor="marketplace-url" className="sr-only">Marketplace source URL</label>
      <input
        id="marketplace-url"
        type="url"
        value={url}
        onChange={(e) => setUrl(e.target.value)}
        placeholder="https://marketplace.example.com"
        required
        className="h-8 min-w-0 flex-1 rounded border border-hairline-strong bg-surface-1 px-3 text-[12px] text-ink placeholder:text-ink-faint transition hover:border-accent focus:border-accent focus:outline-none"
      />
      <button
        type="submit"
        disabled={addMutation.isPending || !url.trim()}
        className="shrink-0 rounded border border-accent/30 bg-accent/10 px-3 py-1 font-display text-[11px] font-medium text-accent-bright transition hover:bg-accent/20 disabled:cursor-not-allowed disabled:opacity-50"
      >
        {addMutation.isPending ? "Adding…" : "Add"}
      </button>
    </form>
  );
}

// ---------------------------------------------------------------------------
// PluginsPanel — public export
// ---------------------------------------------------------------------------

export function PluginsPanel() {
  const { data, isLoading } = usePlugins();

  if (isLoading) {
    return <p className="text-[12px] text-ink-muted">Loading plugins…</p>;
  }

  const installed = data?.installed ?? [];
  const available = data?.available ?? [];
  const marketplaces = data?.marketplaces ?? [];

  return (
    <div className="space-y-8">
      {/* Installed */}
      <section>
        <SectionHeader title="Installed" count={installed.length} />
        {installed.length === 0 ? (
          <SectionEmptyState message="No plugins installed" />
        ) : (
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {installed.map((entry) => (
              <InstalledPluginCard key={entry.id} entry={entry} />
            ))}
          </div>
        )}
      </section>

      {/* Available */}
      <section>
        <SectionHeader title="Available" count={available.length} />
        {available.length === 0 ? (
          <SectionEmptyState message="No plugins available" />
        ) : (
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {available.map((entry) => (
              <AvailablePluginCard key={entry.pluginId} entry={entry} />
            ))}
          </div>
        )}
      </section>

      {/* Marketplaces */}
      <section>
        <SectionHeader title="Marketplaces" count={marketplaces.length} />
        {marketplaces.length === 0 ? (
          <SectionEmptyState message="No marketplaces configured" />
        ) : (
          <div className="overflow-hidden rounded-md border border-hairline bg-surface-1 shadow-inset-hairline">
            {marketplaces.map((entry) => (
              <MarketplaceRow key={entry.name} entry={entry} />
            ))}
          </div>
        )}
        <AddMarketplaceForm />
      </section>
    </div>
  );
}
