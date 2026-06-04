import { useState, useEffect } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useSpaces } from "../hooks/useSpaces";
import { useHarnesses, useCreateHarness, useDeleteHarness } from "../hooks/useHarnesses";
import { cn } from "../utils/cn";
import type { Harness } from "../types";

const LS_KEY = "cronos.harnesses.lastSpaceId";

function formatDate(iso?: string): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleDateString(undefined, {
      year: "numeric",
      month: "short",
      day: "numeric",
    });
  } catch {
    return iso;
  }
}

// Inline card — verbatim markup from HarnessListPage.tsx:34-83 (source of truth)
function HarnessCard({
  harness,
  spaceId,
  onDelete,
}: {
  harness: Harness;
  spaceId: string;
  onDelete: (name: string) => void;
}) {
  const navigate = useNavigate();
  const nodeCount = harness.nodes?.length ?? 0;
  const edgeCount = harness.edges?.length ?? 0;
  const varCount = Object.keys(harness.variables ?? {}).length;

  return (
    <div className="group flex flex-col gap-3 rounded-lg border border-hairline bg-surface-1 p-4 transition hover:border-accent/40 hover:shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <h3 className="truncate font-display text-sm font-semibold text-ink">{harness.name}</h3>
          {harness.description && (
            <p className="mt-0.5 line-clamp-2 text-xs text-ink-muted">{harness.description}</p>
          )}
        </div>
        <div className="flex shrink-0 items-center gap-1">
          <button
            type="button"
            onClick={() => navigate(`/spaces/${spaceId}/harnesses/${encodeURIComponent(harness.name)}/runs`)}
            className="rounded px-2 py-1 text-[11px] font-medium text-ink-muted transition hover:bg-surface-2 hover:text-ink"
          >
            Runs
          </button>
          <button
            type="button"
            onClick={() => navigate(`/spaces/${spaceId}/harnesses/${encodeURIComponent(harness.name)}/edit`)}
            className="rounded bg-accent/10 px-2 py-1 text-[11px] font-medium text-accent-bright transition hover:bg-accent/20"
          >
            Edit
          </button>
          <button
            type="button"
            onClick={() => onDelete(harness.name)}
            className="rounded px-2 py-1 text-[11px] font-medium text-ink-faint opacity-0 transition hover:bg-danger/10 hover:text-danger group-hover:opacity-100"
            aria-label={`Delete ${harness.name}`}
          >
            ✕
          </button>
        </div>
      </div>
      <div className="flex items-center gap-3 text-[11px] text-ink-faint">
        <span>{nodeCount} {nodeCount === 1 ? "node" : "nodes"}</span>
        <span className="text-hairline">·</span>
        <span>{edgeCount} {edgeCount === 1 ? "edge" : "edges"}</span>
        {varCount > 0 && (
          <>
            <span className="text-hairline">·</span>
            <span>{varCount} {varCount === 1 ? "var" : "vars"}</span>
          </>
        )}
        <span className="ml-auto">{formatDate(harness.updated_at ?? harness.created_at)}</span>
      </div>
    </div>
  );
}

function CreateHarnessModal({
  onClose,
  onCreate,
  isLoading,
}: {
  onClose: () => void;
  onCreate: (name: string, description: string) => void;
  isLoading: boolean;
}) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (name.trim()) onCreate(name.trim(), description.trim());
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
      <div className="w-full max-w-md rounded-xl border border-hairline bg-surface-1 p-6 shadow-xl">
        <h2 className="mb-4 font-display text-base font-semibold text-ink">New Harness</h2>
        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-medium text-ink-muted" htmlFor="harness-name">
              Name
            </label>
            <input
              id="harness-name"
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="my-harness"
              autoFocus
              className="rounded-md border border-hairline bg-surface-2 px-3 py-2 text-sm text-ink outline-none placeholder:text-ink-faint focus:border-accent focus:ring-1 focus:ring-accent"
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-medium text-ink-muted" htmlFor="harness-description">
              Description <span className="text-ink-faint">(optional)</span>
            </label>
            <input
              id="harness-description"
              type="text"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="What does this harness do?"
              className="rounded-md border border-hairline bg-surface-2 px-3 py-2 text-sm text-ink outline-none placeholder:text-ink-faint focus:border-accent focus:ring-1 focus:ring-accent"
            />
          </div>
          <div className="flex justify-end gap-2 pt-1">
            <button
              type="button"
              onClick={onClose}
              className="rounded px-3 py-1.5 text-sm text-ink-muted transition hover:bg-surface-2 hover:text-ink"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={!name.trim() || isLoading}
              className={cn(
                "rounded bg-accent px-4 py-1.5 text-sm font-medium text-white transition",
                !name.trim() || isLoading
                  ? "cursor-not-allowed opacity-50"
                  : "hover:bg-accent-bright",
              )}
            >
              {isLoading ? "Creating…" : "Create"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

function HarnessSpaceContent({
  spaceId,
}: {
  spaceId: string;
}) {
  const navigate = useNavigate();
  const { data: harnesses, isLoading, isError, error } = useHarnesses(spaceId);
  const createHarness = useCreateHarness(spaceId);
  const deleteHarness = useDeleteHarness(spaceId);
  const [showCreate, setShowCreate] = useState(false);
  const [deletePending, setDeletePending] = useState<string | null>(null);

  const handleCreate = (name: string, description: string) => {
    createHarness.mutate(
      { name, description },
      {
        onSuccess: (h) => {
          setShowCreate(false);
          navigate(`/spaces/${spaceId}/harnesses/${encodeURIComponent(h.name)}/edit`);
        },
      },
    );
  };

  const confirmDelete = () => {
    if (deletePending) {
      deleteHarness.mutate(deletePending, {
        onSuccess: () => setDeletePending(null),
        onError: () => setDeletePending(null),
      });
    }
  };

  return (
    <>
      <div className="mb-4 flex justify-end">
        <button
          type="button"
          onClick={() => setShowCreate(true)}
          className="rounded-md bg-accent px-3 py-1.5 text-sm font-medium text-white transition hover:bg-accent-bright"
        >
          + New harness
        </button>
      </div>

      {isLoading && (
        <div className="flex items-center gap-2 py-12 text-sm text-ink-muted">
          <span className="h-4 w-4 animate-spin rounded-full border-2 border-hairline border-t-accent" />
          Loading…
        </div>
      )}

      {(isError || error) && (
        <div className="rounded-lg border border-danger/30 bg-danger/10 px-4 py-3 text-sm text-danger">
          Failed to load harnesses
        </div>
      )}

      {!isLoading && !isError && harnesses?.length === 0 && (
        <div className="flex flex-col items-center gap-4 rounded-xl border border-dashed border-hairline py-16 text-center">
          <p className="text-sm text-ink-muted">No harnesses in this space</p>
          <button
            type="button"
            onClick={() => setShowCreate(true)}
            className="rounded-md border border-dashed border-accent/50 px-4 py-2 text-sm text-accent-bright transition hover:bg-accent/10"
          >
            Create your first harness
          </button>
        </div>
      )}

      {!isLoading && !isError && harnesses && harnesses.length > 0 && (
        <div className="flex flex-col gap-3">
          {harnesses.map((h) => (
            <HarnessCard
              key={h.name}
              harness={h}
              spaceId={spaceId}
              onDelete={(name) => setDeletePending(name)}
            />
          ))}
        </div>
      )}

      {showCreate && (
        <CreateHarnessModal
          onClose={() => setShowCreate(false)}
          onCreate={handleCreate}
          isLoading={createHarness.isPending}
        />
      )}

      {deletePending && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
          <div className="w-full max-w-sm rounded-xl border border-hairline bg-surface-1 p-6 shadow-xl">
            <h2 className="mb-2 font-display text-base font-semibold text-ink">Delete harness?</h2>
            <p className="mb-5 text-sm text-ink-muted">
              <span className="font-medium text-ink">{deletePending}</span> will be permanently deleted.
            </p>
            <div className="flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setDeletePending(null)}
                className="rounded px-3 py-1.5 text-sm text-ink-muted transition hover:bg-surface-2 hover:text-ink"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={confirmDelete}
                disabled={deleteHarness.isPending}
                className="rounded bg-danger px-4 py-1.5 text-sm font-medium text-white transition hover:opacity-90 disabled:opacity-50"
              >
                {deleteHarness.isPending ? "Deleting…" : "Delete"}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

export function HarnessesPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const { data, isLoading: spacesLoading } = useSpaces();
  const spaces = data?.spaces ?? [];

  // Deterministic precedence: URL query → localStorage → first space → null
  const urlSpaceId = searchParams.get("space");
  const [selectedSpaceId, setSelectedSpaceId] = useState<string | null>(() => {
    if (urlSpaceId) return urlSpaceId;
    try {
      return localStorage.getItem(LS_KEY);
    } catch {
      return null;
    }
  });

  // Auto-select first space when nothing is selected and spaces are loaded
  useEffect(() => {
    if (selectedSpaceId === null && spaces.length > 0) {
      const first = spaces[0].id;
      setSelectedSpaceId(first);
      try { localStorage.setItem(LS_KEY, first); } catch { /* ignore */ }
      setSearchParams({ space: first }, { replace: true });
    }
  }, [selectedSpaceId, spaces, setSearchParams]);

  // Validate URL param against known spaces once loaded
  useEffect(() => {
    if (!spacesLoading && spaces.length > 0 && urlSpaceId) {
      const known = spaces.find((s) => s.id === urlSpaceId);
      if (!known) {
        // URL param doesn't match; fall back to localStorage or first
        const lsId = (() => { try { return localStorage.getItem(LS_KEY); } catch { return null; } })();
        const fallback = lsId && spaces.find((s) => s.id === lsId) ? lsId : spaces[0].id;
        setSelectedSpaceId(fallback);
        try { localStorage.setItem(LS_KEY, fallback); } catch { /* ignore */ }
        setSearchParams({ space: fallback }, { replace: true });
      }
    }
  // Only run when spacesLoading transitions to false
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [spacesLoading]);

  const handleSelectSpace = (id: string) => {
    setSelectedSpaceId(id);
    try { localStorage.setItem(LS_KEY, id); } catch { /* ignore */ }
    setSearchParams({ space: id }, { replace: true });
  };

  const selectedSpace = spaces.find((s) => s.id === selectedSpaceId) ?? null;

  return (
    <div className="mx-auto max-w-3xl px-6 py-8">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="font-display text-lg font-semibold uppercase tracking-[0.18em] text-ink">
            Harnesses
          </h1>
          <p className="mt-0.5 text-xs text-ink-muted">
            Automation workflows that chain agent tasks
          </p>
        </div>
      </div>

      {spacesLoading && (
        <div className="flex items-center gap-2 py-12 text-sm text-ink-muted">
          <span className="h-4 w-4 animate-spin rounded-full border-2 border-hairline border-t-accent" />
          Loading spaces…
        </div>
      )}

      {!spacesLoading && spaces.length === 0 && (
        <div className="flex flex-col items-center gap-4 rounded-xl border border-dashed border-hairline py-16 text-center">
          <p className="text-sm text-ink-muted">No spaces yet</p>
          <a
            href="/spaces/new"
            className="rounded-md border border-dashed border-accent/50 px-4 py-2 text-sm text-accent-bright transition hover:bg-accent/10"
          >
            Create a space to get started
          </a>
        </div>
      )}

      {!spacesLoading && spaces.length > 0 && (
        <>
          <div className="mb-6">
            <select
              value={selectedSpaceId ?? ""}
              onChange={(e) => handleSelectSpace(e.target.value)}
              className="min-h-9 w-full rounded-md border border-hairline bg-surface-2 px-3 py-2 text-sm text-ink outline-none focus:border-accent focus:ring-1 focus:ring-accent sm:w-auto sm:min-w-[220px]"
              aria-label="Select space"
            >
              {spaces.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.icon ? `${s.icon} ` : ""}{s.name}
                </option>
              ))}
            </select>
            {selectedSpace && (
              <p className="mt-1 text-[11px] text-ink-faint">
                Viewing harnesses in <span className="font-medium text-ink-muted">{selectedSpace.name}</span>
              </p>
            )}
          </div>

          {selectedSpaceId && (
            <HarnessSpaceContent spaceId={selectedSpaceId} />
          )}
        </>
      )}
    </div>
  );
}
