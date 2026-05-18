import { NavLink } from "react-router-dom";
import { cn } from "../utils/cn";
import { useSpaces } from "../hooks/useSpaces";
import type { SpaceSummary } from "../types";
import { ThemeToggle } from "./ThemeToggle";

const primaryNavLinkClasses = ({ isActive }: { isActive: boolean }) =>
  cn(
    "group relative flex h-9 items-center gap-2 rounded px-3 font-display text-[11px] font-semibold uppercase tracking-[0.18em] transition",
    isActive
      ? "bg-surface-2 text-ink shadow-inset-hairline"
      : "text-ink-muted hover:bg-surface-2/60 hover:text-ink",
  );

function ActiveStrip({ color }: { color?: string }) {
  return (
    <span
      aria-hidden
      className="absolute inset-y-1 left-0 w-[2px] rounded"
      style={{ backgroundColor: color ?? "var(--color-accent)" }}
    />
  );
}

function SpaceRow({ space, onClose }: { space: SpaceSummary; onClose?: () => void }) {
  const open = (space.task_counts.active ?? 0) + (space.task_counts.waiting ?? 0);
  return (
    <NavLink
      to={`/spaces/${space.id}`}
      onClick={onClose}
      className={({ isActive }) =>
        cn(
          "group relative flex h-8 items-center gap-2 rounded px-3 text-[12px] transition",
          isActive
            ? "bg-surface-2 text-ink shadow-inset-hairline"
            : "text-ink-muted hover:bg-surface-2/60 hover:text-ink",
        )
      }
    >
      {({ isActive }) => (
        <>
          {isActive && <ActiveStrip color={space.color} />}
          <span
            aria-hidden
            className="h-2 w-2 shrink-0 rounded-sm"
            style={{ backgroundColor: space.color }}
          />
          <span aria-hidden className="shrink-0 text-[13px] leading-none">
            {space.icon ?? "·"}
          </span>
          <span className="min-w-0 flex-1 truncate">{space.name}</span>
          {open > 0 && (
            <span className="font-mono text-[10px] tabular-nums text-ink-faint">
              {String(open).padStart(2, "0")}
            </span>
          )}
        </>
      )}
    </NavLink>
  );
}

interface Props {
  onClose?: () => void;
}

export function Sidebar({ onClose }: Props) {
  const { data } = useSpaces();
  const spaces = data?.spaces ?? [];

  return (
    <aside className="flex h-full w-56 shrink-0 flex-col border-r border-hairline bg-surface-1">
      <div className="flex h-14 items-center justify-between gap-2 border-b border-hairline px-4">
        <div className="flex items-center gap-2">
          <span
            aria-hidden
            className="h-2 w-2 rounded-full bg-accent-bright shadow-accent-glow"
          />
          <span className="font-display text-sm font-semibold uppercase tracking-[0.22em] text-ink">
            Cronos
          </span>
        </div>
        {onClose && (
          <button
            type="button"
            onClick={onClose}
            aria-label="Close menu"
            className="rounded p-1 text-ink-muted transition hover:bg-surface-2 hover:text-ink lg:hidden"
          >
            ✕
          </button>
        )}
      </div>

      <nav className="flex flex-col gap-1 px-2 py-3">
        <NavLink to="/" end className={primaryNavLinkClasses} onClick={onClose}>
          {({ isActive }) => (
            <>
              {isActive && <ActiveStrip />}
              Dashboard
            </>
          )}
        </NavLink>
        <NavLink to="/board" className={primaryNavLinkClasses} onClick={onClose}>
          {({ isActive }) => (
            <>
              {isActive && <ActiveStrip />}
              Board
            </>
          )}
        </NavLink>
        <NavLink to="/archived" className={primaryNavLinkClasses} onClick={onClose}>
          {({ isActive }) => (
            <>
              {isActive && <ActiveStrip />}
              Archived
            </>
          )}
        </NavLink>
        <NavLink to="/tools" className={primaryNavLinkClasses} onClick={onClose}>
          {({ isActive }) => (
            <>
              {isActive && <ActiveStrip />}
              AI Tools
            </>
          )}
        </NavLink>
        <NavLink to="/stats" className={primaryNavLinkClasses} onClick={onClose}>
          {({ isActive }) => (
            <>
              {isActive && <ActiveStrip />}
              Stats
            </>
          )}
        </NavLink>
        <NavLink to="/tests" className={primaryNavLinkClasses} onClick={onClose}>
          {({ isActive }) => (
            <>
              {isActive && <ActiveStrip />}
              Tests
            </>
          )}
        </NavLink>
      </nav>

      <div className="mt-2 border-t border-hairline px-4 pb-1 pt-3">
        <p className="font-display text-[10px] font-semibold uppercase tracking-[0.22em] text-ink-faint">
          Spaces
        </p>
      </div>

      <div className="flex-1 overflow-x-hidden overflow-y-auto px-2 pb-2">
        {spaces.length === 0 ? (
          <p className="px-3 py-2 text-[12px] italic text-ink-faint">No spaces yet</p>
        ) : (
          <div className="flex flex-col gap-0.5">
            {spaces.map((space) => (
              <SpaceRow key={space.id} space={space} onClose={onClose} />
            ))}
          </div>
        )}
      </div>

      <div className="border-t border-hairline px-2 py-2">
        <NavLink
          to="/spaces/new"
          onClick={onClose}
          className="flex h-9 items-center justify-center rounded border border-dashed border-hairline text-[11px] font-medium uppercase tracking-[0.18em] text-ink-muted transition hover:border-accent hover:text-accent-bright"
        >
          + New space
        </NavLink>
      </div>

      <div className="mt-auto flex items-center justify-between border-t border-hairline px-3 py-2">
        <ThemeToggle />
        <span className="font-mono text-[10px] tracking-[0.14em] text-ink-faint">
          v0.0.1
        </span>
      </div>
    </aside>
  );
}
