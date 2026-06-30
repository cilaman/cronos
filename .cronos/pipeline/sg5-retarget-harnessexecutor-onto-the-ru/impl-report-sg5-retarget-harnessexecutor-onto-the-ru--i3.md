---
cc_version: "1.0"
agent: pipeline-implementor
slug: sg5-retarget-harnessexecutor-onto-the-ru--i3
phase: impl
status: done
confidence: 0.95
inputs_used:
  - .cronos/pipeline/sg5-retarget-harnessexecutor-onto-the-ru/design-report-sg5-retarget-harnessexecutor-onto-the-ru.md
  - backend/app/harnesses/run_state.py
  - packages/delivery-workflow/state_types.py
  - packages/delivery-workflow/interface.py
  - backend/tests/test_cronos_adapter_state_telemetry.py
iteration_id: I3
files_changed:
  - backend/app/harnesses/state_mapping.py
  - backend/tests/test_harness_state_mapping.py
validation_command_passed: true
out_of_scope_findings: []
outputs_produced:
  - .cronos/pipeline/sg5-retarget-harnessexecutor-onto-the-ru/impl-report-sg5-retarget-harnessexecutor-onto-the-ru--i3.md
blockers: []
next_consumer: test
metrics:
  tool_calls: 20
  files_read: 5
  memory_hits: 0
  diff_lines_added: 737
  diff_lines_removed: 0
---

## Summary

I3 implements the RunState <-> WorkflowState mapping layer as two pure functions in the new `backend/app/harnesses/state_mapping.py` module. `runstate_to_workflowstate()` converts harness execution state to the delivery-workflow runner's format, preserving all loop bookkeeping fields (attempt, prior_finding_ids) and storing all HarnessNodeState fields in WfNodeState.fields for round-trip fidelity. `workflowstate_to_runstate()` performs the reverse. A `_harness_status` sentinel in fields enables 'skipped' → 'done' → 'skipped' round-trips without ambiguity. All 49 tests pass with 0 failures; validation exit code 0.

## Files changed

| File | Action | Lines +/- | Purpose |
|------|--------|-----------|---------|
| backend/app/harnesses/state_mapping.py | created | +243 / 0 | Pure mapping functions runstate_to_workflowstate and workflowstate_to_runstate |
| backend/tests/test_harness_state_mapping.py | created | +494 / 0 | 49 tests: forward/reverse/round-trip/edge-case coverage of both functions |

## Out-of-scope findings

- None.

## Assumptions

- `WfNodeState.fields` is a `dict[str, Any]` (confirmed in `packages/delivery-workflow/state_types.py` line 20). The design report's risk R5 mitigation stores `prior_finding_ids` there; all other optional HarnessNodeState fields are also stored there for round-trip completeness.
- A `_harness_status` sentinel key is stored in `WfNodeState.fields` to enable lossless round-trip of 'skipped' (which maps forward to 'done' in WorkflowState). This is invisible to the runner and costs zero runtime overhead.
- The sys.path injection pattern follows the established convention in `backend/tests/test_cronos_adapter_state_telemetry.py` (line 24-26): insert `packages/delivery-workflow` root at sys.path[0].
- `RunState.waiting_node_id` is not encoded in WorkflowState (no corresponding field); `workflowstate_to_runstate()` inherits it from `base_run_state` unchanged, preserving human-wait resume routing.
- Scope files read before editing: all listed individually in inputs_used[].

## Open questions

- None.

## Next consumer brief

Validation command to rerun: `cd backend && pytest tests/test_harness_state_mapping.py -v --override-ini="addopts="`

All 49 tests pass (exit code 0). No edge cases uncovered during implementation beyond what the design specified.

The `_harness_status` sentinel key in `WfNodeState.fields` is an implementation detail that I4 (HarnessExecutorAdapter) should be aware of but not need to touch — it is only consumed by `workflowstate_to_runstate()`. I4 may freely add other keys to `fields` without conflict.

Out-of-scope: none flagged. The `RunState.executor_variant` field referenced in I5 does not yet exist; I3 has no dependency on it and does not need it.
