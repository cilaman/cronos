---
cc_version: "1.0"
agent: pipeline-reviewer
slug: gui-detail-ux--attempt2
phase: review
status: done
confidence: 0.9
inputs_used:
  - memory:project_gui_refactor_board_setup
  - memory:project_gui_polish_review_resolved
  - memory:observation_reviewer_trusts_stale_impl_report
  - memory:project_pipeline_reviewer_agent
  - .cronos/pipeline/gui-detail-ux/design-report-gui-detail-ux.md
  - .cronos/pipeline/gui-detail-ux/review-report-gui-detail-ux--attempt1.md
  - .cronos/pipeline/gui-detail-ux/impl-report-gui-detail-ux--i9.md
  - .cronos/pipeline/gui-detail-ux/test-report-gui-detail-ux.md
  - frontend/src/components/ui/DetailShell.tsx
  - frontend/src/components/FeatureDetail.tsx
  - frontend/src/components/Detail.tsx
  - frontend/tests/no-raw-palette-classes.test.ts
outputs_produced:
  - .cronos/pipeline/gui-detail-ux/review-report-gui-detail-ux--attempt2.md
blockers: []
next_consumer: doc
metrics:
  tool_calls: 18
  files_read: 8
  memory_hits: 4
  diff_lines_reviewed: 1650
verdict: pass
attempt: 2
findings:
  - id: F6
    severity: low
    file: frontend/src/components/TreeToolbar.tsx
    evidence: "I7 design scope_files lists TreePage.tsx + TreeView.tsx + TreeToolbar.test.tsx; actual diff modifies TreeToolbar.tsx instead (TreePage.tsx unchanged). Disclosed by I9 out_of_scope_findings[0] as an intentional I7 placement choice (toolbar toggle naturally lives in the toolbar component). Non-blocking: substantively equivalent, test file in scope still covers the behavior."
    blocking: false
    suggested_action: "No code change required. Doc-sync should note in the changelog that the Tree/DAG toggle lives in TreeToolbar.tsx rather than TreePage.tsx."
  - id: F7
    severity: low
    file: frontend/src/components/__tests__/DetailPRSection.test.tsx
    evidence: "I8 modified DetailPRSection.test.tsx (+12/-0 mock-fix for useLiveStream/EventSource JSDOM gap) outside any iteration's scope_files. Disclosed by I9 out_of_scope_findings[1]; the change itself is test-only and uniform. No build/runtime impact."
    blocking: false
    suggested_action: "No code change required. Architect can absorb into a one-line scope addendum for I8 if a strict scope contract is desired for future review chains."
  - id: F8
    severity: low
    file: frontend/src/components/ui/DetailShell.tsx
    evidence: "Design body mentioned DetailShell could own 'amber waiting bar (WAITING)' + 'edit-mode toggle' as part of the shared shell; committed DetailShell renders neither — these stay inline in Detail.tsx and FeatureDetail.tsx as headerActions consumers. Disclosed by I9 out_of_scope_findings[2] as a deliberate deferred deviation (prop-surface expansion judged unworth the refactor cost)."
    blocking: false
    suggested_action: "No code change required. Doc-sync should note the deviation so future readers don't expect a unified waiting bar slot inside DetailShell."
---

## Summary

All four attempt-1 blocking findings (F1, F2, F3, F4, F5) are resolved at fix-tip 2f4144c. Verified independently against the committed tree (not the impl-report claims): `npm run build` exits 0 (tsc + vite clean); `tests/no-raw-palette-classes.test.ts` is 10/10 green; FeatureDetail.test.tsx + Detail.test.tsx are 56/56 green; full vitest run shows exactly the 5 pre-existing failing files (Card.test.tsx, Card.buttons.test.tsx, MarkdownEditorModal.buttons.test.tsx, SpaceFilterDropdown.buttons.test.tsx, ViewPicker.buttons.test.tsx) with 19 pre-existing failures, and ZERO new regressions vs. parent a3fb5ed. Toast.tsx and ToastProvider.test.tsx are deleted from the tree; DetailShell passes `hideDefaultClose` to Modal and owns its single Close button; redundant Escape useEffect handlers are gone from both detail components and the editing guard is preserved via `onClose={editing ? () => {} : onClose}`; raw palette classes in Detail.tsx and FeatureDetail.tsx are replaced with semantic tokens (`danger`, `warning`, `accent`, `surface-*`, `bg-warning/10`, etc.), with the regex's `(?<![:\w])` negative lookbehind correctly excluding remaining `dark:` prefixed palette utilities. Carry-forward F6/F7/F8 from attempt 1 are kept as non-blocking with explicit non-blocking rationales; no new findings introduced.

## Findings

- F6 — TreeToolbar.tsx scope substitution disclosed by I9; non-blocking (low).
- F7 — DetailPRSection.test.tsx mock-fix scope escape disclosed by I9; non-blocking (low).
- F8 — DetailShell does not own waiting bar / edit toggle (design body deviation); disclosed by I9; non-blocking (low).
- F1, F2, F3, F4, F5 — RESOLVED, not carried forward.

## Verdict

pass. All four blocking findings from attempt 1 are independently verified resolved at 2f4144c; build is clean and no new frontend regressions vs. parent baseline a3fb5ed.

## Assumptions

- The 5 pre-existing failing test files identified in the prompt as out-of-scope (Card.test.tsx, Card.buttons.test.tsx, MarkdownEditorModal.buttons.test.tsx, SpaceFilterDropdown.buttons.test.tsx, ViewPicker.buttons.test.tsx) are pre-existing gui-button-focus / gui-polish technical debt that pre-dates this goal and are not gated by this review.
- The test-phase test-report is dominated by backend-401 auth noise and is not the frontend signal; verification was done by running `npm run build` + targeted vitest + full vitest against the committed fix-tip 2f4144c inside the `2026-06-22-1335-impl-gui-tokens-brand` worktree (confirmed clean at the correct commit).
- The `tests/no-raw-palette-classes.test.ts` regex uses `(?<![:\w])` to explicitly exclude `dark:`/`hover:`-prefixed palette utilities; remaining `dark:bg-amber-300` style classes in Detail.tsx/FeatureDetail.tsx are intentional dark-mode state variants, not raw-palette regressions.
- Scope contract for this review is the union of `iterations[].scope_files[]` from the design report; F6/F7 substitutions are accepted as non-blocking because they are substantively equivalent and explicitly disclosed in I9's out_of_scope_findings[].
- F2 was resolved via `hideDefaultClose` on Modal + retain DetailShell's own ✕ (rather than removing DetailShell's button). This is functionally a single Close source per the F2 rationale; Detail.test.tsx mocks Modal as a plain div, so keeping DetailShell's button was required for both test surfaces to remain green.

## Open questions

- None.

## Next consumer brief

Doc-sync: this goal lands a shared `DetailShell` primitive plus three feature-area updates.

- `frontend/src/components/ui/DetailShell.tsx` is the new shared shell — `variant: 'task' | 'feature'`, Modal-wrapped, owns its own Close button (Modal receives `hideDefaultClose`); supports `headerActions` and `footer` slots, plus loading skeleton and error+retry. Used by both Detail and FeatureDetail.
- `frontend/src/components/Detail.tsx` — adopts DetailShell, gains the two-pane workspace layout (`h-full min-h-0` contract), adds the sticky NOW running card for active tasks (with a copied-in SVG asset at `frontend/src/assets/cronos-state-active-animated.svg`), and replaces raw palette classes with semantic tokens.
- `frontend/src/components/FeatureDetail.tsx` — adopts DetailShell, drops local skeleton/header markup, replaces raw palette classes with semantic tokens.
- `frontend/src/components/TreeNode.tsx` — compact row markup + connector lines; dnd-kit useSortable wiring and GapZone preserved.
- `frontend/src/components/TreeToolbar.tsx` + `TreeView.tsx` — Tree/DAG toggle button in the toolbar (TreePage.tsx unchanged — see F6 disclosure).
- Mobile breakpoint is `md:` (768px) across the two-pane layout and mobile tab bar.

Three non-blocking deviations were disclosed and merit a doc-sync note: (a) toggle button is in TreeToolbar.tsx rather than TreePage.tsx (F6), (b) DetailShell does NOT own the waiting bar or edit toggle (those stay inline in Detail/FeatureDetail) (F8), (c) I8 added a mock to DetailPRSection.test.tsx as a test-only fix (F7). No follow-up implementation work required.
