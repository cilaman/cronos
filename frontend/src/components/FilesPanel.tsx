export function FilesPanel() {
  return (
    <aside className="hidden flex-col border-t border-hairline bg-surface-1/30 p-4 lg:flex lg:w-72 lg:shrink-0 lg:border-l lg:border-t-0">
      <h3 className="font-display text-[10px] font-semibold uppercase tracking-[0.2em] text-ink-faint">
        Files
      </h3>
      <div className="mt-3 flex flex-1 flex-col items-start gap-1 text-sm">
        <p className="text-ink-muted">No files attached yet</p>
        <p className="text-xs italic text-ink-faint">Coming soon</p>
      </div>
    </aside>
  );
}
