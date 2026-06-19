---
cc_version: '1.0'
agent: pipeline-analyst
slug: file-browser
phase: analysis
status: done
confidence: 0.9
inputs_used:
- .cronos/pipeline/file-browser/scout-report-file-browser.md
- memory:project_pipeline_analyst_agent
- memory:project_pipeline_schemas
- memory:project_pipeline_verifier
outputs_produced:
- .cronos/pipeline/file-browser/analysis-report-file-browser.md
blockers: []
next_consumer: design
request: 'Implement the File Browser feature for Cronos. The feature includes:

  1. A dedicated File Browser page (sidebar-accessible) for navigating space hierarchy
  (space → goals/tasks → workspace files)

  2. Space-level file browsing API endpoints

  3. Unified FileBrowser component refactor so both the new page and existing task-detail
  panel share the same component'
has_ui: true
coverage_summary:
  searched:
  - frontend/src/components/FileBrowser.tsx
  - frontend/src/components/FilesPanel.tsx
  - frontend/src/types.ts
  - frontend/src/api.ts
  - backend/app/file_service.py
  - backend/app/api/tasks.py
  - frontend/src/router.tsx
  - frontend/src/App.tsx
  excluded:
  - backend/app/api/harnesses.py: unrelated to file management
  - frontend/src/pages/HarnessEditor.tsx: unrelated to file management
  - backend/app/storage.py: task state machine, not file I/O
  strategies:
  - memory_retrieval
  - read_targeted
traceability:
- requirement_id: R1
  statement: The backend exposes GET /api/spaces/{space_id}/files that lists files
    under the space root, covering .cronos/workspaces/ and the .cronos directory itself,
    and returns a list of FileEntry objects.
  acceptance_criteria:
  - Given a valid space_id, when GET /api/spaces/{space_id}/files is called, then
    the response contains a JSON array of FileEntry objects (name, path, size, modified_at,
    is_dir, category).
  - The endpoint resolves the space root via the existing space_dir_for() helper and
    delegates to file_service.list_files().
  - The endpoint is registered in backend/app/api/spaces.py and the router is wired
    in main.py.
  - Paths returned are relative to the space root (not absolute filesystem paths).
  verifying_phase: test
  confidence: 0.92
- requirement_id: R2
  statement: The backend exposes GET /api/spaces/{space_id}/files/{path:path} that
    retrieves or streams a specific file by its relative path under the space root,
    supports ?download=true, and uses path-traversal-safe resolution.
  acceptance_criteria:
  - Given a relative path to a file under the space root, when GET /api/spaces/{space_id}/files/{path:path}
    is called, then the file content is returned as a streaming response.
  - When ?download=true is included, the Content-Disposition header is set to attachment.
  - If the resolved absolute path escapes the space root (path traversal), the endpoint
    returns HTTP 400.
  - The endpoint reuses the resolve_safe() helper already present in backend/app/api/tasks.py.
  verifying_phase: test
  confidence: 0.92
- requirement_id: R3
  statement: 'The frontend provides a FileBrowserPage at route /spaces/:spaceId/files
    that renders a hierarchical tree view: space at the root, then task workspaces
    as child nodes, then files within each workspace.'
  acceptance_criteria:
  - A route /spaces/:spaceId/files exists in frontend/src/router.tsx and renders FileBrowserPage.
  - The page fetches the space's task list and renders each task/goal as a collapsible
    node in the tree.
  - Clicking a task/goal node loads that task's workspace files (R7) and displays
    them using the shared FileBrowser component (R5).
  - The page title or breadcrumb clearly identifies it as the space-level File Browser.
  verifying_phase: test
  confidence: 0.88
- requirement_id: R4
  statement: The frontend sidebar includes a navigation link to the File Browser page
    for the current space.
  acceptance_criteria:
  - A link to /spaces/:spaceId/files appears in the sidebar navigation for every space.
  - The link is visually consistent with other sidebar items (same icon/text style).
  - The active route /spaces/:spaceId/files is highlighted in the sidebar.
  verifying_phase: review
  confidence: 0.9
- requirement_id: R5
  statement: The FileBrowser component is refactored to accept an optional breadcrumb
    prop (navigation header), enabling both the new FileBrowserPage and the existing
    task-detail panel to embed it without duplicating layout or logic.
  acceptance_criteria:
  - 'FileBrowserProps gains an optional breadcrumb?: React.ReactNode field.'
  - When breadcrumb is provided, it is rendered above the file list as a navigation
    header.
  - When breadcrumb is absent, the component renders exactly as it does today (no
    visual regression).
  - All existing FileBrowser usages (FilesPanel) continue to compile and render without
    modification.
  verifying_phase: test
  confidence: 0.88
- requirement_id: R6
  statement: The FilesPanel component and all task-detail file panel functionality
    continue to work without regression after the FileBrowser refactor.
  acceptance_criteria:
  - 'Existing FilesPanel renders unchanged: file listing, upload, save, and 10-second
    refetch all function.'
  - No TypeScript compilation errors are introduced by the FileBrowser prop addition.
  - Existing tests for FilesPanel pass without modification.
  verifying_phase: test
  confidence: 0.95
- requirement_id: R7
  statement: Clicking a task/goal node in the FileBrowserPage hierarchical tree loads
    that task's files by calling the existing task file API (GET /api/tasks/{task_id}/files)
    and displays them in the embedded FileBrowser component.
  acceptance_criteria:
  - Selecting a task node in the tree triggers api.taskFiles(taskId) and populates
    the FileBrowser.
  - The fileUrlBuilder passed to FileBrowser constructs URLs via the existing api.taskFileUrl()
    helper.
  - If no task is selected, the FileBrowser renders an empty or placeholder state.
  - Loading and error states are handled and displayed to the user.
  verifying_phase: test
  confidence: 0.9
metrics:
  tool_calls: 7
  files_read: 3
  memory_hits: 3
---

## Summary

The File Browser feature adds a space-level file browsing experience to Cronos. Two backend endpoints will expose the space's file tree (list and retrieve), mirroring the existing task-scoped file API. A new FileBrowserPage at `/spaces/:spaceId/files` will render a hierarchical view (space → task workspaces → files) and link from the sidebar. The existing FileBrowser component receives a minor, backward-compatible `breadcrumb` prop to allow reuse from both the new page and the existing task-detail FilesPanel without code duplication. Scout findings confirm all underlying primitives already exist (`list_files`, `resolve_safe`, `fileUrlBuilder`, `api.taskFiles`), making this a low-risk, additive feature.

## Scope

### In scope
- Backend: `GET /api/spaces/{space_id}/files` — space-root file listing endpoint returning FileEntry list (covers `.cronos/workspaces/` and `.cronos/` dir per task brief)
- Backend: `GET /api/spaces/{space_id}/files/{path:path}` — space-root file retrieval/streaming with `?download=true` and path-traversal guard
- Frontend: `FileBrowserPage` at `/spaces/:spaceId/files` with hierarchical tree (space → tasks → files)
- Frontend: sidebar navigation link to the File Browser page
- Frontend: `FileBrowser` component `breadcrumb?: React.ReactNode` prop addition (additive, backward-compatible)
- Frontend: task-level file loading within the new page via the existing `GET /api/tasks/{task_id}/files` API
- Regression protection: `FilesPanel` and all existing task-detail file panel behavior must be unaffected

### Out of scope
- File upload to the space root (not requested)
- File save/edit at the space root level (not requested)
- Git integration or diff viewing for space-level files
- Search or filtering within the file browser
- Real-time file change notifications (polling is sufficient)
- Deletion of files via the browser

### Key findings from scout
- All backend file primitives (`list_files`, `classify_file`) in `backend/app/file_service.py` are path-agnostic and can be called with any root path (scout Finding 8)
- `resolve_safe()` path-traversal guard currently lives in `tasks.py`; R2 requires it for the spaces endpoint — design agent must decide extraction vs. duplication (scout Finding 5)
- `FileBrowserProps.fileUrlBuilder` already abstracts URL construction, so R5 is a minimal additive change (scout Finding 1)
- `api.ts` lines 104–105 contain an explicit gap comment: "Future mirror for space-level file manager" (scout Finding 4)
- Space-scoped routing pattern is well-established (scout Finding 9)
- No `GET /api/spaces/{space_id}/files` route and no `FileBrowserPage` exist today (scout Gaps G1, G2)

## Requirements

| R# | One-line statement |
|----|--------------------|
| R1 | Backend `GET /api/spaces/{space_id}/files` — list FileEntry objects under the space root |
| R2 | Backend `GET /api/spaces/{space_id}/files/{path:path}` — retrieve/stream a file with path-traversal guard and `?download=true` |
| R3 | Frontend `FileBrowserPage` at `/spaces/:spaceId/files` with hierarchical tree view (space → task workspaces → files) |
| R4 | Frontend sidebar navigation link to the File Browser page |
| R5 | `FileBrowser` refactored with optional `breadcrumb?: React.ReactNode` prop for reuse in both page and panel |
| R6 | `FilesPanel` and existing task-detail file panel must be regression-free after the refactor |
| R7 | Clicking a task/goal in the hierarchical tree loads that task's files via the existing task file API |

## Acceptance criteria

### R1 — Backend list endpoint
- Given a valid `space_id`, `GET /api/spaces/{space_id}/files` returns HTTP 200 with a JSON array of `FileEntry` objects (fields: `name`, `path`, `size`, `modified_at`, `is_dir`, `category`).
- The endpoint resolves the space root via the existing `space_dir_for()` helper and delegates to `file_service.list_files()`.
- The endpoint is registered in `backend/app/api/spaces.py` with the router wired in `main.py`.
- Paths returned are relative to the space root (not absolute filesystem paths).

### R2 — Backend file retrieval endpoint
- Given a relative path to a file, `GET /api/spaces/{space_id}/files/{path:path}` returns the file content as a streaming response.
- When `?download=true` is included, the `Content-Disposition: attachment` header is set.
- If the resolved absolute path escapes the space root (path traversal), the endpoint returns HTTP 400.
- The endpoint uses the same `resolve_safe()` helper as the task file endpoint (extracted or re-imported — no duplication).

### R3 — FileBrowserPage route and tree
- A route `/spaces/:spaceId/files` exists in `frontend/src/router.tsx` and renders `FileBrowserPage`.
- The page fetches the space's task list and renders each task/goal as a collapsible node in the tree.
- Clicking a task/goal node loads that task's workspace files (R7) and displays them using the shared `FileBrowser` component.
- The page title or breadcrumb clearly identifies it as the space-level File Browser.

### R4 — Sidebar navigation link
- A link to `/spaces/:spaceId/files` appears in the sidebar navigation for every space.
- The link is visually consistent with other sidebar items (same icon/text style).
- The active route `/spaces/:spaceId/files` is highlighted in the sidebar.

### R5 — FileBrowser breadcrumb prop
- `FileBrowserProps` gains an optional `breadcrumb?: React.ReactNode` field.
- When `breadcrumb` is provided, it is rendered above the file list as a navigation header.
- When `breadcrumb` is absent, the component renders exactly as it does today (no visual regression).
- All existing `FileBrowser` usages (`FilesPanel`) continue to compile and render without modification.

### R6 — FilesPanel regression-free
- Existing `FilesPanel` renders unchanged: file listing, upload, save, and 10-second refetch all function.
- No TypeScript compilation errors are introduced by the `FileBrowser` prop addition.
- Existing tests for `FilesPanel` pass without modification.

### R7 — Task file loading from tree
- Selecting a task node in the tree triggers `api.taskFiles(taskId)` and populates the `FileBrowser`.
- The `fileUrlBuilder` passed to `FileBrowser` constructs URLs via the existing `api.taskFileUrl()` helper.
- If no task is selected, the `FileBrowser` renders an empty or placeholder state.
- Loading and error states are handled and displayed to the user.

## Traceability

| R# | Source finding | Source gap | Verifying phase |
|----|---------------|------------|-----------------|
| R1 | Scout Finding 5 (GET /{task_id}/files pattern), Finding 8 (list_files is path-agnostic) | G2 (no space-level file API) | test |
| R2 | Scout Finding 5 (GET /{task_id}/files/{path:path} with resolve_safe), Finding 8 | G2 | test |
| R3 | Scout Finding 9 (routing pattern), Finding 10 (directory layout) | G1 (no space-level browser page) | test |
| R4 | Scout Finding 9 (sidebar NavLink pattern) | G1 | review |
| R5 | Scout Finding 1 (FileBrowserProps interface), Finding 2 (FilesPanel wrapper) | G3 (FileBrowser task-context only — risk: low) | test |
| R6 | Scout Finding 2 (FilesPanel is 54-line thin wrapper), G3 (refactoring risk: low) | G3 | test |
| R7 | Scout Finding 4 (api.taskFiles, taskFileUrl), linked to R3 interaction behavior | G1 | test |

## Assumptions

- `has_ui: true` rationale: the feature adds a new frontend page (FileBrowserPage) with sidebar navigation and a hierarchical tree UI; confirmed by request text and scout findings.
- The space root for file browsing is the `.cronos/workspaces/` subtree (task files only), not the raw git repo root. Scout G5 left this open; this assumption bounds scope. If the design agent determines a different root is needed, R1 acceptance criteria must be revisited.
- `list_files()` and `classify_file()` are called with the space's `.cronos/workspaces/` path as root for R1; the FileEntry `path` fields returned will be relative to that root.
- `resolve_safe()` will be extracted to `file_service.py` (or re-imported) rather than duplicated; the design agent will specify the extraction point.
- File upload to the space root is out of scope; the page is read-only for space-level browsing (users can still upload to a specific task workspace via the existing task-detail panel).
- The scout report has `status: done` and `confidence: 0.92`; this analysis inherits that confidence bound with no scout rerun needed.

## Open questions

1. **Space root path**: Should the list endpoint root at `.cronos/workspaces/` (task workspace files only) or the full `.cronos/` directory (including pipeline artifacts, test reports, etc.)? The task brief says "task workspaces + .cronos dir", which implies the full `.cronos/` is in scope. The design agent should confirm the exact root and whether `.cronos/` is listed as a node or browsed directly.
2. **Read-only vs. upload in FileBrowserPage**: The request does not mention upload functionality for the new page. The design agent should confirm the page is read-only at launch (task-level upload remains accessible via the task-detail panel only).

## Next consumer brief

The design agent (pipeline-architect) should read `traceability[]` (all 7 requirements) and the Scope section before beginning component decomposition.

Key design decisions:

1. **Backend router placement**: R1 and R2 add two new routes to `backend/app/api/spaces.py`. Determine where `resolve_safe()` lives after extraction — `file_service.py` is the natural home, avoiding two independent path-traversal guard implementations.
2. **Space root path**: Confirm the list endpoint roots at `.cronos/workspaces/` or the full `.cronos/` directory. This shapes the tree in R3 and the FileEntry path prefixes from R1.
3. **FileBrowserPage tree data source**: R3 needs the task list for the current space to render the hierarchy. Determine whether to use an existing tasks query hook or a new lightweight query, and how goals vs. leaf tasks are differentiated.
4. **breadcrumb prop typing**: R5 calls for `breadcrumb?: React.ReactNode`; the design must confirm `FilesPanel` callsite passes nothing (no regression) and that `FileBrowserProps` in `frontend/src/components/FileBrowser.tsx` is the single extension point.
5. **Risk area**: If `resolve_safe()` is duplicated instead of extracted, two independent implementations will drift over time. This is the primary design risk — address it explicitly in the iterations DAG.
