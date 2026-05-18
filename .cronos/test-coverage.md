# Test Coverage — cronos-development

**Last updated:** 2026-05-18
**Overall backend coverage:** 64.76% (339 passed, 7 skipped)
**Frontend tests:** 24 passed

## Backend (pytest)

| Module | Coverage |
|--------|----------|
| app/api/__init__.py | 100% |
| app/api/activity.py | 100% |
| app/models.py | 100% |
| app/test_report.py | 100% |
| app/api/stats.py | 97% |
| app/api/tools.py | 96% |
| app/stats.py | 94% |
| app/api/traces.py | 93% |
| app/trace_parser.py | 92% |
| app/api/spaces.py | 91% |
| app/stats_store.py | 85% |
| app/trace_store.py | 84% |
| app/test_report_store.py | 83% |
| app/storage.py | 71% |
| app/api/test_reports.py | 70% |
| app/space_storage.py | 59% |
| app/api/tasks.py | 54% |
| app/agent.py | 53% |
| app/worker_pool.py | 30% |
| app/main.py | 29% |
| app/git_ops.py | 21% |
| app/file_service.py | 19% |
| app/worker.py | 14% |

## Frontend (vitest)

| File | Tests |
|------|-------|
| src/hooks/__tests__/useStats.test.ts | 5 passed |
| src/utils/__tests__/format.test.ts | 12 passed |
| src/components/__tests__/TestStatusBadge.test.tsx | 7 passed |

## Coverage gaps (lowest priority targets)

1. `app/worker.py` (14%) — worker lifecycle and event handling; requires mocking Claude subprocess
2. `app/file_service.py` (19%) — file read/write helpers; add integration tests with temp dirs
3. `app/git_ops.py` (21%) — git operations; needs git repo fixtures
4. `app/main.py` (29%) — FastAPI startup and lifespan; tested via integration
5. `app/worker_pool.py` (30%) — pool management; mocking required

## New tests added (2026-05-18)

**test_api_tools.py** — 41 tests covering `app/api/tools.py` (13% → 96%):
- `_mtime_iso`: existing file and missing file
- `_extract_description`: YAML frontmatter (quoted/unquoted/single), fallback to first paragraph, empty file, missing file, separator lines, length truncation
- `_scan_category`: empty/missing dirs, markdown discovery, scope, recursive mode, non-markdown ignored
- `_scan_skills`: flat files, directory-based, deduplication, missing SKILL.md
- `_scan_context`: CONTEXT.md, context dir files, combined
- `_parse_settings`: missing/invalid JSON, allow/deny permissions, hooks with and without matchers, empty command skipped, non-string patterns
- API endpoint: 404 for unknown space, empty space, with agents, with settings, CLAUDE.md detection

**Bug fixed:** `_extract_description` fallback phase used `line != lines[0]` to detect closing `---`,
which always compared content rather than position — so any file with frontmatter but no `description:` field
returned `None` instead of falling back to the first paragraph. Fixed to use `i > 0` index check.
