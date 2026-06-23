---
cc_version: "1.0"
agent: pipeline-implementor
slug: gui-modal-loading--i12
phase: impl
status: done
confidence: 0.92
inputs_used:
  - memory:project_gui_refactor_board_setup
  - memory:gui-icons review RESOLVED
  - .cronos/pipeline/gui-modal-loading/impl-report-gui-modal-loading--i1.md
  - frontend/src/index.css
  - frontend/src/components/FeatureDetail.tsx
  - frontend/src/components/FeatureForm.tsx
  - frontend/src/components/MarkdownEditorModal.tsx
  - frontend/src/components/ui/Modal.tsx
  - frontend/src/components/ui/Modal.test.tsx
  - frontend/src/components/__tests__/MarkdownEditorModal.buttons.test.tsx
  - frontend/src/components/MarkdownEditorModal.test.tsx
  - frontend/src/components/__tests__/FeatureDetail.test.tsx
  - frontend/src/components/__tests__/FeatureForm.test.tsx
iteration_id: I12
files_changed:
  - frontend/src/index.css
  - frontend/src/components/FeatureDetail.tsx
  - frontend/src/components/FeatureForm.tsx
  - frontend/src/components/MarkdownEditorModal.tsx
  - frontend/src/components/ui/Modal.tsx
  - frontend/src/components/ui/Modal.test.tsx
validation_command_passed: true
out_of_scope_findings:
  - description: "F5 (deferred) — Modal panel body padding/scrim opacity deviations from design spec"
    location: "frontend/src/components/ui/Modal.tsx"
    severity: low
  - description: "F6 (deferred) — MarkdownEditorModal mode-toggle buttons missing focus-visible:ring-accent and focus:outline-none classes"
    location: "frontend/src/components/MarkdownEditorModal.tsx"
    severity: low
  - description: "F8 (deferred) — SpaceFilterDropdown and ViewPicker buttons missing focus ring classes"
    location: "frontend/src/components/__tests__/SpaceFilterDropdown.buttons.test.tsx, frontend/src/components/__tests__/ViewPicker.buttons.test.tsx"
    severity: low
outputs_produced:
  - .cronos/pipeline/gui-modal-loading/impl-report-gui-modal-loading--i12.md
blockers: []
next_consumer: test
metrics:
  tool_calls: 55
  files_read: 13
  memory_hits: 2
  diff_lines_added: 168
  diff_lines_removed: 90
---

## Summary

This review-fix iteration resolves the 4 blocking findings (F1–F4) from the gui-modal-loading attempt-1 review. F1 was fixed by restoring index.css to the 68a7515 parent state (recovering all gui-tokens-brand token blocks and .text-title utility) and then re-applying only the legitimate shimmer @keyframes and .animate-shimmer additions from I1. F2 and F3 were fixed by restoring FeatureDetail.tsx and FeatureForm.tsx to their 68a7515 state (recovering Badge/semantic-token usage) while removing the now-redundant inline `aria-label="Close"` close button and `useEffect` Escape handler that would duplicate Modal.tsx's built-in X button and Escape handling. F4 was fixed by re-adding MarkdownEditorModal's own `aria-label="Close editor"` button with focus-visible ring, adding a `hideDefaultClose` prop to Modal.tsx (default false), and adding 2 tests for the new prop to Modal.test.tsx. All required validation commands passed; the frontend build is green and the test failure count dropped from 65 (ce6e614) to 19 — below the 68a7515 baseline of 51.

## Files changed

| File | Action | Lines +/- | Purpose |
|------|--------|-----------|---------|
| frontend/src/index.css | modified | +101 / -4 | F1: restore all token blocks + .text-title; re-add shimmer @keyframes + .animate-shimmer |
| frontend/src/components/FeatureDetail.tsx | modified | +13 / -32 | F2: restore Badge/semantic tokens; remove duplicate close button; add dismissable={!editing} |
| frontend/src/components/FeatureForm.tsx | modified | +17 / -28 | F3: restore Badge/getTonePriority; remove duplicate close button + Escape useEffect |
| frontend/src/components/MarkdownEditorModal.tsx | modified | +8 / -4 | F4: re-add aria-label="Close editor" button with focus ring; add X + Icon imports |
| frontend/src/components/ui/Modal.tsx | modified | +26 / -16 | F4: add hideDefaultClose prop (default false) with conditional X button render |
| frontend/src/components/ui/Modal.test.tsx | modified | +14 / 0 | F4: add 2 tests asserting hideDefaultClose hides/shows the X button |

## Out-of-scope findings

- F5 (deferred): Modal panel padding/scrim opacity — minor visual deviations from original spec; no test coverage impact.
- F6 (deferred): MarkdownEditorModal mode-toggle and save buttons missing focus ring classes (pre-existing failures in buttons.test.tsx before gui-modal-loading started; outside this iteration's scope).
- F8 (deferred): SpaceFilterDropdown and ViewPicker button focus-ring failures are pre-existing (present at 68a7515) and outside this iteration's scope.

## Assumptions

- The "preferred option a" for F4 (`hideDefaultClose` prop) was implemented but NOT passed from MarkdownEditorModal, because MarkdownEditorModal.test.tsx (added in ce6e614, not in scope for modification) tests for Modal's default `aria-label="Close"` button. Both close controls coexist: Modal provides `aria-label="Close"` and MarkdownEditorModal provides `aria-label="Close editor"`.
- FeatureDetail and FeatureForm had their own Escape useEffect and close button at 68a7515 (before Modal.tsx gained those features). Removing these duplicates is necessary correctness — Modal.tsx at ce6e614 already handles both, and the tests were written expecting a single `aria-label="Close"` button.
- Scope files read before editing: all listed individually in inputs_used[].

## Open questions

- None.

## Next consumer brief

Validation command: `cd frontend && npx vitest run tests/index.css.test.ts tests/no-raw-palette-classes.test.ts && npm run build`

Both test files pass (57/57 tests green). Build exits 0 with no TypeScript errors. Full suite: 19 failures (all pre-existing at 68a7515, down from 65 at ce6e614 and 51 at 68a7515 baseline).

Key edge case for the test agent: the `hideDefaultClose` prop in Modal.tsx is implemented but MarkdownEditorModal does NOT use it (due to MarkdownEditorModal.test.tsx expecting Modal's X). When reviewing Modal.tsx in a future cycle, note that `hideDefaultClose` is present but only testable via Modal.test.tsx direct tests.

Deferred findings needing review attention: F6 (MarkdownEditorModal mode-toggle buttons missing focus ring) and F8 (SpaceFilterDropdown/ViewPicker buttons missing focus ring) — both are pre-existing failures carried from before gui-modal-loading; they should be addressed in a dedicated button-focus pass.
