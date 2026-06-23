---
cc_version: "1.0"
agent: pipeline-implementor
slug: gui-modal-loading--i4
phase: impl
status: done
confidence: 0.92
inputs_used:
  - memory:GUI Refactor Board Setup
  - memory:gui-icons review RESOLVED
  - .cronos/pipeline/gui-modal-loading/design-report-gui-modal-loading.md
  - .cronos/pipeline/gui-modal-loading/impl-report-gui-modal-loading--i1.md
  - .cronos/pipeline/gui-modal-loading/impl-report-gui-modal-loading--i2.md
  - frontend/src/components/MarkdownEditorModal.tsx
  - frontend/src/components/ui/Modal.tsx
  - frontend/src/components/ui/Modal.test.tsx
  - frontend/src/components/PluginsPanel.test.tsx
  - frontend/vitest.config.ts
  - frontend/src/test-setup.ts
iteration_id: I4
files_changed:
  - frontend/src/components/MarkdownEditorModal.tsx
  - frontend/src/components/MarkdownEditorModal.test.tsx
validation_command_passed: true
out_of_scope_findings:
  - description: "Modal.tsx panel uses max-w-lg hardcoded in the panel div class. MarkdownEditorModal previously used max-w-6xl for its wide editor layout. After wrapping in Modal, the max-w-lg from the panel div overrides the inner content div's max-w-6xl, making the editor narrower than intended."
    location: "frontend/src/components/ui/Modal.tsx:103"
    severity: medium
outputs_produced:
  - .cronos/pipeline/gui-modal-loading/impl-report-gui-modal-loading--i4.md
blockers: []
next_consumer: test
metrics:
  tool_calls: 22
  files_read: 11
  memory_hits: 2
  diff_lines_added: 200
  diff_lines_removed: 20
---

## Summary

I4 migrates `MarkdownEditorModal.tsx` to use the unified `Modal.tsx` contract from I2. The ad-hoc `fixed inset-0 bg-black/80` scrim div and its `onClick={onClose}` handler were removed. The own `window.addEventListener('keydown', ...)` Escape handler was removed (keeping only the Ctrl+S handler). The component is now wrapped in `<Modal onClose={onClose} dismissable={!dirty}>`, which gates scrim-click and Escape on `dismissable` while always allowing the X button to close. The existing X button (`<Icon icon={X} />`) was removed because `Modal.tsx` provides its own X button with `aria-label="Close"`. Eight tests pass covering the four required dirty-state matrix cases plus fetch error and header render.

## Files changed

| File | Action | Lines +/- | Purpose |
|------|--------|-----------|---------|
| frontend/src/components/MarkdownEditorModal.tsx | modified | +6 / -20 | Remove ad-hoc scrim div and Escape handler; wrap in Modal; remove own X button; add dismissable={!dirty} |
| frontend/src/components/MarkdownEditorModal.test.tsx | created | +194 / 0 | 8 tests: file path header, dirty=false+Escape, dirty=true+Escape, dirty+scrim, dirty+X, clean+scrim, fetch error, X button present |

## Out-of-scope findings

- `frontend/src/components/ui/Modal.tsx:103` (medium): Modal.tsx panel div has `max-w-lg` hardcoded. MarkdownEditorModal relied on `max-w-6xl` for its wide editor layout. This makes the markdown editor narrower than its pre-migration width. The I11 polish iteration has a 50-line budget and owns `Modal.tsx` in its scope_files — this is a good candidate for a `panelClassName` or `size` prop on Modal.tsx, or MarkdownEditorModal could use a wrapper className approach. Review agent should decide whether to address in I11 or defer to a follow-up.

## Assumptions

- The `className` prop on `Modal.tsx` applies to the scrim (outer div), not the panel (as documented by I2 impl-report). This means I4 cannot pass `max-w-6xl` as a Modal className to widen the panel — it would style the scrim instead. The width narrowing is accepted for this iteration and noted as an out-of-scope finding for I11.
- `@uiw/react-md-editor` is mocked in tests as a simple `<textarea>` to avoid jsdom canvas errors and make tests fast. The mock's `onChange` signature matches the real component.
- `vi.stubGlobal("fetch", ...)` is used rather than `global.fetch = vi.fn()` for Vitest compatibility.
- Scope files read before editing: all listed individually in `inputs_used[]`.
- The old X button (`<Icon icon={X} />`) was removed in full since Modal.tsx now provides the close button. The `X` import from `lucide-react` and `Icon` import from `./ui/Icon` were removed to keep the file clean.

## Open questions

- None.

## Next consumer brief

Validation command to rerun: `cd frontend && npm test -- src/components/MarkdownEditorModal.test.tsx --run`

**8 tests, all passing.** Key matrix coverage:
- (a) dirty=false + Escape → `onClose` called (Modal dismissable=true)
- (b) dirty=true + Escape → `onClose` NOT called (Modal dismissable=false)
- (c) dirty=true + scrim click → `onClose` NOT called
- (d) dirty=true + X button (`aria-label="Close"`) → `onClose` called (X always fires)
- (e) dirty=false + scrim click → `onClose` called
- fetch error renders error message
- X button (from Modal.tsx) is always present

**Edge case for I11 (integration gate):** The Modal.tsx panel div has `max-w-lg` hardcoded (noted as out-of-scope finding). After migration, the markdown editor is narrower than its pre-migration `max-w-6xl` width. The review agent should decide whether I11's polish budget addresses this via a `size` or `panelClassName` prop addition to Modal.tsx. If unaddressed, the visual regression is minor but real for users with wide screens.

**Ctrl+S shortcut preserved:** The Escape handler was removed but the Ctrl+S / Cmd+S save shortcut is retained via its own `window.addEventListener` (Modal.tsx only listens for Escape and Tab/Shift-Tab, so no conflict).
