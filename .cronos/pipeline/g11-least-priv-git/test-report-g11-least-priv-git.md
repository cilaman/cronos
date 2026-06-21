---
cc_version: "1.0"
agent: tester
slug: g11-least-priv-git
phase: test
status: done
confidence: 0.9
inputs_used: []
outputs_produced:
  - .cronos/pipeline/g11-least-priv-git/test-report-g11-least-priv-git.md
blockers: []
next_consumer: user
gate_decision: fail
tests_added: 0
passed: 4139
failed: 1
errors: 0
coverage: 85.77
metrics:
  tool_calls: 9
  files_read: 0
  memory_hits: 0
  tests_run: 4140
---

## Summary

Gate run for goal `g11-least-priv-git` in space `cronos-development`. 4139 tests passed, 1 failed, 0 errored, 0 skipped. Coverage: 85.8%. Gate decision: **FAIL**.

## Gate result

| Metric | Value |
|--------|-------|
| Passed | 4139 |
| Failed | 1 |
| Errors | 0 |
| Skipped | 0 |
| Coverage | 85.8% |
| Exit code | 1 |
| Gate decision | **fail** |

## Failures

- `FileBrowserPage shows error banner when task files fail to load`: TestingLibraryElementError: Unable to find an element with the text: Failed to load files.. This could be because the text is broken up by multiple elements. In this case, you can provide a function f

## Assumptions

- Test suite is at `backend/tests/` (pytest) and `frontend/` (vitest when present).
- `tests_added: 0` — tester is a gate runner only; test authoring belongs to test-architect.
- `tool_calls: 9` is a fixed estimate; Bash-based agents cannot count tool invocations dynamically.
- `inputs_used: []` — the tester runs shell commands against the live test suite, not Read-tool file accesses; R4 is satisfied trivially (0 + 0 >= 0).

## Open questions

- None.

## Next consumer brief

Gate result: **FAIL** — 4139p / 1f / 0e, coverage 85.8%.
Fix 1 failing/errored test(s) before advancing the pipeline. See ## Failures for details.
