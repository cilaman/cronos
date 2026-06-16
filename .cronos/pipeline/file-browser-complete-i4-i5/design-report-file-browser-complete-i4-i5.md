---
cc_version: '1.0'
agent: pipeline-architect
slug: file-browser-complete-i4-i5
phase: design
status: done
confidence: 0.9
inputs_used:
- .cronos/pipeline/file-browser-complete-i4-i5/scout-report-file-browser-complete-i4-i5.md
- .cronos/pipeline/file-browser-complete-i4-i5/analysis-report-file-browser-complete-i4-i5.md
- .cronos/pipeline/file-browser/design-report-file-browser.md
- .cronos/pipeline/file-browser/impl-report-file-browser--i1.md
- .cronos/pipeline/file-browser/impl-report-file-browser--i2.md
- .cronos/pipeline/file-browser/impl-report-file-browser--i3.md
- frontend/src/router.tsx
- frontend/src/components/Sidebar.tsx
- frontend/src/components/FileBrowser.tsx
- frontend/src/components/FilesPanel.tsx
- frontend/src/hooks/useTasks.ts
- frontend/src/pages/BoardPage.tsx
- frontend/src/api.ts
outputs_produced:
- .cronos/pipeline/file-browser-complete-i4-i5/design-report-file-browser-complete-i4-i5.md
blockers: []
next_consumer: impl
coverage_summary:
  searched:
  - .cronos/pipeline/file-browser-complete-i4-i5/
  - .cronos/pipeline/file-browser/
  - frontend/src/router.tsx
  - frontend/src/components/Sidebar.tsx
  - frontend/src/components/FileBrowser.tsx
  - frontend/src/components/FilesPanel.tsx
  - frontend/src/hooks/useTasks.ts
  - frontend/src/pages/BoardPage.tsx
  - frontend/src/api.ts
  excluded:
  - 'backend/: I1 already shipped on feature/implement-file-browser; out of scope
    for I4/I5'
  - 'frontend/src/components/FileBrowser.tsx (modification): I2 already shipped —
    I4 consumes the breadcrumb prop, does not modify the component'
  - 'frontend/src/api.ts (modification): I3 already shipped — I4 consumes the new
    spaceFileUrl/taskFileUrl helpers, does not modify api.ts'
  strategies:
  - memory_retrieval
  - read_targeted
  - grep_symbol
iterations:
- id: I4
  type: frontend
  title: FileBrowserPage with hierarchical task tree, task selection, and embedded
    FileBrowser
  scope_files:
  - frontend/src/pages/FileBrowserPage.tsx
  - frontend/src/pages/__tests__/FileBrowserPage.test.tsx
  - frontend/src/router.tsx
  - frontend/src/components/Sidebar.tsx
  validation_command: cd frontend && npx vitest run src/pages/__tests__/FileBrowserPage.test.tsx
  max_diff_lines: 600
  depends_on: []
  acceptance_criteria:
  - 'R1: New page component frontend/src/pages/FileBrowserPage.tsx renders a hierarchical
    tree of the space''s tasks/goals as collapsible nodes. Data source MUST be the
    existing useBoard(spaceId) hook from frontend/src/hooks/useTasks.ts (returns the
    Board grouped by lane); do NOT introduce a new query. Tree is constructed client-side
    from parent_id adjacency in the TaskSummary[] union of all lanes.'
  - 'R1: Tree layout is responsive — two-column (tree left, FileBrowser right) at
    and above the Tailwind `md:` breakpoint; collapses to a single-column stack below
    `md:` (tree above, FileBrowser below), matching the BoardPage and TreePage conventions
    already used in this codebase.'
  - 'R2: Clicking a task node in the tree calls `api.taskFiles(taskId)` (NOT `api.spaceFiles`
    — explicit per R7 of the original design and analyst Assumptions) via a per-task
    useQuery and passes the resulting TaskFile[] plus `(path, dl) => api.taskFileUrl(taskId,
    path, dl)` as fileUrlBuilder to <FileBrowser/>. When no task is selected, the
    FileBrowser is hidden and an empty-state placeholder with guidance text is shown
    in the right pane.'
  - 'R3: Route `spaces/:spaceId/files` is registered in `frontend/src/router.tsx`
    (NOT `App.tsx`) — inserted as a sibling of `spaces/:spaceId/tree` BEFORE the catch-all
    `path="*"` route. App.tsx MUST remain unchanged.'
  - 'R3: The FileBrowserPage test mounts via MemoryRouter against the registered route
    (initialEntries=["/spaces/test-space/files"]) and asserts the tree nodes render
    from mocked task data. Direct component-render-only tests are NOT sufficient —
    a route-registration miss must be caught in CI.'
  - 'R4: `frontend/src/components/Sidebar.tsx` gains a NavLink to `/spaces/:spaceId/files`,
    rendered inline inside the existing SpaceRow component (sibling of the existing
    tree-icon NavLink at lines 69–89). It uses a folder/files-themed SVG icon consistent
    with the existing tree SVG (same w/h/stroke conventions) and the same NavLink
    active-class pattern as the tree link so the active route highlights.'
  - 'R5: FileBrowserPage wires the I2 breadcrumb prop on <FileBrowser/>. Breadcrumb
    text reads "Space {space_name}" when no task is selected and "Space {space_name}
    / {task_title}" when a task is selected. Space name is resolved via the existing
    useSpaces() hook (matching scope to the route :spaceId); fall back to the route
    :spaceId verbatim if the space record is not yet loaded.'
  - 'R6: Loading and error states are rendered for both queries. While useBoard is
    pending, the tree pane shows a skeleton/spinner element; on query error it shows
    an error banner with a short message. While the per-task useQuery for api.taskFiles
    is pending after node selection, the FileBrowser pane shows a loading indicator;
    on query error it shows an error banner.'
  - 'Tests cover: (a) page renders tree from mocked useBoard data; (b) clicking a
    task node triggers an api.taskFiles call with the correct taskId and renders the
    returned files in FileBrowser; (c) empty-state placeholder when no task is selected;
    (d) loading state for tree and file queries; (e) error state for tree and file
    queries; (f) breadcrumb text updates between unselected ("Space …") and selected
    ("Space … / Task …") modes; (g) responsive collapse via Tailwind class assertions;
    (h) test mounts via MemoryRouter against the registered router.tsx route (R3 guard).'
  - Sidebar NavLink visual placement and icon fidelity (R4) are verified in the review
    phase (per analyst traceability — R4 verifying_phase=review); test assertions
    are limited to NavLink presence and active-class behaviour.
- id: I5
  type: frontend
  title: FilesPanel regression guard — confirm zero-change rendering when breadcrumb
    prop is omitted
  scope_files:
  - frontend/src/components/__tests__/FilesPanel.regression.test.tsx
  validation_command: cd frontend && npx vitest run src/components/__tests__/FilesPanel.regression.test.tsx
  max_diff_lines: 150
  depends_on: []
  acceptance_criteria:
  - 'R7: A new file `frontend/src/components/__tests__/FilesPanel.regression.test.tsx`
    is created. It is the ONLY file changed in I5; `FilesPanel.tsx` MUST NOT be touched
    — the iteration''s premise is that the I2 breadcrumb prop addition introduced
    zero DOM changes when the prop is omitted, and any source edit to FilesPanel.tsx
    is an escalation signal, not a fix.'
  - 'R7: Test mounts FilesPanel with only `taskId` (and optionally `className`) and
    asserts the rendered output does NOT contain a breadcrumb header element. Concretely:
    queryByRole("navigation") returns null AND no element with the breadcrumb wrapper''s
    distinguishing attribute (e.g. data-testid="file-browser-breadcrumb" if introduced
    by I2, else a structural assertion that the <nav> element rendered conditionally
    on the breadcrumb prop is absent).'
  - 'R7: Test asserts the 10-second refetch interval is still configured on the underlying
    useQuery hook for api.taskFiles. Approach: use vitest fake timers (vi.useFakeTimers()),
    mount the component with a mocked api.taskFiles spy that returns an empty array,
    advance time by 10_000 ms, and assert the spy was called at least twice (initial
    + one refetch). Alternative if timers are flaky: inspect the QueryClient observers
    for the ["task-files", taskId] key.'
  - 'R7: Test asserts upload and save mutations remain wired by spying on `api.uploadTaskFile`
    and `api.saveTaskFile` and asserting they are invoked when FileBrowser callbacks
    fire (or by asserting the FileBrowser receives non-null onUpload and onSave callback
    props).'
  - The diff produced by I5 MUST be limited to the new test file. If the diff touches
    FilesPanel.tsx, FileBrowser.tsx, or any other source file, the iteration has failed
    its premise and MUST be returned to design — do NOT modify source files to make
    the test pass.
risks:
- description: 'Implementor mis-routes the new page in App.tsx instead of router.tsx.
    The original design report (`design-report-file-browser.md`, Risk #2) and the
    analyst both flagged this; the scout report also confirmed router.tsx is the source
    of truth. If the route is added to App.tsx, the live app will silently 404 at
    /spaces/:spaceId/files while a direct-component test may still pass.'
  severity: high
  mitigation: I4 acceptance criterion R3 explicitly forbids editing App.tsx and requires
    the route to be added to router.tsx as a sibling of `spaces/:spaceId/tree`. The
    FileBrowserPage test MUST mount via MemoryRouter against the registered route
    (initialEntries=["/spaces/test-space/files"]), not by directly rendering the component
    — so a missed route registration fails in CI. The reviewer is instructed to check
    the diff includes `router.tsx` and excludes `App.tsx` from changed-file list.
- description: I5 fails its own premise by modifying FilesPanel.tsx to pass the regression
    test. R7 is a property the I2 implementation already guarantees (byte-identical
    DOM when breadcrumb is omitted); the test exists to detect drift, not to be made
    to pass by editing source.
  severity: high
  mitigation: I5 scope_files is restricted to a single new test file. The acceptance
    criteria explicitly state that any diff touching FilesPanel.tsx or FileBrowser.tsx
    is an escalation, not a fix. The reviewer MUST run `git diff --name-only` against
    the I5 commit and reject the iteration if any source file is touched.
- description: Breadcrumb text drift between FileBrowserPage (R5) and the FileBrowser
    component (I2 prop contract). If the breadcrumb is rendered inside FileBrowser
    via a `<nav>` wrapper, FileBrowserPage MUST pass JSX/string content that survives
    that wrapping; otherwise tests asserting the breadcrumb text may pass while the
    DOM looks broken in the live app.
  severity: medium
  mitigation: I4 tests assert the rendered text content of the breadcrumb nav (not
    just prop presence) for both unselected and selected modes. The breadcrumb prop
    value is a plain string ("Space {name}" / "Space {name} / {task}") to match the
    I2 prop type ReactNode and avoid layout surprises. If a structured breadcrumb
    is desired later, it can be introduced incrementally without touching the FileBrowser
    contract.
- description: useBoard returns the lane-grouped Board (not a flat TaskSummary[]).
    The implementor may try to fetch a flat list via api.task or attempt to introduce
    a new endpoint, inflating scope.
  severity: medium
  mitigation: 'I4 acceptance criterion R1 explicitly names useBoard as the data source
    and instructs the implementor to flatten lanes client-side into a TaskSummary[]
    keyed by parent_id for tree construction. No new query, no new endpoint, no new
    types. The original design report Risk #6 already vetted reusing useTasks-family
    hooks for performance via React Query caching.'
- description: Task list query inflation — a space with hundreds of tasks may slow
    initial render of the tree. The full TaskSummary[] is rendered as a flat collapsible
    tree, not virtualised.
  severity: low
  mitigation: Reuse the existing useBoard cache (no duplicate fetch) and use the same
    collapsible-node pattern already used by Board/TreePage. Virtualisation is deferred
    — flag in the impl-report next-consumer brief as a follow-up if usage exceeds
    ~500 tasks per space (matches the I1 list_files 500-entry cap pragma).
- description: Sidebar NavLink icon and active-class styling drift between the existing
    `/spaces/:spaceId/tree` NavLink and the new `/spaces/:spaceId/files` NavLink.
    Visual consistency cannot be asserted programmatically.
  severity: low
  mitigation: Analyst marked R4 verifying_phase=review. The reviewer is instructed
    to visually compare the two NavLink icons (folder/files SVG vs the existing tree
    SVG) in the running UI and confirm consistent stroke/width and the same NavLink
    active-class pattern. I4 tests only assert NavLink presence, route target, and
    active-class behaviour.
- description: 'I4 and I5 are sequenced as independent iterations with no inter-dependency
    in the DAG (`depends_on: []`) because their predecessor iterations (I2 and I3
    from the original file-browser design) are already shipped on feature/implement-file-browser.
    If the implementor accidentally runs I4 and I5 against a workspace that is missing
    the I1-I3 changes, both iterations will fail at validation.'
  severity: medium
  mitigation: The goal context (and the original design report's next-consumer brief)
    direct that all I4/I5 commits land on the shared `feature/implement-file-browser`
    branch via `/goal-task-commit`. The implementor MUST confirm the workspace is
    rebased on (or branched from) feature/implement-file-browser before starting —
    verifiable by grepping for `spaceFileUrl` in `frontend/src/api.ts` and for `breadcrumb?:`
    in `frontend/src/components/FileBrowser.tsx`. If either is missing, the implementor
    must rebase before continuing.
metrics:
  tool_calls: 14
  files_read: 10
  memory_hits: 3
  iterations_planned: 2
---

## Summary

This design completes the File Browser feature by scheduling the two remaining iterations from `design-report-file-browser.md` — I4 (`FileBrowserPage` + route + Sidebar NavLink) and I5 (`FilesPanel` regression guard) — against the verified-shipped baseline of I1–I3 on `feature/implement-file-browser`. The plan does not reopen design questions resolved upstream (router.tsx is the route source of truth, `resolve_safe` already lives in `file_service.py`, the page is read-only at launch and scoped to `.cronos/workspaces/`). Both iterations are pure frontend; I4 composes the I2 breadcrumb prop and the I3 API client into the user-facing page, and I5 is a test-only regression guard whose scope boundary is the single new test file. I4 and I5 are independent in this DAG (`depends_on: []`) because their upstream dependencies are already merged on the feature branch.

## Components

### Data
- `TaskSummary` (existing, `frontend/src/types.ts`): consumed verbatim — no schema change. I4 reads `parent_id` and `title` for tree construction.
- `TaskFile` (existing, `frontend/src/types.ts`): consumed verbatim — `api.taskFiles(taskId)` returns this shape; I4 forwards it to `<FileBrowser/>`.

### Backend
- No backend changes in this design. I1's `GET /api/spaces/{space_id}/files` and `GET /api/spaces/{space_id}/files/{file_path:path}` are already shipped on `feature/implement-file-browser` (verified by scout). I4 intentionally does NOT call `api.spaceFiles` per the original design R7 — task selection uses the existing `api.taskFiles` endpoint.

### Frontend
- `frontend/src/pages/FileBrowserPage.tsx` (NEW, I4): two-column page — left column renders the space's tasks/goals as a hierarchical collapsible tree from `useBoard()`; right column renders the existing `<FileBrowser/>` populated by `api.taskFiles(selectedTaskId)`. Wires the I2 `breadcrumb` prop with `Space {space_name}` / `Space {space_name} / {task_title}` content.
- `frontend/src/pages/__tests__/FileBrowserPage.test.tsx` (NEW, I4): MemoryRouter-mounted vitest suite covering tree render, task selection, empty/loading/error states, breadcrumb text, route registration guard.
- `frontend/src/router.tsx` (EXTENDED, I4): adds `<Route path="spaces/:spaceId/files" element={<FileBrowserPage/>} />` as a sibling of the existing `spaces/:spaceId/tree` route, before the catch-all `path="*"`.
- `frontend/src/components/Sidebar.tsx` (EXTENDED, I4): adds an inline NavLink to `/spaces/:spaceId/files` inside the existing `SpaceRow` component, adjacent to the existing tree-icon NavLink. Uses a folder/files SVG icon and the same NavLink active-class pattern as the tree NavLink.
- `frontend/src/components/__tests__/FilesPanel.regression.test.tsx` (NEW, I5): vitest regression suite asserting that `FilesPanel.tsx` renders without a breadcrumb element, that the 10-second refetch interval is intact, and that upload/save mutations remain wired.
- `frontend/src/components/FilesPanel.tsx` (UNCHANGED, I5 guard): MUST NOT be modified by I5. If the diff touches this file, the iteration has failed its premise.
- `frontend/src/components/FileBrowser.tsx` (UNCHANGED in I4 and I5): I4 consumes the existing breadcrumb prop; no modification.
- `frontend/src/api.ts` (UNCHANGED in I4 and I5): I4 consumes the existing `api.taskFiles` and `taskFileUrl`; no modification.

## Implementation plan

| ID | Type     | Depends on | Scope files (abridged)                                                                                                          | Validation                                                                              |
|----|----------|------------|---------------------------------------------------------------------------------------------------------------------------------|-----------------------------------------------------------------------------------------|
| I4 | frontend | -          | frontend/src/pages/FileBrowserPage.tsx, frontend/src/pages/__tests__/FileBrowserPage.test.tsx, router.tsx, Sidebar.tsx           | cd frontend && npx vitest run src/pages/__tests__/FileBrowserPage.test.tsx              |
| I5 | frontend | -          | frontend/src/components/__tests__/FilesPanel.regression.test.tsx                                                                | cd frontend && npx vitest run src/components/__tests__/FilesPanel.regression.test.tsx   |

Topological layers (for orchestrator fan-out):

- Layer 0 (parallel): I4, I5

Both iterations have empty `depends_on` because their upstream iterations (I2, I3 from the original file-browser design) are already shipped on `feature/implement-file-browser`. They can be executed in parallel.

## Risks

| Risk                                                                          | Severity | Mitigation                                                                                                                                              |
|-------------------------------------------------------------------------------|----------|---------------------------------------------------------------------------------------------------------------------------------------------------------|
| Route mis-registered in App.tsx instead of router.tsx (silent 404 in app)     | high     | I4 R3 forbids editing App.tsx; FileBrowserPage test mounts via MemoryRouter against router.tsx-registered route; reviewer checks changed-file list.       |
| I5 modifies FilesPanel.tsx to make regression test pass                       | high     | I5 scope_files restricted to single new test file; ACs explicitly forbid source edits; reviewer rejects iteration if any source file is in I5 diff.      |
| Breadcrumb text drift between FileBrowserPage and FileBrowser nav wrapper     | medium   | Plain-string breadcrumb prop content; tests assert rendered text for both unselected/selected modes.                                                    |
| Implementor introduces a new task-list query instead of useBoard              | medium   | R1 names useBoard explicitly; tree built client-side from parent_id adjacency on the existing cache.                                                     |
| Implementor runs I4/I5 against workspace missing I1–I3 changes                | medium   | Goal context mandates `feature/implement-file-browser` branch; implementor must grep for `spaceFileUrl`/`breadcrumb?:` markers before starting.          |
| Task tree render slow on large spaces (~500+ tasks)                           | low      | Reuse existing useBoard cache + collapsible-node pattern from BoardPage; virtualisation deferred and flagged in next-consumer brief.                     |
| Sidebar NavLink icon/styling drift from existing tree NavLink                 | low      | Analyst marked R4 verifying_phase=review; reviewer visually compares icons; tests only assert presence and active-class behaviour.                       |

## Assumptions

- **I1–I3 are shipped on `feature/implement-file-browser` and are NOT yet on `main`.** Scout, analyst, and the original design report all confirm the feature-branch state. The workspace this task runs in is rooted on main (`f6ec7ae`), so the implementor MUST rebase onto or branch from `feature/implement-file-browser` before starting I4/I5 work — verifiable by grepping for `spaceFileUrl` in `frontend/src/api.ts` (I3 marker) and `breadcrumb?:` in `frontend/src/components/FileBrowser.tsx` (I2 marker). The scout's claim that I1–I3 are "merged to main" is incorrect for the current workspace; the implementor should not be misled.
- **Iteration IDs are I4 and I5 (not renumbered to I1/I2).** This preserves continuity with the original `design-report-file-browser.md` iterations[] and with the existing `impl-report-file-browser--i1.md` … `--i3.md` artefacts. The verifier's pattern (`^I[0-9]+$`) accepts any positive integer; downstream impl-report slug suffixes will be `--i4` and `--i5`.
- **Data source for the tree is the existing useBoard hook**, returning the Board grouped by lane. The implementor MUST NOT introduce a new task-list endpoint or new React Query key — the design reuses what exists. The TaskSummary[] is flattened across lanes client-side; tree is built from `parent_id` adjacency.
- **Breadcrumb content is plain string.** "Space {space_name}" and "Space {space_name} / {task_title}" — simple template strings, not structured JSX nodes. Avoids interaction with FileBrowser's `<nav>` wrapper from I2 and minimises future drift risk.
- **R4 (Sidebar NavLink) is a review-phase verification.** Per analyst traceability, the NavLink's visual fidelity (icon style, grouping placement) is a reviewer responsibility. I4 tests assert presence, route target, and active-class behaviour only.
- **FileBrowserPage is read-only at launch.** No upload/save UI at the space level. Matches the original design Assumption ("FileBrowserPage is read-only at launch") and analyst Out-of-Scope list.

## Open questions

- None blocking. All open questions from the upstream design (Q1: space root scope, Q2: upload UI) were resolved in the original `design-report-file-browser.md` and are inherited here.

## Next consumer brief

The implementor should:

1. **Verify the workspace baseline before starting.** Run two greps from the workspace root:
   - `grep -n "spaceFileUrl" frontend/src/api.ts` — must return at least one match (I3 marker).
   - `grep -n "breadcrumb?:" frontend/src/components/FileBrowser.tsx` — must return one match (I2 marker).
   If either grep returns nothing, the workspace is NOT based on `feature/implement-file-browser`. Rebase or check out the feature branch BEFORE editing any code. Failing this check and proceeding will surface as validation_command failures and is a blocked-iteration signal.

2. **Read the YAML `iterations[]` as the machine-readable source of truth** — each entry's `scope_files`, `validation_command`, `max_diff_lines`, and `acceptance_criteria` are load-bearing for the verifier.

3. **For I4**: Compose `useBoard()` + `useSpaces()` + `api.taskFiles` + `api.taskFileUrl` + the I2 `breadcrumb` prop on `<FileBrowser/>`. Construct the tree client-side from `parent_id` adjacency. Wire the route in `router.tsx` (NOT `App.tsx`) and the NavLink in `Sidebar.tsx`'s `SpaceRow` (NOT a new component). Mount the page test via MemoryRouter against `/spaces/test-space/files` so a missing route registration fails in CI. Diff budget: 600 lines.

4. **For I5**: Author the regression test as the SOLE diff. If you find yourself needing to change `FilesPanel.tsx` (or any other source file) to make the test pass, STOP and escalate — the iteration's premise has failed. Use fake timers to assert the 10-second refetch interval; spy on `api.uploadTaskFile` and `api.saveTaskFile` to assert mutation wiring. Diff budget: 150 lines.

5. **Commit each iteration to `feature/implement-file-browser`** via `/goal-task-commit` after the per-iteration validation_command passes. Do NOT introduce a new feature branch.

6. **Surface in your impl-report next-consumer brief**:
   - The carry-forward 500-entry `list_files()` cap pragma (relevant for the space-scoped browser if a follow-up goal exposes `api.spaceFiles` on this page).
   - The carry-forward note that the page only exposes `.cronos/workspaces/` — linked git working tree is excluded.

The reviewer should verify that:
- I4's diff includes `router.tsx`, EXCLUDES `App.tsx`.
- I5's diff is a single new file (`FilesPanel.regression.test.tsx`) and touches NO source file.
- The Sidebar NavLink icon visually matches the existing tree NavLink (R4 review-phase verification).
- The breadcrumb text renders correctly in both selected/unselected modes (R5 visual cross-check after the test-phase machine assertion).
