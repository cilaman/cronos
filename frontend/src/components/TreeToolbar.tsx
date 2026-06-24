import { Link } from "react-router-dom";
import { useSpaces } from "../hooks/useSpaces";
import type { BoardSortMode } from "../lib/storage";
import { SpaceFilterDropdown } from "./SpaceFilterDropdown";
import { SpaceTag } from "./ui/SpaceTag";
import { StickyToolbar } from "./ui/StickyToolbar";

export type TreeViewMode = "tree" | "dag";

interface Props {
  spaceId: string | null;
  onSpaceChange: (next: string | null) => void;
  filterLocked?: boolean;
  sortMode: BoardSortMode;
  onSortModeToggle: () => void;
  onExpandAll: () => void;
  onCollapseAll: () => void;
  boardLink: string;
  viewMode?: TreeViewMode;
  onViewModeToggle?: () => void;
}

export function TreeToolbar({
  spaceId,
  onSpaceChange,
  filterLocked = false,
  sortMode,
  onSortModeToggle,
  onExpandAll,
  onCollapseAll,
  boardLink,
  viewMode = "tree",
  onViewModeToggle,
}: Props) {
  const { data } = useSpaces();
  const active = spaceId ? data?.spaces.find((s) => s.id === spaceId) ?? null : null;

  return (
    <StickyToolbar>
      <div className="flex min-w-0 items-center gap-3">
        {active ? (
          <>
            <SpaceTag color={active.color} icon={active.icon} size="md" />
            <h1 className="truncate font-display text-[13px] font-semibold uppercase tracking-[0.18em] text-ink">
              {active.name}
            </h1>
          </>
        ) : (
          <h1 className="font-display text-[13px] font-semibold uppercase tracking-[0.18em] text-ink">
            Tree
          </h1>
        )}
        <Link
          to={boardLink}
          className="rounded px-2 py-1 font-mono text-[10px] uppercase tracking-[0.14em] text-ink-muted transition hover:bg-surface-2 hover:text-accent-bright"
        >
          Board view
        </Link>
      </div>

      <div className="flex shrink-0 items-center gap-2">
        {onViewModeToggle && (
          <div className="flex items-center rounded border border-hairline bg-surface-2">
            <button
              type="button"
              onClick={viewMode === "dag" ? onViewModeToggle : undefined}
              aria-pressed={viewMode === "tree"}
              aria-label="Tree view"
              title="Tree view"
              className={[
                "flex h-8 items-center px-2.5 font-display text-[10px] uppercase tracking-[0.14em] transition focus:outline-none focus-visible:ring-1 focus-visible:ring-accent rounded-l",
                viewMode === "tree"
                  ? "bg-accent/10 text-accent-bright"
                  : "text-ink-muted hover:bg-surface-3 hover:text-ink",
              ].join(" ")}
            >
              Tree
            </button>
            <span className="h-4 w-px bg-hairline" aria-hidden="true" />
            <button
              type="button"
              onClick={viewMode === "tree" ? onViewModeToggle : undefined}
              aria-pressed={viewMode === "dag"}
              aria-label="DAG view"
              title="DAG view"
              className={[
                "flex h-8 items-center px-2.5 font-display text-[10px] uppercase tracking-[0.14em] transition focus:outline-none focus-visible:ring-1 focus-visible:ring-accent rounded-r",
                viewMode === "dag"
                  ? "bg-accent/10 text-accent-bright"
                  : "text-ink-muted hover:bg-surface-3 hover:text-ink",
              ].join(" ")}
            >
              DAG
            </button>
          </div>
        )}

        <SpaceFilterDropdown
          value={spaceId}
          onChange={onSpaceChange}
          disabled={filterLocked}
          disabledTooltip="Filter locked to this space"
        />

        <button
          type="button"
          onClick={onSortModeToggle}
          aria-label={sortMode === "priority" ? "Switch to manual order" : "Sort by priority"}
          title={sortMode === "priority" ? "Manual order" : "Sort by priority"}
          className={[
            "flex h-8 items-center gap-1.5 rounded border px-2.5 font-display text-[10px] uppercase tracking-[0.14em] transition focus:outline-none focus-visible:ring-1 focus-visible:ring-accent",
            sortMode === "priority"
              ? "border-accent bg-accent/10 text-accent-bright hover:bg-accent/20"
              : "border-hairline bg-surface-2 text-ink-muted hover:border-hairline-strong hover:bg-surface-3 hover:text-ink",
          ].join(" ")}
        >
          <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" aria-hidden="true">
            <line x1="1" y1="3" x2="11" y2="3"/>
            <line x1="1" y1="6" x2="8" y2="6"/>
            <line x1="1" y1="9" x2="5" y2="9"/>
          </svg>
          <span className="hidden sm:inline">Priority</span>
        </button>

        <div className="flex items-center rounded border border-hairline bg-surface-2">
          <button
            type="button"
            onClick={onExpandAll}
            aria-label="Expand all"
            title="Expand all"
            className="flex h-8 items-center gap-1 rounded-l px-2.5 font-display text-[10px] uppercase tracking-[0.14em] text-ink-muted transition hover:bg-surface-3 hover:text-ink focus:outline-none focus-visible:ring-1 focus-visible:ring-accent"
          >
            <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <path d="M3 5l3 3 3-3"/>
              <line x1="1" y1="2" x2="11" y2="2"/>
            </svg>
            <span className="hidden sm:inline">Expand</span>
          </button>
          <span className="h-4 w-px bg-hairline" aria-hidden="true" />
          <button
            type="button"
            onClick={onCollapseAll}
            aria-label="Collapse all"
            title="Collapse all"
            className="flex h-8 items-center gap-1 rounded-r px-2.5 font-display text-[10px] uppercase tracking-[0.14em] text-ink-muted transition hover:bg-surface-3 hover:text-ink focus:outline-none focus-visible:ring-1 focus-visible:ring-accent"
          >
            <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <path d="M3 7l3-3 3 3"/>
              <line x1="1" y1="10" x2="11" y2="10"/>
            </svg>
            <span className="hidden sm:inline">Collapse</span>
          </button>
        </div>
      </div>
    </StickyToolbar>
  );
}
