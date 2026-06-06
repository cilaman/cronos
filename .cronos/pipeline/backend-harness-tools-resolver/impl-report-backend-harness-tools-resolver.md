---
cc_version: '1.0'
agent: pipeline-implementor
slug: backend-harness-tools-resolver
phase: impl
status: done
confidence: 1.0
inputs_used:
- .cronos/pipeline/backend-harness-tools-resolver/design-report-backend-harness-tools-resolver.md
- .cronos/pipeline/backend-harness-tools-resolver/analysis-report-backend-harness-tools-resolver.md
- backend/app/worker.py
- backend/app/tools/scanner.py
- backend/app/api/tools.py
- backend/app/harnesses/brief_composer.py
- backend/app/harnesses/executor.py
- backend/tests/test_harness_brief_composer.py
outputs_produced:
- backend/app/worker.py
- backend/tests/test_tools_resolver.py
blockers: []
next_consumer: test
metrics:
  tool_calls: 18
  files_read: 9
  memory_hits: 2
  iterations_planned: 3
  iterations_executed: 3
---

## Summary

Replaced the two-line stub `_tools_resolver` closure in `worker.py` with a real implementation. Added a module-level pure function `resolve_tool(space_claude_dir, global_claude_dir, agent_ref)` that reuses the existing scanners (`_scan_category`, `_scan_skills`, `_scan_context`), scans space scope first then global scope, and returns on the first name match. The closure now delegates to `resolve_tool` via a 3-line wrapper. Added 14 pytest cases covering all acceptance criteria. Full suite: 2435 tests passed, 84.86% coverage.

## Files changed

- `backend/app/worker.py` — added `AiToolEntry` to models import; added `resolve_tool` module-level function (lines 222–249); replaced stub `_tools_resolver` closure with a 4-line delegating wrapper
- `backend/tests/test_tools_resolver.py` — new file, 14 test cases covering R1 (agent/skill/command/context match), R2 (space shadows global, global fallback), R4 (skill brief prefix), R6 (missing dirs, empty ref, full coverage floor)

## Out-of-scope findings

- `backend/app/harnesses/executor.py` — verified read-only: `agent_entry` from `tools_resolver` flows unchanged into `compose_brief(node, interpolated_prompt, agent_entry)` at line 758; no change needed.
- `backend/app/harnesses/brief_composer.py` — verified read-only: `_is_skill` detects `"skills/"` path substring correctly for directory-based and flat skill entries.

## Assumptions

- `_scan_context` imported lazily inside `resolve_tool` body to avoid circular import: `app.api.tools` → `app.stats_store` → eventually `app.worker` via `main.py`. Lazy import is safe because `app.api.tools` is already loaded by FastAPI startup before any harness run executes.
- Case-sensitive name matching is correct (mirrors scanner behavior).
- `Path.home() / ".claude"` as global dir matches the pattern in `api/tools.py:37`.

## Open questions

None.

## Next consumer brief

The test phase should verify:
1. `resolve_tool` is importable and returns `AiToolEntry | None`.
2. The full test suite (`cd backend && pytest tests/ --cov=app --cov-report=term-missing --cov-fail-under=60`) exits 0 — confirmed at 84.86% coverage, 2435 tests.
3. Skill entries returned by the resolver have `"skills/"` in their path, causing `compose_brief` to emit the `/<skill-name>` prefix.
