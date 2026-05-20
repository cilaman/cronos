# Test Coverage — cronos-development

**Updated**: 2026-05-20T11:30:00Z
**Overall**: 73.11% (-0.30% vs previous)
**Passed**: 511 | **Failed**: 0 | **Total**: 511
**Backend**: 423 passed (pytest) | **Frontend**: 88 passed (vitest)

## Per-module coverage (backend)

| Module | Coverage |
|--------|----------|
| app/__init__.py | 100% |
| app/api/__init__.py | 100% |
| app/api/activity.py | 100% |
| app/models.py | 100% |
| app/test_report.py | 100% |
| app/stats.py | 98% |
| app/api/stats.py | 97% |
| app/api/tools.py | 96% |
| app/api/traces.py | 92% |
| app/trace_parser.py | 91% |
| app/api/spaces.py | 90% |
| app/file_service.py | 90% |
| app/stats_store.py | 85% |
| app/trace_store.py | 84% |
| app/agent.py | 83% |
| app/test_report_store.py | 83% |
| app/storage.py | 77% |
| app/api/test_reports.py | 70% |
| app/space_storage.py | 59% |
| app/worker.py | 55% |
| app/api/tasks.py | 54% |
| app/worker_pool.py | 30% |
| app/main.py | 29% |
| app/git_ops.py | 21% |

## Recent changes (2026-05-20 — HIGH-005 imported-task sanitization)

Added 4 tests covering the new `_sanitize_imported_tasks()` security fix in
`backend/app/api/spaces.py`. The function is invoked just before an imported
space directory is moved into place; it forces every task to
`state=backlog` with `claude_session_id=None`, clearing `pending_messages`
and `waiting_question`. This blocks an attacker from importing a ZIP that
auto-starts a hijacked Claude session on the operator's machine.

New tests in `backend/tests/test_spaces_api.py`:

- `test_import_active_task_is_forced_to_backlog` — ZIP carrying
  `state: active` arrives on disk as `state: backlog`.
- `test_import_task_with_session_id_is_stripped` — even a clean
  backlog task arrives with `claude_session_id` cleared when the ZIP
  set one.
- `test_import_clean_backlog_task_is_unchanged` — backlog task with
  no session id round-trips unchanged and emits zero
  "Sanitizing imported task" warnings (asserted via `caplog`).
- `test_import_waiting_task_with_question_and_pending_is_sanitized` —
  full payload (`state: waiting` + session id + pending messages +
  waiting question) is normalized: state→backlog, session→None,
  pending→[], waiting_question→None.

Each test reads the post-import file from disk via `parse_file()` to
verify the persisted state (not just the API response). All 4 pass on
first run; full backend (423) and frontend (88) suites green; no
regressions.

## Recent changes (2026-05-19 — file_service coverage pass)

Added 25 tests covering `app/file_service.py`, which was the lowest-covered
backend module at 19%. Coverage of that module is now 90% (+71 pts) and
overall backend+frontend coverage moved from 70.42% to 73.41% (+2.99 pts).

New test file: `backend/tests/test_file_service.py` (25 tests):

- **`classify_file` (6 tests)** — image/text/code/document/archive/binary
  extension mapping; AI prefix rules (`.claude/agents/`, `.claude/skills/`,
  `.claude/commands/`, `.claude/context/`, exact `.claude/CONTEXT.md`)
  taking priority over extension; backslash normalisation.
- **`resolve_safe` (4 tests)** — simple in-root resolution; leading-slash
  and backslash normalisation; traversal attempts via `../` raise
  `ValueError`; empty path resolves to root.
- **`list_files` (7 tests)** — basic tree walk with sizes, categories,
  is_dir flags; hidden files skipped outside `.claude/`; `.claude/` dir
  itself stays hidden by the walker; `skip_prefixes` excludes named dirs
  (e.g. `.cronos`); `max_entries` bound respected; directory-before-file
  sort order; entries are `FileEntry` instances.
- **`list_git_changed_files` (2 tests)** — returns `None` when path is
  not a git repo; in a real repo correctly reports modified + untracked
  files while excluding deleted ones and sorts results by path.
- **`save_upload` (6 tests)** — round-trip write returns a populated
  `FileEntry` and cleans up the `.tmp` file; filename basename is taken
  so path components in `upload.filename` cannot escape the target dir;
  traversal in the `rel_subdir` argument raises `ValueError`; oversized
  uploads raise `ValueError` and leave no partial/temp file behind;
  intermediate target directories are created; missing filename falls
  back to literal `"upload"`.

All 25 tests pass on first run; no regressions introduced in the rest of
the suite (backend 419 passed, frontend 88 passed).

## Recent changes (2026-05-19 — agent identification in history)

Added 28 tests covering the new subagent-types-in-history feature
(commit context: `_extract_subagent_types` + `agents=` header field):

- **test_worker.py** (+20 tests):
  - 13 tests covering `_extract_subagent_types(events)` directly:
    empty input; no Agent calls; single call lowercased; dedup
    across mixed case; insertion-order preservation; missing/non-
    string/empty `subagent_type`; non-assistant events ignored;
    other tool names ignored; malformed event shapes tolerated.
  - 3 tests covering `_finalize()` history-entry serialization
    of the new `agents=` field: appended when subagents used;
    omitted when not; dedup+lowercase in header CSV.
- **parse-history.test.ts** (+8 tests):
  - `agents=` parsing into `AgentInfo.agents` (single, multi, missing,
    empty, key-order independence, full multi-entry round-trip,
    empty-token filter).

Worker module coverage moved from 14.3% → 57.7% (+43 pts) because
`_finalize()` now executes via these tests with realistic event
fixtures. All tests pass on first run; no regressions.

## Recent changes (2026-05-19 — tasks mode visualization)

Added 8 tests covering the `agent_mode` propagation from Task to TaskSummary
(the data path that lets the frontend render mode badges on board cards):
- **test_storage.py** (+6 tests) — `summarize()` direct unit tests for
  `agent_mode` defaulting and propagation (`auto`, `plan`, `ask`), plus a
  preserves-other-fields check, plus `task_store.board()` integration tests
  for default-mode and non-default-mode tasks.
- **test_api_tasks.py** (+2 tests) — `GET /api/tasks` board responses now
  verified to include `agent_mode` on each summary (both default `"auto"`
  and explicitly-set `"plan"`).

Frontend `Card.test.tsx` (+5 tests, by feature author) covers the badge
rendering matrix: Auto shown only in full mode; Plan and Ask shown in both
full and compact modes.

All tests pass on first run; no regressions introduced.

## Recent changes (2026-05-18 second pass)

Added 27 tests covering the worker/agent fixes in commit `cbf5fa4`:

- **test_worker.py** (NEW, 19 tests) — `Worker._finalize()` state resolution
  for false-CRASHED scenarios; verifies that successful runs are not
  misclassified as crashes when STATUS markers are present.
- **test_agent.py** (+8 tests) — STATUS marker parsing for both modern
  and legacy formats; trims whitespace and handles missing markers.
