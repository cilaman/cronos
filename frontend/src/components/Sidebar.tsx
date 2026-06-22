import { NavLink } from "react-router-dom";
import { cn } from "../utils/cn";
import { useSpaces } from "../hooks/useSpaces";
import type { SpaceSummary } from "../types";
import { ThemePicker } from "./ThemePicker";
import { BuildInfo } from "./BuildInfo";
import { CronosMark } from "./CronosMark";

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
    <div className="group relative flex items-center gap-0.5">
      <NavLink
        to={`/spaces/${space.id}`}
        onClick={onClose}
        className={({ isActive }) =>
          cn(
            "relative flex min-w-0 flex-1 h-8 items-center gap-2 rounded px-3 text-[12px] transition",
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
            {space.autopilot === "enabled" && (
              <span
                aria-label="Autopilot enabled"
                title="Autopilot enabled"
                className="h-1.5 w-1.5 shrink-0 rounded-full bg-ink-faint"
              />
            )}
            {open > 0 && (
              <span className="font-mono text-[10px] tabular-nums text-ink-faint">
                {String(open).padStart(2, "0")}
              </span>
            )}
          </>
        )}
      </NavLink>
      <NavLink
        to={`/spaces/${space.id}/tree`}
        onClick={onClose}
        title="Tree view"
        aria-label={`${space.name} tree view`}
        className={({ isActive }) =>
          cn(
            "flex h-6 w-6 shrink-0 items-center justify-center rounded text-ink-faint opacity-0 transition group-hover:opacity-100 focus-visible:opacity-100",
            isActive ? "opacity-100 text-accent-bright" : "hover:bg-surface-2 hover:text-ink",
          )
        }
      >
        <svg width="11" height="11" viewBox="0 0 11 11" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" aria-hidden="true">
          <circle cx="5.5" cy="1.5" r="1"/>
          <circle cx="1.5" cy="8.5" r="1"/>
          <circle cx="9.5" cy="8.5" r="1"/>
          <line x1="5.5" y1="2.5" x2="5.5" y2="5"/>
          <line x1="5.5" y1="5" x2="1.5" y2="7.5"/>
          <line x1="5.5" y1="5" x2="9.5" y2="7.5"/>
        </svg>
      </NavLink>
      <NavLink
        to={`/spaces/${space.id}/files`}
        onClick={onClose}
        title="File browser"
        aria-label={`${space.name} file browser`}
        className={({ isActive }) =>
          cn(
            "flex h-6 w-6 shrink-0 items-center justify-center rounded text-ink-faint opacity-0 transition group-hover:opacity-100 focus-visible:opacity-100",
            isActive ? "opacity-100 text-accent-bright" : "hover:bg-surface-2 hover:text-ink",
          )
        }
      >
        <svg width="11" height="11" viewBox="0 0 11 11" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path d="M1 3.5C1 2.67 1.67 2 2.5 2h2l1 1.5h3c.83 0 1.5.67 1.5 1.5V8.5C10 9.33 9.33 10 8.5 10h-6C1.67 10 1 9.33 1 8.5V3.5z"/>
        </svg>
      </NavLink>
    </div>
  );
}

interface Props {
  onClose?: () => void;
}

export function Sidebar({ onClose }: Props) {
  const { data } = useSpaces();
  const spaces = data?.spaces ?? [];

  return (
    <aside className="flex h-full w-56 shrink-0 flex-col border-r border-hairline bg-surface-1 glass-pane">
      <div className="flex h-14 items-center justify-between gap-2 border-b border-hairline px-4">
        <div className="flex items-center gap-2">
          <CronosMark className="h-6 w-6 shrink-0" />
          <span className="font-mono text-sm font-semibold uppercase tracking-[0.22em] text-ink">
            CRONOS
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
              Tasks
            </>
          )}
        </NavLink>
        <NavLink to="/features" className={primaryNavLinkClasses} onClick={onClose}>
          {({ isActive }) => (
            <>
              {isActive && <ActiveStrip />}
              Features
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
        <NavLink to="/memory" className={primaryNavLinkClasses} onClick={onClose}>
          {({ isActive }) => (
            <>
              {isActive && <ActiveStrip />}
              Memory Browser
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
        <NavLink
          to="/harnesses"
          className={primaryNavLinkClasses}
          onClick={onClose}
        >
          {({ isActive }) => (
            <>
              {isActive && <ActiveStrip />}
              Harnesses
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
        <ThemePicker />
        <BuildInfo />
      </div>
    </aside>
  );
}
