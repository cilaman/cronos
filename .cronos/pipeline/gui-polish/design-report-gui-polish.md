---
cc_version: '1.0'
agent: pipeline-architect
slug: gui-polish
phase: design
status: done
confidence: 0.85
inputs_used:
- memory:project_gui_refactor_board_setup
- memory:project_gui_tokens_brand_review_attempt1
- .cronos/pipeline/gui-polish/analysis-report-gui-polish.md
- .cronos/pipeline/gui-polish/scout-report-gui-polish.md
- frontend/src/components/ui/IconButton.tsx
- frontend/src/components/ui/Modal.tsx
- frontend/src/components/Lane.tsx
outputs_produced:
- .cronos/pipeline/gui-polish/design-report-gui-polish.md
blockers: []
next_consumer: implementation
coverage_summary:
  searched:
  - frontend/src/components/ui/
  - frontend/src/components/
  - frontend/src/pages/
  - .cronos/pipeline/gui-polish/analysis-report-gui-polish.md
  - .cronos/pipeline/gui-polish/scout-report-gui-polish.md
  excluded:
  - 'backend/: frontend-only scope per request'
  - '.claude/agents/: not relevant to UI primitive extraction'
  strategies:
  - memory_retrieval
  - read_targeted
iterations:
- id: I1
  type: frontend
  scope_files:
  - frontend/src/components/ui/Toast.tsx
  - frontend/src/components/ui/ToastProvider.tsx
  - frontend/src/components/ui/useToast.ts
  - frontend/src/components/ui/__tests__/Toast.test.tsx
  - frontend/src/components/ui/__tests__/ToastProvider.test.tsx
  validation_command: cd frontend && npm test -- src/components/ui/__tests__/Toast.test.tsx
    src/components/ui/__tests__/ToastProvider.test.tsx --run
  max_diff_lines: 450
  depends_on: []
- id: I2
  type: frontend
  scope_files:
  - frontend/src/components/ui/Tabs.tsx
  - frontend/src/components/ui/Dropdown.tsx
  - frontend/src/components/ui/Tooltip.tsx
  - frontend/src/components/ui/StatTile.tsx
  - frontend/src/components/ui/ProgressBar.tsx
  - frontend/src/components/ui/__tests__/Tabs.test.tsx
  - frontend/src/components/ui/__tests__/Dropdown.test.tsx
  - frontend/src/components/ui/__tests__/Tooltip.test.tsx
  - frontend/src/components/ui/__tests__/StatTile.test.tsx
  - frontend/src/components/ui/__tests__/ProgressBar.test.tsx
  validation_command: cd frontend && npm test -- src/components/ui/__tests__/Tabs.test.tsx
    src/components/ui/__tests__/Dropdown.test.tsx src/components/ui/__tests__/Tooltip.test.tsx
    src/components/ui/__tests__/StatTile.test.tsx src/components/ui/__tests__/ProgressBar.test.tsx
    --run
  max_diff_lines: 600
  depends_on: []
- id: I3
  type: frontend
  scope_files:
  - frontend/src/components/Lane.tsx
  - frontend/src/components/ui/Modal.tsx
  - frontend/src/components/ui/IconButton.tsx
  - frontend/src/components/__tests__/Lane.test.tsx
  - frontend/src/components/ui/__tests__/Modal.test.tsx
  - frontend/src/components/ui/__tests__/IconButton.test.tsx
  validation_command: cd frontend && npm test -- src/components/__tests__/Lane.test.tsx
    src/components/ui/__tests__/Modal.test.tsx src/components/ui/__tests__/IconButton.test.tsx
    --run
  max_diff_lines: 350
  depends_on: []
- id: I4
  type: frontend
  scope_files:
  - frontend/src/App.tsx
  - frontend/src/__tests__/App.test.tsx
  validation_command: cd frontend && npm test -- src/__tests__/App.test.tsx --run
  max_diff_lines: 200
  depends_on:
  - I1
- id: I5
  type: frontend
  scope_files:
  - frontend/src/components/Detail.tsx
  - frontend/src/pages/SpaceToolsPage.tsx
  - frontend/src/components/__tests__/Detail.test.tsx
  validation_command: cd frontend && npm test -- src/components/__tests__/Detail.test.tsx
    --run
  max_diff_lines: 400
  depends_on:
  - I2
- id: I6
  type: frontend
  scope_files:
  - frontend/src/pages/DashboardPage.tsx
  - frontend/src/pages/StatsPage.tsx
  - frontend/src/pages/__tests__/DashboardPage.test.tsx
  - frontend/src/pages/__tests__/StatsPage.test.tsx
  validation_command: cd frontend && npm test -- src/pages/__tests__/DashboardPage.test.tsx
    src/pages/__tests__/StatsPage.test.tsx --run
  max_diff_lines: 400
  depends_on:
  - I2
- id: I7
  type: frontend
  scope_files:
  - frontend/src/components/Lane.tsx
  - frontend/src/components/Detail.tsx
  - frontend/src/pages/DashboardPage.tsx
  - frontend/src/pages/StatsPage.tsx
  - frontend/src/components/ui/EmptyState.tsx
  - frontend/src/components/ui/__tests__/EmptyState.test.tsx
  validation_command: cd frontend && npm test -- src/components/ui/__tests__/EmptyState.test.tsx
    --run && cd frontend && npm run build
  max_diff_lines: 350
  depends_on:
  - I3
  - I5
  - I6
risks:
- description: Touch-target padding correction on IconButton may collide with dense
    toolbar layouts (sticky toolbars, lane headers) if visual h-7/h-8 sizing is not
    strictly preserved while expanding hit area.
  severity: high
  mitigation: Use a wrapper span with min-h-[44px] min-w-[44px] grid-place-content-center,
    NOT direct padding on the visible button — preserves declared h-7/h-8 dimensions.
    Add explicit visual regression tests in IconButton.test.tsx asserting both the
    inner h-7/h-8 box and the outer 44px hit area dimensions.
- description: Toast wired into App.tsx via ToastProvider could break the existing
    test setup if any existing test renders App without the provider, or if useToast()
    is called from a component rendered without ToastProvider in tests.
  severity: medium
  mitigation: Make useToast() return a no-op show() when invoked outside ToastProvider
    (defensive default context value rather than throw), and add a smoke test in App.test.tsx
    that mounts <App /> and exercises a useToast().show() path. Avoid changing render()
    helpers in existing tests.
- description: Tabs and Dropdown extraction touches Detail.tsx and ViewPicker patterns
    with existing test coverage; mid-iteration test breakage if migration and primitive
    creation are interleaved.
  severity: medium
  mitigation: Split into two layers — I2 creates primitives in isolation (their own
    tests, no callers touched), then I5 migrates call sites in Detail.tsx and SpaceToolsPage.
    Each iteration validates independently before the next runs.
- description: Copy rewrites for error/loading/empty states (R10) can fail existing
    snapshot or text-match assertions in Detail/Dashboard/Lane tests without warning
    until full npm test runs.
  severity: medium
  mitigation: I7 explicitly includes the affected component tests in its scope_files
    and runs a full `npm run build` plus the touched test files. Implementor must
    update matching text assertions in the same commit as the copy change.
- description: Iteration I7 modifies Lane.tsx and Detail.tsx that were already touched
    by I3/I5; merge conflicts or accidental revert of I3 touch-target work if implementor
    checks out a stale base.
  severity: medium
  mitigation: 'I7 depends_on [I3, I5, I6] so it runs strictly after; implementor MUST
    base its branch on the post-I6 tip. Add a pre-flight grep in I7 validation: confirm
    `min-h-[44px]` strings from I3 still exist in Lane.tsx before declaring I7 done.'
- description: 'z-layer drift: Dropdown (z-20) and Tooltip (z-60) must match the design
    system z-index ladder named in docs/ui-ux-review/02-design-system.md §2.5; using
    arbitrary z-30 or z-50 breaks layering against Modal scrim.'
  severity: low
  mitigation: Hard-code the literal Tailwind classes z-[20] for Dropdown and z-[60]
    for Tooltip in the primitives. Reference the design system doc in the source comment
    so future edits do not drift.
metrics:
  tool_calls: 12
  files_read: 5
  memory_hits: 2
  iterations_planned: 7
---

## Summary

GUI Polish (Phase 6) decomposes into seven iterations across three parallel layer-0 tracks (Toast system, utility primitives bundle, touch-target sweep) that converge into a layer-1 wiring step (App.tsx for Toast) and two layer-1 migration steps (Detail/SpaceTools tab/dropdown migration, Dashboard/Stats StatTile migration). A final layer-2 iteration (I7) handles copy rewrites and runs the full `npm run build` exit gate against the converged tree. The DAG is intentionally wide at layer 0 so three implementors can run in parallel; the key invariant is that primitive *creation* (I1, I2) is strictly separated from *migration of call sites* (I4, I5, I6) so each layer validates independently. The principal risk is touch-target padding on IconButton interacting with dense toolbar contexts — mitigated by a wrapper-span approach that preserves the declared h-7/h-8 visual box while expanding only the outer hit area.

## Components

### Data
- (No data-layer changes — frontend-only scope per analysis report.)

### Backend
- (No backend changes — analysis report confirms frontend-only scope.)

### Frontend
- `frontend/src/components/ui/Toast.tsx`: single-toast renderer with tone variants (success|warning|danger|info), auto-dismiss timer, optional action button.
- `frontend/src/components/ui/ToastProvider.tsx`: context provider that holds the active toast stack and exposes show/dismiss methods.
- `frontend/src/components/ui/useToast.ts`: hook consuming ToastContext; returns `{ show, dismiss }` with no-op defaults outside provider.
- `frontend/src/components/ui/Tabs.tsx`: controlled tab bar primitive accepting `items`, `value`, `onChange`; canonicalizes Detail.tsx active-underline pattern.
- `frontend/src/components/ui/Dropdown.tsx`: keyboard-managed trigger+items dropdown extracted from ViewPicker; ESC/outside-click close, z-[20].
- `frontend/src/components/ui/Tooltip.tsx`: keyboard-reachable tooltip primitive (focus + hover), z-[60].
- `frontend/src/components/ui/StatTile.tsx`: label/value/delta/tone tile extracted from DashboardPage inline stats.
- `frontend/src/components/ui/ProgressBar.tsx`: proportional fill with optional segments, tone, showLabel.
- `frontend/src/components/Lane.tsx` (modified): add and hide buttons get min-h-[44px] min-w-[44px] hit area; uses EmptyState primary action slot.
- `frontend/src/components/ui/Modal.tsx` (modified): close button hit area widened to 44px while preserving 16x16 SVG glyph.
- `frontend/src/components/ui/IconButton.tsx` (modified): sm/md variants wrapped to guarantee 44x44 outer hit area while preserving visual h-7/h-8 box.
- `frontend/src/App.tsx` (modified): mounts `<ToastProvider>` around route Outlet.
- `frontend/src/components/Detail.tsx` (modified): inline tab bar replaced by Tabs.tsx; loading copy rewritten.
- `frontend/src/pages/SpaceToolsPage.tsx` (modified): inline tabs replaced by Tabs.tsx where present.
- `frontend/src/pages/DashboardPage.tsx` (modified): inline stat blocks replaced by StatTile; loading/empty copy.
- `frontend/src/pages/StatsPage.tsx` (modified): inline stat blocks replaced by StatTile; loading/empty copy.
- `frontend/src/components/ui/EmptyState.tsx` (modified): primary-action slot for Lane CTA.

## Implementation plan

| ID  | Type     | Depends on   | Scope files (abridged)                                              | Validation                                                                                       |
|-----|----------|--------------|---------------------------------------------------------------------|--------------------------------------------------------------------------------------------------|
| I1  | frontend | -            | ui/Toast.tsx, ui/ToastProvider.tsx, ui/useToast.ts + 2 tests        | npm test Toast.test.tsx + ToastProvider.test.tsx                                                 |
| I2  | frontend | -            | ui/Tabs.tsx, Dropdown.tsx, Tooltip.tsx, StatTile.tsx, ProgressBar.tsx + 5 tests | npm test for all 5 primitive tests                                                       |
| I3  | frontend | -            | Lane.tsx, ui/Modal.tsx, ui/IconButton.tsx + 3 tests                 | npm test Lane.test.tsx + Modal.test.tsx + IconButton.test.tsx                                    |
| I4  | frontend | I1           | App.tsx + App.test.tsx                                              | npm test App.test.tsx                                                                            |
| I5  | frontend | I2           | Detail.tsx, SpaceToolsPage.tsx + Detail.test.tsx                    | npm test Detail.test.tsx                                                                         |
| I6  | frontend | I2           | DashboardPage.tsx, StatsPage.tsx + 2 page tests                     | npm test DashboardPage.test.tsx + StatsPage.test.tsx                                             |
| I7  | frontend | I3, I5, I6   | Lane.tsx, Detail.tsx, DashboardPage.tsx, StatsPage.tsx, ui/EmptyState.tsx + EmptyState.test.tsx | npm test EmptyState.test.tsx + npm run build (exit gate)                          |

## Risks

| Risk                                                                  | Severity | Mitigation                                                                                                                                                       |
|-----------------------------------------------------------------------|----------|------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| IconButton padding collides with dense toolbars                       | high     | Wrapper span min-h-[44px] grid-place-content-center; preserve visual h-7/h-8; explicit dimension assertions in IconButton.test.tsx                               |
| Toast provider missing in existing tests breaks renders               | medium   | useToast() no-op default outside ToastProvider; do not modify existing render() helpers; add App.test.tsx smoke test for provider mount                          |
| Tabs/Dropdown extraction and migration interleave                     | medium   | Strict layer split: I2 creates primitives only (callers untouched); I5 migrates Detail and SpaceTools; each validates independently                              |
| Copy rewrites break existing snapshot/text assertions                 | medium   | I7 scopes the affected component tests in its scope_files; implementor updates matching text in the same diff                                                    |
| I7 reverts I3/I5 work via stale-base implementor checkout              | medium   | I7 depends_on [I3, I5, I6]; pre-flight grep for I3 markers (min-h-[44px]) in Lane.tsx before declaring I7 done                                                    |
| z-layer drift (Dropdown z-20, Tooltip z-60)                           | low      | Hard-code literal z-[20] and z-[60] Tailwind classes; reference docs/ui-ux-review/02-design-system.md §2.5 in source comments                                     |

## Assumptions

- Phases 0–5 of the GUI refactor are already merged to feature/gui-refactor (confirmed by memory:project_gui_refactor_board_setup); design tokens and earlier primitives are available.
- The `frontend/src/components/ui/` and `frontend/src/components/__tests__/` directories follow the existing co-located test convention; new tests go into `frontend/src/components/ui/__tests__/` (matches existing layout listed by `ls`).
- `frontend/src/pages/StatsPage.tsx` is the file referenced by the analysis as `Stats.tsx`; verified by `ls frontend/src/pages/`.
- `frontend/src/components/Detail.tsx` is the file referenced by the analysis as `Detail.tsx`; verified by `ls frontend/src/components/`.
- The IconButton 44px hit area is achieved via a wrapper span pattern rather than direct padding on the button — preserves dense toolbar visuals (key design decision called out in the analysis Next consumer brief).
- `npm run build` is the canonical TypeScript + bundle exit gate (already used by the wider project per CLAUDE.md `cd frontend && npm run build`).
- The optional ESLint rule banning raw palette classes is OUT of scope (analysis "Out of scope" section); not designed here.
- Menu.tsx is folded into Dropdown.tsx (analysis "Out of scope" — "Menu.tsx as a separate primitive (Dropdown covers the pattern; Menu alias deferred)").
- SegmentedControl.tsx is deferred (analysis "Deferred" section).
- All iterations target branch `feature/gui-refactor`; the orchestrator routes implementors to that worktree.

## Open questions

- None.

## Next consumer brief

The implementor reads the YAML `iterations[]` array, picks the iteration matching its assigned `id`, and treats `scope_files` as a hard boundary (no edits outside that list). Cross-iteration invariants the YAML cannot express:

1. **IconButton wrapper pattern (I3)**: the visual button keeps `h-7 w-7` / `h-8 w-8`; the 44px hit area MUST come from an outer wrapper span using `min-h-[44px] min-w-[44px] grid place-content-center`. Direct padding on the button changes its visual size and breaks dense toolbars (e.g. StickyToolbar.tsx).
2. **z-layer literals (I2)**: Dropdown uses `z-[20]`, Tooltip uses `z-[60]` — these match the design system z-index ladder (docs/ui-ux-review/02-design-system.md §2.5); do not invent new layers.
3. **useToast outside provider (I1)**: returning a no-op default (rather than throwing) is intentional — it prevents existing tests that don't wrap with ToastProvider from breaking. Document this in the hook's JSDoc.
4. **Tabs replacement contract (I5)**: Detail.tsx tab bar's active-underline absolute element is the canonical Tabs.tsx visual; the migration is a pure shape swap, no styling deltas.
5. **I7 base discipline**: I7 implementor MUST base on the post-I6 commit (the orchestrator enforces via `depends_on`). Pre-flight check: `grep -q "min-h-\[44px\]" frontend/src/components/Lane.tsx` must succeed before I7 declares done — protects against stale-base reverts.

Open questions for the implementor: none. All design decisions are recorded above or in the analysis report's Next consumer brief.
