export function FilesPanel() {
  return (
    <aside className="flex flex-col border-t border-hairline bg-pitch-50/30 p-4 lg:w-72 lg:shrink-0 lg:border-l lg:border-t-0">
      <h3 className="text-[10px] font-semibold uppercase tracking-[0.2em] text-bone-faint">
        Files
      </h3>
      <div className="mt-3 flex flex-1 flex-col items-start gap-1 text-sm">
        <p className="text-bone-muted">No files attached yet</p>
        <p className="text-xs italic text-bone-faint">Coming soon</p>
      </div>
    </aside>
  );
}
