import { Link } from "react-router-dom";

export function NotFoundPage() {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-3 p-8 text-center">
      <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-ink-faint">
        404
      </p>
      <h1 className="font-display text-[22px] font-semibold uppercase tracking-[0.14em] text-ink">
        Off the map
      </h1>
      <p className="text-sm text-ink-muted">
        That URL doesn't lead anywhere yet.
      </p>
      <Link
        to="/"
        className="rounded border border-accent bg-accent px-3 py-1.5 text-[12px] font-medium text-canvas transition hover:bg-accent-bright"
      >
        Back to dashboard
      </Link>
    </div>
  );
}
