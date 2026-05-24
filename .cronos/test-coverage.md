# Test Coverage — cronos-development

**Updated**: 2026-05-24T18:55:00Z
**Overall**: 77.67% (+1.44% vs previous run)
**Passed**: 614 | **Failed**: 0 | **Total**: 614
**Backend**: 526 passed (pytest) | **Frontend**: 88 passed (vitest)

## Per-module coverage (backend, sorted ascending)

| Module | Coverage | Δ vs previous |
|--------|----------|---------------|
| app/git_ops.py | 21% | +0 |
| app/main.py | 29% | +0 |
| app/api/tasks.py | 59% | +4 |
| app/space_storage.py | 59% | +0 |
| app/api/test_reports.py | 70% | +0 |
| app/worker.py | 75% | +0 |
| app/worker_pool.py | 80% | +0 |
| app/agent.py | 83% | +0 |
| app/test_report_store.py | 83% | +0 |
| app/trace_store.py | 84% | +0 |
| app/stats_store.py | 85% | +0 |
| app/storage.py | 87% | +7 |
| app/file_service.py | 90% | +0 |
| app/api/spaces.py | 90% | +0 |
| app/trace_parser.py | 91% | +0 |
| app/api/traces.py | 92% | +0 |
| app/api/tools.py | 96% | +0 |
| app/api/stats.py | 97% | +0 |
| app/stats.py | 98% | +0 |
| app/api/__init__.py | 100% | +0 |
| app/api/activity.py | 100% | +0 |
| app/models.py | 100% | +0 |
| app/test_report.py | 100% | +0 |

## Lowest-coverage modules (priority queue for next session)

| Module | Coverage | Missing line ranges (top) | Notes |
|--------|----------|--------------------------|-------|
| app/git_ops.py | 21% | 31,36,50-65,74-77,100-113,121-126,136-183,... | user git state — security-sensitive |
| app/main.py | 29% | 41-45,53-63,71-88,100-120,125-201,221-247 | lifespan/watcher uncovered |
| app/api/tasks.py | 59% | 56,59,117,170-181,186-187,217-220,255-256,273-274,303-316,321-342,347-348,360,365-376,386-399,409-423,433-453,476-479,486-487 | file upload/stop/reply/transition branches |
| app/space_storage.py | 59% | 52-56,67-76,86,101-102,149-150,156-160,169-170,176-177,180-182,185-194,198-199,203-231,263-266,270,275-278,286-296,369-399,409-426,452,455 | space lifecycle ops |
| app/api/test_reports.py | 70% | 15,20,69-74,79-87 | small module — easy wins |

## Recent changes (2026-05-24 — arc-1 task 3: block backlog->active when deps unmet)

Added 41 tests covering the new dependency / child gates implemented on the
arc-1/3 branch (`backend/app/storage.py` + `backend/app/api/tasks.py`):

- `_TERMINAL_STATES = {done, archived}`
- `unmet_deps(task, by_id) -> list[str]`
- `open_children(goal_id, by_id) -> list[str]`
- `TaskStore.transition()` gates: backlog→active blocked by unmet deps,
  goal→done blocked by open children.
- `TaskStore.apply_reply()` gate: backlog→active blocked by unmet deps.
- `POST /api/tasks/{id}/start` returns 409 with the blockers' ids in
  `detail` when deps are open.
- `TaskRead.unmet_dependencies: list[str]` surfaced on every task DTO
  (GET, POST, PATCH, /start, /reply responses).

### Tests added in `backend/tests/test_storage.py` (+22)

**Pure predicates — `unmet_deps()` (9 tests)**

- No-deps task returns `[]`.
- All-`done` deps return `[]`.
- All-`archived` deps return `[]`.
- Mixed `done` + `archived` returns `[]`.
- Mixed terminal/non-terminal returns the non-terminal ids in
  `depends_on` order.
- Missing dep id (dangling reference) is reported as unmet — defensive
  against silent skips when a target task was deleted.
- `waiting` state is NOT terminal (locks in the `{done, archived}`
  contract).
- `active` state is NOT terminal.
- Result list preserves `depends_on` order (deterministic for the UI).

**Pure predicates — `open_children()` (6 tests)**

- No children returns `[]`.
- All `done` children return `[]`.
- All `archived` children return `[]`.
- Mix of states reports the three non-terminal states (backlog/active/
  waiting) and excludes the terminal ones.
- A child of a DIFFERENT goal must not appear (off-by-one guard against
  forgetting to filter by `parent_id`).
- Root-level tasks (`parent_id=None`) are never attributed to any goal.

**`TaskStore.transition()` gates (5 tests)**

- backlog→active raises `InvalidTransition` when any dep is open;
  message names the offending id; the task's stored state is
  unchanged (gate enforced before mutation).
- backlog→active succeeds once every dep reaches `done`.
- backlog→active succeeds when every dep reaches `archived`.
- Multi-dep error message lists every open blocker.
- goal→done (via WORKER_TRANSITIONS active→done) raises
  `InvalidTransition` when any child is open; message names the child
  id; the goal's stored state is unchanged.
- goal→done succeeds once every child reaches `done`.
- Gate is scoped to `type='goal'` — `type='task'` parents with open
  children are NOT blocked from being closed.
- Illegality of the transition itself is checked BEFORE the deps gate
  (BACKLOG→DONE under USER_TRANSITIONS surfaces "Cannot move task from
  backlog to done", not the deps error).

**`TaskStore.apply_reply()` gate (3 tests)**

- Reply to a backlog task with unmet deps raises `InvalidTransition`
  and does NOT mutate the task (no history entry, state stays
  `backlog`).
- Reply to a backlog task with all deps `done` promotes to `active`
  and returns `should_enqueue=True`.
- Reply to an ACTIVE task with open deps is NOT blocked — the gate is
  scoped to the backlog branch; active replies still queue
  pending_messages.

### Tests added in `backend/tests/test_api_tasks.py` (+19)

**`POST /api/tasks/{id}/start` (6 tests)**

- 409 when a dep is open; `detail` contains "unmet dependencies" and
  the dep id; task remains in `backlog` after the refused start.
- 200 once every dep reaches `done`; final state is `active`.
- 200 happy path for a task with no deps.
- 200 when the dep is in `archived` state.
- 404 for an unknown task id.
- 409 when the task is already in `active` (lock-in for the "only
  backlog tasks can be started" guard).

**`PATCH /api/tasks/{id}/state` for goal-done (3 tests)**

- 409 on a goal with open children; `detail` contains "open children"
  and the child id; goal's stored state unchanged.
- 200 once every child reaches `done` (goal transitions waiting→done).
- 200 on a `type='task'` parent with open children — gate must NOT
  fire for non-goal types.

(Note: the goal-done flow goes through `waiting→done` because
`USER_TRANSITIONS` doesn't allow `active→done`. Setup primes the goal
into `waiting` via direct store manipulation to reach the user-facing
endpoint.)

**`TaskRead.unmet_dependencies` field (5 tests)**

- `[]` when the task has no deps.
- Populated with every open dep id when deps exist (set equality so
  order isn't asserted at the API boundary).
- Shrinks to `[]` once deps move to `done`.
- Reports a dangling dep id (target never existed) — surface the
  storage-layer defensive contract through the DTO.
- POST /api/tasks response also carries `unmet_dependencies` (the
  TaskRead shape is used on every endpoint that returns a task).

All 526 backend tests pass; all 88 frontend tests pass; no regressions.

## Recent changes (2026-05-24 — arc-1 task 1: type/parent_id/depends_on)

Added 30 tests covering the new hierarchy fields on `Task` (`type`,
`parent_id`, `depends_on`) and the SQLite secondary index that maintains
them.

### Real bug caught by these tests

`TaskStore.delete()` did NOT call `_db_delete()`, so soft-deleted tasks
remained as dangling rows in the SQLite tasks index. This would have leaked
into any future parent_id / type query built on top of the index. Test
`test_sqlite_index_removes_row_on_delete` failed on the first run; one-line
fix added `self._db_delete(task_id)` to the delete path in
`backend/app/storage.py`.

### Tests added in `backend/tests/test_storage.py` (+20)

- **parse_file** — reads `type`/`parent_id`/`depends_on` from frontmatter;
  back-compat defaults when keys are missing; invalid `type` falls back to
  `"task"`; non-list `depends_on` falls back to `[]`.
- **dump_task** — emits the three new keys; full disk round-trip
  (`dump_task` -> file -> `parse_file`) preserves all three.
- **summarize** — `TaskSummary` exposes `type` and `parent_id` (depends_on
  is intentionally NOT on the summary); defaults to `"task"` / `None`.
- **TaskStore.create** — accepts and persists hierarchy fields; defaults
  when omitted; rejects unknown `type` with `StorageError`.
- **TaskStore.update** — persists new values; `depends_on=[]` clears the
  list (vs `None`=no-op); rejects unknown `type`.
- **SQLite index**:
  - `reload_all()` rebuilds the table from MD files with correct
    `type`/`parent_id`/`depends_on_json`.
  - `create` upserts a row.
  - `update` upserts the new values.
  - `delete` removes the row (caught the bug above).
  - `idx_tasks_space_parent` and `idx_tasks_space_type` indices exist.
  - End-to-end query by `(space_id, parent_id)` and `(space_id, type)`
    returns the expected set.

### Tests added in `backend/tests/test_api_tasks.py` (+10)

- `POST /api/tasks` with hierarchy fields echoes them in the response.
- `POST /api/tasks` defaults: `type="task"`, `parent_id=None`,
  `depends_on=[]`.
- `POST /api/tasks` rejects unknown `type` with 422 (Pydantic Literal).
- `PATCH /api/tasks/{id}` updates type/parent_id/depends_on together.
- `PATCH /api/tasks/{id}` with only `type` (or only `depends_on`)
  succeeds — exercises the "no fields provided" guard.
- `GET /api/tasks/{id}` round-trips the three fields through the read
  model.
- Board summaries expose `type` and `parent_id` for card rendering.
- `PATCH` with invalid type returns 422.

All 462 backend tests pass; all 88 frontend tests pass; no regressions.

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
