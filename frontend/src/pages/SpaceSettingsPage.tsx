import { useRef, useState } from "react";
import { Link, Navigate, useNavigate, useParams } from "react-router-dom";
import { SpaceForm } from "../components/spaces/SpaceForm";
import { api } from "../api";
import type { AutopilotMode, Space } from "../types";
import {
  useDeleteSpace,
  useImportSpace,
  useLinkSpaceRepo,
  useSpace,
  useUnlinkSpaceRepo,
  useUpdateSpace,
} from "../hooks/useSpaces";

function RepoPanel({ space }: { space: Space }) {
  const linkMutation = useLinkSpaceRepo(space.id);
  const unlinkMutation = useUnlinkSpaceRepo(space.id);
  const [repoUrl, setRepoUrl] = useState("");
  const [branch, setBranch] = useState("main");
  const [shareCronos, setShareCronos] = useState(false);
  const [confirmingUnlink, setConfirmingUnlink] = useState(false);

  const linked = space.git_repo_url !== null;

  async function doLink() {
    await linkMutation.mutateAsync({
      repo_url: repoUrl.trim(),
      branch: branch.trim(),
      share_cronos: shareCronos,
    });
    setRepoUrl("");
    setBranch("main");
    setShareCronos(false);
  }

  async function doUnlink() {
    await unlinkMutation.mutateAsync();
    setConfirmingUnlink(false);
  }

  return (
    <div className="rounded-md border border-hairline bg-surface-1 p-4 shadow-inset-hairline">
      <h3 className="font-display text-[11px] font-semibold uppercase tracking-[0.2em] text-ink-muted">
        Repository
      </h3>
      {linked ? (
        <div className="mt-2 space-y-2 text-[12px] text-ink">
          <p className="text-ink-muted">Linked to</p>
          <p className="break-all rounded border border-hairline bg-canvas px-2 py-1.5 font-mono text-[11px] text-ink">
            {space.git_repo_url}
          </p>
          <p className="text-ink-muted">
            Base branch:{" "}
            <code className="font-mono text-ink">{space.git_branch}</code>
          </p>
          <p className="text-ink-muted">
            {space.git_share_cronos ? (
              <>
                <code className="font-mono text-ink">.cronos/</code> is shared via git.
              </>
            ) : (
              <>
                <code className="font-mono text-ink">.cronos/</code> is gitignored
                (tasks are local).
              </>
            )}
          </p>
          {!confirmingUnlink ? (
            <button
              type="button"
              onClick={() => setConfirmingUnlink(true)}
              className="mt-2 rounded border border-hairline-strong bg-surface-2 px-3 py-1.5 text-[12px] text-ink transition hover:border-danger hover:text-danger"
            >
              Unlink repo
            </button>
          ) : (
            <div className="mt-3 space-y-2 rounded border border-danger/40 bg-danger/5 p-3">
              <p className="text-[12px] text-ink">
                Removes the <code className="font-mono">.git/</code> directory and
                all repo files. <code className="font-mono">.cronos/</code> (tasks)
                stays intact. Task worktree branches are lost.
              </p>
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={doUnlink}
                  disabled={unlinkMutation.isPending}
                  className="rounded border border-danger bg-danger px-3 py-1.5 text-[12px] font-medium text-canvas transition hover:bg-danger/90 disabled:opacity-60"
                >
                  {unlinkMutation.isPending ? "Unlinking…" : "Confirm unlink"}
                </button>
                <button
                  type="button"
                  onClick={() => setConfirmingUnlink(false)}
                  className="rounded px-3 py-1.5 text-[12px] text-ink-muted transition hover:bg-surface-2 hover:text-ink"
                >
                  Cancel
                </button>
              </div>
            </div>
          )}
          {unlinkMutation.error && (
            <p className="text-[12px] text-danger">
              {unlinkMutation.error.message}
            </p>
          )}
        </div>
      ) : (
        <div className="mt-2 space-y-3">
          <p className="text-[12px] text-ink-muted">
            Link a git repo so each task runs in its own worktree, with access to the
            repo's <code className="font-mono text-ink">.claude/</code> agents and skills.
          </p>
          <label className="block">
            <span className="font-display text-[10px] font-semibold uppercase tracking-[0.2em] text-ink-faint">
              Repo URL
            </span>
            <input
              type="text"
              value={repoUrl}
              onChange={(e) => setRepoUrl(e.target.value)}
              spellCheck={false}
              placeholder="git@github.com:org/repo.git"
              className="mt-1 block w-full rounded border border-hairline-strong bg-canvas px-2.5 py-1.5 font-mono text-[12px] text-ink placeholder:text-ink-faint focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent"
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
              spellCheck={false}
              placeholder="main"
              className="mt-1 block w-full rounded border border-hairline-strong bg-canvas px-2.5 py-1.5 font-mono text-[12px] text-ink placeholder:text-ink-faint focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent"
            />
          </label>
          <label className="flex items-start gap-2">
            <input
              type="checkbox"
              checked={shareCronos}
              onChange={(e) => setShareCronos(e.target.checked)}
              className="mt-0.5 h-3.5 w-3.5 cursor-pointer accent-accent"
            />
            <span className="text-[11px] text-ink-muted">
              Commit <code className="font-mono text-ink">.cronos/</code> to the repo
              (otherwise it's added to <code className="font-mono text-ink">.gitignore</code>)
            </span>
          </label>
          <button
            type="button"
            onClick={doLink}
            disabled={
              !repoUrl.trim() ||
              !branch.trim() ||
              linkMutation.isPending
            }
            className="rounded border border-accent bg-accent px-3 py-1.5 text-[12px] font-medium text-canvas transition hover:bg-accent-bright disabled:cursor-not-allowed disabled:border-hairline disabled:bg-surface-2 disabled:text-ink-faint"
          >
            {linkMutation.isPending ? "Cloning…" : "Link repository"}
          </button>
          {linkMutation.error && (
            <p className="text-[12px] text-danger">
              {linkMutation.error.message}
            </p>
          )}
        </div>
      )}
    </div>
  );
}

const AUTOPILOT_OPTIONS: { value: AutopilotMode; label: string }[] = [
  { value: "disabled", label: "Disabled" },
  { value: "enabled", label: "Enabled" },
  { value: "paused", label: "Paused" },
];

function AutopilotPanel({ space }: { space: Space }) {
  const updateSpace = useUpdateSpace(space.id);
  const current = space.autopilot ?? "disabled";

  async function handleChange(value: AutopilotMode) {
    if (value === current) return;
    await updateSpace.mutateAsync({ autopilot: value });
  }

  return (
    <div className="rounded-md border border-hairline bg-surface-1 p-4 shadow-inset-hairline">
      <h3 className="font-display text-[11px] font-semibold uppercase tracking-[0.2em] text-ink-muted">
        Autopilot
      </h3>
      <p className="mt-1 text-[12px] text-ink-faint">
        When enabled, Cronos auto-picks the next eligible backlog task and opens a PR per task on DONE.
      </p>
      <div className="mt-3 flex overflow-hidden rounded border border-hairline">
        {AUTOPILOT_OPTIONS.map((opt) => (
          <button
            key={opt.value}
            type="button"
            onClick={() => void handleChange(opt.value)}
            disabled={updateSpace.isPending}
            className={[
              "flex-1 py-1.5 text-[12px] font-medium transition focus:outline-none focus-visible:ring-1 focus-visible:ring-accent",
              current === opt.value
                ? "bg-accent text-canvas"
                : "bg-surface-2 text-ink-muted hover:bg-surface-3 hover:text-ink",
              "first:rounded-l last:rounded-r",
            ].join(" ")}
          >
            {opt.label}
          </button>
        ))}
      </div>
      {updateSpace.error && (
        <p className="mt-2 text-[12px] text-danger">{updateSpace.error.message}</p>
      )}
    </div>
  );
}

function DataPanel({ spaceId }: { spaceId: string }) {
  const importMutation = useImportSpace();
  const fileRef = useRef<HTMLInputElement>(null);
  return (
    <div className="rounded-md border border-hairline bg-surface-1 p-4 shadow-inset-hairline">
      <h3 className="font-display text-[11px] font-semibold uppercase tracking-[0.2em] text-ink-muted">
        Data
      </h3>
      <p className="mt-1 text-[12px] text-ink-faint">
        Export a self-contained ZIP of this space (tasks + workspaces), or
        replace it from a previously-exported archive.
      </p>
      <div className="mt-3 flex flex-wrap gap-2">
        <button
          type="button"
          onClick={() => api.exportSpace(spaceId)}
          className="rounded border border-hairline-strong bg-surface-2 px-3 py-1.5 text-[12px] text-ink transition hover:border-accent hover:bg-surface-3"
        >
          Export ZIP
        </button>
        <button
          type="button"
          disabled={importMutation.isPending}
          onClick={() => fileRef.current?.click()}
          className="rounded px-3 py-1.5 text-[12px] text-ink-muted transition hover:bg-surface-2 hover:text-ink disabled:opacity-60"
        >
          {importMutation.isPending ? "Importing…" : "Import another"}
        </button>
        <input
          ref={fileRef}
          type="file"
          accept=".zip"
          className="hidden"
          onChange={async (e) => {
            const file = e.target.files?.[0];
            if (file) {
              try {
                await importMutation.mutateAsync({ file });
              } catch (err) {
                console.error(err);
              }
            }
            e.target.value = "";
          }}
        />
      </div>
      {importMutation.error && (
        <p className="mt-2 text-[12px] text-danger">
          {importMutation.error.message}
        </p>
      )}
    </div>
  );
}

function DangerZone({ spaceId, spaceName }: { spaceId: string; spaceName: string }) {
  const [confirming, setConfirming] = useState(false);
  const [typed, setTyped] = useState("");
  const deleteSpace = useDeleteSpace();
  const navigate = useNavigate();

  async function doDelete() {
    await deleteSpace.mutateAsync({ id: spaceId, cascade: true });
    navigate("/", { replace: true });
  }

  return (
    <div className="rounded-md border border-danger/40 bg-danger/5 p-4">
      <h3 className="font-display text-[11px] font-semibold uppercase tracking-[0.2em] text-danger">
        Danger zone
      </h3>
      <p className="mt-1 text-[12px] text-ink-muted">
        Soft-deletes the space (moves to <code className="font-mono text-ink">.trash/</code>).
        Tasks and workspaces go with it.
      </p>
      {!confirming ? (
        <button
          type="button"
          onClick={() => setConfirming(true)}
          className="mt-3 rounded border border-danger/60 px-3 py-1.5 text-[12px] text-danger transition hover:bg-danger hover:text-canvas"
        >
          Delete space
        </button>
      ) : (
        <div className="mt-3 space-y-2">
          <p className="text-[12px] text-ink">
            Type <span className="font-mono text-ink">{spaceName}</span> to confirm.
          </p>
          <input
            type="text"
            value={typed}
            onChange={(e) => setTyped(e.target.value)}
            className="block w-full rounded border border-hairline-strong bg-canvas px-3 py-1.5 text-[12px] text-ink focus:border-danger focus:outline-none focus:ring-1 focus:ring-danger"
          />
          <div className="flex gap-2">
            <button
              type="button"
              onClick={doDelete}
              disabled={typed !== spaceName || deleteSpace.isPending}
              className="rounded border border-danger bg-danger px-3 py-1.5 text-[12px] font-medium text-canvas transition hover:bg-danger/90 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {deleteSpace.isPending ? "Deleting…" : "I understand, delete"}
            </button>
            <button
              type="button"
              onClick={() => {
                setConfirming(false);
                setTyped("");
              }}
              className="rounded px-3 py-1.5 text-[12px] text-ink-muted transition hover:bg-surface-2 hover:text-ink"
            >
              Cancel
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

export function SpaceSettingsPage() {
  const { spaceId } = useParams();
  const navigate = useNavigate();
  const { data: space, isLoading } = useSpace(spaceId ?? null);
  const updateSpace = useUpdateSpace(spaceId ?? "");

  if (!spaceId) return <Navigate to="/" replace />;
  if (isLoading) return <p className="p-8 text-ink-muted">Loading…</p>;
  if (!space) {
    return (
      <div className="p-8">
        <p className="text-ink-muted">Space not found.</p>
        <Link to="/" className="mt-2 inline-block text-accent">
          Back to dashboard
        </Link>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-5xl space-y-8 p-6 lg:p-8">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-ink-faint">
            <Link to="/" className="hover:text-accent-bright">
              Dashboard
            </Link>{" "}
            /{" "}
            <Link
              to={`/spaces/${space.id}`}
              className="hover:text-accent-bright"
            >
              {space.name}
            </Link>{" "}
            / settings
          </p>
          <h1 className="flex items-center gap-2 font-display text-[22px] font-semibold uppercase tracking-[0.14em] text-ink">
            <span
              aria-hidden
              className="h-4 w-4 rounded-sm"
              style={{ backgroundColor: space.color }}
            />
            {space.icon && <span>{space.icon}</span>}
            {space.name}
          </h1>
        </div>
        <Link
          to={`/spaces/${space.id}`}
          className="flex h-9 items-center rounded px-3 text-[12px] text-ink-muted transition hover:bg-surface-2 hover:text-ink"
        >
          Back to board
        </Link>
      </header>

      <SpaceForm
        mode="edit"
        initial={space}
        submitting={updateSpace.isPending}
        error={updateSpace.error?.message ?? null}
        onCancel={() => navigate(`/spaces/${space.id}`)}
        onSubmit={async (values) => {
          await updateSpace.mutateAsync({
            name: values.name,
            color: values.color,
            icon: values.icon,
            clear_icon: values.icon === null,
            description: values.description,
          });
        }}
        rightSlot={
          <>
            <RepoPanel space={space} />
            <AutopilotPanel space={space} />
            <DataPanel spaceId={space.id} />
            <DangerZone spaceId={space.id} spaceName={space.name} />
          </>
        }
      />
    </div>
  );
}
