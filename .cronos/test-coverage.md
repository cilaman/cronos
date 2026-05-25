# Test Coverage — cronos-development

**Updated**: 2026-05-25T07:18:00Z
**Backend (pytest)**: 78.86% (+0.19% vs previous run) — 627 passed, 0 failed
**Frontend (vitest)**: unchanged (no frontend changes this session)
**Tester rounds this session**: 1 (no regressions)

## Recent changes (2026-05-25 — arc-4 task 1: Space.autopilot schema + yaml round-trip)

Added 28 tests covering the new `autopilot: Literal["disabled","enabled","paused"]`
field on `Space`, the new `SpaceStore.set_autopilot()` mutator, and the
`autopilot` branch of `PATCH /api/spaces/{id}`.

### Tests added in `backend/tests/test_space_storage.py` (+13)

**`dump_space` / `parse_space_yaml` (5 tests)**

- `test_dump_space_emits_autopilot_key` — the YAML serialization always
  carries the `autopilot:` key (default-disabled case).
- `test_dump_space_emits_current_autopilot_value` — emits `enabled` and
  `paused` literally when set on the model.
- `test_parse_space_yaml_missing_autopilot_defaults_disabled` — back-compat
  guard: a legacy `space.yml` without an `autopilot:` key loads with
  `'disabled'` instead of raising. Critical for upgrade safety — every
  existing space on disk pre-dates this field.
- `test_parse_space_yaml_reads_explicit_autopilot` — `autopilot: enabled`
  in the YAML round-trips into the Space model.
- `test_parse_space_yaml_invalid_autopilot_raises` — an unknown literal
  (`autopilot: bogus-mode`) raises `SpaceError` at parse time. Locks the
  Literal[...] contract so typos can't silently become autopilot-off.

**`SpaceStore.set_autopilot()` (8 tests)**

- `test_new_space_defaults_to_disabled_autopilot` — a freshly created space
  has `autopilot='disabled'` and the on-disk yml emits the key.
- `test_set_autopilot_persists_value[disabled|enabled|paused]` — three
  parametrized tests: mutation updates in-memory state AND persists to disk
  (verified via a fresh `SpaceStore.reload_all()` round-trip).
- `test_set_autopilot_paused_reloads_byte_equal` — the acceptance-criteria
  round-trip: save with `paused`, reload via a fresh store, confirm the
  field survives and the on-disk YAML contains the literal line.
- `test_set_autopilot_missing_space_raises` — unknown space id raises
  `SpaceNotFound`.
- `test_set_autopilot_updates_updated_at` — mutator bumps `updated_at` so
  watchers/UIs see the change.
- `test_set_autopilot_preserves_other_fields` — name/color/description are
  untouched by the autopilot mutation (regression guard against future
  refactors that might rebuild the model from a subset of fields).

### Tests added in `backend/tests/test_api_spaces.py` (+15)

**API surface — DTO carries the field (2 tests)**

- `test_get_space_response_includes_autopilot` — `GET /api/spaces/{id}`
  returns the field with the default `'disabled'`.
- `test_create_space_response_includes_autopilot` — `POST /api/spaces`
  response carries the field on a freshly created space.

**`PATCH /api/spaces/{id}` — autopilot round-trips (5 tests)**

- `test_update_space_autopilot_enabled_round_trips` — PATCH `enabled`
  returns 200, response carries the value, and a follow-up GET confirms
  persistence.
- `test_update_space_autopilot_paused_round_trips` — same for `paused`.
- `test_update_space_autopilot_back_to_disabled` — toggle enabled →
  disabled via two PATCHes.
- `test_update_space_autopilot_only_no_other_fields_succeeds` — locks the
  empty-body guard's new `and body.autopilot is None` branch: PATCH with
  ONLY `autopilot` must not 400 with "No fields to update".
- `test_update_space_autopilot_combined_with_name` — PATCH with `name` +
  `autopilot` together must apply BOTH (exercises both branches of the
  handler: base `store.update()` followed by `store.set_autopilot()`).

**`PATCH /api/spaces/{id}` — validation + error paths (7 tests)**

- `test_update_space_autopilot_invalid_value_returns_422` — bogus literal
  is rejected by Pydantic with 422 (not 200, not 400, not 500).
- `test_update_space_autopilot_bad_values_return_422[uppercase|alias-on|empty-string|whitespace-padded|wrong-word]` —
  five parametrized cases asserting that case-sensitive Literal matching
  catches plausibly-looking-but-wrong inputs (`ENABLED`, `on`, `""`,
  `"  enabled  "`, `active`). This is a security-relevant property: typos
  must NOT silently fall back to the default.
- `test_update_space_autopilot_missing_space_returns_404` — autopilot
  PATCH on an unknown space id returns 404, not 500.
- `test_update_space_autopilot_null_treated_as_omitted` — `{"name":"X",
  "autopilot":null}` updates the name but leaves an already-`enabled`
  autopilot untouched. Locks the `body.autopilot is not None` semantic
  in `update_space()` — `null` is the "omit" signal, not "reset to
  disabled".

### Acceptance-criteria coverage matrix

| Acceptance criterion | Test |
|----------------------|------|
| Existing `space.yml` without `autopilot:` loads with `"disabled"` | `test_parse_space_yaml_missing_autopilot_defaults_disabled` |
| After save, `autopilot` key is present in the YAML | `test_dump_space_emits_autopilot_key`, `test_new_space_defaults_to_disabled_autopilot` |
| `PATCH {"autopilot":"enabled"}` round-trips correctly | `test_update_space_autopilot_enabled_round_trips` |
| Invalid `autopilot` value → 422 | `test_update_space_autopilot_invalid_value_returns_422` + 5 parametrized cases |
| `autopilot: paused` reloads byte-equal | `test_set_autopilot_paused_reloads_byte_equal`, `test_set_autopilot_persists_value[paused]`, `test_update_space_autopilot_paused_round_trips` |

### Coverage delta this session

- `app/space_storage.py`: 59% → 61% (+2 pts) — the new `set_autopilot()`
  branch is fully exercised; remaining gap is in link_repo/unlink_repo
  paths that require real git fixtures.
- `app/api/spaces.py`: 90% → 91% (+1 pt) — the new autopilot branches in
  `update_space()` are covered.
- `app/models.py`: 100% → 100% — unchanged (the new Literal field has no
  runtime branches).

All 627 backend tests pass on first run; no regressions.

## Per-module coverage (backend, sorted ascending)

| Module | Coverage | Δ vs previous |
|--------|----------|---------------|
| app/git_ops.py | 21% | +0 |
| app/main.py | 29% | +0 |
| app/space_storage.py | 61% | +2 |
| app/api/tasks.py | 69% | +8 |
| app/api/test_reports.py | 70% | +0 |
| app/worker.py | 75% | +0 |
| app/worker_pool.py | 80% | +0 |
| app/agent.py | 83% | +0 |
| app/test_report_store.py | 83% | +0 |
| app/trace_store.py | 84% | +0 |
| app/stats_store.py | 85% | +0 |
| app/storage.py | 88% | +1 |
| app/file_service.py | 90% | +0 |
| app/api/spaces.py | 91% | +1 |
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
| app/space_storage.py | 59% | 52-56,67-76,86,101-102,149-150,156-160,169-170,176-177,180-182,185-194,198-199,203-231,263-266,270,275-278,286-296,369-399,409-426,452,455 | space lifecycle ops |
| app/api/tasks.py | 61% | 56,59,117,170-181,186-187,217-220,255-256,273-274,306-311,313,321-342,347-348,360,365-376,386-399,409-423,433-453,476-479,486-487 | file upload/stop branches; PATCH not-found |
| app/api/test_reports.py | 70% | 15,20,69-74,79-87 | small module — easy wins |

## Recent changes (2026-05-24 — arc-1 task 3 gap-fill on DTO endpoints)

Added 9 more tests targeting the `_build_task_read(..., store=...)` wiring
across every TaskRead-returning endpoint. The arc-1/3 commit added a new
`store` parameter that several call sites pass; if any of those threadings
regressed, the DTO would silently report `unmet_dependencies=[]` even when
blockers existed.

### Tests added in `backend/tests/test_api_tasks.py` (+5)

- `test_start_response_includes_unmet_dependencies` — POST /start success
  response carries the field (empty list on success).
- `test_patch_state_response_includes_unmet_dependencies` — PATCH /state
  carries the field (open backlog -> active path, deps satisfied).
- `test_patch_task_response_includes_unmet_dependencies` — PATCH /api/tasks/{id}
  carries the field; populated when adding an open dep via the update.
- `test_reply_response_includes_unmet_dependencies` — POST /reply carries the
  field on the active reply path (regression guard for the new `store=` arg).

### Tests added in `backend/tests/test_storage.py` (+5)

- `test_apply_reply_waiting_path_unaffected_by_dep_gate` — waiting->active
  reply with open deps must succeed (gate is BACKLOG-only). Locks the gate's
  exact-match scoping.
- `test_apply_reply_done_path_unaffected_by_dep_gate` — done->active reply
  with open deps must succeed. Same scoping argument.
- `test_unmet_deps_does_not_treat_self_as_satisfied` — self-referential dep
  (data-corruption scenario; create() blocks it) still reports as unmet
  because the task itself is BACKLOG (non-terminal). Lock policy.
- `test_unmet_deps_returns_independent_list` — caller mutation does not
  poison subsequent calls (defensive against shared-list bugs).
- `test_open_children_returns_independent_list` — same independence
  contract for the sibling helper.

## Recent changes (2026-05-24 — arc-1/6 detail panel hierarchy UI)

Task arc-1/6 added a new HierarchySection inside `Detail.tsx` plus three new
API methods (`promote`, `setParent`, `setDependsOn`) and three new hooks
(`usePromoteTask`, `useSetParent`, `useSetDependsOn`). Added 68 new frontend
tests across four files plus four new exports from `Detail.tsx` so the pure
helpers can be unit-tested.

### Tests added in `frontend/src/__tests__/Detail-helpers.test.ts` (17)

Pure tests for the two new helpers:

- `extractDetail` — 8 tests covering: pure-JSON body, JSON-with-prefix,
  no-brace passthrough, malformed JSON passthrough, missing-detail field,
  empty-string falsy fallback, non-string-detail runtime behavior, and a
  brace-in-path placement check.
- `getDescendantIds` — 9 tests covering: no children, immediate children,
  multi-level traversal, root-id exclusion, sibling-tree isolation, **cyclic
  parent-graph defensive termination**, missing root, empty task list, and
  sibling-vs-descendant distinction.

### Tests added in `frontend/src/__tests__/api-hierarchy.test.ts` (15)

Mocks `globalThis.fetch` and asserts URL, method, body, headers, and error
propagation for each new method. The error-propagation tests are the
important ones — they lock the wrapper's "<status> <statusText> on <path>:
<body>" error-message format that `extractDetail` parses.

### Tests added in `frontend/src/hooks/__tests__/useTasks-hierarchy.test.tsx` (13)

Uses a real `QueryClient` with retries disabled and `vi.mock`s `../../api`.
Asserts: argument forwarding, cache writes via `setQueryData(["task", id])`,
board cache invalidation (verified by extracting and invoking the
`predicate` function passed to `invalidateQueries`), error surfacing, and
the "cache untouched on error" contract for `useSetDependsOn`.

### Tests added in `frontend/src/components/__tests__/HierarchySection.test.tsx` (23)

Mocks `useBoard`, `usePromoteTask`, `useSetParent`, `useSetDependsOn` so the
test controls hook state directly. Wraps in `MemoryRouter` for the
`useSearchParams` dependency. Covers:

- TypeBadge rendering for all three types and the `undefined → 'task'` default.
- Promote button visibility: hidden for goals, visible for task/issue/undefined.
- Promote button: disabled + "Promoting…" while pending; calls mutateAsync on
  click; surfaces extracted detail on error.
- Children section: hidden for non-goals, hidden for goals without children,
  visible for goals with children; lists each child with state badge; hidden
  while board data is loading.
- Top-level structure: Hierarchy heading, Parent / Depends on labels,
  dependency chips that resolve titles from the board (with id fallback), and
  the parent breadcrumb with Change/Remove buttons.

### Source change: 4 named exports added to `frontend/src/components/Detail.tsx`

`extractDetail`, `getDescendantIds`, `TypeBadge`, `HierarchySection` are now
named exports so the helpers and the section can be unit-tested in isolation
without exercising the full Detail modal. No behavior change.

All 599 backend tests + 183 frontend tests pass; no regressions.

All 535 backend tests pass; no regressions.

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
