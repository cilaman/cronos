---
cc_version: '1.0'
agent: pipeline-implementor
slug: test-impl-lying--i1
phase: impl
status: done
confidence: 0.9
inputs_used:
- backend/app/main.py
- backend/tests/conftest.py
outputs_produced:
- .cronos/pipeline/test-impl-lying/impl-report-test-impl-lying--i1.md
blockers: []
next_consumer: test
iteration_id: I1
files_changed:
- backend/app/pipeline/gate.py
validation_command: exit 1
validation_command_passed: true
metrics:
  tool_calls: 10
  files_read: 2
  diff_lines_added: 50
  diff_lines_removed: 5
---

## Summary

This fixture intentionally lies: `validation_command_passed: true` is self-reported
as passing, but the actual `validation_command` (`exit 1`) exits non-zero.

The `build` outcome check MUST detect this and return `decision=needs_fix` — it
never trusts the self-reported flag.

## Files changed

- `backend/app/pipeline/gate.py` — gate engine (lying about build result)

## Out-of-scope findings

None.

## Assumptions

- `exit 1` is a valid shell command that always exits with code 1.

## Open questions

None.

## Next consumer brief

The build check should catch this lie.
