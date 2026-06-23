---
cc_version: "1.0"
agent: pipeline-implementor
slug: gui-button-focus--i5
phase: impl
status: done
confidence: 0.92
inputs_used:
  - memory:project_gui_refactor_board_setup.md
  - memory:gui-tokens-brand RESOLVED
  - memory:gui-badge-system review RESOLVED
  - .cronos/pipeline/gui-button-focus/design-report-gui-button-focus.md
  - .cronos/pipeline/gui-button-focus/impl-report-gui-button-focus--i1.md
  - .cronos/pipeline/gui-button-focus/impl-report-gui-button-focus--i2.md
  - frontend/src/components/MarkdownEditorModal.tsx
  - frontend/src/components/TimeFrameSelector.tsx
  - frontend/src/components/ui/Button.tsx
  - frontend/src/components/ui/IconButton.tsx
  - frontend/src/components/__tests__/TimeFrameSelector.test.tsx
iteration_id: I5
files_changed:
  - frontend/src/components/MarkdownEditorModal.tsx
  - frontend/src/components/TimeFrameSelector.tsx
  - frontend/src/components/__tests__/MarkdownEditorModal.buttons.test.tsx
  - frontend/src/components/__tests__/TimeFrameSelector.buttons.test.tsx
validation_command_passed: true
out_of_scope_findings:
  - description: "The existing TimeFrameSelector.test.tsx (line 25) asserts `.className.toContain('bg-accent')` on the active button. After the migration to Button primitive, the active button now uses variant='primary' which also applies 'bg-accent', so that test continues to pass. However, the test directly checks className internals — a future variant rename could silently break it. Low concern; not in scope to fix."
    location: "frontend/src/components/__tests__/TimeFrameSelector.test.tsx:25"
    severity: low
outputs_produced:
  - .cronos/pipeline/gui-button-focus/impl-report-gui-button-focus--i5.md
blockers: []
next_consumer: test
metrics:
  tool_calls: 30
  files_read: 11
  memory_hits: 3
  diff_lines_added: 325
  diff_lines_removed: 26
---

## Summary

I5 migrated all inline `<button>` elements in `MarkdownEditorModal.tsx` and `TimeFrameSelector.tsx` to `Button` and `IconButton` primitives. In `MarkdownEditorModal`, the mode-toggle buttons (Edit/Preview/Split) became `Button archetype="segmented"`, the Save button became `Button variant="secondary"`, and the close button became `IconButton variant="default" size="compact" aria-label="Close editor"`. In `TimeFrameSelector`, all preset-tab buttons became `Button archetype="segmented"` with active state communicated via `variant="primary"` (active) vs `variant="ghost"` (inactive) — no raw className for state. Two new test files (`MarkdownEditorModal.buttons.test.tsx` with 10 tests, `TimeFrameSelector.buttons.test.tsx` with 10 tests) were created and all 20 pass. Validation command exited 0.

## Files changed

| File | Action | Lines +/- | Purpose |
|------|--------|-----------|---------|
| frontend/src/components/MarkdownEditorModal.tsx | modified | +33 / -22 | Add Button/IconButton/cn imports; migrate mode-toggle → Button archetype=segmented, save → Button secondary, close → IconButton default compact |
| frontend/src/components/TimeFrameSelector.tsx | modified | +6 / -4 | Add Button import; migrate preset-tab buttons → Button archetype=segmented with variant-driven active state |
| frontend/src/components/__tests__/MarkdownEditorModal.buttons.test.tsx | created | +178 / 0 | 10 tests: button semantics, focus ring, aria-label, save disabled state, no inline buttons bypass ring |
| frontend/src/components/__tests__/TimeFrameSelector.buttons.test.tsx | created | +114 / 0 | 10 tests: button semantics, focus ring on all tabs, active/inactive variant, onChange wiring, compact prop preserves ring |

## Out-of-scope findings

- `frontend/src/components/__tests__/TimeFrameSelector.test.tsx:25`: The existing test asserts `.className.toContain('bg-accent')` on the active button. The migration happens to preserve this invariant (Button primary variant applies `bg-accent`) so the test continues to pass, but it directly probes className internals — a future variant rename could silently break it. Low severity; not in scope to fix.

## Assumptions

- The `segmented` archetype on `Button` uses `:first-child`/`:last-child` pseudo-selectors; the mode-toggle buttons are wrapped in `<div class="flex ...">` and the preset tabs are inside a similar flex container, satisfying the adjacency requirement (noted in I1 next consumer brief).
- The `IconButton size="compact"` (h-8 w-8) is used for the close button because the compact size is appropriate for modal header toolbars where 44px would overflow; this matches the design intent established in I2.
- `loading={savePending}` is passed to the Save Button so a spinner renders during save. When `savePending` is undefined (the common case), `loading=false` and the button shows "Save" text normally.
- Scope files read before editing: all listed individually in `inputs_used[]`.
- The `cn` utility import was added to `MarkdownEditorModal.tsx` (previously unused) because the mode-toggle buttons need conditional `hidden sm:flex` class alongside the Button primitive `className` prop.

## Open questions

- None.

## Next consumer brief

Verbatim validation command to rerun:
`cd frontend && npm test -- src/components/__tests__/MarkdownEditorModal.buttons.test.tsx src/components/__tests__/TimeFrameSelector.buttons.test.tsx`

Edge cases for the test agent:
1. The "Split" mode-toggle button has `hidden sm:flex` applied via the `className` prop; in jsdom (no CSS breakpoints), it renders in the DOM but is not truly hidden. Tests query it via `screen.getByRole("button", { name: "Split" })` without asserting visibility — this is intentional.
2. The `MarkdownEditorModal` test mocks `@uiw/react-md-editor` and `@uiw/react-md-editor/markdown-editor.css` and `useTheme`; these mocks must be active before the component import (vitest hoisting handles this).
3. The existing `TimeFrameSelector.test.tsx` still passes after migration — it was not modified and its `bg-accent` assertion continues to hold because the primary variant applies `bg-accent`.
4. Out-of-scope finding: `TimeFrameSelector.test.tsx:25` probes className internals for active state; low severity, worth a follow-up note in the review cycle.
