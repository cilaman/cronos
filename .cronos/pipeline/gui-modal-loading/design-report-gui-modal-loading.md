---
cc_version: '1.0'
agent: pipeline-architect
slug: gui-modal-loading
phase: design
status: done
confidence: 0.86
inputs_used:
- memory:GUI Refactor Board Setup
- memory:gui-tokens-brand RESOLVED
- memory:gui-layout-primitives review RESOLVED
- memory:gui-badge-system review RESOLVED
- memory:gui-button-focus review RESOLVED
- memory:gui-icons review RESOLVED
- .cronos/pipeline/gui-modal-loading/analysis-report-gui-modal-loading.md
- .cronos/pipeline/gui-modal-loading/scout-report-gui-modal-loading.md
- frontend/src/components/ui/Modal.tsx
- frontend/tailwind.config.js
- frontend/src/index.css
outputs_produced:
- .cronos/pipeline/gui-modal-loading/design-report-gui-modal-loading.md
blockers: []
next_consumer: implementation
coverage_summary:
  searched:
  - frontend/src/components/ui/
  - frontend/src/components/
  - frontend/src/pages/
  - frontend/tailwind.config.js
  - frontend/src/index.css
  excluded:
  - 'backend/: frontend-only feature'
  - 'frontend/src/components/Detail.tsx: ad-hoc DetailSkeleton not in brief scope
    (deferred)'
  - 'frontend/src/components/FeatureDetail.tsx: ad-hoc FeatureDetailSkeleton not in
    brief scope (deferred)'
  strategies:
  - memory_retrieval
  - read_targeted
iterations:
- id: I1
  type: frontend
  scope_files:
  - frontend/tailwind.config.js
  - frontend/src/index.css
  validation_command: cd frontend && npm run build
  max_diff_lines: 80
  depends_on: []
- id: I2
  type: frontend
  scope_files:
  - frontend/src/components/ui/Modal.tsx
  - frontend/src/components/ui/Modal.test.tsx
  validation_command: cd frontend && npm test -- src/components/ui/Modal.test.tsx
    --run
  max_diff_lines: 400
  depends_on:
  - I1
- id: I3
  type: frontend
  scope_files:
  - frontend/src/components/ui/Skeleton.tsx
  - frontend/src/components/ui/Skeleton.test.tsx
  validation_command: cd frontend && npm test -- src/components/ui/Skeleton.test.tsx
    --run
  max_diff_lines: 250
  depends_on:
  - I1
- id: I4
  type: frontend
  scope_files:
  - frontend/src/components/MarkdownEditorModal.tsx
  - frontend/src/components/MarkdownEditorModal.test.tsx
  validation_command: cd frontend && npm test -- src/components/MarkdownEditorModal.test.tsx
    --run
  max_diff_lines: 250
  depends_on:
  - I2
- id: I5
  type: frontend
  scope_files:
  - frontend/src/components/FileBrowser.tsx
  - frontend/src/components/FileBrowser.test.tsx
  validation_command: cd frontend && npm test -- src/components/FileBrowser.test.tsx
    --run
  max_diff_lines: 250
  depends_on:
  - I2
  - I3
- id: I6
  type: frontend
  scope_files:
  - frontend/src/components/ViewEditor.tsx
  - frontend/src/components/ViewEditor.test.tsx
  validation_command: cd frontend && npm test -- src/components/ViewEditor.test.tsx
    --run
  max_diff_lines: 200
  depends_on:
  - I2
- id: I7
  type: frontend
  scope_files:
  - frontend/src/components/ToolDetailPanel.tsx
  - frontend/src/components/ToolDetailPanel.test.tsx
  validation_command: cd frontend && npm test -- src/components/ToolDetailPanel.test.tsx
    --run
  max_diff_lines: 250
  depends_on:
  - I2
  - I3
- id: I8
  type: frontend
  scope_files:
  - frontend/src/pages/HarnessListPage.tsx
  - frontend/src/pages/HarnessListPage.test.tsx
  validation_command: cd frontend && npm test -- src/pages/HarnessListPage.test.tsx
    --run
  max_diff_lines: 350
  depends_on:
  - I2
  - I3
- id: I9
  type: frontend
  scope_files:
  - frontend/src/pages/FeaturesPage.tsx
  - frontend/src/pages/FeaturesPage.test.tsx
  validation_command: cd frontend && npm test -- src/pages/FeaturesPage.test.tsx --run
  max_diff_lines: 150
  depends_on:
  - I3
- id: I10
  type: frontend
  scope_files:
  - frontend/src/pages/DashboardPage.tsx
  - frontend/src/pages/DashboardPage.test.tsx
  validation_command: cd frontend && npm test -- src/pages/DashboardPage.test.tsx
    --run
  max_diff_lines: 200
  depends_on:
  - I3
- id: I11
  type: frontend
  scope_files:
  - frontend/src/components/ui/Modal.tsx
  - frontend/src/components/ui/Skeleton.tsx
  validation_command: cd frontend && npm run build && npm test -- --run
  max_diff_lines: 50
  depends_on:
  - I4
  - I5
  - I6
  - I7
  - I8
  - I9
  - I10
risks:
- description: Focus-trap implementation in Modal.tsx may break ViewEditor's existing
    usage (Modal already wraps a child at line 300). A bad Tab/Shift-Tab handler can
    either swallow keystrokes inside the editor's controls or leak focus out of the
    panel.
  severity: high
  mitigation: In I2 implement focus-trap via a useEffect that (1) records document.activeElement
    on mount, (2) queries a stable focusable selector list ('a[href], button:not([disabled]),
    [tabindex]:not([tabindex="-1"]), input:not([disabled]), select:not([disabled]),
    textarea:not([disabled])'), (3) wires keydown for Tab/Shift-Tab to cycle within
    the panel, (4) returns focus to the recorded element on unmount. I2 test file
    must include a regression case that mounts a Modal containing an input + a button
    and asserts Tab cycles between them and Shift-Tab cycles backward. I6 ViewEditor
    test must assert the existing Modal usage still renders the form fields and accepts
    text input.
- description: MarkdownEditorModal dirty-state guard (R4) requires threading dismissable=false
    through Modal.tsx when dirty=true. Misrouting this prop will either lock the modal
    permanently (blocking the user) or allow accidental data loss on Escape/scrim-click.
  severity: high
  mitigation: In I2 expose dismissable as an optional prop on ModalProps (default
    true). When dismissable=false, both the Escape keydown handler and the scrim click
    handler MUST early-return without calling onClose. In I4 MarkdownEditorModal passes
    dismissable={dirty} negated correctly (dismissable={!dirty}); test must cover
    (a) dirty=false + Escape closes, (b) dirty=true + Escape does NOT close, (c) dirty=true
    + scrim click does NOT close, (d) dirty=true + clicking the X button still calls
    onClose (X must NOT be gated by dismissable, only scrim/Escape are).
- description: Layer 0 (I1) adds Tailwind transitionDuration tokens (slow=280ms, base=180ms)
    and a @keyframes shimmer block. A typo in tailwind.config.js theme.extend.transitionDuration
    silently produces unstyled animations rather than a build error, masking the failure
    until visual regression.
  severity: medium
  mitigation: I1 validation_command runs 'npm run build' which catches syntax errors
    but not silent key typos. Mitigate with a follow-on assertion in I2 Modal.test.tsx
    that renders the modal and asserts the panel root has the class 'duration-slow'
    (or whatever utility name Tailwind generates from the token) using @testing-library
    queries on className substrings. Document the exact token names in the I1 impl-report
    so I2/I3 can wire them verbatim.
- description: Brief uses 'Dashboard.tsx' but the actual file on feature/gui-refactor
    is 'DashboardPage.tsx'. An implementor blindly following the brief would create
    a new file or scope-escape, breaking R10.
  severity: medium
  mitigation: Iteration I10 scope_files explicitly names frontend/src/pages/DashboardPage.tsx
    (verified to exist via scout report line 8 of inputs_used and Findings section).
    Implementor MUST treat scope_files as authoritative over the brief's free-text
    scope list. Cross-iteration invariant captured in Next consumer brief.
- description: HarnessListPage migration (I8) touches two ad-hoc modals (CreateHarnessModal
    lines 104-160; delete-confirm lines 263-290) plus a loading-state replacement
    (lines 216-220) in the same file. Bundling all three changes in one iteration
    risks an oversized diff and tangled review.
  severity: medium
  mitigation: 'I8 max_diff_lines=350 reflects this combined scope. Implementor must
    split the diff into three semantically-separate hunks (modal #1, modal #2, loading
    state) and keep each hunk minimal: replace the scrim+container div with <Modal
    onClose=...>, delete the per-component window.keydown Escape listener (Modal.tsx
    now owns it), and swap the spinner block for <Skeleton variant=''card'' />. I8
    test must cover all three behaviors (both modals dismiss on Escape; loading shows
    Skeleton cards, not a spinner).'
- description: Skeleton's shimmer @keyframes (R2) is defined in index.css. If the
    keyframes name collides with an existing animation (streamEnter, pulseDot, neonPulseDot,
    neonFlicker are already defined) or the .animate-shimmer utility name overlaps
    with an existing class, the shimmer effect silently breaks.
  severity: low
  mitigation: I1 uses the unambiguous name 'shimmer' (verified via grep in scout that
    no existing animation uses this name). I3 Skeleton.tsx applies the keyframes via
    either a bespoke className backed by a small @layer utilities block in index.css
    OR via Tailwind arbitrary value (animate-[shimmer_180ms_linear_infinite]). The
    choice is captured in I1 impl-report; I3 must follow that decision.
metrics:
  tool_calls: 5
  files_read: 5
  memory_hits: 6
  iterations_planned: 11
---

## Summary

Phase 5 ships a single Modal contract and a shared Skeleton primitive, then migrates six ad-hoc modal sites plus three spinner/text loaders to use them. The iteration DAG has four layers: Layer 0 (I1) lands the Tailwind motion tokens and shimmer @keyframes that both primitives depend on; Layer 1 (I2 Modal, I3 Skeleton) builds the primitives in parallel; Layer 2 (I4-I8) migrates the four-plus-two modal sites onto the new Modal contract, several of them also consuming Skeleton; Layer 3 (I9, I10) replaces the standalone page-level loading states with Skeleton. A final integration gate I11 (zero-diff or trivial polish budget, full build + suite) verifies the contract holds across the combined frontend. Highest-risk areas are focus-trap correctness inside Modal.tsx (must not break ViewEditor's existing usage) and the dirty-guard prop threading in MarkdownEditorModal (must not lock the user out OR silently allow data loss).

## Components

### Data
- None. Phase 5 is pure frontend; no backend models, no schemas, no API surface change.

### Backend
- None. Out of scope per analysis report and scout report.

### Frontend
- frontend/tailwind.config.js: extend theme.transitionDuration with slow=280ms and base=180ms.
- frontend/src/index.css: add @keyframes shimmer (gradient-position shift) and any companion utility class needed to expose it as a Tailwind-friendly animation.
- frontend/src/components/ui/Modal.tsx: rewrite to enforce the unified contract (bg-black/60 scrim z-[30], panel z-[40], backdrop-blur-sm, scale-fade entrance 280ms, Escape handler, focus-trap, dismissable prop default true, single SVG X close button).
- frontend/src/components/ui/Skeleton.tsx: new primitive with variants text | block | card, shimmer animation at 180ms, aria-label='Loading' / aria-hidden semantics.
- frontend/src/components/MarkdownEditorModal.tsx: drop ad-hoc bg-black/80 scrim and window.keydown Escape listener; wrap in Modal; pass dismissable={!dirty}.
- frontend/src/components/FileBrowser.tsx: migrate FileViewerModal to Modal; replace plaintext "Loading..." with Skeleton variant='block'.
- frontend/src/components/ViewEditor.tsx: migrate the inline delete-confirm dialog (line 519) to Modal; remove its window.keydown Escape listener; keep the existing Modal.tsx wrapper at line 300 working unchanged.
- frontend/src/components/ToolDetailPanel.tsx: migrate the bg-canvas/60 backdrop + slide-over panel to Modal; remove the window.keydown Escape listener at line 86; replace the SVG animate-spin spinner with Skeleton variant='block' or 'card'.
- frontend/src/pages/HarnessListPage.tsx: migrate CreateHarnessModal and the inline delete-confirm dialog to Modal; replace the spinner+text harness-list loading state with Skeleton variant='card' cards.
- frontend/src/pages/FeaturesPage.tsx: replace the animate-spin spinner and "Loading spaces..." text with a layout-reserving Skeleton.
- frontend/src/pages/DashboardPage.tsx: replace the three plaintext loading states (lines 601, 699, 816) with Skeleton tiles sized to match the eventual content.

## Implementation plan

| ID  | Type     | Depends on              | Scope files (abridged)                                                                | Validation                                                              |
|-----|----------|-------------------------|---------------------------------------------------------------------------------------|-------------------------------------------------------------------------|
| I1  | frontend | -                       | frontend/tailwind.config.js, frontend/src/index.css                                   | cd frontend && npm run build                                            |
| I2  | frontend | I1                      | frontend/src/components/ui/Modal.tsx, frontend/src/components/ui/Modal.test.tsx       | cd frontend && npm test -- src/components/ui/Modal.test.tsx --run       |
| I3  | frontend | I1                      | frontend/src/components/ui/Skeleton.tsx, frontend/src/components/ui/Skeleton.test.tsx | cd frontend && npm test -- src/components/ui/Skeleton.test.tsx --run    |
| I4  | frontend | I2                      | frontend/src/components/MarkdownEditorModal.tsx, ...MarkdownEditorModal.test.tsx       | cd frontend && npm test -- src/components/MarkdownEditorModal.test.tsx --run |
| I5  | frontend | I2, I3                  | frontend/src/components/FileBrowser.tsx, FileBrowser.test.tsx                          | cd frontend && npm test -- src/components/FileBrowser.test.tsx --run    |
| I6  | frontend | I2                      | frontend/src/components/ViewEditor.tsx, ViewEditor.test.tsx                            | cd frontend && npm test -- src/components/ViewEditor.test.tsx --run     |
| I7  | frontend | I2, I3                  | frontend/src/components/ToolDetailPanel.tsx, ToolDetailPanel.test.tsx                  | cd frontend && npm test -- src/components/ToolDetailPanel.test.tsx --run |
| I8  | frontend | I2, I3                  | frontend/src/pages/HarnessListPage.tsx, HarnessListPage.test.tsx                       | cd frontend && npm test -- src/pages/HarnessListPage.test.tsx --run     |
| I9  | frontend | I3                      | frontend/src/pages/FeaturesPage.tsx, FeaturesPage.test.tsx                             | cd frontend && npm test -- src/pages/FeaturesPage.test.tsx --run        |
| I10 | frontend | I3                      | frontend/src/pages/DashboardPage.tsx, DashboardPage.test.tsx                           | cd frontend && npm test -- src/pages/DashboardPage.test.tsx --run       |
| I11 | frontend | I4,I5,I6,I7,I8,I9,I10   | frontend/src/components/ui/Modal.tsx, Skeleton.tsx (polish budget only)               | cd frontend && npm run build && npm test -- --run                       |

Requirement coverage (cross-check vs analysis traceability[]):
- R1 (Modal contract) -> I2
- R2 (motion tokens + shimmer keyframes) -> I1
- R3 (Skeleton variants) -> I3
- R4 (MarkdownEditorModal migration + dirty guard) -> I4
- R5 (FileViewerModal migration + Skeleton block) -> I5
- R6 (ViewEditor delete dialog migration) -> I6
- R7 (ToolDetailPanel migration + Skeleton) -> I7
- R8 (HarnessListPage's two modals) -> I8
- R9 (FeaturesPage Skeleton) -> I9
- R10 (DashboardPage Skeleton) -> I10
- R11 (HarnessListPage Skeleton card list) -> I8 (combined with R8 since same file)
- R12 (npm run build + npm test green; no new TS errors) -> I11 (and acts as a gate for every iteration's per-file test)

## Risks

| Risk                                                                                                                       | Severity | Mitigation                                                                                                                                                                                                                          |
|----------------------------------------------------------------------------------------------------------------------------|----------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Focus-trap may break ViewEditor's existing Modal.tsx wrapper                                                               | high     | I2 implements a stable focusable selector + Tab/Shift-Tab keydown; tests cover Tab cycle + Shift-Tab cycle; I6 regression test asserts ViewEditor form still accepts input.                                                          |
| MarkdownEditorModal dirty guard misrouting locks user out OR allows data loss                                              | high     | Modal exposes dismissable prop (default true); when false both Escape AND scrim-click early-return; X button NEVER gated; I4 tests cover all four matrix combinations.                                                              |
| Silent typo in tailwind.config.js transitionDuration tokens produces unstyled animations                                   | medium   | I2 test asserts modal panel className includes the expected duration token literal; I1 impl-report documents the exact utility name produced by Tailwind.                                                                            |
| Brief says 'Dashboard.tsx' but actual file is 'DashboardPage.tsx'; implementor could scope-escape                          | medium   | Iteration I10 scope_files names DashboardPage.tsx explicitly; treat scope_files as authoritative over brief free-text.                                                                                                              |
| I8 bundles two modal migrations + one loading-state replacement in one file; risk of tangled review and oversized diff     | medium   | max_diff_lines=350 budget; implementor splits the patch into three semantic hunks; tests cover all three behaviors independently.                                                                                                   |
| Shimmer @keyframes name collision with existing animations in index.css                                                    | low      | Scout confirms no existing animation is named 'shimmer'; I1 impl-report locks the application strategy (utility class vs Tailwind arbitrary value); I3 follows that choice.                                                          |

## Assumptions

- has_ui=true from analysis -> all iterations are type=frontend; no backend/data/infra iterations needed.
- The actual page file for R10 is DashboardPage.tsx (not Dashboard.tsx as written in the goal-context blurb); confirmed by scout findings and Read of /data/spaces/cronos-development/frontend/src/pages/DashboardPage.tsx.
- Focus-trap is implemented inline in Modal.tsx via a custom useEffect; no new dependency is added (consistent with analysis assumption that no third-party focus-trap library is introduced).
- dismissable prop lives on Modal.tsx itself (default true); callers opt out per requirement R4.
- The CreateHarnessModal and the delete-confirm in HarnessListPage are BOTH in R8 scope per the analyst's resolution; combining them with R11 (HarnessListPage spinner+text replacement) into I8 keeps file ownership atomic for the implementor (one file, one diff, one validation command).
- ViewEditor already uses Modal.tsx at line 300 for its main form wrapper; only the inline delete-confirm dialog at line 519 is migrated. I6 must NOT touch the line-300 wrapper except as required by the Modal.tsx prop change in I2 (and the impl-report should call that out).
- All work targets the existing branch feature/gui-refactor (per goal context). No merge to main during this phase.
- I11 is an integration sanity gate; its scope_files are nominal (Modal.tsx + Skeleton.tsx) because the contract requires every iteration to declare files; in practice I11 expects a near-zero diff and only exists to run the full build + suite once after all migrations land. If the gate fails, the failing test points back to whichever Layer-2 / Layer-3 iteration introduced the regression.

## Open questions

- None. Analysis report's Open questions section confirms the orchestrator pre-resolved all scout-raised ambiguities (slide-over scope, dismissable location, Skeleton variant count, focus-trap implementation strategy).

## Next consumer brief

Read iterations[] in YAML order; the topological DAG groups are: Layer 0 = {I1}, Layer 1 = {I2, I3}, Layer 2 = {I4, I5, I6, I7, I8, I9, I10}, Layer 3 = {I11}. The orchestrator may fan out Layer 2 in parallel. Key cross-iteration invariants the YAML cannot fully express:

1. Modal.tsx (I2) MUST keep its existing callable signature compatible with ViewEditor's current usage at line 300: at minimum `<Modal onClose={...} className={...}>children</Modal>` must still render. The new dismissable prop is OPTIONAL and defaults to true.
2. When dismissable=false, the X close button MUST still call onClose. Only scrim-click and Escape are gated.
3. The Tailwind utility class names produced from I1's transitionDuration tokens (likely `duration-slow` and `duration-base`) must be referenced verbatim in I2 (Modal.tsx) and I3 (Skeleton.tsx); the I1 impl-report MUST document the exact token names.
4. The shimmer keyframes name in index.css (I1) and the className that consumes it (I3) must match; lock both in I1 impl-report.
5. R10 file is DashboardPage.tsx (per scout findings), not Dashboard.tsx. Treat iteration scope_files as authoritative over the goal-context blurb.
6. I8 combines R8 (two modals) and R11 (Skeleton card loading state) because they share one file; the implementor splits the diff into three semantic hunks but commits them together so the validation command (single test file) covers all three.
7. Branch is feature/gui-refactor; do not merge to main.
