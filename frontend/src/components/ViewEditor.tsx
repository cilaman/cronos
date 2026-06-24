import { useEffect, useMemo, useRef, useState } from "react";
import { useCreateView, useDeleteView, useUpdateView, useViews } from "../hooks/useViews";
import type { TaskState, TaskType, View } from "../types";
import { Button } from "./ui/Button";
import { FormField } from "./ui/FormField";
import { FormInput } from "./ui/FormInput";
import { Modal } from "./ui/Modal";

// ── Icons ─────────────────────────────────────────────────────────────────────

function StarIcon({ filled = true }: { filled?: boolean }) {
  return (
    <svg width="12" height="12" viewBox="0 0 12 12" fill={filled ? "currentColor" : "none"}
      stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" aria-hidden="true">
      <path d="M6 1.5l1.35 2.73 3.01.44-2.18 2.12.51 3-2.69-1.42L3.31 9.8l.51-3L1.64 4.67l3.01-.44L6 1.5z" />
    </svg>
  );
}

function DuplicateIcon() {
  return (
    <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor"
      strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <rect x="4" y="4" width="7" height="7" rx="1" />
      <path d="M1 8V2a1 1 0 0 1 1-1h6" />
    </svg>
  );
}

function TrashIcon() {
  return (
    <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor"
      strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M1.5 3h9M4 3V2a1 1 0 0 1 1-1h2a1 1 0 0 1 1 1v1M5 5.5v3M7 5.5v3M2.5 3l.5 7a1 1 0 0 0 1 1h4a1 1 0 0 0 1-1l.5-7" />
    </svg>
  );
}

function CloseIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor"
      strokeWidth="1.75" strokeLinecap="round" aria-hidden="true">
      <line x1="2" y1="2" x2="12" y2="12" />
      <line x1="12" y1="2" x2="2" y2="12" />
    </svg>
  );
}

// ── Constants ─────────────────────────────────────────────────────────────────

const LANE_OPTS: { state: TaskState; label: string }[] = [
  { state: "backlog", label: "To Do" },
  { state: "active", label: "Active" },
  { state: "waiting", label: "Waiting" },
  { state: "done", label: "Done" },
];

const TYPE_OPTS: { value: TaskType; label: string }[] = [
  { value: "task", label: "Task" },
  { value: "goal", label: "Goal" },
  { value: "issue", label: "Issue" },
];

// ── Form state helpers ────────────────────────────────────────────────────────

interface FormState {
  name: string;
  lanes: TaskState[];
  type_filter: TaskType[] | null;
  default: boolean;
}

const NEW_ID = "__new__";

function blank(): FormState {
  return { name: "", lanes: ["backlog", "active", "waiting", "done"], type_filter: null, default: false };
}

function fromView(v: View): FormState {
  return {
    name: v.name,
    lanes: [...v.lanes],
    type_filter: v.type_filter ? [...v.type_filter] : null,
    default: v.default,
  };
}

function formsEqual(a: FormState, b: FormState): boolean {
  if (a.name !== b.name || a.default !== b.default) return false;
  const ta = (a.type_filter ? [...a.type_filter].sort() : []).join(",");
  const tb = (b.type_filter ? [...b.type_filter].sort() : []).join(",");
  if (ta !== tb) return false;
  const tna = a.type_filter === null;
  const tnb = b.type_filter === null;
  if (tna !== tnb) return false;
  return [...a.lanes].sort().join(",") === [...b.lanes].sort().join(",");
}

function validate(form: FormState, views: View[], editingId: string): string | null {
  if (!form.name.trim()) return "Name is required.";
  if (form.lanes.length === 0) return "At least one lane must be selected.";
  const dup = views.find(
    (v) => v.id !== editingId && v.name.trim().toLowerCase() === form.name.trim().toLowerCase(),
  );
  if (dup) return `A view named "${dup.name}" already exists.`;
  return null;
}

// ── Props ─────────────────────────────────────────────────────────────────────

export interface ViewEditorProps {
  spaceId: string;
  /** View currently active on the board (null = space default). */
  currentViewId: string | null;
  onClose: () => void;
  /** Called when the board should navigate to a different view (e.g. after deleting the active one). */
  onViewChange?: (viewId: string | null) => void;
}

// ── Component ─────────────────────────────────────────────────────────────────

export function ViewEditor({ spaceId, currentViewId, onClose, onViewChange }: ViewEditorProps) {
  const { data: rawViews } = useViews(spaceId);
  // Stable empty-array fallback so useEffect([selectedId, views]) doesn't fire on every render
  // while the query is still loading (avoids an infinite-setState loop).
  const views = useMemo(() => rawViews ?? [], [rawViews]);
  const createView = useCreateView(spaceId);
  const updateView = useUpdateView(spaceId);
  const deleteView = useDeleteView(spaceId);

  // Which view is loaded in the editor.
  const [selectedId, setSelectedId] = useState<string>(NEW_ID);
  const hasInit = useRef(false);

  // Form state and the last-saved snapshot for dirty tracking.
  const savedForm = useRef<FormState>(blank());
  const [form, setFormRaw] = useState<FormState>(blank());
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);

  // Initialise selection from loaded views once.
  useEffect(() => {
    if (!hasInit.current && views.length > 0) {
      hasInit.current = true;
      const def = views.find((v) => v.default) ?? views[0];
      setSelectedId(def.id);
    }
  }, [views]);

  // Sync form when selected view or views list changes.
  useEffect(() => {
    if (selectedId === NEW_ID) {
      const f = blank();
      savedForm.current = f;
      setFormRaw(f);
      setError(null);
      return;
    }
    const v = views.find((v) => v.id === selectedId);
    if (v) {
      const f = fromView(v);
      savedForm.current = f;
      setFormRaw(f);
      setError(null);
    } else if (views.length > 0) {
      // View was deleted externally — fall back to default.
      const fallback = views.find((v) => v.default) ?? views[0];
      setSelectedId(fallback.id);
    }
  }, [selectedId, views]);

  const isDirty = !formsEqual(form, savedForm.current);

  function setForm(patch: Partial<FormState>) {
    setFormRaw((prev) => ({ ...prev, ...patch }));
    setError(null);
  }

  function confirmIfDirty(action: () => void) {
    if (isDirty && !window.confirm("You have unsaved changes. Discard them?")) return;
    action();
  }

  function handleSelectView(id: string) {
    confirmIfDirty(() => setSelectedId(id));
  }

  function handleClose() {
    confirmIfDirty(onClose);
  }

  async function handleSave() {
    const err = validate(form, views, selectedId);
    if (err) { setError(err); return; }
    setSaving(true);
    setError(null);
    try {
      if (selectedId === NEW_ID) {
        const created = await createView.mutateAsync({
          name: form.name.trim(),
          lanes: form.lanes,
          type_filter: form.type_filter,
          default: form.default,
        });
        setSelectedId(created.id);
        savedForm.current = fromView(created);
      } else {
        const updated = await updateView.mutateAsync({
          viewId: selectedId,
          name: form.name.trim(),
          lanes: form.lanes,
          type_filter: form.type_filter,
          default: form.default,
        });
        savedForm.current = fromView(updated);
      }
      setFormRaw((prev) => ({ ...prev, name: prev.name.trim() }));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSaving(false);
    }
  }

  async function handleDuplicate(v: View) {
    setError(null);
    try {
      const created = await createView.mutateAsync({
        name: `${v.name} (copy)`,
        lanes: [...v.lanes],
        type_filter: v.type_filter ? [...v.type_filter] : null,
        default: false,
      });
      setSelectedId(created.id);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  async function handleSetDefault(v: View) {
    if (v.default) return;
    setError(null);
    try {
      await updateView.mutateAsync({ viewId: v.id, default: true });
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  async function handleDeleteConfirmed(viewId: string) {
    setConfirmDeleteId(null);
    setError(null);
    try {
      await deleteView.mutateAsync(viewId);
      const remaining = views.filter((v) => v.id !== viewId);
      const next = remaining.find((v) => v.default) ?? remaining[0];
      setSelectedId(next ? next.id : NEW_ID);

      // If the board is on the deleted view, navigate away.
      const deletedWasActive =
        viewId === currentViewId ||
        (currentViewId === null && views.find((v) => v.id === viewId)?.default);
      if (deletedWasActive) onViewChange?.(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  // Stable refs for keyboard handler so the effect doesn't re-register on every render.
  const handleSaveRef = useRef(handleSave);
  handleSaveRef.current = handleSave;
  const handleCloseRef = useRef(handleClose);
  handleCloseRef.current = handleClose;

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key === "s") {
        e.preventDefault();
        handleSaveRef.current();
        return;
      }
      // Escape for the main ViewEditor modal is handled by Modal.tsx.
      // Delete-confirm Escape is also handled by Modal.tsx when that dialog is open.
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const isNewView = selectedId === NEW_ID;
  const confirmDeleteView = confirmDeleteId ? views.find((v) => v.id === confirmDeleteId) : null;

  return (
    <>
      <Modal onClose={handleClose} hideDefaultClose panelClassName="max-w-3xl">
        <div
          className="flex max-h-[85vh] w-full flex-col overflow-hidden rounded-lg bg-surface-1 sm:max-w-3xl sm:flex-row sm:border sm:border-hairline sm:shadow-lift"
          onClick={(e) => e.stopPropagation()}
          role="dialog"
          aria-modal="true"
          aria-label="Manage views"
        >
          {/* ── Left pane: view list ───────────────────────────────── */}
          <div className="flex flex-col border-b border-hairline bg-surface-1 sm:w-56 sm:shrink-0 sm:border-b-0 sm:border-r">
            {/* Pane header */}
            <div className="flex items-center justify-between border-b border-hairline px-3 py-2.5">
              <span className="font-display text-[10px] font-semibold uppercase tracking-[0.2em] text-ink-faint">
                Views
              </span>
              <button
                type="button"
                onClick={() => handleSelectView(NEW_ID)}
                className="flex items-center gap-1 rounded px-1.5 py-1 text-[11px] text-ink-muted transition hover:bg-surface-2 hover:text-accent focus:outline-none focus-visible:ring-1 focus-visible:ring-accent"
              >
                <span aria-hidden className="text-sm leading-none">＋</span>
                New view
              </button>
            </div>

            {/* View rows */}
            <div className="flex-1 overflow-y-auto py-1">
              {views.map((v) => {
                const isSelected = v.id === selectedId;
                return (
                  <div
                    key={v.id}
                    className={[
                      "group relative flex items-center gap-1 px-2 py-1.5 transition",
                      isSelected ? "bg-surface-2" : "hover:bg-surface-2/60",
                    ].join(" ")}
                  >
                    <button
                      type="button"
                      onClick={() => handleSelectView(v.id)}
                      className="min-w-0 flex-1 text-left focus:outline-none focus-visible:ring-1 focus-visible:ring-accent"
                    >
                      <span
                        className={[
                          "block truncate text-[12px]",
                          isSelected ? "font-medium text-ink" : "text-ink-muted",
                        ].join(" ")}
                      >
                        {v.name}
                      </span>
                    </button>

                    {/* Always-visible star for default view */}
                    {v.default && (
                      <span className="shrink-0 text-accent group-hover:opacity-0" aria-label="Default view">
                        <StarIcon />
                      </span>
                    )}

                    {/* Action buttons — visible on hover */}
                    <div className="absolute right-1.5 flex items-center gap-0.5 opacity-0 transition-opacity group-hover:opacity-100">
                      <button
                        type="button"
                        onClick={() => handleSetDefault(v)}
                        title={v.default ? "Default view" : "Set as default"}
                        aria-label={v.default ? "Default view" : "Set as default"}
                        className={[
                          "rounded p-1 transition focus:outline-none focus-visible:ring-1 focus-visible:ring-accent",
                          v.default
                            ? "cursor-default text-accent"
                            : "text-ink-faint hover:text-accent",
                        ].join(" ")}
                      >
                        <StarIcon filled={v.default} />
                      </button>
                      <button
                        type="button"
                        onClick={() => handleDuplicate(v)}
                        title="Duplicate"
                        aria-label="Duplicate view"
                        className="rounded p-1 text-ink-faint transition hover:text-ink focus:outline-none focus-visible:ring-1 focus-visible:ring-accent"
                      >
                        <DuplicateIcon />
                      </button>
                      <button
                        type="button"
                        onClick={() => setConfirmDeleteId(v.id)}
                        title={views.length <= 1 ? "Cannot delete the only view" : "Delete view"}
                        aria-label="Delete view"
                        disabled={views.length <= 1}
                        className="rounded p-1 text-ink-faint transition hover:text-danger disabled:cursor-not-allowed disabled:opacity-30 focus:outline-none focus-visible:ring-1 focus-visible:ring-accent"
                      >
                        <TrashIcon />
                      </button>
                    </div>
                  </div>
                );
              })}

              {/* New-view row (selected) */}
              {isNewView && (
                <div className="flex items-center gap-2 bg-surface-2 px-2 py-1.5">
                  <span className="truncate text-[12px] font-medium text-ink-muted italic">
                    New view
                  </span>
                </div>
              )}
            </div>
          </div>

          {/* ── Right pane: editor form ────────────────────────────── */}
          <div className="flex min-w-0 flex-1 flex-col overflow-hidden">
            {/* Form header */}
            <div className="flex items-center justify-between border-b border-hairline px-4 py-2.5">
              <h2 className="font-display text-[11px] font-semibold uppercase tracking-[0.2em] text-ink">
                {isNewView ? "New view" : "Edit view"}
              </h2>
              <button
                type="button"
                onClick={handleClose}
                aria-label="Close"
                className="rounded p-1.5 text-ink-faint transition hover:bg-surface-2 hover:text-ink focus:outline-none focus-visible:ring-1 focus-visible:ring-accent"
              >
                <CloseIcon />
              </button>
            </div>

            {/* Form body */}
            <div className="flex-1 space-y-5 overflow-y-auto px-4 py-4">
              <FormField label="Name">
                <FormInput
                  autoFocus
                  value={form.name}
                  maxLength={100}
                  placeholder="View name"
                  onChange={(e) => setForm({ name: e.target.value })}
                />
              </FormField>

              <FormField label="Lanes">
                <div className="mt-2 flex flex-col gap-2">
                  {LANE_OPTS.map((opt) => (
                    <CheckRow
                      key={opt.state}
                      label={opt.label}
                      checked={form.lanes.includes(opt.state)}
                      onChange={(checked) =>
                        setForm({
                          lanes: checked
                            ? [...form.lanes, opt.state]
                            : form.lanes.filter((l) => l !== opt.state),
                        })
                      }
                    />
                  ))}
                </div>
              </FormField>

              <FormField label="Type filter">
                <div className="mt-2 flex flex-col gap-2">
                  <CheckRow
                    label="All types"
                    checked={form.type_filter === null}
                    onChange={(checked) =>
                      setForm({ type_filter: checked ? null : ["task", "goal", "issue"] })
                    }
                  />
                  {form.type_filter !== null &&
                    TYPE_OPTS.map((opt) => (
                      <CheckRow
                        key={opt.value}
                        label={opt.label}
                        indent
                        checked={form.type_filter!.includes(opt.value)}
                        onChange={(checked) => {
                          const tf = form.type_filter!;
                          setForm({
                            type_filter: checked
                              ? [...tf, opt.value]
                              : tf.filter((t) => t !== opt.value),
                          });
                        }}
                      />
                    ))}
                </div>
              </FormField>

              <CheckRow
                label="Default view"
                labelClass="font-display text-[10px] font-semibold uppercase tracking-[0.2em] text-ink-faint"
                checked={form.default}
                onChange={(checked) => setForm({ default: checked })}
              />

              {error && (
                <p className="rounded border border-danger/40 bg-danger/15 px-3 py-2 text-xs text-danger">
                  {error}
                </p>
              )}
            </div>

            {/* Form footer */}
            <div className="flex items-center gap-2 border-t border-hairline px-4 py-3">
              <span className="mr-auto text-[10px] text-ink-faint">
                {isDirty ? "Unsaved changes" : ""}
              </span>
              <Button variant="secondary" size="sm" onClick={handleClose}>
                Cancel
              </Button>
              <Button variant="primary" size="sm" loading={saving} onClick={handleSave}>
                Save
              </Button>
            </div>
          </div>
        </div>
      </Modal>

      {/* ── Delete confirm dialog ──────────────────────────────────── */}
      {confirmDeleteId && confirmDeleteView && (
        <Modal onClose={() => setConfirmDeleteId(null)}>
          <div
            className="p-5"
            role="alertdialog"
            aria-modal="true"
            aria-label="Confirm delete"
          >
            <h3 className="font-display text-[13px] font-semibold text-ink">Delete view?</h3>
            <p className="mt-2 text-sm text-ink-muted">
              <span className="font-medium text-ink">"{confirmDeleteView.name}"</span> will be
              permanently removed.
            </p>
            <div className="mt-4 flex justify-end gap-2">
              <Button variant="secondary" size="sm" onClick={() => setConfirmDeleteId(null)}>
                Cancel
              </Button>
              <Button
                variant="danger"
                size="sm"
                onClick={() => handleDeleteConfirmed(confirmDeleteId)}
              >
                Delete
              </Button>
            </div>
          </div>
        </Modal>
      )}
    </>
  );
}

// ── CheckRow helper ───────────────────────────────────────────────────────────

function CheckRow({
  label,
  labelClass,
  checked,
  indent = false,
  onChange,
}: {
  label: string;
  labelClass?: string;
  checked: boolean;
  indent?: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <label
      className={[
        "flex cursor-pointer items-center gap-2.5",
        indent ? "pl-5" : "",
      ].join(" ")}
    >
      <input
        type="checkbox"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
        className="h-3.5 w-3.5 shrink-0 cursor-pointer rounded border-hairline-strong accent-[var(--color-accent)]"
      />
      <span className={labelClass ?? "text-sm text-ink"}>{label}</span>
    </label>
  );
}
