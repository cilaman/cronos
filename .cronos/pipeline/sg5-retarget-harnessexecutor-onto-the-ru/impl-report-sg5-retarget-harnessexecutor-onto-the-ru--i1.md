---
cc_version: "1.0"
agent: pipeline-implementor
slug: sg5-retarget-harnessexecutor-onto-the-ru--i1
phase: impl
status: done
confidence: 0.95
inputs_used:
  - .cronos/pipeline/sg5-retarget-harnessexecutor-onto-the-ru/design-report-sg5-retarget-harnessexecutor-onto-the-ru.md
  - packages/delivery-workflow/ir.py
  - packages/delivery-workflow/interface.py
  - packages/delivery-workflow/state_types.py
  - backend/app/harnesses/model.py
  - backend/app/harnesses/executor.py
iteration_id: I1
files_changed:
  - backend/app/harnesses/compiler.py
  - backend/tests/test_harness_compiler.py
validation_command_passed: true
out_of_scope_findings: []
outputs_produced:
  - .cronos/pipeline/sg5-retarget-harnessexecutor-onto-the-ru/impl-report-sg5-retarget-harnessexecutor-onto-the-ru--i1.md
blockers: []
next_consumer: test
metrics:
  tool_calls: 20
  files_read: 6
  memory_hits: 0
  diff_lines_added: 808
  diff_lines_removed: 0
---

## Summary

Implemented Compiler B (`backend/app/harnesses/compiler.py`) as a pure `compile(harness: Harness) → IRGraph` function that translates the Cronos harness data model into the portable IR consumed by the delivery-workflow runner. The compiler handles wait-node disambiguation via an explicit `mode→kind` table (R2), constructs `LoopPolicy` with default `max=10` (R3), encodes `IREdge.port` as `source.port_id` only (OQ-1), and bootstraps `sys.path` so `from ir import IRGraph` resolves from `packages/delivery-workflow`. All 42 unit tests pass (exit code 0); validation command passed on first run.

## Files changed

| File | Action | Lines +/- | Purpose |
|------|--------|-----------|---------|
| backend/app/harnesses/compiler.py | created | +240 / 0 | Pure compile(Harness) → IRGraph; wait-node disambiguation, LoopPolicy construction, sys.path bootstrap |
| backend/tests/test_harness_compiler.py | created | +568 / 0 | 42 unit tests covering R1–R3, R13, and IRGraph structural invariants |

## Out-of-scope findings

- None.

## Assumptions

- `packages/delivery-workflow` is importable from the backend: verified at implementation time by injecting the package root into `sys.path` relative to `compiler.py`'s location. The path is `<space_root>/packages/delivery-workflow`.
- The design report's scope includes the `sys.path` bootstrap inside `compiler.py` itself (noted in ## Assumptions of the design report: "small infra-adjacent change kept inside I1's scope_files for atomicity").
- `IRNode.kind` is typed as a `Literal` union; the compiler passes `# type: ignore[arg-type]` at the call site because Python's type system cannot narrow the return of `_node_kind()` to the exact `Literal` at type-check time. At runtime the correct literal is always produced.
- The `compile` builtin name shadow is annotated with `# noqa: A001`; this is deliberate per the design spec and matches the IR compiler naming convention.
- Scope files read before editing: all 6 files listed individually in inputs_used[].

## Open questions

- None.

## Next consumer brief

Rerun validation command: `cd backend && python -m pytest tests/test_harness_compiler.py -v --override-ini="addopts="`

The test suite covers all 5 requirement areas (R1 node mapping, R1 edge mapping, R1 variables/metadata, R2 wait disambiguation, R3 loop policy, R13 import boundary, plus integration structural invariants). 42/42 pass.

Key edge cases to note for the test agent:
1. The `caplog` fixture tests for warning text substrings ("no 'mode'" and "unrecognised") — if the log messages in `compiler.py` change wording, these tests will break.
2. The `test_compiler_module_imports_only_allowed_symbols` test reads the compiler source file as text; it is a source-level check, not a runtime import check, so it catches commented-out forbidden imports as well.
3. The `test_loop_default_max_is_10` test is the key R3 guard — it explicitly asserts `lp.max == 10` with a message distinguishing it from the runner's default of 5.
4. No out-of-scope findings; I2 (fixture tests) depends on this I1 and can now proceed.
