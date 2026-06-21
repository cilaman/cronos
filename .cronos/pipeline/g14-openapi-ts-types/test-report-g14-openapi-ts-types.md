---
cc_version: "1.0"
agent: tester
slug: g14-openapi-ts-types
phase: test
status: done
confidence: 0.95
inputs_used: []
outputs_produced:
  - .cronos/pipeline/g14-openapi-ts-types/test-report-g14-openapi-ts-types.md
blockers: []
next_consumer: review
gate_decision: pass
tests_added: 0
passed: 4261
failed: 0
errors: 0
coverage: 86.68
metrics:
  tool_calls: 9
  files_read: 0
  memory_hits: 0
  tests_run: 4261
---

## Summary

Gate run for goal `g14-openapi-ts-types` in space `cronos-development`. 4261 tests passed, 0 failed, 0 errored, 0 skipped. Coverage: 86.7%. Gate decision: **PASS**.

## Gate result

| Metric | Value |
|--------|-------|
| Passed | 4261 |
| Failed | 0 |
| Errors | 0 |
| Skipped | 0 |
| Coverage | 86.7% |
| Exit code | 0 |
| Gate decision | **pass** |

## Failures

- None.

## Assumptions

- Test suite is at `backend/tests/` (pytest) and `frontend/` (vitest when present).
- `tests_added: 0` — tester is a gate runner only; test authoring belongs to test-architect.
- `tool_calls: 9` is a fixed estimate; Bash-based agents cannot count tool invocations dynamically.
- `inputs_used: []` — the tester runs shell commands against the live test suite, not Read-tool file accesses; R4 is satisfied trivially (0 + 0 >= 0).

## Open questions

- None.

## Next consumer brief

Gate result: **PASS** — 4261p / 0f / 0e, coverage 86.7%.
All tests pass — proceed to review phase.
