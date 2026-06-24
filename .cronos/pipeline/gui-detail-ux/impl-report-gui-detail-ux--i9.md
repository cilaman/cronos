---
cc_version: "1.0"
agent: pipeline-implementor
slug: gui-detail-ux--i9
phase: impl
status: done
confidence: 0.92
inputs_used:
  - memory:project_gui_refactor_board_setup
  - memory:gui-modal-loading review RESOLVED
  - memory:gui-polish review RESOLVED
  - .cronos/pipeline/gui-detail-ux/design-report-gui-detail-ux.md
  - .cronos/pipeline/gui-detail-ux/review-report-gui-detail-ux--attempt1.md
  - frontend/src/components/ui/DetailShell.tsx
  - frontend/src/components/FeatureDetail.tsx
  - frontend/src/components/Detail.tsx
  - frontend/src/components/ui/Toast.tsx
  - frontend/src/components/ui/__tests__/ToastProvider.test.tsx
  - frontend/src/components/ui/Modal.tsx
  - frontend/src/utils/badgeTone.ts
  - frontend/src/components/ui/Badge.tsx
  - frontend/tailwind.config.js
  - frontend/src/index.css
  - frontend/src/state-badges.ts
  - frontend/src/components/__tests__/FeatureDetail.test.tsx
  - frontend/src/components/__tests__/Detail.test.tsx
iteration_id: I9
files_changed:
  - frontend/src/components/ui/DetailShell.tsx
  - frontend/src/components/FeatureDetail.tsx
  - frontend/src/components/Detail.tsx
  - frontend/src/components/ui/Toast.tsx
  - frontend/src/components/ui/__tests__/ToastProvider.test.tsx
validation_command_passed: true
out_of_scope_findings:
  - description: "F6: Tree/DAG toggle lives in TreeToolbar.tsx — placed there by I7's choice, not TreePage.tsx as design body described. Intentional I7 decision, not a regression."
    location: "frontend/src/components/TreeToolbar.tsx"
    severity: low
  - description: "F7: DetailPRSection.test.tsx mock-fix from I8 was an undisclosed scope escape. Disclosed here; not reverted as it is test-only, uniform and non-blocking."
    location: "frontend/src/components/__tests__/DetailPRSection.test.tsx"
    severity: low
  - description: "F8: Design body mentioned DetailShell could own the waiting bar + edit toggle; current code keeps them per-variant (FeatureDetail/Detail). Intentional deferred deviation — would require expanding DetailShell props significantly."
    location: "frontend/src/components/ui/DetailShell.tsx"
    severity: low
outputs_produced:
  - .cronos/pipeline/gui-detail-ux/impl-report-gui-detail-ux--i9.md
blockers: []
next_consumer: test
metrics:
  tool_calls: 42
  files_read: 18
  memory_hits: 3
  diff_lines_added: 16
  diff_lines_removed: 429
---

## Summary

I9 is a review-fix iteration that resolves all 4 blocking findings (F1-F5) from the attempt-1 review of gui-detail-ux. Toast.tsx and ToastProvider.test.tsx were deleted (no importers; their import of non-existent ToastProvider/useToast broke tsc). DetailShell now passes `hideDefaultClose` to Modal and retains its single Close button — eliminating the double-button that broke FeatureDetail.test.tsx while keeping the button visible for Detail.test.tsx (which mocks Modal as a plain div). Redundant Escape `useEffect` handlers were removed from both FeatureDetail.tsx and Detail.tsx; editing-state guard moved to the `onClose` prop passed to DetailShell/Modal. Raw palette classes (18 in Detail.tsx, 6 in FeatureDetail.tsx) were replaced with semantic tokens (`danger`, `warning`, `accent`, `bg-warning/10`, `surface-*`, CSS-var arbitrary syntax for `--cat-goal`). Full build is clean (tsc + vite exit 0); full vitest run has exactly the 5 pre-existing failing files, zero new regressions.

## Files changed

| File | Action | Lines +/- | Purpose |
|------|--------|-----------|---------|
| frontend/src/components/ui/DetailShell.tsx | modified | +1 / -1 | Pass `hideDefaultClose` to Modal (F2) |
| frontend/src/components/FeatureDetail.tsx | modified | +7 / -24 | Remove Escape useEffect, guard onClose, tokenize raw palette classes (F3, F4) |
| frontend/src/components/Detail.tsx | modified | +8 / -25 | Remove Escape useEffect + unused import, guard onClose, tokenize PRIORITY_BADGE_STYLES + TYPE_BADGE_STYLES (F3, F4) |
| frontend/src/components/ui/Toast.tsx | deleted | 0 / -117 | Remove scope-escaped file with no importers (F1) |
| frontend/src/components/ui/__tests__/ToastProvider.test.tsx | deleted | 0 / -262 | Remove scope-escaped test importing non-existent ToastProvider/useToast (F5) |

## Out-of-scope findings

- F6: Tree/DAG toggle is in TreeToolbar.tsx by I7's choice, not TreePage.tsx as design body described. Not a regression.
- F7: DetailPRSection.test.tsx mock-fix added in I8 was an undisclosed scope escape. Disclosed; not reverted (test-only, non-blocking).
- F8: Per-variant waiting bar / edit toggle kept as-is. Unifying into DetailShell would require significant prop surface expansion; deferred.

## Assumptions

- Toast.tsx had zero importers in `frontend/src/` (confirmed: `git grep "from.*Toast"` showed only the ToastProvider.test.tsx itself).
- The correct F2 fix is `hideDefaultClose` on Modal + keep DetailShell's own button — this satisfies both FeatureDetail.test.tsx (which uses real Modal and previously saw two "Close" buttons) and Detail.test.tsx (which mocks Modal as a plain div and needs the button from DetailShell).
- For F4 tokenization: `warning` and `danger` are the only semantic color tokens in tailwind.config.js. For `goal` type badge the arbitrary CSS-var syntax `[rgb(var(--cat-goal)/0.4)]` is used; for `teal` (P4) neutral surface tokens are used.
- The 5 pre-existing failing test files (Card.test.tsx, Card.buttons.test.tsx, MarkdownEditorModal.buttons.test.tsx, SpaceFilterDropdown.buttons.test.tsx, ViewPicker.buttons.test.tsx) were already red on parent a3fb5ed and are out of scope.
- Scope files read before editing: all listed individually in inputs_used[].

## Open questions

- None.

## Next consumer brief

Validation commands to rerun:
1. `cd frontend && npm run build` — must exit 0 (tsc + vite clean, no TS2307 errors)
2. `cd frontend && npx vitest run tests/no-raw-palette-classes.test.ts` — must pass (10/10)
3. `cd frontend && npx vitest run src/components/__tests__/FeatureDetail.test.tsx src/components/__tests__/Detail.test.tsx` — must pass (56/56)
4. `cd frontend && npx vitest run` — 5 pre-existing failures only (Card.test.tsx, Card.buttons.test.tsx, MarkdownEditorModal.buttons.test.tsx, SpaceFilterDropdown.buttons.test.tsx, ViewPicker.buttons.test.tsx); ZERO new failures

Edge cases uncovered during implementation:
- Detail.test.tsx mocks Modal as a plain div with no Close button. The F2 fix must therefore keep DetailShell's own Close button (with `hideDefaultClose` on Modal) rather than removing it. The review's "pick exactly one Close source (Modal's)" phrasing was slightly ambiguous; `hideDefaultClose` + DetailShell-own-button is the correct single-source pattern.
- The `editing ? () => {} : onClose` guard on onClose in both FeatureDetail and Detail means Modal's Escape handling is already blocked when edit form is active, matching the original `useEffect` guard's semantics.

Out-of-scope findings for next review cycle: F6 (TreeToolbar.tsx toggle placement), F8 (DetailShell unification of waiting bar/edit toggle).
