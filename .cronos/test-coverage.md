# Test Coverage — cronos-development

**Updated**: 2026-05-18T21:05:02Z
**Overall**: 70.17% (+5.41% vs previous)
**Passed**: 366 | **Failed**: 0 | **Total**: 373 (7 skipped)
**Frontend**: 24 passed

## Per-module coverage (backend)

| Module | Coverage |
|--------|----------|
| app/api/__init__.py | 100% |
| app/api/activity.py | 100% |
| app/models.py | 100% |
| app/test_report.py | 100% |
| app/api/stats.py | 97% |
| app/api/tools.py | 96% |
| app/stats.py | 96% |
| app/api/traces.py | 92% |
| app/trace_parser.py | 91% |
| app/api/spaces.py | 90% |
| app/stats_store.py | 85% |
| app/trace_store.py | 84% |
| app/test_report_store.py | 83% |
| app/agent.py | 83% |
| app/storage.py | 79% |
| app/api/test_reports.py | 70% |
| app/space_storage.py | 59% |
| app/api/tasks.py | 54% |
| app/worker.py | 52% |
| app/worker_pool.py | 30% |
| app/main.py | 29% |
| app/git_ops.py | 21% |
| app/file_service.py | 19% |

## Recent changes (2026-05-18 second pass)

Added 27 tests covering the worker/agent fixes in commit `cbf5fa4`:

- **test_worker.py** (NEW, 19 tests) — `Worker._finalize()` state resolution
  order, exit_reason computation in stats and trace records, including the
  new STATUS:DONE-with-nonzero-exit (upgrade-killed) and NO_STATUS branches.
  Lifted `app/worker.py` coverage from 14% to 52%.
- **test_agent.py** (+10 tests) — STATUS_CONTRACT plan-mode rule,
  `_upgrade_instructions()` DONE-before-curl ordering, and the new third-pass
  `parse_status` fallback that scans all turns in reverse via `run_agent()`
  with a mocked subprocess. Lifted `app/agent.py` coverage from 53% to 83%.
