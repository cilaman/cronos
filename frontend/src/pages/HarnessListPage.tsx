import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useHarnesses, useCreateHarness, useDeleteHarness } from "../hooks/useHarnesses";
import { cn } from "../utils/cn";
import { PageContainer } from "../components/ui/PageContainer";
import { PageHeader } from "../components/ui/PageHeader";
import type { Harness } from "../types";

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
    <div
      className="group flex flex-col gap-3 rounded-lg border border-hairline bg-surface-1 p-4 transition hover:border-accent/40 hover:shadow-sm"
    >
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

export function HarnessListPage() {
  const { spaceId = "" } = useParams<{ spaceId: string }>();
  const navigate = useNavigate();
  const { data: harnesses, isLoading, error } = useHarnesses(spaceId);
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

  const handleDelete = (name: string) => {
    setDeletePending(name);
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
    <PageContainer width="content">
      <PageHeader
        title="Harnesses"
        subtitle="Automation workflows that chain agent tasks"
        actions={[
          <button
            key="new"
            type="button"
            onClick={() => setShowCreate(true)}
            className="rounded-md bg-accent px-3 py-1.5 text-sm font-medium text-white transition hover:bg-accent-bright"
          >
            + New harness
          </button>,
        ]}
        className="mb-6"
      />

      {isLoading && (
        <div className="flex items-center gap-2 py-12 text-sm text-ink-muted">
          <span className="h-4 w-4 animate-spin rounded-full border-2 border-hairline border-t-accent" />
          Loading…
        </div>
      )}

      {error && (
        <div className="rounded-lg border border-danger/30 bg-danger/10 px-4 py-3 text-sm text-danger">
          Failed to load harnesses
        </div>
      )}

      {!isLoading && !error && harnesses?.length === 0 && (
        <div className="flex flex-col items-center gap-4 rounded-xl border border-dashed border-hairline py-16 text-center">
          <p className="text-sm text-ink-muted">No harnesses yet</p>
          <button
            type="button"
            onClick={() => setShowCreate(true)}
            className="rounded-md border border-dashed border-accent/50 px-4 py-2 text-sm text-accent-bright transition hover:bg-accent/10"
          >
            Create your first harness
          </button>
        </div>
      )}

      {!isLoading && !error && harnesses && harnesses.length > 0 && (
        <div className="flex flex-col gap-3">
          {harnesses.map((h) => (
            <HarnessCard
              key={h.name}
              harness={h}
              spaceId={spaceId}
              onDelete={handleDelete}
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
    </PageContainer>
  );
}
