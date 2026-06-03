---
cc_version: '1.0'
agent: pipeline-architect
slug: arc6-control-flow
phase: design
status: done
confidence: 0.82
inputs_used:
- memory:project_arc6_board_setup
- memory:project_arc6_61_review_loop
- memory:project_pipeline_architect_agent
- memory:project_pipeline_schemas
- memory:project_pipeline_verifier
- memory:project_architecture_key_modules
- .cronos/pipeline/arc6-control-flow/scout-report-arc6-control-flow.md
- .cronos/pipeline/arc6-control-flow/analysis-report-arc6-control-flow.md
- backend/app/pipeline/schemas/design.schema.yaml
- backend/app/harnesses/model.py
- backend/app/harnesses/executor.py
- backend/app/harnesses/run_state.py
- backend/app/harnesses/validator.py
outputs_produced:
- .cronos/pipeline/arc6-control-flow/design-report-arc6-control-flow.md
blockers: []
next_consumer: implementation
coverage_summary:
  searched:
  - backend/app/harnesses/model.py
  - backend/app/harnesses/executor.py
  - backend/app/harnesses/validator.py
  - backend/app/harnesses/run_state.py
  - backend/app/worker.py
  - backend/app/trace_parser.py
  - backend/app/agent.py
  - backend/app/models.py
  - backend/tests/test_harness_*.py
  excluded:
  - 'frontend/: backend-only feature (has_ui=false in analysis report); control-flow
    UI deferred to a later arc'
  - 'tools/: unrelated to harness control-flow evaluation'
  - 'backend/app/api/: no new endpoints in this arc; resume entry point is internal
    worker hook'
  strategies:
  - memory_retrieval
  - read_targeted
  - grep_symbol
iterations:
- id: I1
  type: data
  scope_files:
  - backend/app/harnesses/model.py
  - backend/app/harnesses/validator.py
  - backend/tests/test_harness_model.py
  - backend/tests/test_harness_validator.py
  validation_command: cd backend && pytest tests/test_harness_model.py tests/test_harness_validator.py
    -v
  max_diff_lines: 300
  depends_on: []
- id: I2
  type: data
  scope_files:
  - backend/app/harnesses/run_state.py
  - backend/tests/test_harness_run_state.py
  validation_command: cd backend && pytest tests/test_harness_run_state.py -v
  max_diff_lines: 250
  depends_on: []
- id: I3
  type: backend
  scope_files:
  - backend/app/harnesses/decision.py
  - backend/tests/test_harness_decision.py
  validation_command: cd backend && pytest tests/test_harness_decision.py -v
  max_diff_lines: 450
  depends_on:
  - I1
- id: I4
  type: backend
  scope_files:
  - backend/app/harnesses/wait.py
  - backend/tests/test_harness_wait.py
  validation_command: cd backend && pytest tests/test_harness_wait.py -v
  max_diff_lines: 400
  depends_on:
  - I1
  - I2
- id: I5
  type: backend
  scope_files:
  - backend/app/harnesses/aggregator.py
  - backend/tests/test_harness_aggregator.py
  validation_command: cd backend && pytest tests/test_harness_aggregator.py -v
  max_diff_lines: 400
  depends_on:
  - I2
- id: I6
  type: backend
  scope_files:
  - backend/app/harnesses/executor.py
  - backend/tests/test_harness_executor.py
  validation_command: cd backend && pytest tests/test_harness_executor.py -v
  max_diff_lines: 600
  depends_on:
  - I3
  - I4
  - I5
- id: I7
  type: backend
  scope_files:
  - backend/app/worker.py
  - backend/tests/test_harness_wiring.py
  validation_command: cd backend && pytest tests/test_harness_wiring.py -v
  max_diff_lines: 350
  depends_on:
  - I6
- id: I8
  type: backend
  scope_files:
  - backend/tests/test_harness_validator.py
  validation_command: cd backend && pytest tests/test_harness_validator.py::test_decision_edge_cycle_rejected
    -v
  max_diff_lines: 120
  depends_on:
  - I1
- id: I9
  type: backend
  scope_files:
  - backend/tests/test_harness_acceptance.py
  validation_command: cd backend && pytest tests/test_harness_acceptance.py -v
  max_diff_lines: 500
  depends_on:
  - I6
  - I7
risks:
- description: Replacing the static Kahn's topo-sort in executor.py with a runtime-gated
    BFS could regress existing all-Agent harness execution (incorrect node ordering,
    double-enqueue, or missed nodes). All harness e2e/wiring tests depend on the current
    traversal.
  severity: high
  mitigation: I6 must preserve sorted-by-node-id determinism in ready-queue insertion
    (matching _topo_sort's tie-break), and must re-run the full test_harness_executor.py
    + test_harness_executor_e2e.py + test_harness_wiring.py suites unmodified before
    merge. Add a regression test asserting a 4-Agent linear chain produces the same
    node execution order as the current implementation.
- description: 'Wait (human) resume path crosses the executor/worker boundary: the
    executor parks the harness goal in TaskState.WAITING, and a pending_messages reply
    must re-enter execute() at the waiting Wait node. If the worker calls execute()
    from the top instead of from waiting_node_id, the resumed run will re-execute
    completed Agent nodes (creating duplicate child tasks) or skip the Wait''s outgoing
    edges.'
  severity: high
  mitigation: I2 stores waiting_node_id on RunState (not just NodeState); I6's execute()
    detects an existing in_progress Wait node and resumes traversal from its outgoing
    edges; I7's worker pending_messages handler calls executor.execute(run_goal_id,
    harness, space) unchanged, relying on the executor to internally resume from waiting_node_id.
    Add a test that asserts a Wait-human resume re-uses already-completed Agent node
    outputs from run_state.nodes_executed without re-running them.
- description: Aggregator predecessor discovery relies on traversing Harness.edges
    in reverse (target == aggregator_id). In a linear traversal the predecessors will
    have already been executed when the Aggregator's turn comes; in a runtime-gated
    BFS they may complete out of order, and mode='any' requires firing as soon as
    the first predecessor reports done — not waiting for the Aggregator's slot in
    the queue.
  severity: medium
  mitigation: 'I5 + I6: when any predecessor of an Aggregator reaches a terminal state,
    the executor immediately evaluates the Aggregator''s readiness (count of done/failed
    predecessors vs. mode). For mode=''all'', enqueue Aggregator only when all predecessors
    are terminal. For mode=''any'', enqueue Aggregator as soon as the first done predecessor
    is finalized. Test with a 2-Agent + Aggregator(any) harness where one Agent completes
    much faster than the other.'
- description: Decision condition matching has four distinct cases (Status exact-match,
    exit_reason exact-match, regex on final_text_snippet, scope-variable comparison)
    plus a default-edge fallback. Misordered precedence or sloppy regex compilation
    could cause a Decision to silently route to the wrong edge — a class of bug that
    passes unit tests on simple cases but fails in production.
  severity: medium
  mitigation: I3 implements a single resolve_signal() function returning a typed tuple
    (layer, value), and a separate edge_matches(edge, signal, scope) predicate. Decision
    unit tests in test_harness_decision.py must include each precedence layer in isolation
    AND a layered case (Status present but a regex edge also matches — Status wins).
    Variable-comparison conditions are parsed with a small whitelisted grammar (==,
    !=, in) — no eval().
- description: max_wait_seconds is a new required field on human Wait nodes. Existing
    fixtures, smoke harnesses, and any user-saved harnesses in {space}/.cronos/harnesses/
    without this field will fail validation on load, potentially blocking the upgrade.
  severity: medium
  mitigation: 'I1 grep-audits the repo for existing Wait(human) fixtures and updates
    them in the same iteration. Validator error message must include the offending
    node id and the exact field name to allow a fast user-side fix. Migration is forward-only:
    arc6.3 release notes call out the new field.'
- description: Timed Wait uses asyncio.sleep in-process; if the harness goal is cancelled
    or the process restarts mid-sleep, the run resumes from the Wait node and re-sleeps
    the full duration. There is no persisted 'sleep-started-at' timestamp.
  severity: low
  mitigation: 'Acceptable for arc6.3 MVP — documented in the Wait node code header
    and in the release notes. A persisted resume_at field is deferred to a future
    arc (noted in ## Open questions).'
metrics:
  tool_calls: 12
  files_read: 7
  memory_hits: 6
  iterations_planned: 9
---

## Summary

This design replaces the silent control-flow stub in `executor.py` (lines 278–287) with three first-class in-process evaluators — Decision, Wait, and Aggregator — split into dedicated modules under `backend/app/harnesses/` and wired into a runtime-gated BFS traversal that replaces the current static Kahn's topo-sort. Decision routing applies a three-layer signal precedence (Status enum > `exit_reason` > regex on `final_text_snippet`) against `HarnessEdge.condition` labels with a `None`-condition default edge as fallback. Wait nodes either park the harness run goal in `TaskState.WAITING` (human mode, resumed via `pending_messages` re-entry at the waiting node) or sleep in-process with `asyncio.sleep` (timed mode). Aggregators synchronize N predecessors with all/any semantics and explicit partial-failure handling. The `max_wait_seconds` field becomes mandatory on human Wait nodes (R6 guardrail), Decision-edge cycles are caught by the existing `find_cycle()` mechanism (R11), and all evaluators are in-process only — no subprocess, no child task, no CLI invocation (R9).

## Components

### Data
- `backend/app/harnesses/model.py`: HarnessNode `data` schema documents `mode`, `duration_seconds`, `waiting_question`, `max_wait_seconds` for Wait nodes; `mode` ('all'|'any') for Aggregator nodes. No new top-level model classes — keeps `data: dict` open per existing convention.
- `backend/app/harnesses/validator.py`: New `_validate_wait_nodes()` rule rejects human Wait nodes lacking `max_wait_seconds`; reuses `find_cycle()` for Decision-edge cycles (no new code path).
- `backend/app/harnesses/run_state.py`: `NodeState.status` accepts `'in_progress'` semantically for control-flow nodes (already a valid value, but documented). `RunState` gains optional `waiting_node_id: str | None` field for human Wait resume routing.

### Backend
- `backend/app/harnesses/decision.py` (new): `evaluate_decision(node, predecessors_state, scope, run_trace) -> str` returns the chosen edge id. Internal helpers `resolve_signal()` and `edge_matches()` keep precedence and matching logic separable and unit-testable.
- `backend/app/harnesses/wait.py` (new): `enter_wait(node, run_state) -> WaitOutcome` for human mode (sets run goal to WAITING + records `waiting_node_id`); `await_timed_wait(node) -> None` async sleep for timed mode. Pure functions — no subprocess, no Task creation.
- `backend/app/harnesses/aggregator.py` (new): `aggregator_ready(node, predecessors_state) -> AggregatorVerdict` (`pending` | `done` | `failed`) plus `compose_output(verdict, predecessors_state, mode)`. Predecessor discovery via `[e.source.node_id for e in harness.edges if e.target.node_id == node.id]`.
- `backend/app/harnesses/executor.py`: Replaces `_topo_sort` + linear `for node in ordered_nodes` loop with a runtime-gated BFS (`ready_queue` + dynamic in-degree decrement). Control-flow dispatch table replaces the stub at line 280. Persists `NodeState` transitions through `'in_progress'` → `'done'`/`'failed'` for control-flow nodes (R12). Exposes resume re-entry through the existing `execute()` entry point — internal logic detects a Wait node with `status='in_progress'` and resumes traversal from its outgoing edges.
- `backend/app/worker.py`: pending_messages reply handler for a WAITING harness goal calls `executor.execute(run_goal_id, harness, space)` (already exists); the executor internally consults `RunState.waiting_node_id` to resume.

### Frontend
<!-- has_ui=false per analysis report; no frontend components in this arc. -->

## Implementation plan

| ID | Type    | Depends on  | Scope files (abridged)                                                                                    | Validation                                                                       |
|----|---------|-------------|-----------------------------------------------------------------------------------------------------------|----------------------------------------------------------------------------------|
| I1 | data    | -           | backend/app/harnesses/model.py, validator.py, tests/test_harness_model.py, test_harness_validator.py      | cd backend && pytest tests/test_harness_model.py tests/test_harness_validator.py -v |
| I2 | data    | -           | backend/app/harnesses/run_state.py, tests/test_harness_run_state.py                                       | cd backend && pytest tests/test_harness_run_state.py -v                          |
| I3 | backend | I1          | backend/app/harnesses/decision.py, tests/test_harness_decision.py                                         | cd backend && pytest tests/test_harness_decision.py -v                           |
| I4 | backend | I1, I2      | backend/app/harnesses/wait.py, tests/test_harness_wait.py                                                 | cd backend && pytest tests/test_harness_wait.py -v                               |
| I5 | backend | I2          | backend/app/harnesses/aggregator.py, tests/test_harness_aggregator.py                                     | cd backend && pytest tests/test_harness_aggregator.py -v                         |
| I6 | backend | I3, I4, I5  | backend/app/harnesses/executor.py, tests/test_harness_executor.py                                         | cd backend && pytest tests/test_harness_executor.py -v                           |
| I7 | backend | I6          | backend/app/worker.py, tests/test_harness_wiring.py                                                       | cd backend && pytest tests/test_harness_wiring.py -v                             |
| I8 | backend | I1          | backend/tests/test_harness_validator.py                                                                   | cd backend && pytest tests/test_harness_validator.py::test_decision_edge_cycle_rejected -v |
| I9 | backend | I6, I7      | backend/tests/test_harness_acceptance.py                                                                  | cd backend && pytest tests/test_harness_acceptance.py -v                         |

Requirement coverage cross-check:

| Req | Covered by                            |
|-----|---------------------------------------|
| R1  | I3 (resolve_signal three-layer)       |
| R2  | I3 (edge_matches by condition type)   |
| R3  | I3 (default edge + fail-fast)         |
| R4  | I4 (human mode) + I7 (worker resume)  |
| R5  | I4 (timed mode async sleep)           |
| R6  | I1 (validator guardrail)              |
| R7  | I5 (mode='all' + partial-failure)     |
| R8  | I5 (mode='any' first-done)            |
| R9  | I6 (executor dispatch, no subprocess) |
| R10 | I6 (runtime-gated BFS)                |
| R11 | I8 (Decision-edge cycle test)         |
| R12 | I2 + I6 (NodeState lifecycle)         |

## Risks

| Risk                                                                                          | Severity | Mitigation                                                                                                                                  |
|-----------------------------------------------------------------------------------------------|----------|---------------------------------------------------------------------------------------------------------------------------------------------|
| Runtime-gated BFS regresses existing all-Agent harness execution                              | high     | I6 preserves sorted-by-node-id determinism; full existing suites re-run unmodified; add 4-Agent linear chain regression test.               |
| Wait (human) resume re-executes completed Agent nodes (duplicate child tasks)                 | high     | I2 stores `waiting_node_id` on RunState; I6 detects in_progress Wait and resumes at its outgoing edges; I7 reuses existing execute() entry. |
| Aggregator mode='any' requires firing out-of-queue-order                                      | medium   | I5+I6: each predecessor's terminal transition triggers Aggregator readiness check; tested with skewed-completion Aggregator harness.        |
| Decision condition matching has four cases — silent mis-routing risk                          | medium   | I3 splits resolve_signal/edge_matches; per-layer and layered unit tests; whitelisted comparison grammar (no eval).                          |
| max_wait_seconds required field breaks existing human-Wait fixtures                           | medium   | I1 audits + updates fixtures in the same iteration; clear validator error message; release-notes call-out.                                  |
| Timed Wait sleep restart on process crash re-sleeps full duration                             | low      | Documented MVP limitation; persisted resume_at deferred (see Open questions).                                                               |

## Assumptions

- Control-flow evaluators never create child tasks, never spawn subprocesses, never invoke the Claude Code CLI (confirmed by analysis R9 + scout Section 8).
- `find_cycle()` in `validator.py` already covers Decision-edge cycles because Decision edges are normal `HarnessEdge` objects (analysis R11; scout Section 9). No runtime cycle check is needed.
- The existing `NodeState.status` value `'in_progress'` is accepted by `run_state.py` (confirmed at line 24 of the docstring) — R12 needs no new status enum value.
- Decision condition syntax: exact string match for Status/exit_reason values (case-sensitive); regex via `re.search` (Python inline flags `(?i)...` for case-insensitivity); variable comparison via a small whitelisted grammar (`==`, `!=`, `in`) — no `eval()`.
- Aggregator predecessor discovery is computed on-the-fly by reverse-traversing `Harness.edges`; no separate predecessor list is stored.
- The worker's existing `pending_messages` processing already calls into the harness execute path; I7 verifies/extends rather than re-architects that hook.
- `has_ui=false` per the analysis report — no frontend visualization in this arc.
- `waiting_node_id` is stored on RunState rather than embedded in `waiting_question`, per analysis Open question recommendation.
- Memory hits counted: 6 (arc6_board_setup, arc6_61_review_loop, pipeline_architect_agent, pipeline_schemas, pipeline_verifier, architecture_key_modules) — all consulted while reasoning about iteration shape, prior arc6 design pattern, and verifier rules.

## Open questions

- Should the executor persist a `sleep_resume_at: datetime` on timed Wait nodes so that a process restart mid-sleep resumes for the remaining duration instead of re-sleeping the full duration? Deferred — low risk, simple to add later, not in arc6.3 scope.
- For Decision regex conditions, should the executor support an explicit `/pattern/flags` syntax in addition to Python inline flags? Recommend: inline flags only for arc6.3; flag-suffix syntax can come in arc6.4 if user demand exists.
- When a human Wait reply arrives with content the harness wants to inject as a scope variable, should the Wait node write to `scope` or stay scope-immutable? Analysis assumption says control-flow nodes do not mutate scope; design preserves that. Revisit if Wait-with-reply-data becomes a real use case.

## Next consumer brief

Implementors should read the YAML `iterations[]` array and pick up exactly one entry per invocation. Three cross-iteration invariants are NOT derivable from `iterations[]` alone and must be honored:

1. `RunState.waiting_node_id` is the **single** source of truth for Wait-human resume routing — I2 introduces it, I6 reads it, I7 must not duplicate the resume logic in the worker.
2. The new modules `decision.py`, `wait.py`, `aggregator.py` are **pure functions** with no subprocess/asyncio.create_subprocess_*/os.system calls and no `await self.store.create(...)` for control-flow nodes — R9 is reviewer-verified, but implementors should not be tempted to inline a fallback path.
3. The runtime-gated BFS in I6 must preserve the **sorted-by-node-id tie-break** that `_topo_sort` uses (executor.py L119, L127) to keep deterministic node execution order for existing all-Agent harnesses — the high-severity regression risk hinges on this.

Open question on `sleep_resume_at` (timed Wait restart) is explicitly out of scope; implementors should NOT add that field. The Decision regex `/pattern/flags` syntax is also deferred — use plain `re.search` with Python inline flags only.
