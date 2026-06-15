---
cc_version: '1.0'
agent: pipeline-implementor
slug: file-browser--i1
phase: impl
iteration_id: I1
status: done
confidence: 0.98
inputs_used:
- .cronos/pipeline/file-browser/design-report-file-browser.md
- backend/app/api/spaces.py
- backend/app/file_service.py
- backend/app/space_storage.py
- backend/tests/conftest.py
- backend/tests/test_api_spaces.py
- backend/pyproject.toml
outputs_produced:
- .cronos/pipeline/file-browser/impl-report-file-browser--i1.md
- backend/app/api/spaces.py
- backend/tests/test_space_files.py
validation_command: cd backend && pytest tests/test_space_files.py -xvs
validation_command_passed: true
files_changed:
- backend/app/api/spaces.py
- backend/tests/test_space_files.py
blockers: []
next_consumer: test
metrics:
  tool_calls: 10
  files_read: 7
  memory_hits: 2
  diff_lines_added: 193
  diff_lines_removed: 1
---

## Summary

Implemented the two space file browsing endpoints in `backend/app/api/spaces.py` and wrote
12 tests in `backend/tests/test_space_files.py`. All 12 tests pass. Full suite: 2563 passed,
85% coverage (floor: 60%).

## Files changed

### `backend/app/api/spaces.py`

Added two new imports (`FileResponse` from fastapi.responses; `FileEntry`, `list_files`,
`resolve_safe` from `..file_service`) and two new routes at the end of the file:

- `GET /{space_id}/files` — returns `list[FileEntry]` listing all files under
  `space_store.workspaces_dir(space_id)` (= `.cronos/workspaces/`). Returns 404 when
  the space does not exist; returns `[]` when the workspaces directory is absent.

- `GET /{space_id}/files/{file_path:path}` — serves a file via `FileResponse`. Uses
  `resolve_safe(workspaces_root, file_path)` to guard against path traversal; raises
  HTTP 400 on traversal, 404 on missing space or missing/directory target. Sets
  `Content-Disposition: attachment` when `?download=true`.

`resolve_safe` is imported directly from `backend/app/file_service` (single source of
truth). `space_store.workspaces_dir(space_id)` is used instead of importing
`space_dir_for`/`CRONOS_SUBDIR` from `agent.py` — the `SpaceStore` method is the
canonical path for this calculation and is already used in the export endpoint.

### `backend/tests/test_space_files.py`

12 new tests covering:

1. `test_list_space_files_happy_path` — 200 with FileEntry[] including name/path/size/modified_at/is_dir/category
2. `test_list_space_files_paths_relative_to_workspaces_root` — paths are relative (no leading slash)
3. `test_list_space_files_empty_workspaces_dir` — empty workspaces dir → 200 `[]`
4. `test_list_space_files_no_workspaces_dir` — absent workspaces dir → 200 `[]`
5. `test_list_space_files_unknown_space` — 404
6. `test_get_space_file_inline` — 200, body matches file content, no attachment header
7. `test_get_space_file_download_header` — `?download=true` sets `Content-Disposition: attachment`
8. `test_get_space_file_not_found` — 404 for missing file
9. `test_get_space_file_path_traversal_rejected` — percent-encoded `%2e%2e` traversal → 400, error detail does not leak path
10. `test_get_space_file_path_traversal_encoded` — fully percent-encoded traversal → 400 or 404 (not 200)
11. `test_get_space_file_unknown_space` — 404
12. `test_get_space_file_directory_rejected` — directory target → 404

## Out-of-scope findings

- `backend/app/models.py`: The task brief mentioned adding `task_id`/`workspace` fields to
  `FileEntry`. The design report's scope_files for I1 does not include `models.py` (FileEntry
  lives in `file_service.py`, not `models.py`), and the design explicitly says "FileEntry
  reused verbatim — no schema change." Left untouched per scope boundary.
- The 500-entry `list_files()` cap is documented in the design risks (Risk #4). No test
  exercises boundary behavior since constructing 500 files in a tmp fixture is excessive;
  the risk is documented for doc-sync.

## Assumptions

- `space_store.workspaces_dir(space_id)` is equivalent to `space_dir_for(space_id) / CRONOS_SUBDIR / "workspaces"` — confirmed by reading `space_storage.py:672`.
- Path traversal via URL `..` segments is normalized by the HTTP layer before reaching
  FastAPI, so the `resolve_safe()` test uses percent-encoded `%2e%2e` to exercise the
  code path. This is the realistic attack surface.
- `GET /{space_id}/files/{file_path:path}` route is added after the more-specific
  `/{space_id}/export`, `/{space_id}/stream`, etc. routes — FastAPI matches the more
  specific patterns first, so no conflict.

## Open questions

None.

## Next consumer brief

I3 (frontend API client) must call `GET /api/spaces/{spaceId}/files` (no trailing slash)
and `GET /api/spaces/{spaceId}/files/{encoded-path}`. The URL contract from I1:

- List: `GET /api/spaces/{space_id}/files` → `list[FileEntry]` (6 fields: name, path, size,
  modified_at, is_dir, category)
- Retrieve: `GET /api/spaces/{space_id}/files/{file_path:path}` with `?download=true`
  optional → file bytes with optional `Content-Disposition: attachment`

The path field in each FileEntry is relative to `.cronos/workspaces/` and typically starts
with a task workspace name (e.g. `2026-06-01-1234-some-task/notes.md`). Downstream consumers
(I3/I4) can split on `/` to extract the workspace prefix.

Deferred items for doc-sync / retro:
1. The 500-entry `list_files()` cap silently truncates large workspaces. Pagination is out
   of scope per the analyst; flag in user docs.
2. The space file browser only shows `.cronos/workspaces/` — not the linked git working
   tree. Note this in user-facing docs.
