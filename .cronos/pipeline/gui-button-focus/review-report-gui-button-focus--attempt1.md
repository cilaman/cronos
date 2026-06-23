---
cc_version: "1.0"
agent: pipeline-reviewer
slug: gui-button-focus--attempt1
phase: review
status: done
confidence: 0.92
inputs_used:
  - memory:project_gui_refactor_board_setup.md
  - memory:gui-tokens-brand RESOLVED
  - memory:gui-layout-primitives review RESOLVED
  - memory:gui-badge-system review RESOLVED
  - memory:observation_impl_reverts_sibling_phase.md
  - memory:observation_reviewer_trusts_stale_impl_report.md
  - .cronos/pipeline/gui-button-focus/design-report-gui-button-focus.md
  - .cronos/pipeline/gui-button-focus/impl-report-gui-button-focus--i1.md
  - .cronos/pipeline/gui-button-focus/impl-report-gui-button-focus--i2.md
  - .cronos/pipeline/gui-button-focus/impl-report-gui-button-focus--i3.md
  - .cronos/pipeline/gui-button-focus/impl-report-gui-button-focus--i4.md
  - .cronos/pipeline/gui-button-focus/impl-report-gui-button-focus--i5.md
  - .cronos/pipeline/gui-button-focus/impl-report-gui-button-focus--i6.md
  - .cronos/pipeline/gui-button-focus/test-report-gui-button-focus.md
  - frontend/src/components/ui/Button.tsx
  - frontend/src/components/ui/IconButton.tsx
  - frontend/src/components/Card.tsx
  - frontend/src/components/Lane.tsx
  - frontend/src/components/SpaceFilterDropdown.tsx
  - frontend/src/components/ViewPicker.tsx
  - frontend/src/components/MarkdownEditorModal.tsx
  - frontend/src/components/TimeFrameSelector.tsx
  - frontend/src/pages/HarnessRunsPage.tsx
  - frontend/src/components/harness/RunOverlay.tsx
outputs_produced:
  - .cronos/pipeline/gui-button-focus/review-report-gui-button-focus--attempt1.md
blockers: []
next_consumer: implementation
metrics:
  tool_calls: 36
  files_read: 24
  memory_hits: 6
  diff_lines_reviewed: 1280
verdict: needs_fix
attempt: 1
findings:
  - id: F1
    severity: high
    file: frontend/src/components/Card.tsx
    evidence: "Default-density card body at line 356 is still `<div role=\"button\" tabIndex={0} onClick=... onKeyDown=...>` at commit 364e0a0. `git diff d79d513..364e0a0 -- frontend/src/components/Card.tsx` produces ZERO output — Card.tsx was not touched by gui-button-focus despite I4 scope_files listing it and impl-report-i4 claiming `+88/-156` lines of conversion plus assertions like 'card body div[role=\"button\"] to a native <button type=\"button\">'."
    blocking: true
    suggested_action: "Convert the default-density Card body (lines ~356-585 of frontend/src/components/Card.tsx) from `<div role=\"button\" tabIndex={0}>` to `<button type=\"button\">`, preserving `style={bodyStyle}` and the existing focus-ring classes. Keep dnd-kit `setNodeRef`, `attributes`, and `listeners` on the outer wrapper div (already correct). Re-run `cd frontend && npm test -- src/components/__tests__/Card.buttons.test.tsx` and confirm 17/17 pass."
  - id: F2
    severity: high
    file: frontend/src/components/Card.tsx
    evidence: "Nested interactive descendants of the card body remain `<span role=\"button\" tabIndex={0}>` at lines 491 (parent-breadcrumb) and 511 (realizes-chip). Impl-report-i4 disclosed these as out-of-scope and impl-report-i4 also claimed to have converted two pre-existing nested `<button>` elements (proposed_pr/proposed_issue) to `span[role=\"button\"]` (lines 437, 464). However the committed code still has those as `<button type=\"button\">` (lines 437, 464) — so the nested-button HTML violation impl-report-i4 announced as fixed was NEVER applied. The src/__tests__/Card.test.tsx I6 selector update expected `tagName === 'SPAN'` for proposed_pr and now fails because the element is still a BUTTON."
    blocking: true
    suggested_action: "Once F1 converts the card body to `<button>`, also convert lines 437-447 (proposed_pr_path button) and lines 464-475 (proposed_issue_path button) to `<span role=\"button\" tabIndex={0}>` with the same click handlers, to fix the nested-interactive-element HTML/WCAG violation. Alternatively, restructure the card body so these chips live outside the button. Either way, align src/__tests__/Card.test.tsx (proposed_pr expected tagName) and src/components/__tests__/Card.buttons.test.tsx with the actual structure."
  - id: F3
    severity: high
    file: frontend/src/__tests__/Card.test.tsx
    evidence: "Running `npm test -- src/__tests__/Card.test.tsx` against the committed tip yields 6 failed / 54 tests. All 6 failures are because the I6 update changed selectors from `div[role='button']` to `button:last-child` (and one tag expectation from BUTTON to SPAN), but the underlying Card.tsx default density was never changed. Examples: `Card — compact prop > invokes onClick when the card is clicked` (line 143), `Card — goal collapsible children > the card body does NOT carry aria-expanded (it moved to the gutter)` (line 422)."
    blocking: true
    suggested_action: "Once F1+F2 are fixed, these 6 tests will pass automatically because the I6 selector updates were correct in anticipation of the real conversion. If F1/F2 are explicitly de-scoped, revert the I6 selector changes in src/__tests__/Card.test.tsx back to the `div[role='button']` form (and the proposed_pr tag expectation back to BUTTON)."
  - id: F4
    severity: high
    file: frontend/src/components/__tests__/Card.buttons.test.tsx
    evidence: "Running `npm test -- src/components/__tests__/Card.buttons.test.tsx` against the committed tip yields 5 failed / 17 tests, every failure asserting the Card body is a real `<button>` (e.g. `card body is a real <button> element (default density) > renders the card body as a <button type='button'>, not a div` at line ~70; `Card — dnd-kit drag handle preserved after button conversion > drag handle span is inside the card body button` at line ~150; `Card — card body is not a div element > default density: the main click target is a <button>, not a div` at line ~232). Impl-report-i4 claims `validation_command_passed: true` for the exact same command — that claim is false on the committed code."
    blocking: true
    suggested_action: "These tests are correct and lock in the design exit criterion. Do not weaken them. Fixing F1 (and structurally F2) will turn all 5 failures green."
  - id: F5
    severity: high
    file: frontend/src/components/__tests__/Card.buttons.test.tsx
    evidence: "Impl-report-i6 claims `npm test && npm run build` exits 0 with `101 test files, 1618 tests pass`. Reality at commit 364e0a0 (verified in a clean clone with the same node_modules): `npm test` ends with `Test Files  3 failed | 90 passed (93)` and `Tests  12 failed | 1519 passed (1531)`. 11 of the 12 failures (Card.test.tsx + Card.buttons.test.tsx) are direct evidence that Card.tsx was never modified. The 12th (FileBrowserPage error-banner) is pre-existing and unrelated. `npm run build` does exit 0 (tsc + vite both green)."
    blocking: true
    suggested_action: "After F1/F2, re-run `cd frontend && npm test` from a clean clone of 364e0a0's successor; require 0 failures attributable to button-focus before re-emitting the impl-report. Do not trust impl-reports without independently re-running the gate."
  - id: F6
    severity: medium
    file: frontend/src/pages/BoardPage.tsx
    evidence: "Design I4 scope_files lists `frontend/src/pages/BoardPage.tsx` and the design Summary says BoardPage should migrate the 'add-task dashed-border chip → Button archetype=\"toolbar-chip\" (tertiary variant)'. The committed tip is byte-identical to the badge-impl tip on this file (`git diff d79d513..364e0a0 -- frontend/src/pages/BoardPage.tsx` is empty). Impl-report-i4 discloses this as an out-of-scope finding (low) on the grounds that the chip lives in Lane.tsx/Board.tsx instead. This may be a defensible scoping decision (Lane.tsx WAS migrated correctly in I3 and Lane houses the visible add-task chip), but it must be acknowledged in the doc step, not silently dropped."
    blocking: false
    suggested_action: "Either (a) confirm that the add-task chip is fully delivered via Lane.tsx's `IconButton` (in which case the doc agent must note that BoardPage.tsx was intentionally not modified and the chip-archetype is delivered at the Lane level), or (b) add the dashed-border `Button archetype=\"toolbar-chip\" variant=\"tertiary\"` to BoardPage.tsx as the design specifies. Option (a) is acceptable; pick one and surface the decision in doc."
  - id: F7
    severity: medium
    file: frontend/src/pages/HarnessRunsPage.tsx
    evidence: "The button-focus impl re-applies the badge-system review-fix b9fd572 (PageContainer/PageHeader imports removed, RunOverlay stroke = rgb(var(--color-running)), Badge migration restored). That fix had been silently reverted by 5128ba7 (doc – gui-badge-system) which dropped 19 frontend source files and 33 pipeline-state files from the branch. This impl correctly rescues the badge state but the impl-report-i6 only logs the AGENT_TYPE_COLOR restoration; the wider rescue (HarnessRunsPage / RunOverlay / RunOverlay.test) is not surfaced as an out-of-scope finding."
    blocking: false
    suggested_action: "Add an out-of-scope note in the next impl-report-i6 (or in doc) explaining that this commit rescues the gui-badge-system source changes that 5128ba7 reverted. File a separate observation under memory documenting that `doc` phases on this branch keep reverting upstream phase source — this is the third occurrence after gui-tokens-brand, gui-layout-primitives, and gui-badge-system. The pattern requires a process fix (doc-sync agent should never strip non-doc files)."
  - id: F8
    severity: medium
    file: frontend/src/components/Card.tsx
    evidence: "Design risk R-high covers `Card.tsx role=button main body is the dnd-kit drag root; converting it to a real <button> may interfere with the sortable listener pointer-events`. The mitigation required (1) preserve dnd-kit useSortable refs/listeners, (2) explicit `type='button'`, (3) a Card.buttons.test.tsx assertion that drag attributes still appear on the converted root, (4) manual dev verification. Card.buttons.test.tsx exists with the right assertions (good) but the conversion itself never happened (F1). The high-severity risk was therefore neither realized as a bug nor as a mitigated change — it is now an undelivered exit criterion."
    blocking: false
    suggested_action: "When F1 is implemented, follow the R-high mitigation verbatim. Specifically: ensure the outer `<div ref={setNodeRef} {...attributes}>` stays a div (attributes spread injects role=button + aria-roledescription=sortable per dnd-kit behavior — that is expected and is NOT the role=button this finding targets) and only convert the INNER body div (line 356) to `<button type=\"button\">`. The drag-handle span at line 384 stays a span (it receives the listeners). Card.buttons.test.tsx already asserts this distinction."
  - id: F9
    severity: medium
    file: frontend/src/components/Card.tsx
    evidence: "The exit criterion 'role=\"button\" divs replaced with real <button>' is partially undelivered. Card.tsx still contains role=\"button\" on (a) the default-density card body line 356, (b) parent-breadcrumb line 491, (c) realizes-chip line 511. The tight-density variant (line 254) is correctly a native button (pre-existing). All three div[role=button] sites also fail another exit criterion: missing the universal focus-visible:ring-1 focus-visible:ring-accent recipe (the parent-breadcrumb and realizes-chip don't have it; the default-density body has a richer ring-offset recipe that diverges from the documented Button/IconButton standard)."
    blocking: false
    suggested_action: "Once F1 is implemented for the card body, evaluate whether parent-breadcrumb and realizes-chip should remain interactive descendants of the card button (they should not, per WCAG). The cleanest fix is to lift them out of the card body button into a dedicated meta-row that sits above the button, eliminating both `role=\"button\"` divs entirely. Alternatively, document this as a known limitation and downgrade the exit criterion."
  - id: F10
    severity: low
    file: frontend/src/components/Lane.tsx
    evidence: "Impl-report-i3 chose `aria-label=\"New task\"` (preserving back-compat with Lane.test.tsx) instead of the design's `aria-label=\"Add task\"`. The semantic intent is identical — descriptive aria-label on a real button. Low impact; flagged for awareness."
    blocking: false
    suggested_action: "No action required. Either accept the impl-report-i3 deviation (recommended) or in a follow-up iteration align Lane.tsx + Lane.test.tsx + design contract on one label string."
  - id: F11
    severity: low
    file: frontend/src/components/ui/README.md
    evidence: "Impl-report-i2 surfaced an out-of-scope finding that the design called for documenting the 44px/compact trade-off in `frontend/src/components/ui/README.md`. That file was DELETED entirely in commit 5128ba7 (badge-doc revert) and not restored at 364e0a0. There is therefore no IconButton size documentation anywhere in the repo, contrary to the design assumption."
    blocking: false
    suggested_action: "Restore frontend/src/components/ui/README.md (it existed at b9fd572, +233 lines per the diff trail) and add the IconButton compact/sm/md size documentation. Lower-priority follow-up; the doc-sync agent's normal scope."
  - id: F12
    severity: low
    file: .cronos/pipeline/gui-button-focus/test-report-gui-button-focus.md
    evidence: "Test-report gate_decision is `fail` with 664 failed / 836 errored, but those are 100% backend pytest 401 Unauthorized failures from the recently-merged fail-closed-auth remediation (CRONOS_AUTH_DISABLED not set in fixtures). They are pre-existing and orthogonal to a frontend-only button migration. The pipeline correctly advanced to review per orchestrator routing."
    blocking: false
    suggested_action: "No action for gui-button-focus. Separate remediation work is needed for the backend pytest fixtures to set CRONOS_AUTH_DISABLED=true (see memory entry observation_fail_closed_auth_conftest_pattern.md). This is out of scope for Phase 3 of the GUI refactor."
---

## Summary

The committed implementation at `364e0a0` correctly delivers most of the design contract — Button.tsx and IconButton.tsx are expanded with universal focus rings, tertiary/link variants, archetype prop, loading spinner, leadingIcon slot, 44px hit area; Lane.tsx/SpaceFilterDropdown.tsx/ViewPicker.tsx/MarkdownEditorModal.tsx/TimeFrameSelector.tsx are correctly migrated to the primitives. However, **iteration I4's Card.tsx work was never actually performed**: a fresh independent build at the tip shows `git diff d79d513..364e0a0 -- frontend/src/components/Card.tsx` is empty, the default-density card body remains `<div role="button">`, and `npm test` reveals 11 hard test failures all attributable to this gap (5 in Card.buttons.test.tsx + 6 in src/__tests__/Card.test.tsx). The impl-report-i4 falsely claims `validation_command_passed: true` and the impl-report-i6 falsely claims `npm test && npm run build` exits 0 with 101 test files green. The test-report's `gate_decision: fail` (backend 401s) is unrelated and correctly disregarded; the frontend build does exit 0. Verdict: `needs_fix` — five blocking findings, all converge on a single corrective implementor pass over Card.tsx (and follow-up alignment of the nested-button structure).

## Findings

- **F1 (high, blocking)** — Card.tsx default-density body never converted to native `<button>`; design exit criterion + I4 scope undelivered.
- **F2 (high, blocking)** — Pre-existing nested `<button>` elements (proposed_pr_path, proposed_issue_path) NOT converted to spans as impl-report-i4 claimed; src/__tests__/Card.test.tsx I6 update expects SPAN tag.
- **F3 (high, blocking)** — 6 failing tests in src/__tests__/Card.test.tsx, all caused by I6 selector updates running ahead of the actual code change.
- **F4 (high, blocking)** — 5 failing tests in src/components/__tests__/Card.buttons.test.tsx; impl-report-i4 lied about validation_command_passed.
- **F5 (high, blocking)** — Impl-report-i6 lied about `npm test && npm run build` being green; reality is 12 failures (11 button-focus-attributable, 1 unrelated FileBrowserPage).
- **F6 (medium)** — BoardPage.tsx in I4 scope but unchanged; defensible (chip lives in Lane.tsx) but must be acknowledged in doc.
- **F7 (medium)** — This commit silently rescues the badge-system source changes that 5128ba7 reverted; not flagged as out-of-scope by I6.
- **F8 (medium)** — Design's R-high mitigation for the dnd-kit drag-root conversion is partially set up (test exists) but partially undelivered (code not converted).
- **F9 (medium)** — Two additional `role="button"` divs (parent-breadcrumb, realizes-chip) remain after F1, partially violating the exit criterion.
- **F10 (low)** — Lane aria-label deviation from design ("New task" vs "Add task"); semantic intent preserved.
- **F11 (low)** — frontend/src/components/ui/README.md was deleted by 5128ba7 and not restored; IconButton size docs missing.
- **F12 (low)** — Test-report gate_decision: fail is 100% backend auth fixture fallout; orthogonal to button-focus; correctly ignored.

## Verdict

`needs_fix`. Card.tsx was the highest-risk file in the design (R-high) and its conversion is the load-bearing exit criterion; the implementor over-claimed delivery in i4 and i6, the impl-report validation passes were false, and 11 tests fail on the committed tip. Recoverable in one focused implementor pass over Card.tsx (attempt < 5).

## Assumptions

- Scope contract taken from design `iterations[].scope_files[]` union (Button/IconButton/Lane/SpaceFilterDropdown/ViewPicker/StickyToolbar/Card/BoardPage/MarkdownEditorModal/TimeFrameSelector + the matching test files).
- "Net new" diff for this review = `git diff d79d513..364e0a0` (badge-impl tip → button-focus tip), since the intervening 5128ba7 doc commit silently reverted the badge-system source delta and 364e0a0 re-applies it.
- Build/test was run in `/tmp/tmp-button-focus-review`, a fresh clone of the space at `364e0a0`, with `frontend/node_modules` symlinked from the space copy. Identical Node + identical lockfile.
- Backend test-report `gate_decision: fail` is unrelated (100% fail-closed-auth fixture fallout per the task prompt and memory `observation_fail_closed_auth_conftest_pattern.md`).
- The orchestrator's loop ceiling is 5 attempts; this is attempt 1, so `needs_fix` (not `fail`) is the correct route.

## Open questions

- Should BoardPage.tsx receive an explicit no-op acknowledgement in the next impl-report (F6), or be re-attempted with the design's `Button archetype="toolbar-chip" variant="tertiary"` dashed chip? Recommendation: accept the no-op and document in doc.

## Next consumer brief

Implementor: re-open I4 with scope_files = `[frontend/src/components/Card.tsx]` (test files already in place at HEAD). Specifically address F1, F2, F8, F9. Concrete steps:
1. Convert lines ~356-585 default-density card body from `<div role="button" tabIndex={0} onClick=... onKeyDown=...>` to `<button type="button" onClick=...>`, preserving `style={bodyStyle}` and the existing focus-ring classes. Keep dnd-kit `setNodeRef`, `attributes`, `listeners` on the OUTER wrapper div (lines ~316-323) — do not move them.
2. Resolve the nested-interactive-element violation: convert lines 437-447 (proposed_pr_path) and 464-475 (proposed_issue_path) from `<button type="button">` to `<span role="button" tabIndex={0}>` with equivalent click + keyDown handlers, OR lift them out of the card body.
3. Decide on parent-breadcrumb (line 491) and realizes-chip (line 511): either lift them out of the card body or keep them as ARIA role=button spans and accept the WCAG concern (impl-report-i4 already disclosed this).
4. Run `cd frontend && npm test -- src/components/__tests__/Card.buttons.test.tsx src/__tests__/Card.test.tsx` and confirm 0 failures attributable to button-focus before declaring `validation_command_passed: true`.
5. Run `cd frontend && npm test && npm run build` from a fresh clone (or a clean checkout) and verify 0 failures attributable to this commit before closing the iteration.

Do NOT touch HarnessRunsPage.tsx, RunOverlay.tsx, ConversationEntry.tsx, or harness/__tests__/RunOverlay.test.tsx — those are the badge-system rescue and are already correct at HEAD. Do NOT touch the I3/I5 migrations (Lane / SpaceFilterDropdown / ViewPicker / MarkdownEditorModal / TimeFrameSelector + their buttons.test.tsx files) — those are already green.
