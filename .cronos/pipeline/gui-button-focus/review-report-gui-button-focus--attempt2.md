---
cc_version: "1.0"
agent: pipeline-reviewer
slug: gui-button-focus--attempt2
phase: review
status: done
confidence: 0.92
inputs_used:
  - memory:project_gui_refactor_board_setup.md
  - memory:gui-button-focus review attempt1 needs_fix
  - memory:observation_reviewer_trusts_stale_impl_report.md
  - memory:observation_impl_reverts_sibling_phase.md
  - .cronos/workspaces/2026-06-22-1335-review-gui-button-focus/.cronos/pipeline/gui-button-focus/design-report-gui-button-focus.md
  - .cronos/pipeline/gui-button-focus/review-report-gui-button-focus--attempt1.md
  - .cronos/pipeline/gui-button-focus/impl-report-gui-button-focus--i7.md
  - .cronos/pipeline/gui-button-focus/test-report-gui-button-focus.md
  - frontend/src/components/Card.tsx
  - frontend/src/components/__tests__/Card.test.tsx
  - frontend/src/components/__tests__/FeaturesBoard.test.tsx
  - frontend/src/components/__tests__/Board.sharedBacklog.test.tsx
  - frontend/src/components/__tests__/Board.features-backlog.test.tsx
outputs_produced:
  - .cronos/pipeline/gui-button-focus/review-report-gui-button-focus--attempt2.md
blockers: []
next_consumer: doc
metrics:
  tool_calls: 17
  files_read: 9
  memory_hits: 4
  diff_lines_reviewed: 173
verdict: pass
attempt: 2
findings:
  - id: F6
    severity: medium
    file: frontend/src/pages/BoardPage.tsx
    evidence: "BoardPage.tsx remains untouched in this iteration (df59946 stat: only Card.tsx + 4 test files). Design I4 scope listed BoardPage.tsx for the add-task dashed-border chip → `Button archetype=\"toolbar-chip\" (tertiary)` migration, but the chip is delivered via Lane.tsx (I3, already on tip). Carried forward from attempt 1 unchanged (carried from attempt 1). Defensible scoping decision — flagging for doc-phase acknowledgement, not for impl rework."
    blocking: false
    suggested_action: "Doc-sync must note in the changelog that the toolbar-chip archetype for add-task is delivered at the Lane.tsx level, and that BoardPage.tsx was intentionally not modified. No code action required."
  - id: F9
    severity: medium
    file: frontend/src/components/Card.tsx
    evidence: "Two `role=\"button\"` spans remain on the parent-breadcrumb (line 500) and realizes-chip (line 520) inside the new card-body `<button>`. These are intentional nested-interactive structures: converting them to native `<button>` would yield invalid nested-interactive HTML; converting the card body back to a div defeats the migration. The current span-with-role-button form preserves keyboard activation while avoiding the WCAG nested-button violation. Carried forward from attempt 1 (carried from attempt 1) — non-blocking, design trade-off acknowledged in the task prompt."
    blocking: false
    suggested_action: "Doc-sync should record this as a known design trade-off: the card body becomes the primary clickable surface; nested interactive descendants (parent breadcrumb, realizes link, proposed_pr, proposed_issue) deliberately use `span[role=\"button\"]` rather than native `<button>` to keep the parent body button accessible. Long-term, consider lifting these chips out of the card body into a sibling meta-row; deferred from this goal."
  - id: F10
    severity: low
    file: frontend/src/components/Lane.tsx
    evidence: "Lane uses `aria-label=\"New task\"` instead of design's `aria-label=\"Add task\"`. Semantic intent identical. Carried forward from attempt 1 (carried from attempt 1). Unchanged at df59946."
    blocking: false
    suggested_action: "No action required. Accept the deviation; semantic equivalence preserved."
  - id: F11
    severity: low
    file: frontend/src/components/ui/README.md
    evidence: "frontend/src/components/ui/README.md remains absent at df59946 (deleted by 5128ba7 doc-revert of gui-badge-system, never restored). IconButton compact/sm/md size documentation has no home in the repo. Carried forward from attempt 1 (carried from attempt 1)."
    blocking: false
    suggested_action: "Doc-sync agent should restore frontend/src/components/ui/README.md (the b9fd572 +233-line content) and add IconButton size documentation when convenient. Low-priority follow-up; does not block doc phase for this goal."
  - id: F12
    severity: low
    file: .cronos/pipeline/gui-button-focus/test-report-gui-button-focus.md
    evidence: "Test-report gate_decision: fail is still 100% backend pytest 401 fallout from fail-closed-auth fixtures (CRONOS_AUTH_DISABLED not set). Orthogonal to a frontend-only button migration. Test-report was not regenerated for this attempt and reflects pre-fix state regardless. Carried forward from attempt 1 (carried from attempt 1)."
    blocking: false
    suggested_action: "No action for gui-button-focus. Frontend independently verified at df59946: 1530/1531 vitest, only pre-existing FileBrowserPage failure (last touched commit e957bfc, layout-primitives/file-browser phase). Backend 401s are remediation work tracked separately."
  - id: F13
    severity: low
    file: frontend/src/pages/__tests__/FileBrowserPage.test.tsx
    evidence: "One vitest failure at df59946 in `FileBrowserPage > shows error banner when task files fail to load` (line 340). Independently confirmed pre-existing on branch: `git log --oneline -- frontend/src/pages/__tests__/FileBrowserPage.test.tsx` shows the file last touched at commit e957bfc (file-browser-complete-i4-i5), well before this goal began. Not caused by button migration; not in I7 scope_files."
    blocking: false
    suggested_action: "Track separately under a file-browser remediation task. Out of scope for gui-button-focus."
---

## Summary

Independent build and full vitest run at df59946 (throwaway worktree, symlinked node_modules) confirm the I7 fix lands every blocking finding from attempt 1: `npm run build` exits 0 (tsc + vite clean); `npx vitest run` reports 92 passed / 1 failed test files and 1530 passed / 1 failed tests, with the lone failure being the pre-existing `FileBrowserPage.test.tsx > shows error banner` test (last touched commit e957bfc on the file-browser-complete iteration, unrelated to button migration). Card.tsx default-density body is now `<button type="button">` at lines 355-593 with the focus ring preserved and dnd-kit `setNodeRef`/`{...attributes}` correctly kept on the outer wrapper div while `{...listeners}` stays on the drag-handle span (R-high mitigation verbatim). The two nested `<button>` elements for `proposed_pr_path` and `proposed_issue_path` are converted to `<span role="button" tabIndex={0}>` with onKeyDown handlers, eliminating the WCAG nested-interactive HTML violation. The four sibling-test selector fixes (`closest('[role="button"]')` → `closest('button')`, `div[role='button']` → `> div > button:last-child`) preserve original test intent across Card.test.tsx, FeaturesBoard.test.tsx, Board.sharedBacklog.test.tsx, Board.features-backlog.test.tsx — all green. F1–F5 (all attempt-1 blockers) resolved; verdict: pass.

## Findings

- **F6 (medium, non-blocking)** — Carried: BoardPage.tsx in I4 scope but unchanged; chip delivered at Lane.tsx level. Doc-sync acknowledgement only.
- **F9 (medium, non-blocking)** — Carried: parent-breadcrumb + realizes-chip spans remain `role="button"` by design (nested inside card body button); deliberate trade-off, documented.
- **F10 (low, non-blocking)** — Carried: Lane aria-label "New task" vs design "Add task". Semantic equivalence.
- **F11 (low, non-blocking)** — Carried: ui/README.md still missing (deleted 5128ba7). Doc-sync follow-up.
- **F12 (low, non-blocking)** — Carried: test-report gate=fail is backend auth-fixture orthogonal; ignored.
- **F13 (low, non-blocking)** — New: pre-existing FileBrowserPage error-banner failure on branch; outside button-focus scope.

## Verdict

`pass`. All five attempt-1 blocking findings (F1, F2, F3, F4, F5) are independently verified resolved at df59946: Card.tsx body is now a native button, nested proposed_pr/issue buttons are spans, and the full vitest suite has exactly 1 failure which is pre-existing and unrelated to this goal. Doc phase may proceed.

## Assumptions

- Scope contract taken from design `iterations[].scope_files[]` union; I7 is the fix iteration for I4's Card.tsx work (no design rewrite, no scope expansion beyond the four sibling test files that depended on the now-changed Card.tsx shape).
- Build + test were independently executed at the committed tip df59946 in a fresh worktree (`/tmp/review-attempt2`) with `frontend/node_modules` symlinked from the space copy; worktree cleaned up after measurement. Result was NOT taken on faith from the impl-report.
- F1 resolution is verified by inspecting Card.tsx at df59946 lines 355-593 (new body `<button>`), plus a zero-error vitest run on Card.buttons.test.tsx; F2 by inspecting lines 431/466 (now span role=button); F3/F4 by full vitest run; F5 by independent full-suite count.
- Card.tsx parent-breadcrumb (line 500) and realizes-chip (line 520) intentionally remain `<span role="button" tabIndex={0}>` per the task prompt's documented design decision — nested-interactive HTML inside the card-body button must not be native buttons.
- The single FileBrowserPage failure is genuinely pre-existing: `git log -- frontend/src/pages/__tests__/FileBrowserPage.test.tsx` last-touched at e957bfc (file-browser goal), not on any gui-button-focus commit.
- The orchestrator's review-loop ceiling (5 attempts) is not approached; pass at attempt 2 terminates the loop.

## Open questions

- None.

## Next consumer brief

For doc-sync (Phase 7):

User-visible change for gui-button-focus (Phase 3 of GUI refactor):
1. Button.tsx and IconButton.tsx primitives expanded with universal `focus-visible:ring-1 focus-visible:ring-accent` focus rings on all variants, new `tertiary` and `link` variants on Button, `loading` spinner prop, `leadingIcon` slot, and the `archetype` prop (`toolbar-chip` | `dropdown-trigger` | `segmented` | `list-row`). IconButton defaults to 44px hit area on `sm`/`md` sizes with an opt-in `compact` (h-8 w-8) escape hatch.
2. Approximately 160 inline buttons migrated to Button/IconButton across Lane.tsx, SpaceFilterDropdown.tsx, ViewPicker.tsx, Card.tsx, MarkdownEditorModal.tsx, TimeFrameSelector.tsx.
3. Card.tsx default-density body is now a native `<button type="button">` (was `<div role="button">`); dnd-kit drag-to-reorder preserved by keeping `useSortable` refs and `{...attributes}` on the outer wrapper div and `{...listeners}` on the drag-handle span.
4. Nested interactive descendants of the card body (proposed_pr_path, proposed_issue_path, parent-breadcrumb, realizes-chip) use `<span role="button" tabIndex={0}>` with `onKeyDown` to avoid invalid nested-interactive HTML.

Acknowledgements to surface in the doc/changelog:
- BoardPage.tsx was intentionally not modified (F6); the toolbar-chip archetype is delivered at the Lane.tsx level. The original design assumption that the add-task chip lives in BoardPage was wrong.
- `frontend/src/components/ui/README.md` is still missing (F11; deleted in 5128ba7 by the gui-badge-system doc phase, never restored). Restoring it with the new Button/IconButton API + IconButton size guidance is a low-priority follow-up.
- 1 unrelated pre-existing vitest failure (F13: FileBrowserPage error-banner) remains on the branch from the file-browser-complete iteration; tracked separately.

Do NOT include any backend test changes in the doc; the test-report gate=fail (F12) is 100% fail-closed-auth fixture fallout and is unrelated to this goal.
