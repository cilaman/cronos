import { useEffect, useRef, useState } from "react";
import { ChevronDown } from "lucide-react";
import { Icon } from "./ui/Icon";
import { useViews } from "../hooks/useViews";
import type { View } from "../types";

interface Props {
  spaceId: string;
  /** The view ID in the URL (null = using the space's default view). */
  viewId: string | null;
  onChange: (viewId: string | null) => void;
  onManageViews: () => void;
}

function StarIcon() {
  return (
    <svg
      width="10"
      height="10"
      viewBox="0 0 10 10"
      fill="currentColor"
      aria-hidden="true"
      className="shrink-0 text-accent"
    >
      <path d="M5 1l1.12 2.27L9 3.64l-2 1.95.47 2.76L5 7.13 2.53 8.35 3 5.59 1 3.64l2.88-.37L5 1z" />
    </svg>
  );
}

function CheckIcon() {
  return (
    <svg
      width="12"
      height="12"
      viewBox="0 0 12 12"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      className="shrink-0"
    >
      <polyline points="2,6 5,9 10,3" />
    </svg>
  );
}

export function ViewPicker({ spaceId, viewId, onChange, onManageViews }: Props) {
  const { data: views } = useViews(spaceId);
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    function onMouseDown(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    window.addEventListener("mousedown", onMouseDown);
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("mousedown", onMouseDown);
      window.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const resolvedView: View | null = (() => {
    if (!views) return null;
    if (viewId !== null) {
      return views.find((v) => v.id === viewId) ?? views.find((v) => v.default) ?? null;
    }
    return views.find((v) => v.default) ?? views[0] ?? null;
  })();

  function handleSelect(v: View) {
    // Use null (clean URL) when selecting the default view
    onChange(v.default ? null : v.id);
    setOpen(false);
  }

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => setOpen((x) => !x)}
        className="flex h-8 items-center gap-2 rounded border border-hairline-strong bg-surface-1 px-2.5 text-[12px] text-ink transition hover:border-accent hover:bg-surface-2 focus:outline-none focus-visible:ring-1 focus-visible:ring-accent"
      >
        {resolvedView ? (
          <>
            {resolvedView.default && <StarIcon />}
            <span className="max-w-[8rem] truncate">{resolvedView.name}</span>
          </>
        ) : (
          <span className="text-ink-muted">Views</span>
        )}
        <Icon icon={ChevronDown} size="sm" className="text-ink-faint" />
      </button>

      {open && (
        <div className="absolute left-0 z-30 mt-1 w-52 overflow-hidden rounded-md border border-hairline bg-surface-1 shadow-lift">
          <div className="max-h-60 overflow-y-auto">
            {(views ?? []).map((v) => {
              const isActive = resolvedView?.id === v.id;
              return (
                <button
                  key={v.id}
                  type="button"
                  onClick={() => handleSelect(v)}
                  className={[
                    "flex w-full items-center gap-2 px-3 py-2 text-left text-[12px] transition hover:bg-surface-2 focus:outline-none focus-visible:ring-1 focus-visible:ring-accent",
                    isActive ? "text-ink" : "text-ink-muted",
                  ].join(" ")}
                >
                  <span className="w-3 shrink-0">
                    {isActive && <CheckIcon />}
                  </span>
                  <span className="min-w-0 flex-1 truncate">{v.name}</span>
                  {v.default && <StarIcon />}
                </button>
              );
            })}
          </div>
          <div className="border-t border-hairline">
            <button
              type="button"
              onClick={() => {
                setOpen(false);
                onManageViews();
              }}
              className="flex w-full items-center gap-2 px-3 py-2 text-left text-[12px] text-ink-muted transition hover:bg-surface-2 hover:text-ink focus:outline-none focus-visible:ring-1 focus-visible:ring-accent"
            >
              <svg
                width="12"
                height="12"
                viewBox="0 0 12 12"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.5"
                strokeLinecap="round"
                aria-hidden="true"
                className="shrink-0"
              >
                <circle cx="6" cy="6" r="4" />
                <line x1="6" y1="4" x2="6" y2="8" />
                <line x1="4" y1="6" x2="8" y2="6" />
              </svg>
              Manage views…
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
