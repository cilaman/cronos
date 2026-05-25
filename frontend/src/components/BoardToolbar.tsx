import { Link } from "react-router-dom";
import { useSpaces } from "../hooks/useSpaces";
import type { BoardSortMode } from "../lib/storage";
import { SpaceFilterDropdown } from "./SpaceFilterDropdown";
import { ViewPicker } from "./ViewPicker";
import { SpaceTag } from "./ui/SpaceTag";
import { StickyToolbar } from "./ui/StickyToolbar";

interface Props {
  spaceId: string | null;
  onSpaceChange: (next: string | null) => void;
  filterLocked?: boolean;
  onNewTask: () => void;
  compact: boolean;
  onCompactToggle: () => void;
  sortMode: BoardSortMode;
  onSortModeToggle: () => void;
  /** Current view ID (null = default view). Only shown when spaceId is set. */
  viewId?: string | null;
  onViewChange?: (viewId: string | null) => void;
  onManageViews?: () => void;
  /** When true, child tasks of expanded goals are hidden from their lanes. */
  hideExpandedChildren?: boolean;
  onHideExpandedChildrenToggle?: () => void;
}

export function BoardToolbar({
  spaceId,
  onSpaceChange,
  filterLocked = false,
  onNewTask,
  compact,
  onCompactToggle,
  sortMode,
  onSortModeToggle,
  viewId = null,
  onViewChange,
  onManageViews,
  hideExpandedChildren = false,
  onHideExpandedChildrenToggle,
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
            <Link
              to={`/spaces/${active.id}/settings`}
              className="rounded px-2 py-1 font-mono text-[10px] uppercase tracking-[0.14em] text-ink-muted transition hover:bg-surface-2 hover:text-accent-bright"
            >
              Settings
            </Link>
          </>
        ) : (
          <h1 className="font-display text-[13px] font-semibold uppercase tracking-[0.18em] text-ink">
            All spaces
          </h1>
        )}
      </div>
      <div className="flex shrink-0 items-center gap-2">
        {spaceId && onViewChange && (
          <ViewPicker
            spaceId={spaceId}
            viewId={viewId}
            onChange={onViewChange}
            onManageViews={onManageViews ?? (() => {})}
          />
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
          <span className="hidden sm:inline">
            {sortMode === "priority" ? "Priority" : "Priority"}
          </span>
        </button>
        {onHideExpandedChildrenToggle && (
          <button
            type="button"
            onClick={onHideExpandedChildrenToggle}
            aria-pressed={hideExpandedChildren}
            title={hideExpandedChildren ? "Show expanded children in lanes" : "Hide expanded goal's children from lanes"}
            className={[
              "flex h-8 items-center gap-1.5 rounded border px-2.5 font-display text-[10px] uppercase tracking-[0.14em] transition focus:outline-none focus-visible:ring-1 focus-visible:ring-accent",
              hideExpandedChildren
                ? "border-accent bg-accent/10 text-accent-bright hover:bg-accent/20"
                : "border-hairline bg-surface-2 text-ink-muted hover:border-hairline-strong hover:bg-surface-3 hover:text-ink",
            ].join(" ")}
          >
            <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <path d="M2 3h8M2 6h5M2 9h3"/>
              <path d="M9 7v4M7 9l2 2 2-2" strokeWidth="1.25"/>
            </svg>
            <span className="hidden sm:inline">Focus</span>
          </button>
        )}
        <button
          type="button"
          onClick={onCompactToggle}
          aria-label={compact ? "Switch to full cards" : "Switch to minimal cards"}
          title={compact ? "Full cards" : "Minimal cards"}
          className="flex h-8 w-8 items-center justify-center rounded border border-hairline bg-surface-2 text-ink-muted transition hover:border-hairline-strong hover:bg-surface-3 hover:text-ink focus:outline-none focus-visible:ring-1 focus-visible:ring-accent"
        >
          {compact ? (
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" aria-hidden="true">
              <rect x="1" y="1" width="12" height="4" rx="1" fill="currentColor" stroke="none" opacity="0.25"/>
              <line x1="1" y1="2.5" x2="13" y2="2.5"/>
              <line x1="1" y1="5" x2="13" y2="5"/>
              <line x1="1" y1="7.5" x2="13" y2="7.5"/>
              <line x1="1" y1="10" x2="13" y2="10"/>
              <line x1="1" y1="12.5" x2="13" y2="12.5"/>
            </svg>
          ) : (
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" aria-hidden="true">
              <rect x="1" y="1" width="12" height="5.5" rx="1"/>
              <line x1="3" y1="9" x2="11" y2="9"/>
              <line x1="3" y1="11.5" x2="9" y2="11.5"/>
            </svg>
          )}
        </button>
        <button
          type="button"
          onClick={onNewTask}
          aria-label="New task"
          className="flex h-8 items-center gap-1.5 rounded border border-accent bg-accent px-3 text-[12px] font-medium text-canvas transition hover:bg-accent-bright"
        >
          <span aria-hidden className="text-base leading-none">＋</span>
          <span className="hidden sm:inline">New task</span>
        </button>
      </div>
    </StickyToolbar>
  );
}
