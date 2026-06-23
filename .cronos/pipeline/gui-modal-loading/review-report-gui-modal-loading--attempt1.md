---
cc_version: "1.0"
agent: pipeline-reviewer
slug: gui-modal-loading--attempt1
phase: review
status: done
confidence: 0.92
inputs_used:
  - memory:GUI Refactor Board Setup
  - memory:gui-tokens-brand RESOLVED
  - memory:gui-layout-primitives review RESOLVED
  - memory:gui-badge-system review RESOLVED
  - memory:gui-button-focus review RESOLVED
  - memory:gui-icons review RESOLVED
  - memory:observation_impl_reverts_sibling_phase
  - memory:observation_reviewer_trusts_stale_impl_report
  - .cronos/pipeline/gui-modal-loading/design-report-gui-modal-loading.md
  - .cronos/pipeline/gui-modal-loading/test-report-gui-modal-loading.md
  - .cronos/pipeline/gui-modal-loading/impl-report-gui-modal-loading--i1.md
  - .cronos/pipeline/gui-modal-loading/impl-report-gui-modal-loading--i2.md
  - .cronos/pipeline/gui-modal-loading/impl-report-gui-modal-loading--i3.md
  - .cronos/pipeline/gui-modal-loading/impl-report-gui-modal-loading--i4.md
  - .cronos/pipeline/gui-modal-loading/impl-report-gui-modal-loading--i5.md
  - .cronos/pipeline/gui-modal-loading/impl-report-gui-modal-loading--i6.md
  - .cronos/pipeline/gui-modal-loading/impl-report-gui-modal-loading--i7.md
  - .cronos/pipeline/gui-modal-loading/impl-report-gui-modal-loading--i8.md
  - .cronos/pipeline/gui-modal-loading/impl-report-gui-modal-loading--i9.md
  - .cronos/pipeline/gui-modal-loading/impl-report-gui-modal-loading--i10.md
  - .cronos/pipeline/gui-modal-loading/impl-report-gui-modal-loading--i11.md
  - frontend/src/components/ui/Modal.tsx
  - frontend/src/components/ui/Skeleton.tsx
  - frontend/src/components/MarkdownEditorModal.tsx
  - frontend/src/components/FileBrowser.tsx
  - frontend/src/components/ToolDetailPanel.tsx
  - frontend/src/components/ViewEditor.tsx
  - frontend/src/components/FeatureDetail.tsx
  - frontend/src/components/FeatureForm.tsx
  - frontend/src/pages/FeaturesPage.tsx
  - frontend/src/pages/DashboardPage.tsx
  - frontend/src/pages/HarnessListPage.tsx
  - frontend/src/index.css
  - frontend/tailwind.config.js
  - frontend/src/components/Card.tsx
outputs_produced:
  - .cronos/pipeline/gui-modal-loading/review-report-gui-modal-loading--attempt1.md
blockers: []
next_consumer: implementation
metrics:
  tool_calls: 32
  files_read: 27
  memory_hits: 8
  diff_lines_reviewed: 4046
verdict: needs_fix
attempt: 1
findings:
  - id: F1
    severity: critical
    file: frontend/src/index.css
    evidence: "ce6e614 diff hunks @ lines 33-58, 66-83, 105-122 delete ALL of: --color-running, --color-success, --color-info, --color-neutral (all 3 themes); --cat-goal/feature/fix/issue/plan/ask (all 3 themes); --brand, --brand-deep, --brand-light. Also reverts --color-warning/danger to pre-brand values and deletes the .text-title utility block (gui-layout-primitives PageHeader spec). Causes 42 new failures in tests/index.css.test.ts (R1/R2/R3/Q1/Q2 suites) — every one passed at parent 68a7515."
    blocking: true
    suggested_action: "Restore the deleted token blocks in frontend/src/index.css to the values present at commit 68a7515 (parent of ce6e614). Use `git show 68a7515:frontend/src/index.css` and re-apply ONLY the I1 additions (shimmer @keyframes + .animate-shimmer utility) on top of that base. Do not touch any unrelated CSS-variable block. Verify with `cd frontend && npx vitest run tests/index.css.test.ts` — all 42 tests must pass."
  - id: F2
    severity: high
    file: frontend/src/components/FeatureDetail.tsx
    evidence: "Not in any iteration scope_files (design report iterations[] union). ce6e614 nonetheless modifies it: removes Badge primitive in favour of inline className spans (e.g. line 117-141 replaces `<Badge tone=...>` with `<span className=\"bg-violet-100 ... dark:bg-violet-400/10 ...\">`); replaces semantic tokens bg-feature/bg-fix with raw bg-emerald-500/bg-rose-500; replaces border-warning/30 bg-warning/10 text-warning with border-amber-300 bg-amber-50 text-amber-700 (lines 256-264). Reverts gui-badge-system and gui-tokens-brand work."
    blocking: true
    suggested_action: "Revert FeatureDetail.tsx to the version at parent commit 68a7515: `git checkout 68a7515 -- frontend/src/components/FeatureDetail.tsx`. If the legitimate intent was only to remove the redundant window.keydown Escape handler and the duplicate ✕ close button (the Modal contract collision flagged in impl-report-i11.md), apply ONLY those two minimal edits — do NOT touch Badge usage, semantic tokens, or styling. Add FeatureDetail.tsx to a follow-up iteration's scope_files if structural Badge/styling changes are still wanted."
  - id: F3
    severity: high
    file: frontend/src/components/FeatureForm.tsx
    evidence: "Not in any iteration scope_files. ce6e614 removes `import { Badge }`, removes `getTonePriority` helper import, replaces the priority-buttons' `<Badge tone={getTonePriority(opt.value)}>{opt.label}</Badge>` with hand-rolled `border-red-200 bg-red-50 text-red-600 dark:...` raw-palette classes (PRIORITY_OPTIONS array lines 7-12). Also drops the type-toggle's `<Badge tone=\"feature\">/<Badge tone=\"fix\">` and replaces with raw `bg-emerald-100/text-emerald-700` and `bg-rose-100/text-rose-700`. Two new failures: tests/no-raw-palette-classes.test.ts > FeatureForm.tsx and > FeatureDetail.tsx."
    blocking: true
    suggested_action: "Revert FeatureForm.tsx via `git checkout 68a7515 -- frontend/src/components/FeatureForm.tsx`. If removal of the duplicate window.keydown Escape and the redundant ✕ Close button (Modal X collision) is required, apply ONLY those two edits and keep Badge + getTonePriority + getTonePriority/Badge tones intact. Add FeatureForm.tsx to a follow-up iteration's scope_files if more is wanted."
  - id: F4
    severity: high
    file: frontend/src/components/MarkdownEditorModal.tsx
    evidence: "I4 dropped the file's own header `<button aria-label=\"Close editor\">` (formerly a Button/IconButton primitive carrying focus-visible ring classes) on the assumption that Modal.tsx's own X button (`aria-label=\"Close\"`) replaces it. Two pre-existing gui-button-focus tests now fail: `MarkdownEditorModal.buttons.test.tsx > close button is a real <button> with aria-label='Close editor'` and `> close button carries focus-visible ring class`. The Modal X button is `aria-label=\"Close\"` (not `\"Close editor\"`) and lives in Modal.tsx, so the assertions on MarkdownEditorModal's own DOM cannot find it."
    blocking: true
    suggested_action: "EITHER (a) keep the file's own `<button aria-label=\"Close editor\">` in the header (calling onClose) and add a `hideDefaultClose` prop to Modal.tsx so the duplicate Modal X button can be suppressed for this caller — this preserves the buttons test contract; OR (b) update the two assertions in src/components/__tests__/MarkdownEditorModal.buttons.test.tsx to match the new Modal-owned close button (aria-label=\"Close\", element lives in Modal.tsx's panel). Either fix is in-scope for a Layer-2/I11 revision; option (a) is preferred because it preserves the existing accessibility contract (named aria-label-per-modal)."
  - id: F5
    severity: medium
    file: frontend/src/components/ui/Modal.tsx:103
    evidence: "Panel className hardcodes `w-full max-w-lg`. Callers cannot widen the panel via the `className` prop because that prop is applied to the scrim, not the panel (per I2 impl-report). Concretely: MarkdownEditorModal lost its pre-migration `max-w-6xl` width (I4 impl-report flags this as medium out-of-scope); FileBrowser FileViewerModal lost its `max-w-4xl` (I5 impl-report flags it). Both are real visual regressions on wide screens for the file/markdown viewer flows. Does NOT cause test failures so it is not blocking on its own, but it is a contract gap the architect intentionally deferred to I11 polish which never addressed it."
    blocking: false
    suggested_action: "Add a `size?: 'sm' | 'md' | 'lg' | 'xl' | '2xl' | '4xl' | '6xl'` prop on Modal.tsx (or a `panelClassName?: string`) and pass through. Update MarkdownEditorModal to pass size=\"6xl\" and FileBrowser FileViewerModal to pass size=\"4xl\". Cover with one Modal.test.tsx case asserting the panel class changes per prop. Strictly scoped to Modal.tsx + Modal.test.tsx (already in I2/I11 scope_files) so this fits a follow-up iteration cleanly."
  - id: F6
    severity: medium
    file: frontend/src/components/ToolDetailPanel.tsx
    evidence: "I7 wraps the slide-over inside `<Modal>` but the slide-over's `fixed inset-y-0 right-0 z-50` escapes Modal's flex-center container while Modal still renders its own X close button (aria-label=\"Close\") at z-[40] behind the slide-over. The Modal X is in the DOM but visually obscured; screen-reader users may find two Close affordances (Modal's and the panel's own \"Close panel\"). I7 impl-report flagged this as low; given that ToolDetailPanel is a slide-over (not a centered dialog), reusing Modal as a scrim+escape shell is a contract-misuse smell rather than a regression. Tests still pass (impl uses aria-label=\"Close panel\" to disambiguate)."
    blocking: false
    suggested_action: "Either add the `hideDefaultClose` prop (see F4) and pass it from ToolDetailPanel, or extract a `<Scrim>` primitive (scrim + Escape + scrim-click only, no panel/X) and let slide-overs use Scrim while centered dialogs continue to use Modal. Both are minor refactors of ui/Modal.tsx (in I2/I11 scope). Defer if F1-F4 keep the loop short."
  - id: F7
    severity: medium
    file: .cronos/pipeline/gui-modal-loading/test-report-gui-modal-loading.md
    evidence: "Test report gate_decision=fail with 663 failed / 836 errored. Inspection shows the vast majority are backend pytest 401-Unauthorized failures (e.g. tests/api/test_features_board.py — 12 tests, tests/api/test_features_create.py — 16 tests, etc.) that look like the fail-closed auth + missing CRONOS_AUTH_DISABLED conftest env from memory:observation_fail_closed_auth_conftest_pattern. None of these tests are in the gui-modal-loading scope (all frontend-only iterations). Tester ran the whole suite and reported a meaningless fail."
    blocking: false
    suggested_action: "For this review the test gate signal is restricted to the frontend suite, which is the only scope this goal touches. Frontend `npm run build` is green at ce6e614 and `npm test` shows 65 failures of which only 45 are new vs parent (and all 45 are tied to F1/F3/F4 above). The backend pytest failures pre-exist this goal and are not caused by it; orchestrator should re-route them to a backend goal. Re-run tester scoped to `frontend/` only after F1-F4 are fixed."
  - id: F8
    severity: low
    file: frontend/src/components/FileBrowser.tsx:188
    evidence: "The list-level isLoading branch still renders `<p>Loading…</p>` (per I5 out_of_scope_findings). R5 only required FileViewerModal Skeleton; the list-level placeholder is technically inconsistent with the brief's \"no plaintext loading text anywhere\" intent but not in any iteration's scope."
    blocking: false
    suggested_action: "Swap the `<p>Loading…</p>` for `<Skeleton variant=\"block\" />` in a follow-up polish iteration (FileBrowser.tsx already in I5 scope; add a one-line change + 1-line test update)."
---

## Summary

The gui-modal-loading commit (ce6e614 on feature/gui-refactor) ships the core deliverables — unified Modal contract (scrim/focus-trap/Escape/dismissable/X), Skeleton primitive (text/block/card + shimmer), and migrations of the four modals plus three page-level loaders. Frontend `npm run build` is green and the 11 scoped iterations land correctly. However, the implementor silently reverted prior sibling-phase work in two distinct, independently blocking ways: (1) I1 stripped the gui-tokens-brand R1/R2/R3 token blocks plus the .text-title utility from index.css (42 new test failures), and (2) the commit modified two out-of-scope files (FeatureDetail.tsx + FeatureForm.tsx) that revert gui-badge-system Badge primitives and gui-tokens-brand semantic tokens back to raw Tailwind palette classes (2 new test failures). A third regression (F4) breaks MarkdownEditorModal.buttons.test.tsx because the file's own `aria-label="Close editor"` button was removed in favour of Modal's `aria-label="Close"`. This is the same anti-pattern documented in memory:observation_impl_reverts_sibling_phase — verdict is needs_fix; the deliverables are sound, the cross-phase damage must be reverted before merge.

## Findings

- F1 (critical, blocking): frontend/src/index.css strips gui-tokens-brand R1/R2/R3 token blocks + .text-title utility (42 new test failures).
- F2 (high, blocking): frontend/src/components/FeatureDetail.tsx scope escape — reverts Badge primitive + semantic tokens to raw palette classes.
- F3 (high, blocking): frontend/src/components/FeatureForm.tsx scope escape — reverts Badge primitive + getTonePriority helper to raw palette classes (2 new test failures).
- F4 (high, blocking): frontend/src/components/MarkdownEditorModal.tsx removes its own `aria-label="Close editor"` button — breaks 2 pre-existing gui-button-focus assertions.
- F5 (medium, non-blocking): Modal.tsx panel hardcodes max-w-lg — MarkdownEditorModal and FileViewerModal lose their pre-migration widths.
- F6 (medium, non-blocking): ToolDetailPanel slide-over nests inside Modal, leaving Modal's X button in the DOM behind the slide-over.
- F7 (medium, non-blocking): test-report-gui-modal-loading.md gate_decision=fail is dominated by unrelated backend 401-Unauthorized failures; new frontend-only regressions are limited to F1/F3/F4.
- F8 (low, non-blocking): FileBrowser.tsx:188 list-level `<p>Loading…</p>` not migrated to Skeleton (out of I5 scope).

## Verdict

needs_fix. F1–F4 are blocking sibling-phase regressions and scope escapes; revert the affected non-scope edits and restore the stripped index.css tokens, then re-spawn the implementor for a targeted attempt-2 pass.

## Assumptions

- Scope contract taken from `iterations[].scope_files[]` union in design-report-gui-modal-loading.md.
- Worktree at /data/spaces/cronos-development/.cronos/workspaces/2026-06-22-1335-impl-gui-tokens-brand was dirty at start; stashed unrelated changes (saved as stash@{0}, popped after build/test) so all build/test results below reflect the clean commit tip ce6e614.
- `npm run build` at ce6e614: exit 0 (vite build 14.35s, 2791 modules transformed, no TS errors).
- `npm test` at ce6e614: 65 failed / 1607 passed (1672 total). Baseline at parent 68a7515: 59 failed / 1613 passed. Pure new-failure delta attributable to ce6e614 = 45 tests (see comm -13 diff captured in /tmp).
- The "Card.buttons" failures present in both 68a7515 and ce6e614 are pre-existing (gui-icons commit 68a7515 reverted the gui-button-focus df59946 Card body button conversion). Not in scope for this review.
- Backend pytest failures in test-report-gui-modal-loading.md (663 failed / 836 errored, mostly 401-Unauthorized) are environment-driven and unrelated to a frontend-only goal; the orchestrator should re-route the backend test failures separately.

## Open questions

- None.

## Next consumer brief

Implementor: re-run iteration scope for attempt 2, addressing F1–F4 (all blocking). Concrete plan:

1. F1 fix: `git checkout 68a7515 -- frontend/src/index.css` then re-apply ONLY the I1 additions (shimmer @keyframes + .animate-shimmer utility) on top. Verify `npx vitest run tests/index.css.test.ts` is green.
2. F2 fix: `git checkout 68a7515 -- frontend/src/components/FeatureDetail.tsx`. If the Modal-X collision still bites, remove ONLY the redundant window.keydown Escape effect and the inline ✕ button — preserve Badge/semantic-token usage and structural styling.
3. F3 fix: same pattern on frontend/src/components/FeatureForm.tsx (revert + minimal Modal-X cleanup only).
4. F4 fix: pick option (a) — re-add the file's own `<button aria-label="Close editor">` to MarkdownEditorModal.tsx's header (calls onClose; carries focus-visible ring) AND add a `hideDefaultClose?: boolean` prop to Modal.tsx so the duplicate Modal X is suppressed for this caller. Update I2's Modal.test.tsx with one assertion that hideDefaultClose=true hides the X.
5. Re-run the I11 integration gate: `cd frontend && npm run build && npm test`. New-failure delta vs parent must be zero (45 → 0).
6. Do NOT touch any file not enumerated above. F5/F6/F8 are deferred polish; document them in an out-of-scope-findings list for the next review cycle.

Branch stays feature/gui-refactor; rebase is NOT needed (parent is unchanged). Commit message: `fix(gui): resolve gui-modal-loading review findings (F1-F4)`.
