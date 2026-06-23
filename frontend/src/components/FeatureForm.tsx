import { useState } from "react";
import { Button } from "./ui/Button";
import { FormField } from "./ui/FormField";
import { FormInput, FormTextarea } from "./ui/FormInput";
import { Modal } from "./ui/Modal";
import { useCreateFeature } from "../hooks/useFeatures";

const PRIORITY_OPTIONS = [
  { value: 1, label: "P1", cls: "border-red-200 bg-red-50 text-red-600 dark:border-red-400/30 dark:bg-red-400/10 dark:text-red-400" },
  { value: 2, label: "P2", cls: "border-orange-200 bg-orange-50 text-orange-600 dark:border-orange-400/30 dark:bg-orange-400/10 dark:text-orange-400" },
  { value: 3, label: "P3", cls: "border-amber-200 bg-amber-50 text-amber-600 dark:border-amber-400/30 dark:bg-amber-400/10 dark:text-amber-400" },
  { value: 4, label: "P4", cls: "border-teal-200 bg-teal-50 text-teal-600 dark:border-teal-400/30 dark:bg-teal-400/10 dark:text-teal-400" },
  { value: 5, label: "P5", cls: "border-hairline bg-surface-2 text-ink-faint" },
] as const;

interface Props {
  spaceId: string;
  onClose: () => void;
}

export function FeatureForm({ spaceId, onClose }: Props) {
  const [type, setType] = useState<"feature" | "fix">("feature");
  const [title, setTitle] = useState("");
  const [priority, setPriority] = useState(3);
  const [brief, setBrief] = useState("");
  const createFeature = useCreateFeature(spaceId);

  const heading = type === "feature" ? "New Feature" : "New Fix";
  const submitLabel = createFeature.isPending
    ? "Adding…"
    : type === "feature" ? "Add Feature" : "Add Fix";
  const canSubmit = title.trim().length > 0 && !createFeature.isPending;

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!canSubmit) return;
    createFeature.mutate(
      { title: title.trim(), type, description: brief.trim() || undefined, priority },
      { onSuccess: onClose },
    );
  }

  const errorMsg = createFeature.error
    ? ((createFeature.error as Error).message ?? "Failed to create feature.")
    : null;

  return (
    <Modal onClose={onClose}>
      <form
        onClick={(e) => e.stopPropagation()}
        onSubmit={handleSubmit}
        className="flex h-full w-full max-w-2xl flex-col overflow-hidden border border-hairline bg-surface-1 shadow-lift sm:h-auto sm:max-h-[90vh] sm:rounded-lg"
      >
        <header className="flex items-center justify-between border-b border-hairline p-4">
          <h2 className="font-display text-base font-semibold uppercase tracking-[0.18em] text-ink">
            {heading}
          </h2>
        </header>

        <div className="flex-1 space-y-4 overflow-x-hidden overflow-y-auto p-4">
          <FormField label="Type">
            <div className="mt-1 flex gap-1.5">
              <button
                type="button"
                onClick={() => setType("feature")}
                className={[
                  "rounded border px-3 py-1 text-xs font-semibold transition",
                  type === "feature"
                    ? "border-emerald-300 bg-emerald-100 text-emerald-700 dark:border-emerald-400/50 dark:bg-emerald-400/20 dark:text-emerald-300 ring-2 ring-offset-1 ring-offset-canvas ring-emerald-400/50"
                    : "border-hairline bg-surface-2 text-ink-muted opacity-60 hover:opacity-80",
                ].join(" ")}
              >
                Feature
              </button>
              <button
                type="button"
                onClick={() => setType("fix")}
                className={[
                  "rounded border px-3 py-1 text-xs font-semibold transition",
                  type === "fix"
                    ? "border-rose-300 bg-rose-100 text-rose-700 dark:border-rose-400/50 dark:bg-rose-400/20 dark:text-rose-300 ring-2 ring-offset-1 ring-offset-canvas ring-rose-400/50"
                    : "border-hairline bg-surface-2 text-ink-muted opacity-60 hover:opacity-80",
                ].join(" ")}
              >
                Fix
              </button>
            </div>
          </FormField>

          <FormField label="Title">
            <FormInput
              autoFocus
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              maxLength={200}
              required
            />
          </FormField>

          <FormField label="Priority">
            <div className="mt-1 flex gap-1.5">
              {PRIORITY_OPTIONS.map((opt) => (
                <button
                  key={opt.value}
                  type="button"
                  onClick={() => setPriority(opt.value)}
                  className={[
                    "rounded border px-2.5 py-1 font-mono text-[11px] font-semibold uppercase tracking-wide transition",
                    opt.cls,
                    priority === opt.value
                      ? "ring-2 ring-offset-1 ring-offset-canvas ring-current"
                      : "opacity-50 hover:opacity-80",
                  ].join(" ")}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          </FormField>

          <FormField label="Brief">
            <FormTextarea
              value={brief}
              onChange={(e) => setBrief(e.target.value)}
              rows={8}
              placeholder="Describe the feature or fix. Markdown supported."
              className="font-mono"
            />
          </FormField>

          {errorMsg && (
            <p className="rounded border border-danger/40 bg-danger/15 px-3 py-2 text-sm text-danger">
              {errorMsg}
            </p>
          )}
        </div>

        <footer className="flex items-center justify-end gap-2 border-t border-hairline p-3">
          <Button type="button" variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" disabled={!canSubmit} loading={createFeature.isPending}>
            {submitLabel}
          </Button>
        </footer>
      </form>
    </Modal>
  );
}
