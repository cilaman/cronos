# Test Coverage — cronos-development

**Updated**: 2026-05-19T14:23:31Z
**Overall**: 70.42% (+0.28% vs previous)
**Passed**: 482 | **Failed**: 0 | **Total**: 482
**Backend**: 394 passed (pytest) | **Frontend**: 88 passed (vitest)

## Per-module coverage (backend)

| Module | Coverage |
|--------|----------|
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
| app/stats_store.py | 85% |
| app/trace_store.py | 84% |
| app/test_report_store.py | 83% |
| app/agent.py | 83% |
| app/storage.py | 76% |
| app/api/test_reports.py | 70% |
| app/space_storage.py | 59% |
| app/worker.py | 58% |
| app/api/tasks.py | 55% |
| app/worker_pool.py | 30% |
| app/main.py | 29% |
| app/git_ops.py | 21% |
| app/file_service.py | 19% |

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
