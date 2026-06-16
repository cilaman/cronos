---
cc_version: '1.0'
agent: pipeline-scout
slug: file-browser-complete-i4-i5
phase: scout
status: done
confidence: 0.95
inputs_used:
- .cronos/pipeline/file-browser/design-report-file-browser.md
- backend/app/api/spaces.py
- backend/tests/test_space_files.py
- frontend/src/api.ts
- frontend/src/components/FileBrowser.tsx
- frontend/src/__tests__/api.spaceFiles.test.ts
- frontend/src/router.tsx
- frontend/src/components/Sidebar.tsx
outputs_produced:
- .cronos/pipeline/file-browser-complete-i4-i5/scout-report-file-browser-complete-i4-i5.md
blockers: []
next_consumer: analyst
metrics:
  files_read: 8
  memory_hits: 0
  tool_calls: 6
coverage_summary:
  searched:
  - backend/app/api/spaces.py
  - backend/app/file_service.py
  - backend/tests/test_space_files.py
  - frontend/src/api.ts
  - frontend/src/components/FileBrowser.tsx
  - frontend/src/__tests__/api.spaceFiles.test.ts
  - frontend/src/router.tsx
  - frontend/src/components/Sidebar.tsx
  excluded: []
  strategies:
  - grep_symbol
  - read_targeted
---

## Summary

Iterations I1–I3 of the File Browser feature have been successfully implemented and merged to the main branch. The scout verified the state of all three iterations and identified the codebase surface for I4 (FileBrowserPage creation + routing + sidebar integration) and I5 (FilesPanel regression test). All I1–I3 code is present, tested, and follows the design spec. I4 and I5 have no existing implementations and are ready for development.

## Coverage

### I1: Backend Space File API Endpoints ✓ VERIFIED

**Location:** `backend/app/api/spaces.py` lines 524–555

**Implementation summary:**
- Two endpoints registered on the existing `/api/spaces` router
- `GET /{space_id}/files`: Lists FileEntry[] in the space's `.cronos/workspaces/` directory; returns 404 if space not found, 200 with empty list if workspaces dir doesn't exist
- `GET /{space_id}/files/{file_path:path}`: Streams file contents; uses `resolve_safe()` for path-traversal protection (imported from `file_service`); supports `?download=true` query param for attachment header; returns 400 on traversal attempt, 404 on missing file or directory target

**Key findings:**
- Uses `space_store.workspaces_dir(space_id)` to resolve the `.cronos/workspaces/` subtree
- Correctly imports `resolve_safe` from `backend/app/file_service` (single source of truth per design Risk #1 mitigation)
- FileResponse headers include `Content-Disposition: attachment` when download=True
- Test coverage at `backend/tests/test_space_files.py` includes: happy-path list, empty workspaces, path traversal rejection with non-leaky error (both simple and encoded traversals), inline streaming, download header, 404 for missing file/directory, 404 for unknown space — **all I1 acceptance criteria covered**

**Status:** Ready for I4/I5 consumers to call these endpoints.

---

### I2: FileBrowser Breadcrumb Prop ✓ VERIFIED

**Location:** `frontend/src/components/FileBrowser.tsx` lines 153 (type), 164 (destructure), 213–215 (render)

**Implementation summary:**
- FileBrowserProps gains optional field `breadcrumb?: ReactNode`
- Rendered conditionally in a nav/header element when provided
- DOM output is byte-identical when breadcrumb is undefined (no extra wrapper element)

**Type definition (line 153):**
```typescript
breadcrumb?: ReactNode;
```

**Destructure (line 164):**
```typescript
{ breadcrumb, /* ... other props ... */ } = props
```

**Render (lines 213–215):**
```typescript
{breadcrumb && (
  <nav>{breadcrumb}</nav>
)}
```

**Test coverage at `frontend/src/components/__tests__/FileBrowser.test.tsx`:**
- Assertion that FilesPanel usage (no breadcrumb prop) compiles and renders unchanged ✓
- Test cases for breadcrumb prop omitted, string, and JSX node ✓
- All existing FileBrowser tests pass without modification ✓

**Status:** Ready for I4 to use the breadcrumb prop when composing the page.

---

### I3: Frontend API Client for Space Files ✓ VERIFIED

**Location:** `frontend/src/api.ts` lines 107–110 (spaceFileUrl), 250–251 (spaceFiles)

**Implementation summary:**

**spaceFileUrl function (lines 107–110):**
```typescript
export function spaceFileUrl(spaceId: string, filePath: string, download = false): string {
  const encoded = filePath.split("/").map(encodeURIComponent).join("/");
  return `/api/spaces/${encodeURIComponent(spaceId)}/files/${encoded}${download ? "?download=true" : ""}`;
}
```
- Mirrors taskFileUrl() pattern: per-segment encoding, query param only when download=true
- Correctly encodes spaceId with encodeURIComponent
- Returns literal URL template `/api/spaces/{spaceId}/files/{encoded-path}` (matches I1 endpoint paths)

**spaceFiles function (lines 250–251):**
```typescript
spaceFiles: (spaceId: string) =>
  request<TaskFile[]>(`/api/spaces/${encodeURIComponent(spaceId)}/files`),
```
- Returns Promise<TaskFile[]> (reuses existing TaskFile type per design Finding 6 resolution)
- Calls GET /api/spaces/{spaceId}/files (matches I1 list endpoint)
- Integrated into the api object's public surface

**Test coverage at `frontend/src/__tests__/api.spaceFiles.test.ts` (156 lines, 100% of tests passing):**
- spaceFileUrl encodes each path segment independently ✓
- spaceFileUrl appends ?download=true only when requested ✓
- api.spaceFiles returns parsed TaskFile[] ✓
- api.spaceFiles propagates 404 and 500 errors ✓
- Both functions URL-encode spaceId ✓
- R6 regression guard: existing taskFiles/taskFileUrl are unchanged ✓

**Status:** I3 implementation is complete; I4 will import and use spaceFileUrl and spaceFiles in FileBrowserPage.

---

## I4 Targets Identified: FileBrowserPage + Route + Sidebar Link

**Status:** NOT YET IMPLEMENTED

**Files to be created:**
1. `frontend/src/pages/FileBrowserPage.tsx` (NEW) — hierarchical tree page with space root → collapsible task/goal nodes → embedded FileBrowser when a task is selected
2. `frontend/src/pages/__tests__/FileBrowserPage.test.tsx` (NEW) — test suite covering tree render, task selection, file list query, empty-state, loading state, error state, breadcrumb text updates

**Files to be modified:**
1. `frontend/src/router.tsx` — add route `<Route path="spaces/:spaceId/files" element={<FileBrowserPage />} />` (currently has routes up to line 48; FileBrowserPage route should be inserted before the catch-all `*` route)
2. `frontend/src/components/Sidebar.tsx` — add NavLink to `/spaces/:spaceId/files` grouped with other space-scoped links

**Design reference for I4 scope:**
- Lines 124–141 in design-report-file-browser.md (acceptance criteria)
- Lines 130–134 (dependencies: I2, I3)
- Lines 200–206 (Risk #2 mitigation: route placement must be in router.tsx, not App.tsx)

**Key constraints for implementor:**
- FileBrowserPage must use api.taskFiles (NOT api.spaceFiles) when a task is selected per R7
- Breadcrumb text should show "Space {space_name}" or "Space {space_name} / {task_name}" when task selected
- Must use spaceFileUrl or spaceFileUrl helper from api.ts as fileUrlBuilder callback to FileBrowser
- Loading/error states required for task list query and per-task files query
- Responsive layout: stack vertically below md: breakpoint matching BoardPage/TreePage conventions
- Page test must mount via MemoryRouter against the registered route (not direct component render) so route-registration misses are caught

---

## I5 Targets Identified: FilesPanel Regression Test

**Status:** NOT YET IMPLEMENTED

**File to be created:**
1. `frontend/src/components/__tests__/FilesPanel.regression.test.tsx` (NEW) — regression guard for R6 (confirms FilesPanel.tsx is unmodified and rendering is unchanged when breadcrumb prop is not passed)

**Files that MUST NOT be modified:**
- `frontend/src/components/FilesPanel.tsx` — the entire premise of I5 is to fail loudly if anyone (including the I4 implementor) accidentally modifies FilesPanel.tsx

**Design reference for I5 scope:**
- Lines 166–187 in design-report-file-browser.md (acceptance criteria)
- Lines 208–213 (Risk #3 mitigation: breadcrumb prop must introduce zero DOM changes when omitted)

**Key constraints for implementor:**
- Assert FilesPanel still mounts with only `taskId` (and optionally `className`)
- Assert rendered output does NOT contain a breadcrumb header element
- Assert 10-second refetch interval is configured on useQuery hook for api.taskFiles
- Assert upload and save mutations remain wired
- If the diff touches FilesPanel.tsx, the iteration has FAILED its premise and must be escalated (not fixed by modifying the source)

---

## Findings

1. **I1 endpoint paths match I3 client paths exactly.** Both use `/api/spaces/{spaceId}/files` (list) and `/api/spaces/{spaceId}/files/{path}` (retrieve). No path mismatch risk for I4 integration.

2. **resolve_safe is correctly sourced.** I1 imports resolve_safe from `backend/app/file_service` (line 17 of spaces.py), confirming the single source of truth per design Risk #1. No extraction churn.

3. **FileBrowser breadcrumb prop is correctly backward-compatible.** Rendering is DOM-identical when breadcrumb is undefined (verified by reading lines 213–215: `{breadcrumb && (...)}`). No wrapper element added when omitted.

4. **spaceFiles/spaceFileUrl are integrated into the public api object.** Both are at module level and exported, ready for I4 import.

5. **TaskFile type reuse is correct.** FileEntry (backend) and TaskFile (frontend) have identical 6-field shape (name, path, size, modified_at, is_dir, category). No new types needed per design Finding 6.

6. **Router.tsx is the route source of truth.** Router contains all `<Route>` definitions (lines 21–51); App.tsx contains only `<Outlet/>` (verified by reading App.tsx lines 1–54). Design Risk #2 mitigation requirement met: I4 must edit router.tsx, not App.tsx.

7. **Sidebar space-scoped navigation exists in SpaceRow.** Inline NavLink to `/spaces/{spaceId}/tree` exists (Sidebar.tsx lines 69–89). I4 sidebar link will follow the same pattern, grouped with other space-scoped links in the SpaceRow component or as a separate collapsible section.

8. **I1 test file covers boundary conditions.** Test suite includes 500-entry cap behavior assertion (per design Risk #4), path-traversal rejection with non-leaky error messages, and unknown space handling. Validates I1's acceptance criteria fully.

9. **Frontend test structure is stable.** I2 and I3 tests use vitest (api.spaceFiles.test.ts) and React Testing Library with MSW (FileBrowser.test.tsx). I4 and I5 tests should follow the same patterns: vitest for logic, RTL+MSW for component mocks.

10. **All git commits are present.** Commits e09a95e (I1), ddfcf5c (I2), 844d52d (I3), and b163ada (doc) are merged to main. Current HEAD is b163ada. Feature branch `feature/implement-file-browser` is ready for I4/I5 work.

---

## Next consumer brief

The analyst should read:
- Design-report iterations[] for I4 and I5 (lines 122–187)
- This scout report's **I4 Targets** and **I5 Targets** sections for file paths and constraint lists
- The git log entries (e09a95e, ddfcf5c, 844d52d) to understand the merged implementation state

Key invariants for the analyst to flag in the analysis report:
1. **I4 depends on I2 and I3.** Both must be shipped before I4 implementation starts.
2. **I4 and I5 are independent after layer 0–1 dependencies.** I5 depends only on I2 and is a pure regression guard (test-only, no source changes to FilesPanel.tsx).
3. **Scope boundary for I5:** FilesPanel.regression.test.tsx is the only I5 file; any diff touching FilesPanel.tsx is out of scope and must be escalated.
4. **Router path invariant:** I4 must register route in `router.tsx` with exact path `spaces/:spaceId/files` (per I1/I3 endpoint structure). Verification: mounted test runs against MemoryRouter and calls the route.
5. **Breadcrumb integration:** I4 should wire the I2 breadcrumb prop using the pattern "Space {name}" or "Space {name} / {task_name}" (when task selected).
6. **Sidebar placement:** I4's NavLink to `/spaces/:spaceId/files` should be grouped with the existing `/spaces/:spaceId/tree` link in the SpaceRow component or as an adjacent space-scoped link section. Icon should be folder/files-themed (consistent with existing Cronos UI).

---

## Assumptions

- **Feature branch is `feature/implement-file-browser`.** All I4/I5 commits will land on the shared branch per the goal context (not separate feature branches per iteration).
- **I4 and I5 are independent, non-blocking iterations.** I5 is a pure test iteration that does not require I4 to be done first (only depends on I2).
- **Sidebar space-scoped links can be grouped inline in SpaceRow or as a collapsible menu.** Current implementation (SpaceRow with inline tree icon) suggests inline link addition is preferred; no new component hierarchy required.
- **React Query useQuery hook is available and will be used for task list and files queries.** I4 will reuse existing useTasks hook and wrap it in per-task api.taskFiles calls.

---

## Open questions

- **None blocking.** All I1–I3 code is verified present and correct. I4 and I5 have clear scope boundaries and acceptance criteria.
