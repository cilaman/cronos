import { useEffect, useRef, useState } from "react";
import { useSpaces } from "../hooks/useSpaces";
import { AGENT_MODES, AGENT_MODELS, type AgentMode, type AgentModel } from "../types";
import { Button } from "./ui/Button";
import { Badge } from "./ui/Badge";
import { FormField } from "./ui/FormField";
import { FormInput, FormSelect, FormTextarea } from "./ui/FormInput";
import { Modal } from "./ui/Modal";
import { getTonePriority } from "../utils/badgeTone";

const PRIORITY_OPTIONS = [
  { value: 1 as const, label: "P1" },
  { value: 2 as const, label: "P2" },
  { value: 3 as const, label: "P3" },
  { value: 4 as const, label: "P4" },
  { value: 5 as const, label: "P5" },
];

interface Props {
  heading: string;
  initialTitle?: string;
  initialBrief?: string;
  initialModel?: AgentModel;
  initialMode?: AgentMode;
  initialPriority?: number;
  initialSpaceId?: string | null;
  showSpacePicker?: boolean;
  lockedSpaceId?: string | null;
  submitting?: boolean;
  error?: string | null;
  onSubmit: (body: {
    title: string;
    brief: string;
    agent_model: AgentModel;
    agent_mode: AgentMode;
    priority: number;
    space_id?: string;
    startImmediately: boolean;
    files: File[];
  }) => void;
  onCancel: () => void;
}

export function TaskForm({
  heading,
  initialTitle = "",
  initialBrief = "",
  initialModel = "default",
  initialMode = "auto",
  initialPriority = 3,
  initialSpaceId = null,
  showSpacePicker = false,
  lockedSpaceId = null,
  submitting = false,
  error = null,
  onSubmit,
  onCancel,
}: Props) {
  const [title, setTitle] = useState(initialTitle);
  const [brief, setBrief] = useState(initialBrief);
  const [model, setModel] = useState<AgentModel>(initialModel);
  const [mode, setMode] = useState<AgentMode>(initialMode);
  const [priority, setPriority] = useState(initialPriority);
  const [startImmediately, setStartImmediately] = useState(false);
  const [files, setFiles] = useState<File[]>([]);
  const [spaceId, setSpaceId] = useState<string | null>(
    lockedSpaceId ?? initialSpaceId,
  );
  const fileInputRef = useRef<HTMLInputElement>(null);
  const { data: spacesData } = useSpaces();
  const spaces = spacesData?.spaces ?? [];

  useEffect(() => {
    if (!spaceId && spaces.length > 0) {
      setSpaceId(spaces[0].id);
    }
  }, [spaces, spaceId]);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onCancel();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onCancel]);

  const effectiveSpaceId = lockedSpaceId ?? spaceId;
  const canSubmit =
    title.trim().length > 0 &&
    !submitting &&
    (!showSpacePicker || !!effectiveSpaceId);

  function addFiles(incoming: FileList | null) {
    if (!incoming) return;
    const next = Array.from(incoming);
    setFiles((prev) => {
      const names = new Set(prev.map((f) => f.name));
      return [...prev, ...next.filter((f) => !names.has(f.name))];
    });
  }

  function removeFile(name: string) {
    setFiles((prev) => prev.filter((f) => f.name !== name));
  }

  const submitLabel = submitting
    ? startImmediately ? "Starting…" : "Creating…"
    : startImmediately ? "Create & Start" : "Create";

  return (
    <Modal onClose={onCancel}>
      <form
        onClick={(e) => e.stopPropagation()}
        onSubmit={(e) => {
          e.preventDefault();
          if (!canSubmit) return;
          onSubmit({
            title: title.trim(),
            brief: brief.trim(),
            agent_model: model,
            agent_mode: mode,
            priority,
            space_id: effectiveSpaceId ?? undefined,
            startImmediately,
            files,
          });
        }}
        className="flex h-full w-full max-w-2xl flex-col overflow-hidden border border-hairline bg-surface-1 shadow-lift sm:h-auto sm:max-h-[90vh] sm:rounded-lg"
      >
        <header className="flex items-center justify-between border-b border-hairline p-4">
          <h2 className="font-display text-base font-semibold uppercase tracking-[0.18em] text-ink">
            {heading}
          </h2>
          <button
            type="button"
            onClick={onCancel}
            aria-label="Close"
            className="rounded p-1 text-ink-muted transition hover:bg-surface-2 hover:text-ink"
          >
            ✕
          </button>
        </header>

        <div className="flex-1 space-y-4 overflow-x-hidden overflow-y-auto p-4">
          <div className="flex flex-col gap-3 sm:flex-row">
            <FormField label="Title" className="flex-1">
              <FormInput
                autoFocus
                type="text"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                maxLength={200}
                required
              />
            </FormField>
            <FormField label="Mode" className="sm:w-32">
              <FormSelect
                value={mode}
                onChange={(e) => setMode(e.target.value as AgentMode)}
              >
                {AGENT_MODES.map((m) => (
                  <option key={m.value} value={m.value}>{m.label}</option>
                ))}
              </FormSelect>
            </FormField>
            <FormField label="Model" className="sm:w-32">
              <FormSelect
                value={model}
                onChange={(e) => setModel(e.target.value as AgentModel)}
              >
                {AGENT_MODELS.map((m) => (
                  <option key={m.value} value={m.value}>{m.label}</option>
                ))}
              </FormSelect>
            </FormField>
          </div>

          <FormField label="Priority">
            <div className="flex gap-1.5">
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

          {showSpacePicker && (
            <FormField label="Space">
              <FormSelect
                value={effectiveSpaceId ?? ""}
                onChange={(e) => setSpaceId(e.target.value)}
                disabled={!!lockedSpaceId}
              >
                {spaces.length === 0 && (
                  <option value="">No spaces — create one first</option>
                )}
                {spaces.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.icon ? `${s.icon}  ` : ""}
                    {s.name}
                  </option>
                ))}
              </FormSelect>
            </FormField>
          )}

          <FormField label="Brief">
            <FormTextarea
              value={brief}
              onChange={(e) => setBrief(e.target.value)}
              rows={8}
              placeholder="Describe what the agent should do. Markdown supported."
              className="font-mono"
            />
          </FormField>

          <div>
            <span className="font-display text-[10px] font-semibold uppercase tracking-[0.2em] text-ink-faint">
              Files
            </span>
            <div className="mt-1 rounded border border-hairline-strong bg-canvas p-3">
              {files.length > 0 && (
                <ul className="mb-2 space-y-1">
                  {files.map((f) => (
                    <li
                      key={f.name}
                      className="flex items-center justify-between rounded px-2 py-1 text-sm text-ink hover:bg-surface-2"
                    >
                      <span className="min-w-0 truncate font-mono text-xs text-ink-muted">
                        {f.name}
                      </span>
                      <button
                        type="button"
                        onClick={() => removeFile(f.name)}
                        className="ml-2 flex-shrink-0 text-ink-faint transition hover:text-danger"
                        aria-label={`Remove ${f.name}`}
                      >
                        ✕
                      </button>
                    </li>
                  ))}
                </ul>
              )}
              <input
                ref={fileInputRef}
                type="file"
                multiple
                className="hidden"
                onChange={(e) => addFiles(e.target.files)}
              />
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                className="flex items-center gap-1.5 rounded border border-hairline-strong bg-surface-1 px-3 py-1.5 text-xs text-ink-muted transition hover:border-accent hover:bg-surface-2 hover:text-ink"
              >
                <span aria-hidden className="text-sm leading-none">↑</span>
                {files.length > 0 ? "Add more files" : "Upload files"}
              </button>
            </div>
          </div>

          {error && (
            <p className="rounded border border-danger/40 bg-danger/15 px-3 py-2 text-sm text-danger">
              {error}
            </p>
          )}
        </div>

        <footer className="flex items-center justify-between gap-2 border-t border-hairline p-3">
          <label className="flex cursor-pointer items-center gap-2 select-none">
            <input
              type="checkbox"
              checked={startImmediately}
              onChange={(e) => setStartImmediately(e.target.checked)}
              className="h-4 w-4 rounded border-hairline-strong accent-accent"
            />
            <span className="font-display text-[10px] font-semibold uppercase tracking-[0.18em] text-ink-muted">
              Start immediately
            </span>
          </label>
          <div className="flex items-center gap-2">
            <Button type="button" variant="ghost" onClick={onCancel}>
              Cancel
            </Button>
            <Button type="submit" disabled={!canSubmit} loading={submitting}>
              {submitLabel}
            </Button>
          </div>
        </footer>
      </form>
    </Modal>
  );
}
