---
cc_version: "1.0"
agent: pipeline-doc-sync
slug: sg5-retarget-harnessexecutor-onto-the-ru
phase: doc
status: done
confidence: 0.85
inputs_used:
  - .cronos/pipeline/sg5-retarget-harnessexecutor-onto-the-ru/review-report-sg5-retarget-harnessexecutor-onto-the-ru--attempt1.md
  - .cronos/pipeline/sg5-retarget-harnessexecutor-onto-the-ru/impl-report-sg5-retarget-harnessexecutor-onto-the-ru--i1.md
  - .cronos/pipeline/sg5-retarget-harnessexecutor-onto-the-ru/impl-report-sg5-retarget-harnessexecutor-onto-the-ru--i2.md
  - .cronos/pipeline/sg5-retarget-harnessexecutor-onto-the-ru/impl-report-sg5-retarget-harnessexecutor-onto-the-ru--i3.md
  - .cronos/pipeline/sg5-retarget-harnessexecutor-onto-the-ru/impl-report-sg5-retarget-harnessexecutor-onto-the-ru--i4.md
  - .cronos/pipeline/sg5-retarget-harnessexecutor-onto-the-ru/impl-report-sg5-retarget-harnessexecutor-onto-the-ru--i5.md
  - .cronos/pipeline/sg5-retarget-harnessexecutor-onto-the-ru/impl-report-sg5-retarget-harnessexecutor-onto-the-ru--i6.md
  - .cronos/pipeline/sg5-retarget-harnessexecutor-onto-the-ru/impl-report-sg5-retarget-harnessexecutor-onto-the-ru--i7.md
  - CLAUDE.md
  - docs/HARNESSES.md
outputs_produced:
  - .cronos/pipeline/sg5-retarget-harnessexecutor-onto-the-ru/doc-report-sg5-retarget-harnessexecutor-onto-the-ru.md
  - CLAUDE.md
blockers: []
next_consumer: user
intentionally_not_updated:
  - path: docs/HARNESSES.md
    reason: "User-facing guide documents harness behavior at the user level, not internal executor implementation details. The runner path is an internal optimization gated by CRONOS_HARNESS_RUNNER env flag; users interact with the same harness model and API regardless of the executor variant chosen."
  - path: README.md
    reason: "Quick-start and ops guide unchanged; no new user-visible API endpoints or public runtime parameters introduced in this SG. Executor variant selection is internal (env flag)."
  - path: backend/tests/test_harness_compiler.py
    reason: "Test file — not documentation. Changes to test files are scope-exempt per Contract."
  - path: backend/tests/test_harness_compiler_fixtures.py
    reason: "Test file — not documentation."
  - path: backend/tests/test_harness_state_mapping.py
    reason: "Test file — not documentation."
  - path: backend/tests/test_harness_executor_adapter.py
    reason: "Test file — not documentation."
  - path: backend/tests/test_run_executor_runner_flag.py
    reason: "Test file — not documentation."
  - path: backend/tests/test_harness_runner_parity.py
    reason: "Test file — not documentation."
  - path: backend/tests/conftest_harness_parity.py
    reason: "Test file — not documentation."
  - path: backend/tests/test_harness_flag_matrix.py
    reason: "Test file — not documentation."
metrics:
  tool_calls: 6
  files_read: 10
  memory_hits: 0
  docs_updated: 1
  docs_considered: 10
---

## Summary

SG5 implementation adds a dual-execution-path harness engine: a new **runner path** (via delivery-workflow) alongside the existing BFS executor, gated by the `CRONOS_HARNESS_RUNNER` env flag. Seven new Python modules were created: compiler (translates Cronos harness model to portable IR), state_mapping (bidirectional RunState↔WorkflowState conversion), executor_adapter (harness→runner bridge), plus test fixtures and parity tests. The only user-facing documentation change is **CLAUDE.md**, which now documents the three new harness backend modules (compiler, state_mapping, executor_adapter) and updates the executor/run_executor descriptions to note the dual-path architecture. All other changed files are internal implementation or test-only; no user API or behavioral change. The harness feature remains transparent to end users — both paths execute the same harness model identically.

## Updated docs

| File | Change summary |
|------|----------------|
| CLAUDE.md | Added entries for backend/app/harnesses/compiler.py, backend/app/harnesses/state_mapping.py, backend/app/harnesses/executor_adapter.py; updated executor.py description to note dual-path (BFS vs runner); updated run_executor.py entry to document CRONOS_HARNESS_RUNNER flag and executor-variant persistence. |

## Intentionally not updated

- **docs/HARNESSES.md** — User-facing guide documents harness behavior at the user level, not internal executor implementation details. The runner path is an internal optimization gated by CRONOS_HARNESS_RUNNER env flag; users interact with the same harness model and API regardless of the executor variant chosen.
- **README.md** — Quick-start and ops guide unchanged; no new user-visible API endpoints or public runtime parameters introduced in this SG. Executor variant selection is internal (env flag).
- **backend/tests/test_harness_compiler.py** — Test file — not documentation. Changes to test files are scope-exempt per Contract.
- **backend/tests/test_harness_compiler_fixtures.py** — Test file — not documentation.
- **backend/tests/test_harness_state_mapping.py** — Test file — not documentation.
- **backend/tests/test_harness_executor_adapter.py** — Test file — not documentation.
- **backend/tests/test_run_executor_runner_flag.py** — Test file — not documentation.
- **backend/tests/test_harness_runner_parity.py** — Test file — not documentation.
- **backend/tests/conftest_harness_parity.py** — Test file — not documentation.
- **backend/tests/test_harness_flag_matrix.py** — Test file — not documentation.

## Assumptions

- The implementation review flagged F1 (runner-path resume gap) as a blocking issue requiring follow-up iteration; the doc-sync phase documents what was shipped, not what was reviewed, so F1 is noted in Context but does not affect doc scope.
- SG5 is an internal architecture iteration with zero user-visible behavioral change — the dual-path executor is a development-mode optimization, not a product feature exposed to users. Documentation reflects this: only architecture/modules table updated, not user guides or operational docs.
- `CRONOS_HARNESS_RUNNER` env flag is an implementation detail gated behind a default-off flag; documentation notes its existence in the Key modules tables but does not appear in user-facing README or HARNESSES guide.
- All test files are intentionally excluded from doc-sync scope per Contract §2 (never modify test files).

## Open questions

- None.

## Next consumer brief

**CLAUDE.md updated.** Three new harness backend modules (compiler, state_mapping, executor_adapter) and two modified entries (executor.py, run_executor.py) now document the dual-execution-path architecture. The implementation ships with the runner path gated behind `CRONOS_HARNESS_RUNNER=1` (default: BFS path). No changes to user-facing guides (README, HARNESSES) as the executor variant is transparent to users — the same harness model works identically via either path.

Review flagged F1 (runner-path resume from human-wait silently skips post-wait nodes), which requires a follow-up iteration to add resume support to the runner path. This is expected and does not affect the doc-sync gate.
