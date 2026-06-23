import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { useFeature, usePatchFeature, useProcessFeature, useSetRealize } from "../hooks/useFeatures";
import { IconButton } from "./ui/IconButton";
import { Modal } from "./ui/Modal";
import type { FeatureState } from "../types";

const FEATURE_STATE_BADGE: Record<FeatureState, string> = {
  backlog: "bg-surface-2 text-ink-muted ring-1 ring-hairline",
  processing:
    "bg-violet-100 text-violet-800 ring-1 ring-violet-300 dark:bg-violet-400/10 dark:text-violet-300 dark:ring-violet-400/40",
  planned:
    "bg-indigo-100 text-indigo-800 ring-1 ring-indigo-300 dark:bg-indigo-400/10 dark:text-indigo-300 dark:ring-indigo-400/40",
  waiting:
    "bg-amber-100 text-amber-800 ring-1 ring-amber-300 dark:bg-amber-400/10 dark:text-amber-300 dark:ring-amber-400/40",
  done:
    "bg-sky-100 text-sky-800 ring-1 ring-sky-300 dark:bg-sky-400/10 dark:text-sky-300 dark:ring-sky-400/40",
};

function FeatureDetailSkeleton() {
  return (
    <div className="animate-pulse space-y-4 p-6">
      <div className="flex gap-2">
        <div className="h-5 w-16 rounded bg-surface-3" />
        <div className="h-5 w-24 rounded bg-surface-3" />
      </div>
      <div className="h-7 w-2/3 rounded bg-surface-3" />
      <div className="space-y-2 pt-2">
        <div className="h-4 w-full rounded bg-surface-3" />
        <div className="h-4 w-5/6 rounded bg-surface-3" />
        <div className="h-4 w-4/6 rounded bg-surface-3" />
      </div>
    </div>
  );
}

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
    <Modal onClose={onClose} dismissable={!editing}>
      <div
        className="flex h-full w-full max-w-3xl flex-col overflow-hidden border border-hairline bg-surface-1 shadow-lift sm:h-auto sm:max-h-[90vh] sm:rounded-lg glass-pane"
        onClick={(e) => e.stopPropagation()}
      >
        {isLoading && <FeatureDetailSkeleton />}
        {error && (
          <div className="flex flex-col items-center gap-3 p-10 text-center">
            <p className="rounded border border-danger/40 bg-danger/15 px-4 py-3 text-sm text-danger">
              {error.message}
            </p>
            <button
              type="button"
              onClick={() => void refetch()}
              className="rounded border border-hairline-strong bg-canvas px-3 py-1.5 text-xs text-ink-muted transition hover:bg-surface-2 hover:text-ink"
            >
              Retry
            </button>
          </div>
        )}
        {feature && (
          <>
            <header className="flex items-start justify-between gap-4 border-b border-hairline p-4">
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  {feature.feature_state && (
                    <span
                      className={`rounded px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.18em] ${
                        FEATURE_STATE_BADGE[feature.feature_state]
                      }`}
                    >
                      {feature.feature_state}
                    </span>
                  )}
                  <span
                    className={`rounded px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.18em] ${
                      feature.type === "fix"
                        ? "bg-rose-100 text-rose-800 ring-1 ring-rose-300 dark:bg-rose-400/10 dark:text-rose-300 dark:ring-rose-400/40"
                        : "bg-emerald-100 text-emerald-800 ring-1 ring-emerald-300 dark:bg-emerald-400/10 dark:text-emerald-300 dark:ring-emerald-400/40"
                    }`}
                  >
                    {feature.type}
                  </span>
                  {feature.feature_key && (
                    <span className="font-mono text-xs text-ink-faint">{feature.feature_key}</span>
                  )}
                  <span className="font-mono text-xs text-ink-faint">{feature.id}</span>
                </div>
                <h2 className="mt-2 text-xl font-semibold leading-tight tracking-tight text-ink">
                  {feature.title}
                </h2>
              </div>
              <div className="flex shrink-0 items-center gap-1">
                <button
                  type="button"
                  onClick={startEditing}
                  aria-label="Edit"
                  className="rounded border border-hairline bg-surface-2 px-2 py-1 text-xs text-ink-muted transition hover:bg-surface-3 hover:text-ink"
                >
                  Edit
                </button>
              </div>
            </header>

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
          </>
        )}
      </div>
    </Modal>
  );
}
