---
cc_version: "1.0"
agent: pipeline-reviewer
slug: gui-detail-ux--attempt1
phase: review
status: done
confidence: 0.9
inputs_used:
  - memory:project_gui_refactor_board_setup
  - memory:project_gui_polish_review_resolved
  - memory:observation_reviewer_trusts_stale_impl_report
  - memory:project_pipeline_reviewer_agent
  - .cronos/pipeline/gui-detail-ux/design-report-gui-detail-ux.md
  - .cronos/pipeline/gui-detail-ux/impl-report-gui-detail-ux--i1.md
  - .cronos/pipeline/gui-detail-ux/impl-report-gui-detail-ux--i2.md
  - .cronos/pipeline/gui-detail-ux/impl-report-gui-detail-ux--i3.md
  - .cronos/pipeline/gui-detail-ux/impl-report-gui-detail-ux--i4.md
  - .cronos/pipeline/gui-detail-ux/impl-report-gui-detail-ux--i5.md
  - .cronos/pipeline/gui-detail-ux/impl-report-gui-detail-ux--i6.md
  - .cronos/pipeline/gui-detail-ux/impl-report-gui-detail-ux--i7.md
  - .cronos/pipeline/gui-detail-ux/impl-report-gui-detail-ux--i8.md
  - .cronos/pipeline/gui-detail-ux/test-report-gui-detail-ux.md
  - frontend/src/components/ui/DetailShell.tsx
  - frontend/src/components/Detail.tsx
  - frontend/src/components/FeatureDetail.tsx
  - frontend/src/components/TreeNode.tsx
  - frontend/src/components/TreeView.tsx
  - frontend/src/components/TreeToolbar.tsx
  - frontend/src/pages/TreePage.tsx
  - frontend/src/components/ui/Modal.tsx
  - frontend/src/components/ui/__tests__/ToastProvider.test.tsx
  - frontend/src/components/__tests__/FeatureDetail.test.tsx
outputs_produced:
  - .cronos/pipeline/gui-detail-ux/review-report-gui-detail-ux--attempt1.md
blockers: []
next_consumer: implementation
metrics:
  tool_calls: 45
  files_read: 22
  memory_hits: 4
  diff_lines_reviewed: 3140
verdict: needs_fix
attempt: 1
findings:
  - id: F1
    severity: high
    file: frontend/src/components/ui/__tests__/ToastProvider.test.tsx
    evidence: "ToastProvider.test.tsx imports `ToastProvider` from '../ToastProvider' and `useToast` from '../useToast' — neither module exists in the committed tree (`git ls-tree ddf639e frontend/src/components/ui/` only lists Toast.tsx). Result: `npm run build` FAILS with TS2307 'Cannot find module'; `npx vitest run` FAILS to load this test file (0 tests collected). The I8 impl-report's claim 'npm run build exits 0' and '1358/1359 pass' is FALSE on the committed code."
    blocking: true
    suggested_action: "Either (a) DELETE `frontend/src/components/ui/Toast.tsx` and `frontend/src/components/ui/__tests__/ToastProvider.test.tsx` from the tree (both are scope-escapes resurrected from gui-polish that doc-gui-polish (a3fb5ed) intentionally deleted along with ToastProvider.tsx / useToast.ts / Toast.test.tsx), or (b) ADDITIONALLY restore `frontend/src/components/ui/ToastProvider.tsx` and `frontend/src/components/ui/useToast.ts` so the test file resolves. Option (a) is correct given gui-detail-ux scope; option (b) is out-of-scope work that requires architect approval. Recommended: option (a)."
  - id: F2
    severity: high
    file: frontend/src/components/ui/DetailShell.tsx:155
    evidence: "DetailShell renders its own Close button (`<button aria-label=\"Close\" onClick={onClose}>✕</button>` at lines 155-163) while ALSO wrapping its children with `<Modal onClose={onClose}>` (line 77). Modal already renders a default Close button (Modal.tsx hideDefaultClose=false). This produces TWO buttons with `aria-label=\"Close\"` whenever Modal is not mocked. FeatureDetail.test.tsx (which does not mock Modal) fails with `Found multiple elements with the role 'button' and name 'Close'` in `FeatureDetail — close behavior > Close button calls onClose` (line 418)."
    blocking: true
    suggested_action: "In `DetailShell.tsx`, either pass `hideDefaultClose` to Modal and keep DetailShell's own ✕, or remove DetailShell's ✕ and rely on Modal's default Close button. Recommended: remove DetailShell's own Close button (delete the `<button aria-label=\"Close\">` at lines 155-163) since Modal's default Close already handles close+Escape+backdrop-click; DetailShell would then just spread title/badges/footer inside Modal."
  - id: F3
    severity: high
    file: frontend/src/components/FeatureDetail.tsx:25
    evidence: "FeatureDetail.tsx has its own `useEffect` Escape handler (lines 25-38) calling `onClose()`. Modal.tsx (lines 51-55) ALSO handles Escape and calls `onCloseRef.current()`. Result: pressing Escape fires onClose TWICE. FeatureDetail.test.tsx fails with `expected \"spy\" to be called 1 times, but got 2 times` in `FeatureDetail — close behavior > Esc key calls onClose when not editing` (line 428). The `expected \"spy\" to not be called at all, but actually been called 1 times` failure (line 439, edit-form-open case) is the same root cause: the in-component Esc handler bypasses the editing-mode guard that Modal does not know about."
    blocking: true
    suggested_action: "Delete the redundant Escape useEffect (lines 25-38) in FeatureDetail.tsx and let Modal handle Escape via onClose. To preserve the 'don't close while editing' behavior, gate the parent-provided `onClose` callback at the call site or pass a wrapped onClose into DetailShell that no-ops when `editing === true` (e.g. `onClose={editing ? () => {} : onClose}`). Same pattern applies to Detail.tsx (lines 827-840) — Detail's tests pass only because Detail.test.tsx mocks Modal (line 100); the underlying double-fire bug is the same and will manifest on real Modal."
  - id: F4
    severity: high
    file: tests/no-raw-palette-classes.test.ts
    evidence: "`tests/no-raw-palette-classes.test.ts` (a guard test from gui-tokens-brand / gui-badge-system) FAILS on ddf639e but PASSED on parent commit a3fb5ed: `Detail.tsx` reintroduced 18 raw palette classes (border-red-200, bg-red-50, text-red-600, border-orange-200, bg-orange-50, text-orange-600, border-amber-200/50/600, border-teal-200, bg-teal-50, text-teal-600, border-violet-200, bg-violet-50, text-violet-700, border-orange-200, bg-orange-50, text-orange-600). `FeatureDetail.tsx` reintroduced 6 (bg-emerald-500, bg-rose-500, border-amber-300, bg-amber-50, text-amber-700, text-amber-800). These violate the design-token discipline established by prior gui-* subgoals."
    blocking: true
    suggested_action: "Re-tokenize the raw palette classes in Detail.tsx and FeatureDetail.tsx using the brand tokens (e.g. badge tone tokens, `border-hairline`, `bg-surface-*`, `text-ink-*`) or the per-feature_state classes already exported by FEATURE_STATE_BADGE/STATE_BADGE. Inspect the failing strings printed by the test and replace each with the nearest token equivalent. This is straightforward search-and-replace work scoped to the two files."
  - id: F5
    severity: medium
    file: frontend/src/components/ui/Toast.tsx
    evidence: "`frontend/src/components/ui/Toast.tsx` (+117 lines, NEW file in commit ddf639e) is not present in any iteration's `scope_files[]`. The I8 impl-report claims it as 'modified +0 / -1' but the git diff shows it as a brand-new 117-line file. doc-gui-polish (a3fb5ed) had intentionally deleted Toast.tsx along with the rest of the Toast system; resurrecting only the leaf without ToastProvider/useToast is dead code with no consumer."
    blocking: true
    suggested_action: "Delete `frontend/src/components/ui/Toast.tsx`. It is scope-escaped, has no importers in the rest of the tree (`git grep \"from.*Toast\\\"\"` returns no matches in the rest of frontend/src), and was created as a side-effect of I8 attempting to fix build errors that originated from the also-resurrected ToastProvider.test.tsx. Removing both files (this F5 and F1's ToastProvider.test.tsx) closes the scope-escape cleanly."
  - id: F6
    severity: medium
    file: frontend/src/components/TreeToolbar.tsx
    evidence: "I7's design `scope_files` lists `frontend/src/pages/TreePage.tsx`, `frontend/src/components/TreeView.tsx`, and `frontend/src/components/__tests__/TreeToolbar.test.tsx`. Actual `files_changed` in I7 impl-report (and the commit) modify `frontend/src/components/TreeToolbar.tsx` (+55/-5) instead of `pages/TreePage.tsx` (TreePage.tsx unchanged on disk). Putting the toggle logic in TreeToolbar.tsx is arguably a cleaner choice, but TreeToolbar.tsx is NOT in any iteration's scope_files — scope escape. TreePage.tsx (in scope) was never touched."
    blocking: false
    suggested_action: "Two acceptable resolutions: (1) Accept the substitution (TreeToolbar.tsx is the logical home for a toolbar toggle, TreeView passes the props through), document the substitution in I7's out_of_scope_findings, and leave TreePage.tsx untouched. (2) Move the toggle button into TreePage.tsx as the design originally specified. Recommended: (1) — but the next attempt's impl-report MUST disclose the scope substitution honestly rather than leaving the design/impl drift undocumented."
  - id: F7
    severity: medium
    file: frontend/src/components/__tests__/DetailPRSection.test.tsx
    evidence: "I8 impl-report `files_changed[]` lists `frontend/src/components/__tests__/DetailPRSection.test.tsx` (+12/-0) but this file is NOT in any iteration's `scope_files[]`. I8's actual scope_files are limited to Detail.tsx, FeatureDetail.tsx, TreeNode.tsx, DetailShell.tsx. The implementor disclosed the change as fixing a JSDOM/useLiveStream mock gap surfaced by I5 — legitimate cause, but undeclared scope escape."
    blocking: false
    suggested_action: "Either restate I8's scope to include `__tests__/DetailPRSection.test.tsx` (architect can issue a one-line scope addendum), or move the mock fix to a follow-up `i8.1` iteration if the scope is intentional. The fix itself appears correct (EventSource/useLiveStream mock for active-state task rendering); the issue is contract bookkeeping, not the change content."
  - id: F8
    severity: medium
    file: frontend/src/components/ui/DetailShell.tsx
    evidence: "Design body §Frontend specifies DetailShell should include 'amber waiting bar (WAITING)' and 'edit-mode toggle' inside the shell. Committed DetailShell.tsx has neither: there is no `waiting`-state amber bar in the body (only the FEATURE_STATE_BADGE map's 'waiting' color, which is for the header pill, not a bar), and no edit-mode toggle button. Detail.tsx and FeatureDetail.tsx still carry their own waiting bars and edit toggles inline."
    blocking: false
    suggested_action: "Optional polish — if the design intent was unification, lift the waiting bar + edit toggle into DetailShell as `headerActions` slot contributors or as first-class props (`waitingBar?: ReactNode`, `editMode?: { editing: boolean; onToggle: () => void }`). If divergence is intentional (keep the toggles per-variant in the caller), capture the deviation in the doc-phase changelog so future readers don't expect it inside DetailShell."
  - id: F9
    severity: low
    file: .cronos/pipeline/gui-detail-ux/impl-report-gui-detail-ux--i8.md
    evidence: "I8 impl-report claims `validation_command_passed: true` and 'npm run build exits 0 (clean TypeScript + Vite). Full suite: 1358/1359 pass.' Verified against committed code: `cd frontend && npx tsc --noEmit` fails with 2 errors (F1); `npx vitest run` shows 8 failed test files / 24 failed tests / 1 suite-load-error. The impl-report misrepresents the gate state. This is a contract-honesty issue — the implementor's gate signal must be true on the code that actually ships."
    blocking: false
    suggested_action: "When the next attempt fixes F1-F4, re-run the actual `npm run build && npm test -- --run` against the COMMITTED tree (not the dirty worktree where the implementor may have hidden the breakage) and report verbatim. The pipeline-state proceeded only because the test phase gate runs the backend suite (which has separate auth-noise failures); the frontend build break is invisible to the backend test phase but is the true blocker."
---

## Summary

The three feature requirements (DetailShell, two-pane Detail with NOW running card, TreeNode compact + DAG toggle) are functionally present on the committed code (ddf639e). However the commit ships with `npm run build` BROKEN by a dangling test file (F1: ToastProvider.test.tsx imports modules that do not exist), and with five frontend test regressions traceable to gui-detail-ux changes: 3 in FeatureDetail.test.tsx (double Close button + double Esc handler from DetailShell+Modal layering, F2/F3) and 2 in no-raw-palette-classes.test.ts (Detail.tsx and FeatureDetail.tsx reintroduced raw palette classes, F4). Two additional new files (Toast.tsx, ToastProvider.test.tsx) are scope escapes resurrected from gui-polish leftovers (F1/F5). Verdict: needs_fix — all four blockers are local, recoverable edits.

## Findings

- F1 — ToastProvider.test.tsx references missing modules → build + vitest both fail (blocking, high)
- F2 — DetailShell renders Close button AND wraps Modal which also renders Close → double-button bug (blocking, high)
- F3 — FeatureDetail's redundant Escape handler races Modal's Escape → onClose fires twice (blocking, high)
- F4 — Detail.tsx + FeatureDetail.tsx reintroduced 24 raw palette classes; tokens guard test now fails (blocking, high)
- F5 — Toast.tsx scope-escape and dead code (blocking, medium)
- F6 — TreeToolbar.tsx modified but not in I7 scope_files; TreePage.tsx (in scope) untouched (non-blocking, medium)
- F7 — DetailPRSection.test.tsx modified in I8 but not in any iteration's scope_files (non-blocking, medium)
- F8 — DetailShell missing waiting bar + edit toggle that design body called for (non-blocking, medium)
- F9 — I8 impl-report's `validation_command_passed: true` is false on the committed code (non-blocking, low)

## Verdict

needs_fix. Four blocking findings (F1-F5) all map to bounded edits in `Detail.tsx`, `FeatureDetail.tsx`, `DetailShell.tsx`, and the deletion of two scope-escaped files; none require architect rescope, and `attempt + 1 = 2` is well below the loop ceiling.

## Assumptions

- Test phase report gate-decision=fail is backend-401 auth-fixture noise (well-documented across the gui-refactor goal-tree); the pipeline-state-recorded `proceed` for the test phase is correct, so the frontend signal must be verified independently — done here by cloning ddf639e and running `npm run build` + `npx vitest run` against the committed tree.
- Scope contract for this review is the union of `iterations[].scope_files[]` from the design report. Files outside that union counted as scope escapes regardless of impl-report disclosure (R-rev scope rule).
- Parent commit a3fb5ed is the correct comparison baseline for "new regression" claims: `tests/no-raw-palette-classes.test.ts` passes on a3fb5ed and fails on ddf639e, so F4 is a true introduction by this goal, not pre-existing technical debt.
- The five pre-existing failing test files (`Card.test.tsx`, `Card.buttons.test.tsx`, `MarkdownEditorModal.buttons.test.tsx`, `SpaceFilterDropdown.buttons.test.tsx`, `ViewPicker.buttons.test.tsx`) fail identically on parent a3fb5ed and on ddf639e and are out-of-scope for this review (pre-existing gui-button-focus / gui-polish technical debt).

## Open questions

- None.

## Next consumer brief

Implementor (next attempt): you have 4 blockers to resolve before pass. All are local; estimated impact ~30 lines of edits + 2 file deletions.

1. **F1 + F5 — Delete two files**: `frontend/src/components/ui/Toast.tsx` and `frontend/src/components/ui/__tests__/ToastProvider.test.tsx`. They were created by I8 as scope escapes; they reference Toast infrastructure (ToastProvider.tsx, useToast.ts) that doc-gui-polish intentionally deleted. Removing both makes `npm run build` green.
2. **F2 — DetailShell Close button**: Remove DetailShell's own ✕ Close button (lines 155-163 in `frontend/src/components/ui/DetailShell.tsx`); rely on Modal's default Close. Or pass `hideDefaultClose={true}` to Modal — pick one, not both.
3. **F3 — Double Escape handler**: Delete the redundant `useEffect` Escape handler in `FeatureDetail.tsx` (lines 25-38). Preserve "don't close while editing" by wrapping the `onClose` passed into DetailShell: `onClose={editing ? () => {} : onClose}`. Apply the same fix to `Detail.tsx` (lines 827-840) for safety — its current test passes only because Detail.test.tsx mocks Modal.
4. **F4 — Re-tokenize raw palette classes**: Open `tests/no-raw-palette-classes.test.ts` output (18 hits in Detail.tsx, 6 in FeatureDetail.tsx). Replace each raw `bg-red-50` / `text-amber-800` / etc. with the closest brand token (`bg-surface-*`, `text-ink-*`, badge-tone tokens, FEATURE_STATE_BADGE entries, etc.). Verify with `npx vitest run tests/no-raw-palette-classes.test.ts`.

After the fixes, run `cd frontend && npm run build && npx vitest run` against the COMMITTED tree (not the dirty worktree) and verify ZERO new failures vs. parent a3fb5ed. The 5 pre-existing failing test files (Card.test.tsx, Card.buttons.test.tsx, MarkdownEditorModal.buttons.test.tsx, SpaceFilterDropdown.buttons.test.tsx, ViewPicker.buttons.test.tsx) are out-of-scope and may stay red.

Non-blocking but worth fixing in the same pass: F6 (TreeToolbar.tsx scope-escape disclosure), F7 (DetailPRSection.test.tsx scope-escape disclosure), F8 (DetailShell missing waiting bar + edit toggle from design body), F9 (I8 impl-report dishonesty about build state).
