import { useMemo, useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import { useSpaces, useSpaceTools, useUnadoptTool } from "../hooks/useSpaces";
import { cn } from "../utils/cn";
import { Tabs } from "../components/ui/Tabs";
import { formatRelative } from "../utils/format";
import type { AdoptedTool, AiToolEntry, HookEntry, PermissionEntry } from "../types";
import { ToolDetailPanel } from "../components/ToolDetailPanel";
import { DiscoveryPanel } from "../components/DiscoveryPanel";
import { PluginsPanel } from "../components/PluginsPanel";
import { AdoptedToolTelemetry } from "../components/AdoptedToolTelemetry";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const CATEGORY_ICON: Record<string, string> = {
  agent: "🤖",
  command: "⌘",
  skill: "⚡",
  context: "📖",
};

const KIND_ICON: Record<string, string> = {
  agent: "🤖",
  skill: "⚡",
  command: "⌘",
  hook: "🪝",
};

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function ScopeBadge({ scope }: { scope: "space" | "global" | "plugin" }) {
  return (
    <span
      className={cn(
        "shrink-0 rounded border px-1.5 py-0.5 font-mono text-[9px] uppercase tracking-[0.14em]",
        scope === "space"
          ? "border-accent/20 bg-accent/10 text-accent-bright"
          : "border-hairline bg-surface-2 text-ink-muted",
      )}
    >
      {scope}
    </span>
  );
}

function SectionHeader({ label, count }: { label: string; count: number }) {
  return (
    <div className="mb-3 flex items-baseline gap-2">
      <h2 className="font-display text-[11px] font-semibold uppercase tracking-[0.2em] text-ink-muted">
        {label}
      </h2>
      <span className="font-mono text-[10px] tabular-nums text-ink-faint">
        {String(count).padStart(2, "0")}
      </span>
    </div>
  );
}

function SectionEmptyState({ label, subfolder }: { label: string; subfolder: string }) {
  return (
    <div className="rounded-md border border-dashed border-hairline bg-surface-1/40 px-4 py-8 text-center">
      <p className="font-display text-[11px] uppercase tracking-[0.18em] text-ink-faint">
        No {label.toLowerCase()} configured
      </p>
      <p className="mt-1 text-[11px] text-ink-faint">
        Add files to{" "}
        <code className="font-mono text-[10px]">.claude/{subfolder}/</code>
      </p>
    </div>
  );
}

function ToolCard({
  entry,
  category,
  onClick,
}: {
  entry: AiToolEntry;
  category: string;
  onClick: () => void;
}) {
  return (
    <div
      className="group relative cursor-pointer rounded-md border border-hairline bg-surface-1 p-4 shadow-inset-hairline transition hover:-translate-y-px hover:border-hairline-strong hover:shadow-lift focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/40"
      onClick={onClick}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && onClick()}
    >
      <div className="mb-2 flex items-start justify-between gap-2">
        <div className="flex min-w-0 items-center gap-2">
          <span className="shrink-0 text-[18px] leading-none" aria-hidden>
            {CATEGORY_ICON[category] ?? "📄"}
          </span>
          <span className="truncate font-display text-[13px] font-semibold tracking-[0.04em] text-ink">
            {entry.name}
          </span>
        </div>
        <ScopeBadge scope={entry.scope} />
      </div>
      <p className="line-clamp-2 text-[12px] leading-relaxed text-ink-muted">
        {entry.description ?? (
          <span className="italic text-ink-faint">No description</span>
        )}
      </p>
      <div className="mt-3 flex items-center justify-between gap-2">
        <span className="max-w-[60%] truncate font-mono text-[10px] text-ink-faint">
          {entry.path}
        </span>
        <span className="shrink-0 font-mono text-[10px] text-ink-faint">
          {formatRelative(entry.modified_at)}
        </span>
      </div>
    </div>
  );
}

function ToolGrid({
  entries,
  category,
  label,
  subfolder,
  onToolClick,
}: {
  entries: AiToolEntry[];
  category: string;
  label: string;
  subfolder: string;
  onToolClick: (entry: AiToolEntry) => void;
}) {
  return (
    <section>
      <SectionHeader label={label} count={entries.length} />
      {entries.length === 0 ? (
        <SectionEmptyState label={label} subfolder={subfolder} />
      ) : (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {entries.map((e) => (
            <ToolCard
              key={`${e.scope}:${e.path}`}
              entry={e}
              category={category}
              onClick={() => onToolClick(e)}
            />
          ))}
        </div>
      )}
    </section>
  );
}

function HooksPanel({ hooks }: { hooks: HookEntry[] }) {
  return (
    <div>
      <SectionHeader label="Hooks" count={hooks.length} />
      {hooks.length === 0 ? (
        <SectionEmptyState label="hooks" subfolder=".claude/settings.json → hooks" />
      ) : (
        <div className="overflow-hidden rounded-md border border-hairline bg-surface-1 shadow-inset-hairline">
          {hooks.map((hook, i) => (
            <div
              key={i}
              className="grid grid-cols-[5.5rem_1fr_4rem] items-start gap-3 border-b border-hairline px-4 py-2.5 last:border-b-0 hover:bg-surface-2/40"
            >
              <span className="font-mono text-[10px] uppercase tracking-[0.1em] text-warning">
                {hook.event}
              </span>
              <div className="min-w-0">
                {hook.matcher && (
                  <span className="mb-0.5 mr-1.5 inline-block rounded bg-surface-2 px-1.5 py-0.5 font-mono text-[10px] text-ink-muted">
                    {hook.matcher}
                  </span>
                )}
                <code className="block truncate font-mono text-[11px] text-ink">
                  {hook.command}
                </code>
              </div>
              <ScopeBadge scope={hook.scope} />
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function PermissionsPanel({ permissions }: { permissions: PermissionEntry[] }) {
  return (
    <div>
      <SectionHeader label="Permissions" count={permissions.length} />
      {permissions.length === 0 ? (
        <SectionEmptyState label="permissions" subfolder=".claude/settings.json → permissions" />
      ) : (
        <div className="flex min-h-[4rem] flex-wrap gap-1.5 rounded-md border border-hairline bg-surface-1 p-4 shadow-inset-hairline">
          {permissions.map((p, i) => (
            <span
              key={i}
              className={cn(
                "rounded border px-2 py-0.5 font-mono text-[10px]",
                p.allowed
                  ? "border-accent/20 bg-accent/10 text-accent-bright"
                  : "border-danger/20 bg-danger/10 text-danger",
              )}
              title={p.scope}
            >
              {p.pattern}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Adopted section
// ---------------------------------------------------------------------------

function StatusPill({ status }: { status: AdoptedTool["status"] }) {
  return (
    <span
      className={cn(
        "shrink-0 rounded border px-1.5 py-0.5 font-mono text-[9px] uppercase tracking-[0.14em]",
        status === "pristine" && "border-hairline bg-surface-2 text-ink-muted",
        status === "edited" && "border-amber-400/30 bg-amber-400/10 text-amber-600 dark:text-amber-400",
        status === "evolved" && "border-orange-400/30 bg-orange-400/10 text-orange-600 dark:text-orange-400",
      )}
      data-testid={`status-pill-${status}`}
    >
      {status}
    </span>
  );
}

function sourceLink(sourceUrl: string, sourceSha: string, sourcePath: string): string {
  const base = sourceUrl.replace(/\.git$/, "");
  return `${base}/tree/${sourceSha}/${sourcePath}`;
}

function AdoptedSection({
  adopted,
  spaceId,
}: {
  adopted: AdoptedTool[];
  spaceId: string;
}) {
  const [confirmKey, setConfirmKey] = useState<string | null>(null);
  const unadoptMutation = useUnadoptTool(spaceId);

  function handleUnadoptClick(tool: AdoptedTool) {
    setConfirmKey(`${tool.kind}:${tool.name}`);
  }

  function handleConfirm(tool: AdoptedTool) {
    unadoptMutation.mutate(
      { kind: tool.kind, name: tool.name },
      { onSettled: () => setConfirmKey(null) },
    );
  }

  function handleCancel() {
    setConfirmKey(null);
  }

  return (
    <section>
      <SectionHeader label="Adopted" count={adopted.length} />
      <div className="overflow-hidden rounded-md border border-hairline bg-surface-1 shadow-inset-hairline">
        {adopted.map((tool) => {
          const key = `${tool.kind}:${tool.name}`;
          const isConfirming = confirmKey === key;
          const isRemoving = unadoptMutation.isPending && confirmKey === key;
          const icon = KIND_ICON[tool.kind] ?? "📄";
          const link = sourceLink(tool.source_url, tool.source_sha, tool.source_path);

          return (
            <div
              key={key}
              className="border-b border-hairline px-4 py-3 last:border-b-0 hover:bg-surface-2/40"
            >
              {/* Top row: icon + name/badges + unadopt */}
              <div className="flex items-center gap-3">
                <span className="shrink-0 text-[16px] leading-none" aria-hidden>
                  {icon}
                </span>
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-display text-[13px] font-semibold tracking-[0.04em] text-ink">
                      {tool.name}
                    </span>
                    <StatusPill status={tool.status} />
                    <span className="rounded border border-hairline bg-surface-2 px-1.5 py-0.5 font-mono text-[9px] uppercase tracking-[0.1em] text-ink-faint">
                      {tool.kind}
                    </span>
                  </div>
                  <div className="mt-0.5 flex items-center gap-2">
                    <span className="font-mono text-[10px] text-ink-faint">{tool.source_slug}</span>
                    <a
                      href={link}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="font-mono text-[10px] text-accent-bright hover:underline"
                      title={`View at ${tool.source_sha.slice(0, 7)}`}
                    >
                      {tool.source_sha.slice(0, 7)}
                    </a>
                  </div>
                </div>
                <div className="flex shrink-0 items-center gap-2">
                  {isConfirming ? (
                    <>
                      <span className="font-display text-[11px] text-ink-muted">Remove?</span>
                      <button
                        type="button"
                        onClick={() => handleConfirm(tool)}
                        disabled={isRemoving}
                        className="rounded border border-danger/30 bg-danger/10 px-2.5 py-1 font-display text-[11px] font-medium text-danger transition hover:bg-danger/20 disabled:opacity-60"
                      >
                        {isRemoving ? "Removing…" : "Yes, remove"}
                      </button>
                      <button
                        type="button"
                        onClick={handleCancel}
                        className="rounded border border-hairline px-2.5 py-1 font-display text-[11px] font-medium text-ink-muted transition hover:text-ink"
                      >
                        Cancel
                      </button>
                    </>
                  ) : (
                    <button
                      type="button"
                      onClick={() => handleUnadoptClick(tool)}
                      aria-label={`Unadopt ${tool.name}`}
                      className="rounded border border-hairline px-2.5 py-1 font-display text-[11px] font-medium text-ink-muted transition hover:border-danger/30 hover:bg-danger/5 hover:text-danger"
                    >
                      Unadopt
                    </button>
                  )}
                </div>
              </div>

              {/* Telemetry strip (below main row, indented to align with name) */}
              <div className="mt-1 pl-7">
                <AdoptedToolTelemetry
                  spaceId={spaceId}
                  kind={tool.kind}
                  name={tool.name}
                />
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

type Tab = "installed" | "discover" | "plugins";

const TABS: { id: Tab; label: string }[] = [
  { id: "installed", label: "Installed" },
  { id: "discover", label: "Discover" },
  { id: "plugins", label: "Plugins" },
];

export function SpaceToolsPage() {
  const { spaceId: routeSpaceId } = useParams<{ spaceId?: string }>();
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState<Tab>("installed");
  const { data: spacesData, isLoading: spacesLoading } = useSpaces();
  const spaces = spacesData?.spaces ?? [];

  // Determine active space: from URL param, or from a selector on the /tools route
  const activeSpaceId = routeSpaceId ?? null;

  const { data: tools, isLoading: toolsLoading, isError: toolsError } = useSpaceTools(activeSpaceId);

  const [searchParams, setSearchParams] = useSearchParams();

  const toolName = searchParams.get("tool");
  const toolCategory = searchParams.get("category") as "agent" | "command" | "skill" | "context" | null;
  const toolScope = searchParams.get("scope") as "space" | "global" | null;

  const selectedTool = useMemo(() => {
    if (!tools || !toolName || !toolCategory || !toolScope) return null;
    const allTools = [
      ...tools.agents.map((e) => ({ ...e, category: "agent" as const })),
      ...tools.commands.map((e) => ({ ...e, category: "command" as const })),
      ...tools.skills.map((e) => ({ ...e, category: "skill" as const })),
      ...tools.context_files.map((e) => ({ ...e, category: "context" as const })),
    ];
    return allTools.find((e) => e.name === toolName && e.category === toolCategory && e.scope === toolScope) ?? null;
  }, [tools, toolName, toolCategory, toolScope]);

  // Set of adopted tool keys for the DiscoveryPanel
  const adoptedKeys = useMemo(() => {
    const s = new Set<string>();
    (tools?.adopted ?? []).forEach((a) => s.add(`${a.kind}:${a.name}`));
    return s;
  }, [tools?.adopted]);

  function handleToolClick(
    entry: AiToolEntry,
    category: "agent" | "command" | "skill" | "context",
  ) {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      next.set("tool", entry.name);
      next.set("category", category);
      next.set("scope", entry.scope);
      return next;
    });
  }

  function handleClose() {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      next.delete("tool");
      next.delete("category");
      next.delete("scope");
      return next;
    });
  }

  function handleSpaceChange(e: React.ChangeEvent<HTMLSelectElement>) {
    const val = e.target.value;
    if (val) {
      navigate(`/spaces/${val}/tools`);
    } else {
      navigate("/tools");
    }
  }

  const activeSpace = spaces.find((s) => s.id === activeSpaceId) ?? null;

  const totalCount =
    (tools?.agents.length ?? 0) +
    (tools?.commands.length ?? 0) +
    (tools?.skills.length ?? 0) +
    (tools?.context_files.length ?? 0);

  return (
    <div className="mx-auto max-w-[1280px] space-y-8 p-6 lg:p-8">
      {/* Page header */}
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-ink-faint">
            Cronos · AI Tools
          </p>
          <h1 className="font-display text-[22px] font-semibold uppercase tracking-[0.14em] text-ink">
            {activeSpace ? activeSpace.name : "Inventory"}
          </h1>
        </div>

        {/* Space selector (only relevant for Installed tab; hidden for Discover and Plugins) */}
        {activeTab === "installed" && (
          <div className="flex items-center gap-2">
            {spacesLoading ? (
              <span className="text-[12px] text-ink-muted">Loading…</span>
            ) : (
              <select
                value={activeSpaceId ?? ""}
                onChange={handleSpaceChange}
                className="h-9 rounded border border-hairline-strong bg-surface-1 px-3 text-[12px] text-ink transition hover:border-accent focus:border-accent focus:outline-none"
              >
                <option value="">Select a space…</option>
                {spaces.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.icon ? `${s.icon} ` : ""}{s.name}
                  </option>
                ))}
              </select>
            )}
          </div>
        )}
      </header>

      {/* Tab switcher */}
      <Tabs
        items={TABS.map((t) => ({ value: t.id, label: t.label }))}
        value={activeTab}
        onChange={(v) => setActiveTab(v as Tab)}
      />

      {/* Tool detail panel */}
      {selectedTool && activeSpaceId && (
        <ToolDetailPanel
          tool={selectedTool}
          spaceId={activeSpaceId}
          onClose={handleClose}
        />
      )}

      {/* Discover tab */}
      {activeTab === "discover" && (
        <DiscoveryPanel spaceId={activeSpaceId} adoptedKeys={adoptedKeys} />
      )}

      {/* Plugins tab */}
      {activeTab === "plugins" && <PluginsPanel />}

      {/* Installed tab */}
      {activeTab === "installed" && (
        <>
          {/* No space selected */}
          {!activeSpaceId && (
            <div className="rounded-lg border border-dashed border-hairline-strong bg-surface-1 p-10 shadow-inset-hairline">
              <div className="mx-auto max-w-sm text-center">
                <p className="font-display text-[13px] font-semibold uppercase tracking-[0.14em] text-ink">
                  Select a space
                </p>
                <p className="mt-2 text-[12px] text-ink-muted">
                  Choose a space above to view its available AI tools — agents, commands, skills, context files, hooks, and permissions.
                </p>
              </div>
            </div>
          )}

          {/* Loading */}
          {activeSpaceId && toolsLoading && (
            <p className="text-[12px] text-ink-muted">Loading tools…</p>
          )}

          {/* Error */}
          {activeSpaceId && toolsError && (
            <div className="rounded-md border border-danger/20 bg-danger/5 px-4 py-3 text-[12px] text-danger">
              Failed to load tools for this space.
            </div>
          )}

          {/* Content */}
          {activeSpaceId && tools && (
            <>
              {/* Summary stats bar */}
              <div className="flex flex-wrap items-center gap-2">
                {[
                  { label: "Agents", count: tools.agents.length },
                  { label: "Commands", count: tools.commands.length },
                  { label: "Skills", count: tools.skills.length },
                  { label: "Context", count: tools.context_files.length },
                ].map(({ label, count }) => (
                  <div
                    key={label}
                    className="flex items-center gap-1.5 rounded border border-hairline bg-surface-1 px-3 py-1.5 shadow-inset-hairline"
                  >
                    <span className="font-mono text-[16px] font-semibold tabular-nums text-ink">
                      {String(count).padStart(2, "0")}
                    </span>
                    <span className="font-display text-[10px] uppercase tracking-[0.18em] text-ink-faint">
                      {label}
                    </span>
                  </div>
                ))}
                {totalCount === 0 && (
                  <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-ink-faint">
                    No tools found
                  </span>
                )}
                {tools.has_claude_md && (
                  <div className="flex items-center gap-1.5 rounded border border-hairline bg-surface-2 px-3 py-1.5">
                    <span className="font-display text-[10px] uppercase tracking-[0.18em] text-ink-muted">
                      CLAUDE.md ✓
                    </span>
                  </div>
                )}
              </div>

              {/* Adopted section — above the regular tool grids */}
              {tools.adopted.length > 0 && (
                <AdoptedSection adopted={tools.adopted} spaceId={activeSpaceId} />
              )}

              {/* Artifact sections */}
              <ToolGrid
                entries={tools.agents}
                category="agent"
                label="Agents"
                subfolder="agents"
                onToolClick={(e) => handleToolClick(e, "agent")}
              />
              <ToolGrid
                entries={tools.commands}
                category="command"
                label="Commands"
                subfolder="commands"
                onToolClick={(e) => handleToolClick(e, "command")}
              />
              <ToolGrid
                entries={tools.skills}
                category="skill"
                label="Skills"
                subfolder="skills"
                onToolClick={(e) => handleToolClick(e, "skill")}
              />
              <ToolGrid
                entries={tools.context_files}
                category="context"
                label="Context"
                subfolder="context"
                onToolClick={(e) => handleToolClick(e, "context")}
              />

              {/* Settings */}
              <section>
                <div className="mb-3 flex items-baseline gap-2">
                  <h2 className="font-display text-[11px] font-semibold uppercase tracking-[0.2em] text-ink-muted">
                    Settings
                  </h2>
                </div>
                <div className="grid gap-6 md:grid-cols-2">
                  <HooksPanel hooks={tools.hooks} />
                  <PermissionsPanel permissions={tools.permissions} />
                </div>
              </section>
            </>
          )}
        </>
      )}
    </div>
  );
}
