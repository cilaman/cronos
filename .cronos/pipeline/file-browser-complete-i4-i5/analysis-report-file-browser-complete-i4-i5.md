---
cc_version: '1.0'
agent: pipeline-analyst
slug: file-browser-complete-i4-i5
phase: analysis
status: done
confidence: 0.93
inputs_used:
- memory:project_file_browser_i3_impl
- .cronos/pipeline/file-browser-complete-i4-i5/scout-report-file-browser-complete-i4-i5.md
- .cronos/pipeline/file-browser/design-report-file-browser.md
- .cronos/pipeline/file-browser/impl-report-file-browser--i3.md
outputs_produced:
- .cronos/pipeline/file-browser-complete-i4-i5/analysis-report-file-browser-complete-i4-i5.md
blockers: []
next_consumer: design
request: 'Finish the File Browser feature by implementing design iterations I4 and
  I5.


  **Context:** The file-browser goal completed iterations I1–I3 (backend endpoints,
  FileBrowser breadcrumb prop, frontend API client) but iterations I4 (FileBrowserPage
  + route + Sidebar) and I5 (FilesPanel regression test) were not scheduled. This
  goal completes the feature using the CC v1 pipeline and commits to the shared `feature/implement-file-browser`
  branch.


  **Iterations to implement:**

  - **I4**: FileBrowserPage component, route registration in router.tsx, Sidebar navigation
  link

  - **I5**: FilesPanel regression test guard (must NOT modify FilesPanel.tsx)


  **Design reference:** `.cronos/pipeline/file-browser/design-report-file-browser.md`
  (iterations[] define I4 and I5 acceptance criteria, scope_files, and validation
  commands)'
has_ui: true
coverage_summary:
  searched:
  - .cronos/pipeline/file-browser-complete-i4-i5/
  - .cronos/pipeline/file-browser/
  - frontend/src/pages/
  - frontend/src/components/__tests__/
  excluded:
  - backend/: I4 and I5 are frontend-only; I1 backend endpoints already verified by
      scout
  - frontend/src/pages/__tests__/: FileBrowserPage.test.tsx does not yet exist (I4
      will create it)
  strategies:
  - memory_retrieval
  - read_targeted
traceability:
- requirement_id: R1
  statement: FileBrowserPage renders a hierarchical tree of space tasks and goals
    as collapsible nodes.
  acceptance_criteria:
  - Given a space is selected, when the user navigates to /spaces/:spaceId/files,
    FileBrowserPage renders a tree of tasks/goals for that space using data from the
    existing useTasks() hook.
  - 'Tasks and goals are presented as collapsible tree nodes; the tree collapses to
    a single-column stack on viewports below the md: Tailwind breakpoint.'
  - A page test mounts FileBrowserPage via MemoryRouter against the registered route
    (not direct component render) and asserts the tree nodes render from mocked task
    data.
  verifying_phase: test
  confidence: 0.95
- requirement_id: R2
  statement: Clicking a task node in the tree loads that task's files and displays
    them in the embedded FileBrowser component.
  acceptance_criteria:
  - Given FileBrowserPage is rendered and a task is visible in the tree, when the
    user clicks a task node, the page calls api.taskFiles(taskId) (NOT api.spaceFiles)
    and passes the result to <FileBrowser/>.
  - The fileUrlBuilder prop passed to <FileBrowser/> calls api.taskFileUrl(taskId,
    path, download) matching the FileBrowser API contract.
  - When no task is selected, the FileBrowser is hidden or an empty-state placeholder
    is shown with guidance text.
  - The page test asserts api.taskFiles is called with the correct taskId on node
    click and that FileBrowser receives the resulting files array.
  verifying_phase: test
  confidence: 0.92
- requirement_id: R3
  statement: Route /spaces/:spaceId/files is registered in router.tsx (NOT App.tsx).
  acceptance_criteria:
  - frontend/src/router.tsx gains a <Route path="spaces/:spaceId/files" element={<FileBrowserPage/>}
    /> entry before the catch-all * route.
  - App.tsx is NOT modified — it contains only <Outlet/> and must remain unchanged.
  - The page test mounts via MemoryRouter with the exact path /spaces/:spaceId/files,
    confirming the route registration is present and the component is reachable.
  verifying_phase: test
  confidence: 0.97
- requirement_id: R4
  statement: Sidebar has a NavLink to /spaces/:spaceId/files that highlights when
    the route is active.
  acceptance_criteria:
  - frontend/src/components/Sidebar.tsx gains a NavLink to /spaces/:spaceId/files
    grouped with other space-scoped links (Tree, Settings, Space Tools, Harnesses).
  - The link uses a folder/files-themed SVG icon consistent with the existing Cronos
    sidebar icon pattern.
  - The link is rendered only when a space is selected, matching the existing /spaces/:spaceId/*
    conditional pattern.
  - NavLink's active class is applied when the current route matches /spaces/:spaceId/files.
  verifying_phase: review
  confidence: 0.9
- requirement_id: R5
  statement: FileBrowserPage wires the I2 breadcrumb prop to FileBrowser with contextual
    space/task text.
  acceptance_criteria:
  - When no task is selected, the breadcrumb text passed to <FileBrowser breadcrumb=...>
    reads 'Space {space_name}'.
  - When a task is selected, the breadcrumb text reads 'Space {space_name} / {task_name}'.
  - The page test asserts breadcrumb prop updates correctly when a task node is clicked
    (before and after selection).
  verifying_phase: test
  confidence: 0.88
- requirement_id: R6
  statement: Loading and error states for the task list query and the per-task file
    query are rendered in FileBrowserPage.
  acceptance_criteria:
  - While the task list is loading (useTasks pending), FileBrowserPage renders a skeleton/spinner
    element.
  - If the task list query fails, FileBrowserPage renders an error banner.
  - While the per-task files query is loading after task selection, the FileBrowser
    area shows a loading indicator.
  - If the per-task files query fails, an error banner is shown in the FileBrowser
    area.
  - The page test asserts the loading and error states via mocked query responses.
  verifying_phase: test
  confidence: 0.9
- requirement_id: R7
  statement: FilesPanel.regression.test.tsx asserts that the I2 breadcrumb prop addition
    introduces zero DOM change when FilesPanel omits the prop.
  acceptance_criteria:
  - A new file frontend/src/components/__tests__/FilesPanel.regression.test.tsx is
    created; it is the ONLY file changed in I5.
  - The test asserts FilesPanel mounts with only taskId (and optionally className)
    and that the rendered output does NOT contain a breadcrumb header element.
  - The test asserts the 10-second refetch interval is still configured on the useQuery
    hook for api.taskFiles (via fake timers advancing and asserting a second fetch,
    or by inspecting the React Query observer).
  - The test asserts upload and save mutation callbacks remain wired to FileBrowser
    (callback presence assertions on FileBrowser props or mocked api spies).
  - FilesPanel.tsx is NOT modified in I5 — if the diff touches it, the iteration has
    failed its premise and must be escalated.
  verifying_phase: test
  confidence: 0.97
metrics:
  tool_calls: 6
  files_read: 3
  memory_hits: 1
---

## Summary

This analysis decomposes the remaining two File Browser iterations — I4 (FileBrowserPage + route + Sidebar NavLink) and I5 (FilesPanel regression guard) — into seven atomic, testable requirements. I1–I3 are verified complete by the scout: backend list/retrieve endpoints live in `spaces.py`, the `breadcrumb` prop is wired in `FileBrowser.tsx`, and `api.spaceFiles` / `spaceFileUrl` are exported from `api.ts`. I4 composes these foundations into the user-facing page; I5 is a pure test-only guard that must never touch `FilesPanel.tsx`. `has_ui: true` because I4 introduces a new React page, route, and sidebar link.

## Scope

### In scope
- `FileBrowserPage.tsx` (NEW) — hierarchical task/goal tree + embedded FileBrowser on task selection
- Route registration in `router.tsx` at `spaces/:spaceId/files`
- Sidebar NavLink to `/spaces/:spaceId/files` in `Sidebar.tsx`
- Breadcrumb prop wiring: "Space {name}" / "Space {name} / {task}" context text
- Loading and error states for both the task-list query and per-task files query
- `FilesPanel.regression.test.tsx` (NEW) — test-only regression guard for R7 / I5

### Out of scope
- Modifications to `FilesPanel.tsx` (must remain unchanged — I5 is a guard, not a source edit)
- Modifications to `App.tsx` (layout shell only; route belongs in `router.tsx`)
- `api.spaceFiles` usage in I4 (task-click wires `api.taskFiles`, not the new space-level API)
- File upload or save UI at the space level (deferred to a follow-up goal)
- Pagination of the file list (500-entry cap is a known limitation, deferred per design Risk #4)

### Deferred
- Pagination for `list_files()` beyond the 500-entry cap
- Display of the linked git working tree (page shows `.cronos/workspaces/` subtree only at launch)
- Space-level file upload/edit UI

## Requirements

| R# | One-line summary |
|----|------------------|
| R1 | FileBrowserPage renders a hierarchical task/goal tree using useTasks() |
| R2 | Task node click loads task files via api.taskFiles and shows them in FileBrowser |
| R3 | Route spaces/:spaceId/files is registered in router.tsx (not App.tsx) |
| R4 | Sidebar NavLink to /spaces/:spaceId/files with active-route highlight |
| R5 | FileBrowserPage wires breadcrumb prop with space/task context text |
| R6 | Loading and error states rendered for task-list and file queries |
| R7 | FilesPanel.regression.test.tsx guards zero DOM change from I2 breadcrumb prop |

## Acceptance criteria

Acceptance criteria for every requirement are listed in the YAML `traceability[]` array (the machine-readable source of truth). Summary:

- R1 — useTasks() provides tree data; vitest test mounts via MemoryRouter route; responsive collapse below md:
- R2 — api.taskFiles(taskId) called on node click; fileUrlBuilder = api.taskFileUrl; empty-state when nothing selected
- R3 — Route in router.tsx only; App.tsx unchanged; page test exercises registered route
- R4 — NavLink in Sidebar.tsx grouped with space-scoped links; folder/files icon; active class when route matches
- R5 — Breadcrumb text "Space {name}" unselected, "Space {name} / {task}" selected; test asserts both states
- R6 — Skeleton/spinner during loading; error banner on failure for both task list and file queries
- R7 — New test file only; asserts no breadcrumb element; asserts 10s refetch; asserts mutation callbacks; FilesPanel.tsx NOT touched

## Traceability

The full requirement → acceptance criteria → verifying_phase map is the YAML `traceability[]` array.

| R# | Verifying phase | Statement |
|----|-----------------|-----------|
| R1 | test | FileBrowserPage renders a hierarchical tree of space tasks and goals as collapsible nodes. |
| R2 | test | Clicking a task node loads that task's files and displays them in the embedded FileBrowser component. |
| R3 | test | Route /spaces/:spaceId/files is registered in router.tsx (NOT App.tsx). |
| R4 | review | Sidebar has a NavLink to /spaces/:spaceId/files that highlights when the route is active. |
| R5 | test | FileBrowserPage wires the I2 breadcrumb prop with contextual space/task text. |
| R6 | test | Loading and error states for the task list and per-task file queries are rendered. |
| R7 | test | FilesPanel.regression.test.tsx asserts zero DOM change when the breadcrumb prop is omitted. |

## Assumptions

- **I1–I3 are fully shipped** — scout confirmed commits e09a95e (I1), ddfcf5c (I2), 844d52d (I3) are merged to main and all acceptance criteria pass. This analysis builds directly on that baseline without re-verifying those iterations.
- **has_ui: true** — I4 introduces a new React page (`FileBrowserPage.tsx`), a route entry, and a sidebar navigation link. All involve user-visible rendering and interaction.
- **R4 is review-verified** — the NavLink's visual placement and icon styling are best confirmed by a human reviewer looking at the running UI; no automated assertion captures visual grouping or icon fidelity. All other requirements are test-verified.
- **useTasks() hook is the correct data source for the task tree** — the existing `frontend/src/hooks/useTasks.ts` returns all tasks for a space; React Query caching prevents redundant fetches. No new query or API endpoint is required for the tree.
- **api.taskFiles (not api.spaceFiles) is correct for R2** — the design explicitly directs I4 to reuse the existing task-file endpoint when a task is selected; `api.spaceFiles` is intentionally not used on this code path.
- **FilesPanel.tsx must not be modified in I5** — this is both a design constraint and the entire premise of the regression guard iteration. Any I5 diff touching FilesPanel.tsx is an escalation signal, not a fix.

## Open questions

- None. All design open questions (space root scope, upload UI, route placement) were resolved in the upstream design report's Assumptions section.

## Next consumer brief

The **design agent** (or, since a complete design already exists in `design-report-file-browser.md`, the **implementor**) should:

1. Read `traceability[]` — especially R3 (router.tsx, NOT App.tsx) and R7 (FilesPanel.tsx must NOT be touched in I5) — these are the highest-risk invariants.
2. Use the existing `design-report-file-browser.md` iterations I4 and I5 as the implementation DAG; the `scope_files`, `validation_command`, `acceptance_criteria`, and `max_diff_lines` are already fully specified there.
3. Note that R4 is `verifying_phase: review` — the sidebar NavLink visual placement and icon consistency cannot be automatically tested; flag this for the reviewer to visually check.
4. Preserve the **I4 / I5 ordering** in the DAG: I4 depends on both I2 and I3 (both done); I5 depends only on I2 (done) and is independent of I4 — they can be executed in parallel.
5. Implementors: `FilesPanel.regression.test.tsx` is the only file in I5 scope; escalate if any other file appears in the I5 diff.
