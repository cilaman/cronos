import { useEffect, useState } from "react";
import { PRESET_SPACE_COLORS, PRESET_SPACE_ICONS } from "../../types";
import type { Space } from "../../types";

export interface SpaceFormValues {
  name: string;
  color: string;
  icon: string | null;
  description: string;
  repoUrl: string | null;
  branch: string | null;
  shareCronos: boolean;
}

interface Props {
  mode: "create" | "edit";
  initial?: Partial<Space>;
  submitting?: boolean;
  error?: string | null;
  onSubmit: (values: SpaceFormValues) => void;
  onCancel?: () => void;
  rightSlot?: React.ReactNode;
}

const DEFAULT_COLOR = PRESET_SPACE_COLORS[0].value;

export function SpaceForm({
  mode,
  initial,
  submitting = false,
  error,
  onSubmit,
  onCancel,
  rightSlot,
}: Props) {
  const [name, setName] = useState(initial?.name ?? "");
  const [color, setColor] = useState(initial?.color ?? DEFAULT_COLOR);
  const [icon, setIcon] = useState<string | null>(initial?.icon ?? null);
  const [description, setDescription] = useState(initial?.description ?? "");
  const [linkRepo, setLinkRepo] = useState(false);
  const [repoUrl, setRepoUrl] = useState("");
  const [branch, setBranch] = useState("main");
  const [shareCronos, setShareCronos] = useState(false);

  // Track initial values for the dirty check below (only matters in edit mode).
  const [snap] = useState({
    name: initial?.name ?? "",
    color: initial?.color ?? DEFAULT_COLOR,
    icon: initial?.icon ?? null,
    description: initial?.description ?? "",
  });
  const dirty =
    name !== snap.name ||
    color !== snap.color ||
    icon !== snap.icon ||
    description !== snap.description;

  useEffect(() => {
    if (mode === "edit" && initial) {
      setName(initial.name ?? "");
      setColor(initial.color ?? DEFAULT_COLOR);
      setIcon(initial.icon ?? null);
      setDescription(initial.description ?? "");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initial?.id]);

  const repoReady = !linkRepo || (repoUrl.trim().length > 0 && branch.trim().length > 0);
  const canSubmit =
    !submitting &&
    name.trim().length > 0 &&
    repoReady &&
    (mode === "create" || dirty);

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        if (!canSubmit) return;
        onSubmit({
          name: name.trim(),
          color,
          icon,
          description: description.trim(),
          repoUrl: linkRepo ? repoUrl.trim() : null,
          branch: linkRepo ? branch.trim() : null,
          shareCronos: linkRepo && shareCronos,
        });
      }}
      className="grid gap-8 lg:grid-cols-[1fr_320px]"
    >
      <div className="space-y-6">
        <label className="block">
          <span className="font-display text-[10px] font-semibold uppercase tracking-[0.2em] text-ink-faint">
            Name
          </span>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            maxLength={80}
            required
            placeholder="e.g. Marketing site"
            className="mt-1 block w-full rounded border border-hairline-strong bg-canvas px-3 py-2 text-sm text-ink placeholder:text-ink-faint focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent"
          />
        </label>

        <label className="block">
          <span className="font-display text-[10px] font-semibold uppercase tracking-[0.2em] text-ink-faint">
            Description
          </span>
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={3}
            maxLength={2000}
            placeholder="What lives in this space?"
            className="mt-1 block w-full rounded border border-hairline-strong bg-canvas px-3 py-2 text-sm text-ink placeholder:text-ink-faint focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent"
          />
        </label>

        <div className="block">
          <span className="font-display text-[10px] font-semibold uppercase tracking-[0.2em] text-ink-faint">
            Color
          </span>
          <div className="mt-2 flex flex-wrap gap-2">
            {PRESET_SPACE_COLORS.map((swatch) => (
              <button
                key={swatch.value}
                type="button"
                onClick={() => setColor(swatch.value)}
                title={swatch.name}
                aria-label={swatch.name}
                className="relative h-7 w-7 rounded-sm transition focus:outline-none focus-visible:ring-1 focus-visible:ring-accent focus-visible:ring-offset-2 focus-visible:ring-offset-surface-1"
                style={{
                  backgroundColor: swatch.value,
                  boxShadow:
                    color === swatch.value
                      ? `0 0 0 2px rgb(var(--color-canvas)), 0 0 0 4px ${swatch.value}`
                      : "inset 0 0 0 1px rgb(0 0 0 / 0.08)",
                }}
              >
                {color === swatch.value && (
                  <span
                    aria-hidden
                    className="absolute inset-0 flex items-center justify-center text-[12px] text-white drop-shadow"
                  >
                    ✓
                  </span>
                )}
              </button>
            ))}
          </div>
        </div>

        <div className="block">
          <span className="font-display text-[10px] font-semibold uppercase tracking-[0.2em] text-ink-faint">
            Icon
          </span>
          <div className="mt-2 grid grid-cols-8 gap-2 sm:grid-cols-8">
            <button
              type="button"
              onClick={() => setIcon(null)}
              className={`flex h-9 items-center justify-center rounded-sm border text-[11px] uppercase tracking-wide transition ${
                icon === null
                  ? "border-accent bg-accent/10 text-accent-bright"
                  : "border-hairline text-ink-muted hover:border-hairline-strong hover:text-ink"
              }`}
            >
              None
            </button>
            {PRESET_SPACE_ICONS.map((glyph) => (
              <button
                key={glyph}
                type="button"
                onClick={() => setIcon(glyph)}
                className={`flex h-9 items-center justify-center rounded-sm border text-base transition ${
                  icon === glyph
                    ? "border-accent bg-accent/10"
                    : "border-hairline hover:border-hairline-strong hover:bg-surface-2"
                }`}
              >
                {glyph}
              </button>
            ))}
          </div>
        </div>

        {mode === "create" && (
          <div className="rounded border border-hairline bg-surface-1 p-4">
            <label className="flex items-start gap-3">
              <input
                type="checkbox"
                checked={linkRepo}
                onChange={(e) => setLinkRepo(e.target.checked)}
                className="mt-0.5 h-4 w-4 cursor-pointer accent-accent"
              />
              <div>
                <span className="font-display text-[11px] font-semibold uppercase tracking-[0.2em] text-ink">
                  Link to a git repository
                </span>
                <p className="mt-0.5 text-[12px] text-ink-muted">
                  Cronos clones the repo into the space; each task runs in its own
                  worktree with access to the repo's <code className="font-mono text-ink">.claude/</code>{" "}
                  agents and skills.
                </p>
              </div>
            </label>

            {linkRepo && (
              <div className="mt-4 space-y-3 border-t border-hairline pt-4">
                <label className="block">
                  <span className="font-display text-[10px] font-semibold uppercase tracking-[0.2em] text-ink-faint">
                    Repo URL
                  </span>
                  <input
                    type="text"
                    value={repoUrl}
                    onChange={(e) => setRepoUrl(e.target.value)}
                    required={linkRepo}
                    spellCheck={false}
                    placeholder="git@github.com:org/repo.git"
                    className="mt-1 block w-full rounded border border-hairline-strong bg-canvas px-3 py-2 font-mono text-[12px] text-ink placeholder:text-ink-faint focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent"
                  />
                </label>
                <label className="block">
                  <span className="font-display text-[10px] font-semibold uppercase tracking-[0.2em] text-ink-faint">
                    Base branch
                  </span>
                  <input
                    type="text"
                    value={branch}
                    onChange={(e) => setBranch(e.target.value)}
                    required={linkRepo}
                    spellCheck={false}
                    placeholder="main"
                    className="mt-1 block w-full rounded border border-hairline-strong bg-canvas px-3 py-2 font-mono text-[12px] text-ink placeholder:text-ink-faint focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent"
                  />
                </label>
                <label className="flex items-start gap-3">
                  <input
                    type="checkbox"
                    checked={shareCronos}
                    onChange={(e) => setShareCronos(e.target.checked)}
                    className="mt-0.5 h-4 w-4 cursor-pointer accent-accent"
                  />
                  <div>
                    <span className="text-[12px] text-ink">
                      Commit <code className="font-mono">.cronos/</code> to the repo
                    </span>
                    <p className="mt-0.5 text-[11px] text-ink-muted">
                      Off (default): adds <code className="font-mono">.cronos/</code> to{" "}
                      <code className="font-mono">.gitignore</code> so task data stays
                      local. On: teammates can share the same tasks via git.
                    </p>
                  </div>
                </label>
              </div>
            )}
          </div>
        )}

        {error && (
          <p className="rounded border border-danger/40 bg-danger/15 px-3 py-2 text-sm text-danger">
            {error}
          </p>
        )}

        <div className="sticky bottom-0 -mx-1 flex items-center justify-end gap-2 border-t border-hairline bg-canvas/95 px-1 py-3 backdrop-blur">
          {onCancel && (
            <button
              type="button"
              onClick={onCancel}
              className="rounded px-3 py-2 text-sm text-ink-muted transition hover:bg-surface-2 hover:text-ink"
            >
              Cancel
            </button>
          )}
          <button
            type="submit"
            disabled={!canSubmit}
            className="rounded border border-accent bg-accent px-4 py-2 text-sm font-medium text-canvas transition hover:bg-accent-bright hover:shadow-accent-glow disabled:cursor-not-allowed disabled:border-hairline disabled:bg-surface-2 disabled:text-ink-faint disabled:shadow-none"
          >
            {submitting ? "Saving…" : mode === "create" ? "Create space" : "Save changes"}
          </button>
        </div>
      </div>

      {rightSlot && <aside className="space-y-4">{rightSlot}</aside>}
    </form>
  );
}
