---
cc_version: '1.0'
agent: pipeline-implementor
slug: file-browser-complete-i4-i5
phase: impl
status: done
confidence: 0.97
inputs_used:
- .cronos/pipeline/file-browser/design-report-file-browser.md
- .cronos/pipeline/file-browser-complete-i4-i5/scout-report-file-browser-complete-i4-i5.md
- .cronos/pipeline/file-browser/impl-report-file-browser--i3.md
- frontend/src/router.tsx
- frontend/src/components/Sidebar.tsx
- frontend/src/components/FileBrowser.tsx
- frontend/src/components/FilesPanel.tsx
- frontend/src/hooks/useTasks.ts
- frontend/src/hooks/useSpaces.ts
- frontend/src/api.ts
- frontend/src/types.ts
- frontend/src/pages/__tests__/HarnessRunsPage.test.tsx
- frontend/src/__tests__/router.harness-editor.test.tsx
outputs_produced:
- frontend/src/pages/FileBrowserPage.tsx
- frontend/src/pages/__tests__/FileBrowserPage.test.tsx
- frontend/src/components/__tests__/FilesPanel.regression.test.tsx
- frontend/src/router.tsx (modified)
- frontend/src/components/Sidebar.tsx (modified)
blockers: []
next_consumer: test
metrics:
  tool_calls: 18
  files_read: 14
  memory_hits: 2
  iterations_planned: 2
  validation_command_passed: true
---

## Summary

Implemented I4 (FileBrowserPage + route registration + Sidebar NavLink) and I5 (FilesPanel regression test). All 1225 frontend tests pass (76 test files). The file-browser feature is now complete: the new page lives at `/spaces/:spaceId/files`, the route is registered in `router.tsx`, and a folder-icon NavLink appears in the space row of `Sidebar.tsx`. I5 added a dedicated regression guard that asserts FilesPanel still mounts without breadcrumb and that upload/save mutations and the 10s refetch interval remain wired.

## Files changed

| File | Action | Scope |
|------|--------|-------|
| `frontend/src/pages/FileBrowserPage.tsx` | created | I4 scope_files ✓ |
| `frontend/src/pages/__tests__/FileBrowserPage.test.tsx` | created | I4 scope_files ✓ |
| `frontend/src/router.tsx` | modified | I4 scope_files ✓ |
| `frontend/src/components/Sidebar.tsx` | modified | I4 scope_files ✓ |
| `frontend/src/components/__tests__/FilesPanel.regression.test.tsx` | created | I5 scope_files ✓ |

**FilesPanel.tsx was NOT modified** — I5 premise preserved.

## Validation

### I4
```
cd frontend && npx vitest run src/pages/__tests__/FileBrowserPage.test.tsx
✓ src/pages/__tests__/FileBrowserPage.test.tsx (14 tests) 298ms
```
All 14 tests pass.

### I5
```
cd frontend && npx vitest run src/components/__tests__/FilesPanel.regression.test.tsx
✓ src/components/__tests__/FilesPanel.regression.test.tsx (7 tests) 145ms
```
All 7 tests pass.

### Full suite
```
Test Files  76 passed (76)
Tests  1225 passed (1225)
```

## Implementation notes

### I4: FileBrowserPage

**FileBrowserPage.tsx** renders a two-panel layout:
- Left: task tree panel (collapsible goals → child tasks; root tasks at top level). Uses `useBoard(spaceId)` from the existing `hooks/useTasks.ts` hook. Tasks from backlog/active/waiting/done lanes are included; archived is excluded.
- Right: `<FileBrowser/>` panel, shown when a task is selected, with `breadcrumb="Space {name} / {task_title}"`. When no task is selected, an empty-state guidance text is shown.

File URLs are built with `taskFileUrl(selectedTaskId, path, dl)` per R7 (task endpoint, not the space file endpoint).

The page uses `useQuery` directly for the per-task files query (`queryKey: ["task-files", selectedTaskId]`, `enabled: selectedTaskId !== null`) so the query only fires on demand.

**router.tsx**: Route `spaces/:spaceId/files` added before the harnesses route, after `spaces/:spaceId/settings`.

**Sidebar.tsx**: A folder-icon NavLink added adjacent to the existing tree icon in `SpaceRow`, following the same styling pattern (opacity-0 → group-hover:opacity-100, active accent). The folder SVG uses a `<path>` to draw a folder shape.

**Test approach**: Tests mock `useBoard`, `useSpace`, and `api.taskFiles`; mount via MemoryRouter with the explicit route path `"/spaces/:spaceId/files"` so `useParams` resolves correctly. FileBrowser is mocked to capture props (breadcrumb, files, fileUrlBuilder) and render simple output. Covers: loading state, error state, empty-state, task tree render, goal expansion, task click → files query, breadcrumb update, files loading state, files error state, fileUrlBuilder correctness, and responsive layout class.

### I5: FilesPanel.regression.test.tsx

**FilesPanel is NOT modified.** The test file:
1. Mocks `FileBrowser` to capture its props
2. Asserts no `<nav>` element in the DOM (no breadcrumb injected)
3. Asserts `breadcrumb` prop is `undefined` on the captured FileBrowser call
4. Asserts `onUpload` and `onSave` are functions (mutations remain wired)
5. Asserts `fileUrlBuilder` generates task-scoped URLs with the correct taskId
6. Asserts `api.taskFiles` refetches after 10 seconds using `vi.useFakeTimers()` + `vi.advanceTimersByTime(10_001)`

## Out-of-scope findings

- The 500-entry `list_files()` cap (design Risk #4) remains as documented. No workspaces in the test environment approached the cap.
- The space root scope (`.cronos/workspaces/` only) is as designed — the linked git working tree is not shown. This should be noted in user-facing docs.
- The sidebar only shows the files link icon in `SpaceRow` (space-scoped). If the user is not viewing a space, the link is not accessible from the sidebar — consistent with tree/settings/harnesses links.

## Assumptions

- `useBoard()` is the hook name in `hooks/useTasks.ts` (no `useTasks()` export exists). The design's reference to "useTasks() hook" maps to `useBoard()` in the actual codebase.
- `archived` tasks are excluded from the file browser tree (users shouldn't need to browse archived task files via this page; they still have the task detail view).
- The `Board` type includes `backlog`, `active`, `waiting`, `done`, `archived` — only the first four are included in the tree.

## Open questions

- **Deferred: pagination for large task spaces.** The 500-entry `list_files()` cap (design Risk #4) is not yet surfaced to the user. A follow-up goal should add pagination or a "load more" action if real usage exceeds the cap.
- **Deferred: space root / full .cronos tree browsing.** The design explicitly defers browsing the full `.cronos/` directory or the linked git working tree. If requested, a separate goal should extend the scope.

## Next consumer brief

The doc-sync agent should update `CLAUDE.md`'s Key modules table with:
- `frontend/src/pages/FileBrowserPage.tsx` — Space-level file browser page; hierarchical task tree → embedded FileBrowser; route `/spaces/:spaceId/files`.

The reviewer should verify:
1. `FilesPanel.tsx` diff is zero lines (I5 premise).
2. Route is in `router.tsx`, NOT `App.tsx` (design Risk #2 mitigation).
3. `fileUrlBuilder` in `FileBrowserPage` calls `taskFileUrl` (not `spaceFileUrl`) per R7.
4. No new files outside I4/I5 scope_files.
