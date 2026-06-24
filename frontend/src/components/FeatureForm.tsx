import { useState } from "react";
import { Button } from "./ui/Button";
import { Badge } from "./ui/Badge";
import { FormField } from "./ui/FormField";
import { FormInput, FormTextarea } from "./ui/FormInput";
import { Modal } from "./ui/Modal";
import { useCreateFeature } from "../hooks/useFeatures";
import { getTonePriority } from "../utils/badgeTone";

const PRIORITY_OPTIONS = [
  { value: 1 as const, label: "P1" },
  { value: 2 as const, label: "P2" },
  { value: 3 as const, label: "P3" },
  { value: 4 as const, label: "P4" },
  { value: 5 as const, label: "P5" },
];

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
                  "transition",
                  type === "feature"
                    ? "ring-2 ring-offset-1 ring-offset-canvas ring-current rounded-sm"
                    : "opacity-60 hover:opacity-80",
                ].join(" ")}
              >
                <Badge tone="feature">Feature</Badge>
              </button>
              <button
                type="button"
                onClick={() => setType("fix")}
                className={[
                  "transition",
                  type === "fix"
                    ? "ring-2 ring-offset-1 ring-offset-canvas ring-current rounded-sm"
                    : "opacity-60 hover:opacity-80",
                ].join(" ")}
              >
                <Badge tone="fix">Fix</Badge>
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
                    "transition",
                    priority === opt.value
                      ? "ring-2 ring-offset-1 ring-offset-canvas ring-current rounded-sm"
                      : "opacity-50 hover:opacity-80",
                  ].join(" ")}
                >
                  <Badge tone={getTonePriority(opt.value)}>{opt.label}</Badge>
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
