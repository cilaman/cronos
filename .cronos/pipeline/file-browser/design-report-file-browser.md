---
cc_version: '1.0'
agent: pipeline-architect
slug: file-browser
phase: design
status: done
confidence: 0.86
inputs_used:
- memory:project_pipeline_architect_agent
- memory:project_pipeline_schemas
- memory:project_pipeline_verifier
- .cronos/pipeline/file-browser/analysis-report-file-browser.md
- .cronos/pipeline/file-browser/scout-report-file-browser.md
- backend/app/api/tasks.py
- backend/app/api/spaces.py
- backend/app/agent.py
- backend/app/file_service.py
- frontend/src/App.tsx
- frontend/src/router.tsx
outputs_produced:
- .cronos/pipeline/file-browser/design-report-file-browser.md
blockers: []
next_consumer: impl
coverage_summary:
  searched:
  - backend/app/api/
  - backend/app/file_service.py
  - backend/app/agent.py
  - frontend/src/router.tsx
  - frontend/src/App.tsx
  - frontend/src/components/Sidebar.tsx
  - frontend/src/components/FileBrowser.tsx
  - frontend/src/components/FilesPanel.tsx
  excluded:
  - 'frontend/src/pages/HarnessEditor.tsx: unrelated to file management'
  - 'backend/app/harnesses/: unrelated to file management'
  - 'backend/app/storage.py: task state machine, not file I/O'
  strategies:
  - memory_retrieval
  - read_targeted
  - grep_symbol
iterations:
- id: I1
  type: backend
  title: Space file API endpoints (list + retrieve) with traversal guard
  scope_files:
  - backend/app/api/spaces.py
  - backend/tests/test_space_files.py
  validation_command: cd backend && pytest tests/test_space_files.py -xvs
  max_diff_lines: 350
  depends_on: []
  acceptance_criteria:
  - 'R1: GET /api/spaces/{space_id}/files returns 200 with FileEntry[] (name, path,
    size, modified_at, is_dir, category); paths are relative to the space root.'
  - 'R1: Endpoint resolves the space root via the existing space_dir_for() helper
    from backend/app/agent.py and delegates to file_service.list_files().'
  - 'R1: The space root passed to list_files is space_dir_for(space_id) / CRONOS_SUBDIR
    / ''workspaces'' (resolves Open Question Q1; .cronos/workspaces/ subtree only
    — matches analyst''s stated assumption and limits read surface).'
  - 'R1: New router prefix /api/spaces/{space_id}/files is registered inside the existing
    APIRouter in spaces.py (prefix=''/api/spaces'' already in place — no main.py changes
    required for router wiring; verify by reading the file).'
  - 'R2: GET /api/spaces/{space_id}/files/{file_path:path} streams file contents;
    uses resolve_safe(workspace_root, file_path) imported directly from backend/app/file_service
    (resolve_safe ALREADY lives there — no extraction is needed; this overrides the
    analyst''s extraction assumption).'
  - 'R2: When ?download=true is included, response sets Content-Disposition: attachment;
    default behavior streams inline.'
  - 'R2: Path-traversal attempt (e.g. ../../etc/passwd) returns HTTP 400 with a non-leaky
    error message.'
  - 'R2: Missing file or directory target returns HTTP 404.'
  - 'Test file backend/tests/test_space_files.py covers: happy-path list, empty workspaces
    directory, path traversal rejected (400), file streamed inline, ?download=true
    sets attachment header, 404 for missing path, and unknown space_id returns 404.'
  - Backend coverage floor (60%) must still pass when test suite runs holistically.
- id: I2
  type: frontend
  title: FileBrowser breadcrumb prop (additive, backward-compatible)
  scope_files:
  - frontend/src/components/FileBrowser.tsx
  - frontend/src/components/__tests__/FileBrowser.test.tsx
  validation_command: cd frontend && npx vitest run src/components/__tests__/FileBrowser.test.tsx
  max_diff_lines: 200
  depends_on: []
  acceptance_criteria:
  - 'R5: FileBrowserProps gains an optional field `breadcrumb?: React.ReactNode`.'
  - 'R5: When breadcrumb is provided, the node is rendered above the file list inside
    a header region (semantically a nav/header element) without altering the existing
    file-list layout.'
  - 'R5: When breadcrumb is undefined, the component DOM output is byte-identical
    to the pre-change render (no extra wrapping element, no extra className). The
    test must assert this.'
  - 'R5/R6: All existing FilesPanel usage (which does NOT pass breadcrumb) continues
    to compile and render unchanged — TypeScript build remains green.'
  - 'Tests cover: (a) prop omitted -> no breadcrumb element in DOM; (b) prop = string
    -> rendered above file list; (c) prop = JSX node -> rendered; (d) all existing
    FileBrowser tests still pass without modification.'
- id: I3
  type: frontend
  title: Frontend API client for space files (typed)
  scope_files:
  - frontend/src/api.ts
  - frontend/src/types.ts
  - frontend/src/__tests__/api.spaceFiles.test.ts
  validation_command: cd frontend && npx vitest run src/__tests__/api.spaceFiles.test.ts
  max_diff_lines: 200
  depends_on:
  - I1
  acceptance_criteria:
  - 'R1/R7 plumbing: Add `api.spaceFiles(spaceId): Promise<TaskFile[]>` calling GET
    /api/spaces/{spaceId}/files — reuses the existing TaskFile type (backend FileEntry
    already has the same 6 fields per scout Finding 6), no new type required. Document
    the reuse decision in the api.ts comment block (replace the existing ''Future
    mirror'' comment at lines 104–105).'
  - 'R2 plumbing: Add `spaceFileUrl(spaceId, filePath, download=false): string` that
    returns `/api/spaces/{spaceId}/files/{encoded-path}{?download=true}` mirroring
    the existing taskFileUrl() helper (same encodeURIComponent-per-segment logic).'
  - 'Tests cover: spaceFileUrl encodes each path segment, appends ?download=true only
    when requested; api.spaceFiles returns parsed JSON; 404 propagates as a thrown
    error consistent with existing api.taskFiles error handling.'
  - No change to existing taskFiles / taskFileUrl APIs — R6 regression guard.
- id: I4
  type: frontend
  title: FileBrowserPage with hierarchical tree, task selection, and embedded FileBrowser
  scope_files:
  - frontend/src/pages/FileBrowserPage.tsx
  - frontend/src/pages/__tests__/FileBrowserPage.test.tsx
  - frontend/src/router.tsx
  - frontend/src/components/Sidebar.tsx
  validation_command: cd frontend && npx vitest run src/pages/__tests__/FileBrowserPage.test.tsx
  max_diff_lines: 600
  depends_on:
  - I2
  - I3
  acceptance_criteria:
  - 'R3: New page component frontend/src/pages/FileBrowserPage.tsx renders a hierarchical
    tree (space root -> tasks/goals collapsible nodes -> embedded FileBrowser when
    a task is selected).'
  - 'R3: Route `/spaces/:spaceId/files` is added to frontend/src/router.tsx (NOT App.tsx
    — App.tsx is only a layout shell with <Outlet/>; the scout report''s mention of
    App.tsx as the route source was incorrect, and this design follows router.tsx
    per scout Finding 9).'
  - 'R3: Page title / breadcrumb identifies the page as the space-level File Browser.
    The breadcrumb is wired into the FileBrowser component using the R5 breadcrumb
    prop (showing ''Space {space_name} / {task_name}'' when a task is selected, or
    ''Space {space_name}'' otherwise).'
  - 'R4: A sidebar NavLink to `/spaces/:spaceId/files` is added to frontend/src/components/Sidebar.tsx,
    grouped with other space-scoped links (Tree, Settings, Space Tools, Harnesses);
    the link is highlighted via NavLink''s active class when the route matches.'
  - 'R4: Sidebar link uses an icon consistent with existing entries (e.g. a folder/files
    SVG) and is rendered only when a space is selected, matching the existing `/spaces/:spaceId/*`
    link pattern.'
  - 'R7: When the user clicks a task node in the tree, the page calls `api.taskFiles(taskId)`
    (NOT the new space file API — R7 explicitly requires reusing the existing task
    file endpoint) and passes the resulting files plus `(path, dl) => api.taskFileUrl(taskId,
    path, dl)` as fileUrlBuilder to <FileBrowser/>.'
  - 'R7: When no task is selected, the FileBrowser is hidden OR rendered with an empty-state
    placeholder (page shows guidance text).'
  - 'R7: Loading and error states for both the task list query and the per-task files
    query are rendered (skeleton/spinner during loading; an error banner on failure).'
  - 'Tests cover: page renders task list as a tree, clicking a task triggers a files
    query and shows files in FileBrowser, empty-state when no task selected, loading
    state, error state, and breadcrumb text updates with selection. Mock api.taskFiles
    and the task-list query via MSW or the existing test-utils pattern used by other
    page tests.'
- id: I5
  type: frontend
  title: FilesPanel regression guard (R6) — confirm zero-change rendering
  scope_files:
  - frontend/src/components/__tests__/FilesPanel.regression.test.tsx
  validation_command: cd frontend && npx vitest run src/components/__tests__/FilesPanel.regression.test.tsx
  max_diff_lines: 150
  depends_on:
  - I2
  acceptance_criteria:
  - 'R6: A new regression test file asserts FilesPanel still mounts with only `taskId`
    (and optionally `className`) and renders FileBrowser without a breadcrumb.'
  - 'R6: Test asserts FilesPanel''s rendered output does NOT contain a breadcrumb
    header element (because it does not pass the prop).'
  - 'R6: Test asserts the 10-second refetch interval is still configured on the underlying
    useQuery hook for api.taskFiles (e.g. via inspecting the React Query observer,
    or by advancing fake timers and asserting a second fetch is issued).'
  - 'R6: Test asserts upload and save mutations remain wired (callback assertions
    on FileBrowser props or mocked api spies).'
  - Does NOT modify FilesPanel.tsx itself — the whole point of R6 is that NO source
    file in the FilesPanel path needs to change. If this iteration's diff touches
    FilesPanel.tsx, the iteration has failed its premise and must be returned to design.
risks:
- description: Backend path-traversal regression — if R2 imports a stale resolve_safe
    or shadows it with a local helper, the endpoint could leak files outside the space
    root. Compounded by the analyst's incorrect note that resolve_safe lives in tasks.py
    (it actually lives in file_service.py).
  severity: high
  mitigation: I1's acceptance criteria explicitly direct the implementor to import
    resolve_safe from backend/app/file_service (with file path) — single source of
    truth. The dedicated traversal test (`../../etc/passwd -> 400`) in test_space_files.py
    is mandatory and is the validation_command's first assertion.
- description: 'Route placement mismatch — the brief and the analyst both reference
    both router.tsx and App.tsx for routing. App.tsx is in fact only a layout shell
    (verified by grep: contains only <Outlet/>, no <Route>). An implementor who edits
    App.tsx instead of router.tsx will silently produce a 404 in the live app while
    tests may still pass if they mount the page directly.'
  severity: medium
  mitigation: I4's acceptance criteria explicitly call out router.tsx as the route
    source of truth and explicitly forbid editing App.tsx for routing. The FileBrowserPage
    test must mount via MemoryRouter against the route from router.tsx, not by direct
    component render, so a route-registration miss is caught in CI.
- description: Breadcrumb prop introduces a DOM wrapper that breaks FilesPanel's CSS
    expectations (mobile drawer width, padding) — R6 regression.
  severity: medium
  mitigation: I2 acceptance criteria require byte-identical DOM output when `breadcrumb`
    is undefined (no extra wrapper element). I5 is a dedicated regression test iteration
    whose only job is to fail loudly if FilesPanel rendering changes.
- description: Large workspaces directory — list_files has a 500-entry cap (per scout
    Finding 8). A space with many tasks and files may silently truncate, hiding files
    the user expects to see.
  severity: medium
  mitigation: 'I1 documents the 500-entry cap behavior in test_space_files.py (assert
    behavior at boundary). Tracked as deferred follow-up: pagination is out of scope
    for this design (analyst''s Out-of-Scope list); a follow-up goal is recommended
    if real usage exceeds the cap. Surface this in the impl-report''s next-consumer
    brief so doc-sync flags it.'
- description: Mobile layout regression in FileBrowserPage — the page's tree-plus-embedded-FileBrowser
    two-column layout may not collapse cleanly on small viewports.
  severity: low
  mitigation: I4 acceptance criteria require responsive layout (stack vertically below
    `md:` breakpoint, matching the BoardPage and TreePage conventions used in this
    codebase). FileBrowserPage tests include a viewport-collapse render check via
    Tailwind class assertions; visual QA is deferred to the review phase.
- description: Task list query inflation — fetching the entire task list to render
    the tree may slow down spaces with hundreds of tasks. The existing useTasks()
    hook returns all tasks for a space, so reusing it is correct but performance-sensitive.
  severity: low
  mitigation: I4 reuses the existing useTasks() hook from frontend/src/hooks/useTasks.ts
    (no new query); React Query caching already prevents redundant fetches. Tree rendering
    uses the existing TreePage's collapsible-node pattern (dagre-free, parent->children
    adjacency on the client) to avoid extra dependencies.
metrics:
  tool_calls: 12
  files_read: 8
  memory_hits: 3
  iterations_planned: 5
---

## Summary

The File Browser feature adds a space-level file browser at `/spaces/:spaceId/files` while keeping the existing task-scoped FilesPanel untouched. The DAG splits cleanly along type boundaries: one backend iteration (I1) ships both REST endpoints with a traversal guard; two parallel layer-0 frontend iterations land the `breadcrumb` prop on FileBrowser (I2) and the new API client (I3) — both independent and parallelizable with I1; I4 then composes them into the new page, route, and sidebar link; I5 is a dedicated regression iteration that guards FilesPanel against the R5 prop addition. The plan corrects two analyst assumptions: `resolve_safe()` already lives in `file_service.py` (no extraction churn needed), and routes live in `router.tsx` (not `App.tsx`, which is only a layout shell).

## Components

### Data
- `FileEntry` (existing, `backend/app/file_service.py`): reused verbatim by the new space file endpoints; no schema change.
- `TaskFile` (existing, `frontend/src/types.ts`): reused by the new `api.spaceFiles()` client since backend FileEntry has identical shape.

### Backend
- `backend/app/api/spaces.py`: gains `GET /{space_id}/files` and `GET /{space_id}/files/{file_path:path}` on the existing APIRouter; router is already wired in `main.py`.
- `backend/app/file_service.py` (reused only): `list_files()`, `classify_file()`, `resolve_safe()` consumed without modification — single source of truth for path-traversal safety.
- `backend/app/agent.py` (reused only): `space_dir_for()` and `CRONOS_SUBDIR` consumed without modification.

### Frontend
- `frontend/src/pages/FileBrowserPage.tsx` (NEW): hierarchical tree page — space root, collapsible task/goal nodes, embedded `<FileBrowser/>` with breadcrumb.
- `frontend/src/components/FileBrowser.tsx` (EXTENDED): adds optional `breadcrumb?: React.ReactNode` prop; existing render path unchanged when prop is omitted.
- `frontend/src/components/FilesPanel.tsx` (UNCHANGED): wraps FileBrowser without passing breadcrumb — R6 regression guard.
- `frontend/src/router.tsx` (EXTENDED): adds `<Route path="spaces/:spaceId/files" element={<FileBrowserPage/>} />`.
- `frontend/src/components/Sidebar.tsx` (EXTENDED): adds a NavLink to `/spaces/:spaceId/files` grouped with other space-scoped links.
- `frontend/src/api.ts` (EXTENDED): adds `api.spaceFiles(spaceId)` and `spaceFileUrl(spaceId, path, download?)`; existing task-file APIs untouched.

## Implementation plan

| ID  | Type     | Depends on  | Scope files (abridged)                                                                                  | Validation                                                                                |
|-----|----------|-------------|---------------------------------------------------------------------------------------------------------|-------------------------------------------------------------------------------------------|
| I1  | backend  | -           | backend/app/api/spaces.py, backend/tests/test_space_files.py                                            | cd backend && pytest tests/test_space_files.py -xvs                                       |
| I2  | frontend | -           | frontend/src/components/FileBrowser.tsx, frontend/src/components/__tests__/FileBrowser.test.tsx         | cd frontend && npx vitest run src/components/__tests__/FileBrowser.test.tsx               |
| I3  | frontend | I1          | frontend/src/api.ts, frontend/src/types.ts, frontend/src/__tests__/api.spaceFiles.test.ts               | cd frontend && npx vitest run src/__tests__/api.spaceFiles.test.ts                        |
| I4  | frontend | I2, I3      | frontend/src/pages/FileBrowserPage.tsx, .../__tests__/FileBrowserPage.test.tsx, router.tsx, Sidebar.tsx | cd frontend && npx vitest run src/pages/__tests__/FileBrowserPage.test.tsx                |
| I5  | frontend | I2          | frontend/src/components/__tests__/FilesPanel.regression.test.tsx                                        | cd frontend && npx vitest run src/components/__tests__/FilesPanel.regression.test.tsx     |

Topological layers (for orchestrator fan-out):

- Layer 0 (parallel): I1, I2
- Layer 1 (parallel): I3 (depends on I1 contract), I5 (depends on I2)
- Layer 2: I4 (depends on I2 + I3)

## Risks

| Risk                                                                | Severity | Mitigation                                                                                                  |
|---------------------------------------------------------------------|----------|-------------------------------------------------------------------------------------------------------------|
| Path-traversal regression via stale/local resolve_safe              | high     | I1 imports resolve_safe from file_service.py (correcting analyst); traversal test mandatory in I1.          |
| Route placement (App.tsx vs router.tsx) mismatch                    | medium   | I4 ACs forbid touching App.tsx for routing; page test mounts via MemoryRouter against the registered route. |
| Breadcrumb prop changes FilesPanel DOM (R6)                         | medium   | I2 ACs require byte-identical DOM when prop is omitted; I5 is a dedicated regression guard.                 |
| 500-entry list_files cap truncates large workspaces                 | medium   | I1 documents the cap in test_space_files.py boundary case; pagination deferred (out of scope per analyst).  |
| Mobile layout regression in FileBrowserPage                         | low      | I4 ACs require responsive collapse below `md:`; class assertions in tests; visual QA in review phase.       |
| Task list query inflation                                           | low      | I4 reuses existing useTasks() hook + React Query cache; client-side tree from adjacency only.               |

## Traceability

| R# | Covered by iteration(s) | Notes                                                                                                  |
|----|-------------------------|--------------------------------------------------------------------------------------------------------|
| R1 | I1                      | Backend list endpoint; root = `.cronos/workspaces/` per Q1 resolution.                                 |
| R2 | I1                      | Backend retrieval endpoint with resolve_safe (file_service.py), ?download support, 400 on traversal.   |
| R3 | I4                      | FileBrowserPage + route in router.tsx; depends on I2 (breadcrumb) and I3 (API client).                 |
| R4 | I4                      | Sidebar NavLink to /spaces/:spaceId/files; active-route highlight via NavLink class.                   |
| R5 | I2                      | FileBrowser breadcrumb prop addition; DOM-identical when omitted.                                      |
| R6 | I5 (+ I2 ACs)           | Dedicated regression test iteration; I2 also guarantees zero-change DOM in the omitted-prop case.      |
| R7 | I4                      | Task-node click -> api.taskFiles(taskId) + api.taskFileUrl as fileUrlBuilder; empty/loading/error UX.  |

## Assumptions

- **Space root for R1 is `.cronos/workspaces/`** (resolving analyst Open Question Q1): this matches the analyst's stated assumption, is the minimum-risk read surface, and aligns with R7's task-file semantics. The full `.cronos/` directory and the linked git working tree are explicitly out of scope for this design; revisit if a follow-up goal requests it.
- **FileBrowserPage is read-only at launch** (resolving analyst Open Question Q2): no upload or save UI on the new page — task-level upload remains accessible via the existing task-detail FilesPanel. This is consistent with the analyst's Out-of-Scope list ("File upload to the space root", "File save/edit at the space root level").
- **`resolve_safe()` extraction is unnecessary** — it already lives in `backend/app/file_service.py` (verified by grep). The analyst's risk about "extraction churn" does not apply; both endpoints simply import it. The existing `tasks.py` usage will continue to work.
- **Router source of truth is `router.tsx`** — verified by grep: `App.tsx` contains only `<Outlet/>` and zero `<Route>` definitions. The brief's "router.tsx vs App.tsx" ambiguity is resolved in favor of router.tsx.
- **Backend coverage floor (60%) is not at risk** — I1 only adds new code (two endpoints + tests); the new test file alone exercises the new endpoints fully.

## Open questions

- None blocking. Both analyst open questions (Q1 space root, Q2 upload UI) are resolved in `## Assumptions` above.

## Next consumer brief

Implementors should read the YAML `iterations[]` (specifically each iteration's `scope_files`, `validation_command`, and embedded `acceptance_criteria`) as the machine-readable source of truth. Two cross-iteration invariants that the YAML cannot encode and that all implementors must respect:

1. **Path strings are load-bearing.** I3 emits the literal URL template `/api/spaces/{spaceId}/files/{encoded-path}`; I1 must register exactly that path in `spaces.py` (no trailing slash). If either drifts, I4's integration test will fail at run time.
2. **R6 is a property, not a feature.** I5 must not modify FilesPanel.tsx — its purpose is to fail if anyone else's iteration accidentally breaks it. If I5's diff touches FilesPanel.tsx, the iteration has failed its premise and the implementor should escalate rather than satisfy the test by editing the source.

Two unresolved-but-deferred items implementors should surface in their impl-reports' next-consumer briefs so doc-sync / retro can pick them up:

- The `list_files()` 500-entry cap (Risk #4) — flag if any test data approaches the cap.
- The space root scope (`.cronos/workspaces/` only) — note in user-facing docs that the page does NOT show the linked git working tree at launch.

The reviewer should verify that no iteration's diff bleeds outside its declared `scope_files`, with particular attention to I5 (must not touch FilesPanel.tsx) and I4 (must edit router.tsx, NOT App.tsx, for the route registration).
