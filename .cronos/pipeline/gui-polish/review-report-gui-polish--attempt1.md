---
cc_version: "1.0"
agent: pipeline-reviewer
slug: gui-polish--attempt1
phase: review
status: done
confidence: 0.88
inputs_used:
  - memory:project_gui_refactor_board_setup
  - memory:project_gui_modal_loading_review_resolved
  - .cronos/pipeline/gui-polish/design-report-gui-polish.md
  - .cronos/pipeline/gui-polish/impl-report-gui-polish--i1.md
  - .cronos/pipeline/gui-polish/impl-report-gui-polish--i2.md
  - .cronos/pipeline/gui-polish/impl-report-gui-polish--i3.md
  - .cronos/pipeline/gui-polish/impl-report-gui-polish--i4.md
  - .cronos/pipeline/gui-polish/impl-report-gui-polish--i5.md
  - .cronos/pipeline/gui-polish/impl-report-gui-polish--i6.md
  - .cronos/pipeline/gui-polish/impl-report-gui-polish--i7.md
  - .cronos/pipeline/gui-polish/test-report-gui-polish.md
  - frontend/src/components/ui/Toast.tsx
  - frontend/src/components/ui/ToastProvider.tsx
  - frontend/src/components/ui/useToast.ts
  - frontend/src/components/ui/IconButton.tsx
  - frontend/src/components/ui/Modal.tsx
  - frontend/src/components/ui/Tabs.tsx
  - frontend/src/components/ui/Dropdown.tsx
  - frontend/src/components/ui/Tooltip.tsx
  - frontend/src/components/ui/StatTile.tsx
  - frontend/src/components/ui/ProgressBar.tsx
  - frontend/src/components/ui/EmptyState.tsx
  - frontend/src/components/Lane.tsx
  - frontend/src/components/Detail.tsx
  - frontend/src/components/Card.tsx
  - frontend/src/components/MarkdownEditorModal.tsx
  - frontend/src/components/SpaceFilterDropdown.tsx
  - frontend/src/components/ViewPicker.tsx
  - frontend/src/App.tsx
  - frontend/src/__tests__/App.test.tsx
  - frontend/src/pages/DashboardPage.tsx
  - frontend/src/pages/StatsPage.tsx
  - frontend/src/pages/SpaceToolsPage.tsx
  - frontend/src/components/ui/__tests__/IconButton.test.tsx
  - frontend/src/components/ui/__tests__/Modal.test.tsx
  - frontend/src/components/__tests__/Lane.test.tsx
  - frontend/src/components/__tests__/Detail.test.tsx
  - frontend/src/components/__tests__/Card.test.tsx
  - frontend/src/components/__tests__/Board.features-backlog.test.tsx
  - frontend/src/components/__tests__/Board.sharedBacklog.test.tsx
  - frontend/src/components/__tests__/FeaturesBoard.test.tsx
  - frontend/src/pages/__tests__/SpaceToolsPage.test.tsx
  - frontend/src/pages/__tests__/StatsPage.test.tsx
outputs_produced:
  - .cronos/pipeline/gui-polish/review-report-gui-polish--attempt1.md
blockers: []
next_consumer: doc
metrics:
  tool_calls: 35
  files_read: 41
  memory_hits: 2
  diff_lines_reviewed: 2767
verdict: pass
attempt: 1
findings:
  - id: F1
    severity: low
    file: frontend/src/components/Lane.tsx:107
    evidence: "EmptyState rendered as `<EmptyState title=\"No tasks\" />` — design Components section says Lane.tsx \"uses EmptyState primary action slot\". I7 added the `action` prop to EmptyState and tests it, but Lane.tsx itself does not pass `action={{ label: '+ New task', onClick: onAdd }}`. I7 documented the deferral in Assumptions (Lane.test.tsx's singular `getByRole(\"button\", { name: /New task/i })` would throw on a second matching button)."
    blocking: false
    suggested_action: "Either (a) wire `action={{ label: '+ New task', onClick: onAdd }}` on Lane's EmptyState and tighten the affected Lane test to scope by container, or (b) accept the deferral and remove the \"primary action slot\" language from a future design doc. Low priority — primitive is shipped and tested, only the Lane callsite is unwired."
  - id: F2
    severity: low
    file: frontend/src/components/Card.tsx:352
    evidence: "Out-of-scope edit: Card body converted from `<div role=\"button\" tabIndex={0} onKeyDown=…>` to a native `<button type=\"button\">`. Companion test-file changes in Board.features-backlog.test.tsx, Board.sharedBacklog.test.tsx, FeaturesBoard.test.tsx, Card.test.tsx switch selectors from `closest('[role=\"button\"]')` to `closest('button')`. The change is identical in spirit to the gui-button-focus I7 conversion (commit df59946) and is wired safely (proposed_pr_path icon switched to `span[role=button]` to preserve nested-button HTML validity)."
    blocking: false
    suggested_action: "Acknowledge as appropriate accessibility hardening that landed under gui-polish even though Card.tsx is not in the design `scope_files`. No code change required — flag for the doc agent so the change is mentioned in the changelog hook."
  - id: F3
    severity: low
    file: frontend/src/components/SpaceFilterDropdown.tsx:51
    evidence: "Out-of-scope edits to SpaceFilterDropdown.tsx, ViewPicker.tsx, and MarkdownEditorModal.tsx add `focus:outline-none focus-visible:ring-1 focus-visible:ring-accent` to 6 interactive button classNames. These are pure a11y improvements (matching the project-wide focus-ring convention from gui-button-focus) and do not change behavior, but they are not in any iteration's `scope_files`."
    blocking: false
    suggested_action: "Acknowledge as appropriate a11y hardening; no code change required. Consider listing in a future scope_files when polish-class focus-ring additions are planned."
  - id: F4
    severity: low
    file: frontend/src/pages/SpaceToolsPage.tsx:487
    evidence: "Pill-style tab switcher replaced by underline-style `<Tabs>` primitive. The design Components section calls this out explicitly (\"inline tabs replaced by Tabs.tsx where present\"), and I5 documents the visual-style change in its Next consumer brief. Visual delta is intentional design-system unification, not regression."
    blocking: false
    suggested_action: "No code change required. Flag for the doc agent so the SpaceTools visual change is mentioned in the user-facing changelog."
---

## Summary

The gui-polish committed implementation (`ca21f22` on `feature/gui-refactor`) lands all five exit-criteria deliverables: (1) Touch targets — IconButton (sm/md), Modal close, and Lane +/× use the wrapper-span pattern with `min-h-[44px] min-w-[44px] place-content-center`, with dedicated tests asserting the wrapper dimensions; (2) Toast system — `Toast.tsx` + `ToastProvider.tsx` + `useToast.ts` render an `aria-live="polite"` container, auto-dismiss (default 4s), four tone variants, optional action button, no focus steal, no-op default outside provider; mounted in App.tsx with a smoke test; (3) Five utility primitives — `Tabs.tsx`, `Dropdown.tsx` (z-[20]), `Tooltip.tsx` (z-[60]), `StatTile.tsx`, `ProgressBar.tsx` — created in isolation per the layer-split strategy and then migrated into Detail.tsx + SpaceToolsPage.tsx + DashboardPage.tsx + StatsPage.tsx; (4) EmptyState gained an optional `action` prop with 13 tests; (5) `npm run build` and the full vitest suite (116 files / 1825 tests) are green on the committed tip — independently re-verified in this review worktree. The test-report's `gate_decision: fail` is entirely backend pytest auth noise (401 Unauthorized from the recently-merged fail-closed-auth conftest requirement) unrelated to this frontend-only goal; documented in the report's Assumptions. Scope discipline is mostly clean: four out-of-scope edits (Card.tsx role-button→button conversion, SpaceFilterDropdown / ViewPicker / MarkdownEditorModal focus-ring additions) are all minor accessibility hardening with companion test fixes; recorded as low-severity non-blocking findings F2–F4. F1 records the only design-vs-impl divergence (Lane EmptyState `action` slot consciously unwired by I7 to preserve Lane test assertion shape; primitive itself ships and is tested).

## Findings

- F1 (low, non-blocking): Lane.tsx's EmptyState does not pass the new `action` prop despite the design Components section mentioning it.
- F2 (low, non-blocking): Card.tsx role-button → native button conversion is out of design `scope_files` but is correct accessibility hardening with companion test selector fixes.
- F3 (low, non-blocking): Focus-ring additions on SpaceFilterDropdown / ViewPicker / MarkdownEditorModal are out of scope but are pure a11y polish.
- F4 (low, non-blocking): SpaceToolsPage tab-switcher visual style change (pill → underline) is design-intended unification, called out by I5; no regression.

## Verdict

pass

All five goal exit criteria are met on the committed tip `ca21f22`; the frontend build and the full 1825-test vitest suite pass; out-of-scope edits are minor accessibility polish with test fixes, not scope creep. Backend test-report failures are pre-existing auth-conftest noise unrelated to this frontend-only goal.

## Assumptions

- The orchestrator-verified state of the `feature/gui-refactor` tip at `ca21f22` matches the files on disk in this review worktree — independently confirmed by inspecting `git show ca21f22:<file>` for every committed source under review and by running `npm run build` (clean) and `npm test` (116 files / 1825 pass) in this worktree.
- Backend pytest failures reported by `test-report-gui-polish.md` (663f / 836e / coverage 50.5%) are pre-existing fail-closed-auth conftest gaps from `feature/cronos-remediation-plan` (recently merged); they are not gui-polish regressions and the gui-polish diff touches zero backend code.
- Scope contract is the union of `iterations[].scope_files` in `design-report-gui-polish.md`.
- The `extractDetail()` helper in Detail.tsx (renders `JSON.parse(...).detail` or falls back to raw message) is the canonical user-voiced error path; no raw `Error: {message}` prefix is rendered.

## Open questions

- None.

## Next consumer brief

Doc agent: this pipeline introduces (1) a new Toast system available as `useToast()` from `frontend/src/components/ui/useToast.ts`, mounted globally in `App.tsx`, with four tones (`success | warning | danger | info`), optional action button, 4-second auto-dismiss, and no-op default outside provider; (2) five new shared UI primitives — `Tabs`, `Dropdown` (z-[20]), `Tooltip` (z-[60]), `StatTile`, `ProgressBar` — all in `frontend/src/components/ui/`; (3) WCAG 2.5.5 (44 × 44 px) touch targets on IconButton sm/md, Modal close, and Lane +/× via outer wrapper spans (visual button size unchanged); (4) Detail.tsx and SpaceToolsPage.tsx now use the new `Tabs` primitive — SpaceToolsPage's tab switcher changes visual style from filled-pill to active-underline (intentional design-system unification); (5) Dashboard and Stats inline stat blocks now use the shared `StatTile`; (6) `EmptyState` accepts an optional `action: { label, onClick }` prop. Out-of-scope hardening also landed: Card body became a native button (with test selector updates), and three components gained focus-ring classes. No backend changes.

STATUS: REVIEW=pass attempt=1
