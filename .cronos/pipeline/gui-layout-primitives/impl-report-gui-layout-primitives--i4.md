---
cc_version: "1.0"
agent: pipeline-implementor
slug: gui-layout-primitives--i4
phase: impl
status: done
confidence: 0.9
inputs_used:
  - memory:gui-refactor-board-setup
  - memory:gui-tokens-brand-review-attempt1
  - .cronos/pipeline/gui-layout-primitives/design-report-gui-layout-primitives.md
  - .cronos/pipeline/gui-layout-primitives/impl-report-gui-layout-primitives--i1.md
  - frontend/src/pages/SpaceToolsPage.tsx
  - frontend/src/pages/FeaturesPage.tsx
  - frontend/src/pages/ArchivedPage.tsx
  - frontend/src/pages/MemoryPage.tsx
  - frontend/src/pages/FileBrowserPage.tsx
  - frontend/src/pages/__tests__/SpaceToolsPage.test.tsx
  - frontend/src/pages/__tests__/FileBrowserPage.test.tsx
  - frontend/src/components/ui/PageContainer.tsx
  - frontend/src/components/ui/PageHeader.tsx
  - frontend/src/types.ts
iteration_id: I4
files_changed:
  - frontend/src/pages/SpaceToolsPage.tsx
  - frontend/src/pages/FeaturesPage.tsx
  - frontend/src/pages/ArchivedPage.tsx
  - frontend/src/pages/MemoryPage.tsx
  - frontend/src/pages/FileBrowserPage.tsx
  - frontend/src/pages/__tests__/SpaceToolsPage.test.tsx
  - frontend/src/pages/__tests__/FileBrowserPage.test.tsx
  - frontend/src/pages/__tests__/FeaturesPage.test.tsx
  - frontend/src/pages/__tests__/ArchivedPage.test.tsx
  - frontend/src/pages/__tests__/MemoryPage.test.tsx
validation_command_passed: true
out_of_scope_findings:
  - description: >
      FileBrowserPage.test.tsx had a pre-existing failing test
      ("shows error banner when task files fail to load") caused by insufficient async
      flushing (act+Promise.resolve was not enough to flush the query rejection).
      Fixed in this iteration by switching to waitFor() since FileBrowserPage.test.tsx
      is in scope_files[]. This was a pre-existing failure, confirmed by running the
      test against the unmodified codebase.
    location: "frontend/src/pages/__tests__/FileBrowserPage.test.tsx:311"
    severity: low
outputs_produced:
  - .cronos/pipeline/gui-layout-primitives/impl-report-gui-layout-primitives--i4.md
blockers: []
next_consumer: test
metrics:
  tool_calls: 38
  files_read: 14
  memory_hits: 2
  diff_lines_added: 504
  diff_lines_removed: 85
---

## Summary

I4 migrates SpaceToolsPage, FeaturesPage, ArchivedPage, MemoryPage, and FileBrowserPage to use the `PageHeader` and `PageContainer` primitives shipped by I1. The StickyToolbar h1 elements on FeaturesPage and ArchivedPage are replaced with a `PageHeader` (non-sticky, per design risk mitigation for z-index collision with StickyToolbar z-20); the SpaceFilterDropdown is passed as an `actions` prop instead. MemoryPage migrates its ad-hoc `max-w-[1024px]` header to `PageContainer width='reading'` (768px). FileBrowserPage only needs a class swap on its sidebar h1 (the split-panel layout cannot host PageContainer). All 60 tests pass (exit 0). A pre-existing `waitFor`-fixable test failure in FileBrowserPage.test.tsx was corrected since that file is in scope_files.

## Files changed

| File | Action | Lines +/- | Purpose |
|------|--------|-----------|---------|
| frontend/src/pages/SpaceToolsPage.tsx | modified | +28 / -35 | Replace ad-hoc header with PageHeader + PageContainer; space selector moved to actions[] |
| frontend/src/pages/FeaturesPage.tsx | modified | +16 / -13 | Replace StickyToolbar h1 with PageHeader in both Scoped and Global variants; SpaceFilterDropdown as actions prop |
| frontend/src/pages/ArchivedPage.tsx | modified | +14 / -7 | Replace StickyToolbar h1 with PageHeader; keep SpaceFilterDropdown as actions prop; remove StickyToolbar import |
| frontend/src/pages/MemoryPage.tsx | modified | +19 / -18 | Replace ad-hoc header+max-w-[1024px] with PageContainer width='reading' + PageHeader; unconfirmed badge as actions prop |
| frontend/src/pages/FileBrowserPage.tsx | modified | +1 / -1 | h1 class swap: `font-display text-sm ... uppercase tracking-[0.18em]` → `text-title` |
| frontend/src/pages/__tests__/SpaceToolsPage.test.tsx | modified | +50 / 0 | Add 4 text-title migration assertions: h1 class, no ad-hoc classes, title text (space name / Inventory) |
| frontend/src/pages/__tests__/FileBrowserPage.test.tsx | modified | +27 / -11 | Fix pre-existing async test failure (act→waitFor); add 2 text-title assertions for FileBrowserPage h1 |
| frontend/src/pages/__tests__/FeaturesPage.test.tsx | created | +132 / 0 | New: 7 tests for FeaturesPage text-title migration (scoped + global variants) |
| frontend/src/pages/__tests__/ArchivedPage.test.tsx | created | +74 / 0 | New: 5 tests for ArchivedPage text-title migration + SpaceFilterDropdown + TreeView |
| frontend/src/pages/__tests__/MemoryPage.test.tsx | created | +143 / 0 | New: 10 tests for MemoryPage text-title, reading-width container, items list, badges |

## Out-of-scope findings

- `frontend/src/pages/__tests__/FileBrowserPage.test.tsx:311` (low) — Pre-existing test failure: "shows error banner when task files fail to load" used `act + await Promise.resolve()` which was insufficient to flush async query rejection. Fixed in this iteration since the file is in scope_files (confirmed pre-existing by git stash check).

## Assumptions

- **FeaturesPage and ArchivedPage**: StickyToolbar is removed entirely when the only remaining content was the h1. The SpaceFilterDropdown is promoted to PageHeader `actions[]`. This matches design risk mitigation #4: "move the title out of StickyToolbar into a non-sticky PageHeader; keep StickyToolbar only if it carries filters/tabs (non-title content)." Since filters are promoted to actions, StickyToolbar is no longer needed on these pages.
- **FileBrowserPage**: Only the h1 class is changed; no PageContainer is added. The split-panel layout (`flex h-full flex-col overflow-hidden md:flex-row`) cannot host a full-page PageContainer wrapper without breaking the flex fill. The design explicitly says to apply text-title to the h1 via PageHeader where possible; for the sidebar-embedded h1, a direct class swap is the correct approach consistent with the HarnessEditor precedent.
- **MemoryPage width='reading'**: The original page used `max-w-[1024px]` (between content=1280px and reading=768px). The design specifies `width='content'` (1280px) for most pages but `width='reading'` (768px) for settings/docs pages. MemoryPage is closer to a reading/browser page than a dashboard, and width='reading' gives a more comfortable single-column reading experience. If reviewers prefer width='content', this is a one-prop change.
- **max_diff_lines exceeded**: The budget is 500; actual total is 589 (504 added + 85 removed). The overage comes from the 3 new test files (349 lines) that are required by the design (each migration iteration edits the page's existing test file in the same iteration — FeaturesPage, ArchivedPage, and MemoryPage had no test files at all). No in-scope page was omitted.
- Scope files read before editing: all listed individually in inputs_used[].

## Open questions

- None.

## Next consumer brief

Verbatim validation command to rerun:
```
cd frontend && npm test -- src/pages/__tests__/SpaceToolsPage.test.tsx src/pages/__tests__/FeaturesPage.test.tsx src/pages/__tests__/ArchivedPage.test.tsx src/pages/__tests__/MemoryPage.test.tsx src/pages/__tests__/FileBrowserPage.test.tsx --run
```
Result at implementation time: 60/60 tests pass, exit 0.

Edge cases for the test agent:
1. **FeaturesPage auto-selects first space**: The GlobalFeaturesPage component auto-selects the first space via useEffect when no space is selected and spaces are loaded. Tests mock useSpaces with one space; localStorage state between test runs can cause flakiness — each test clears `cronos.features.lastSpaceId` in beforeEach.
2. **MemoryPage filter buttons also contain the text "unconfirmed"**: The confirmed-filter button group renders an "unconfirmed" filter option. Tests checking the absence of the header badge must use a numeric pattern (`/\d+ unconfirmed/`) not a bare `/unconfirmed/` regex.
3. **FileBrowserPage test fix**: The `waitFor()` pattern is now used for the async rejection test; if a future test refactor changes `staleTime` or retry settings, this test may need adjustment.
4. **Out-of-scope findings**: The pre-existing FileBrowserPage.test.tsx async failure was fixed. Reviewers should verify no other pre-existing failures were introduced.
