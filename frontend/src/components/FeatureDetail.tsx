import { useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { useFeature, usePatchFeature, useProcessFeature, useSetRealize } from "../hooks/useFeatures";
import { IconButton } from "./ui/IconButton";
import { DetailShell } from "./ui/DetailShell";

interface Props {
  featureId: string;
  onClose: () => void;
}

export function FeatureDetail({ featureId, onClose }: Props) {
  const { data: feature, isLoading, error, refetch } = useFeature(featureId);
  const patchFeature = usePatchFeature();
  const processFeature = useProcessFeature();
  const setRealize = useSetRealize();
  const [editing, setEditing] = useState(false);
  const [editTitle, setEditTitle] = useState("");
  const [editBrief, setEditBrief] = useState("");
  const [editType, setEditType] = useState<"feature" | "fix">("feature");

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key !== "Escape" || editing) return;
      const active = document.activeElement;
      if (
        active instanceof HTMLTextAreaElement ||
        active instanceof HTMLInputElement ||
        active instanceof HTMLSelectElement
      ) {
        return;
      }
      onClose();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose, editing]);

  function startEditing() {
    if (!feature) return;
    setEditTitle(feature.title);
    setEditBrief(feature.brief);
    setEditType(feature.type as "feature" | "fix");
    setEditing(true);
  }

  async function handleSaveEdit() {
    if (!feature) return;
    await patchFeature.mutateAsync({
      featureId: feature.id,
      body: { title: editTitle, brief: editBrief, type: editType },
    });
    setEditing(false);
  }

  async function handleProcess() {
    if (!feature) return;
    if (
      !window.confirm(
        `Process "${feature.title}"? This will start decomposition into implementation tasks.`
      )
    ) {
      return;
    }
    await processFeature.mutateAsync(feature.id);
  }

  async function handleUnlink(itemId: string) {
    if (!feature) return;
    await setRealize.mutateAsync({
      featureId: feature.id,
      body: { item_id: itemId, feature_id: null },
    });
  }

  const isProcessing = feature?.feature_state === "processing";

  return (
    <DetailShell
      variant="feature"
      entity={feature}
      isLoading={isLoading}
      error={error}
      onRetry={() => void refetch()}
      onClose={onClose}
      headerActions={
        feature && !editing ? (
          <button
            type="button"
            onClick={startEditing}
            aria-label="Edit"
            className="rounded border border-hairline bg-surface-2 px-2 py-1 text-xs text-ink-muted transition hover:bg-surface-3 hover:text-ink"
          >
            Edit
          </button>
        ) : null
      }
      footer={
        feature ? (
          <div className="flex-1 space-y-6 overflow-x-hidden overflow-y-auto overscroll-contain p-4">
            {editing ? (
              <section>
                <h3 className="font-display text-[10px] font-semibold uppercase tracking-[0.2em] text-ink-faint">
                  Edit
                </h3>
                <div className="mt-2 space-y-3">
                  <div>
                    <label className="mb-1 block text-[10px] font-semibold uppercase tracking-[0.14em] text-ink-faint">
                      Type
                    </label>
                    <div className="inline-flex rounded border border-hairline bg-surface-1 p-0.5">
                      <button
                        type="button"
                        onClick={() => setEditType("feature")}
                        className={`rounded px-3 py-1 text-xs font-semibold transition ${
                          editType === "feature"
                            ? "bg-emerald-500 text-white"
                            : "text-ink-muted hover:text-ink"
                        }`}
                      >
                        Feature
                      </button>
                      <button
                        type="button"
                        onClick={() => setEditType("fix")}
                        className={`rounded px-3 py-1 text-xs font-semibold transition ${
                          editType === "fix"
                            ? "bg-rose-500 text-white"
                            : "text-ink-muted hover:text-ink"
                        }`}
                      >
                        Fix
                      </button>
                    </div>
                  </div>
                  <div>
                    <label className="mb-1 block text-[10px] font-semibold uppercase tracking-[0.14em] text-ink-faint">
                      Title
                    </label>
                    <input
                      type="text"
                      value={editTitle}
                      onChange={(e) => setEditTitle(e.target.value)}
                      aria-label="Title"
                      className="w-full rounded border border-hairline bg-surface-1 px-3 py-2 text-sm text-ink focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent"
                    />
                  </div>
                  <div>
                    <label className="mb-1 block text-[10px] font-semibold uppercase tracking-[0.14em] text-ink-faint">
                      Brief
                    </label>
                    <textarea
                      value={editBrief}
                      onChange={(e) => setEditBrief(e.target.value)}
                      aria-label="Brief"
                      rows={8}
                      className="w-full rounded border border-hairline bg-surface-1 px-3 py-2 font-mono text-sm text-ink focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent"
                    />
                  </div>
                  <div className="flex gap-2">
                    <button
                      type="button"
                      onClick={() => void handleSaveEdit()}
                      disabled={patchFeature.isPending}
                      className="rounded border border-hairline bg-surface-2 px-3 py-1.5 text-xs font-semibold text-ink-muted transition hover:bg-accent hover:text-white disabled:opacity-50"
                    >
                      {patchFeature.isPending ? "Saving…" : "Save"}
                    </button>
                    <button
                      type="button"
                      onClick={() => setEditing(false)}
                      className="rounded border border-hairline bg-surface-2 px-3 py-1.5 text-xs font-semibold text-ink-muted transition hover:bg-surface-3 hover:text-ink"
                    >
                      Cancel
                    </button>
                  </div>
                  {patchFeature.error && (
                    <p className="text-xs text-danger">{patchFeature.error.message}</p>
                  )}
                </div>
              </section>
            ) : (
              <section>
                <h3 className="font-display text-[10px] font-semibold uppercase tracking-[0.2em] text-ink-faint">
                  Brief
                </h3>
                <div className="prose prose-sm dark:prose-invert mt-2 max-w-none prose-headings:text-ink prose-p:text-ink prose-strong:text-ink prose-a:text-accent-bright prose-code:text-accent-bright prose-pre:bg-canvas prose-pre:border prose-pre:border-hairline prose-pre:overflow-x-auto">
                  {feature.brief ? (
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>{feature.brief}</ReactMarkdown>
                  ) : (
                    <p className="italic text-ink-faint">No brief yet.</p>
                  )}
                </div>
              </section>
            )}

            {feature.waiting_question && (
              <section>
                <div
                  data-testid="waiting-question-box"
                  className="rounded-lg border border-amber-300 bg-amber-50 p-4 dark:border-amber-400/40 dark:bg-amber-400/10"
                >
                  <p className="text-xs font-semibold uppercase tracking-[0.14em] text-amber-700 dark:text-amber-300">
                    Waiting
                  </p>
                  <p className="mt-1 text-sm text-amber-800 dark:text-amber-200">
                    {feature.waiting_question}
                  </p>
                </div>
              </section>
            )}

            <section>
              <h3 className="font-display text-[10px] font-semibold uppercase tracking-[0.2em] text-ink-faint">
                Decompose
              </h3>
              <div className="mt-2 flex items-center gap-2">
                <IconButton
                  variant="accent"
                  size="sm"
                  onClick={() => void handleProcess()}
                  disabled={isProcessing || processFeature.isPending}
                  loading={processFeature.isPending || isProcessing}
                  aria-label="Start decomposition"
                  title="Start decomposition"
                >
                  ▶
                </IconButton>
                <span className="text-xs text-ink-faint">
                  {isProcessing ? "Processing…" : "Start decomposition"}
                </span>
                {processFeature.error && (
                  <p className="text-xs text-danger">{processFeature.error.message}</p>
                )}
              </div>
            </section>

            {feature.realizing_items.length > 0 && (
              <section>
                <h3 className="font-display text-[10px] font-semibold uppercase tracking-[0.2em] text-ink-faint">
                  Realizing Goals ({feature.realizing_items.length})
                </h3>
                <ul className="mt-2 space-y-1">
                  {feature.realizing_items.map((item) => (
                    <li
                      key={item.id}
                      className="flex items-center justify-between gap-2 rounded border border-hairline bg-surface-2 px-3 py-2 text-sm"
                    >
                      <span className="min-w-0 flex-1 truncate text-ink">{item.title}</span>
                      <span className="shrink-0 rounded bg-surface-3 px-1.5 py-0.5 font-mono text-[10px] text-ink-faint">
                        {item.state}
                      </span>
                      <button
                        type="button"
                        onClick={() => void handleUnlink(item.id)}
                        aria-label={`Unlink ${item.title}`}
                        className="shrink-0 rounded px-1.5 py-0.5 text-xs text-ink-faint transition hover:bg-danger/10 hover:text-danger"
                      >
                        Unlink
                      </button>
                    </li>
                  ))}
                </ul>
              </section>
            )}

            {feature.issue_url && (
              <section>
                <h3 className="font-display text-[10px] font-semibold uppercase tracking-[0.2em] text-ink-faint">
                  Issue
                </h3>
                <div className="mt-2">
                  <a
                    href={feature.issue_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1.5 rounded border border-hairline bg-surface-2 px-3 py-1.5 text-[12px] text-ink-muted transition hover:border-accent hover:text-accent-bright"
                  >
                    {feature.issue_url}
                  </a>
                </div>
              </section>
            )}
          </div>
        ) : null
      }
    />
  );
}
