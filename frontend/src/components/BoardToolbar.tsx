import { Link } from "react-router-dom";
import { useSpaces } from "../hooks/useSpaces";
import { SpaceFilterDropdown } from "./SpaceFilterDropdown";
import { SpaceTag } from "./ui/SpaceTag";
import { StickyToolbar } from "./ui/StickyToolbar";

interface Props {
  spaceId: string | null;
  onSpaceChange: (next: string | null) => void;
  filterLocked?: boolean;
  onNewTask: () => void;
}

export function BoardToolbar({
  spaceId,
  onSpaceChange,
  filterLocked = false,
  onNewTask,
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
        <SpaceFilterDropdown
          value={spaceId}
          onChange={onSpaceChange}
          disabled={filterLocked}
          disabledTooltip="Filter locked to this space"
        />
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
