import { useEffect, useRef, useState } from "react";
import { Button } from "./ui/Button";
import { useSpaces } from "../hooks/useSpaces";

interface Props {
  value: string | null; // null ⇒ All spaces
  onChange: (next: string | null) => void;
  disabled?: boolean;
  disabledTooltip?: string;
}

export function SpaceFilterDropdown({
  value,
  onChange,
  disabled = false,
  disabledTooltip,
}: Props) {
  const { data } = useSpaces();
  const spaces = data?.spaces ?? [];
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    function onClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    window.addEventListener("mousedown", onClick);
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("mousedown", onClick);
      window.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const active = value ? spaces.find((s) => s.id === value) : null;

  return (
    <div ref={ref} className="relative">
      <Button
        archetype="dropdown-trigger"
        variant="secondary"
        size="sm"
        disabled={disabled}
        title={disabled ? disabledTooltip : undefined}
        onClick={() => !disabled && setOpen((v) => !v)}
        className="h-8 gap-2 px-2.5 text-[12px]"
      >
        {active ? (
          <>
            <span
              aria-hidden
              className="h-2 w-2 rounded-sm"
              style={{ backgroundColor: active.color }}
            />
            {active.icon && <span aria-hidden>{active.icon}</span>}
            <span className="max-w-[8rem] truncate">{active.name}</span>
          </>
        ) : (
          <span className="text-ink-muted">All spaces</span>
        )}
        <span aria-hidden className="text-[10px] text-ink-faint">
          ▾
        </span>
      </Button>
      {open && (
        <div className="absolute right-0 z-30 mt-1 w-56 overflow-hidden rounded-md border border-hairline bg-surface-1 shadow-lift">
          <Button
            archetype="list-row"
            variant="ghost"
            size="sm"
            onClick={() => {
              onChange(null);
              setOpen(false);
            }}
            className={`gap-2 text-[12px] ${value === null ? "text-ink" : "text-ink-muted"}`}
          >
            <span aria-hidden className="h-2 w-2 rounded-sm bg-hairline-strong" />
            All spaces
          </Button>
          <div className="max-h-72 overflow-x-hidden overflow-y-auto border-t border-hairline">
            {spaces.map((s) => (
              <Button
                key={s.id}
                archetype="list-row"
                variant="ghost"
                size="sm"
                onClick={() => {
                  onChange(s.id);
                  setOpen(false);
                }}
                className={`gap-2 text-[12px] ${value === s.id ? "text-ink" : "text-ink-muted"}`}
              >
                <span
                  aria-hidden
                  className="h-2 w-2 rounded-sm"
                  style={{ backgroundColor: s.color }}
                />
                {s.icon && <span aria-hidden>{s.icon}</span>}
                <span className="truncate">{s.name}</span>
              </Button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
