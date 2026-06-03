---
cc_version: '1.0'
agent: pipeline-architect
slug: arc6-executor
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
- .cronos/pipeline/arc6-executor/scout-report-arc6-executor.md
- .cronos/pipeline/arc6-executor/analysis-report-arc6-executor.md
- backend/app/pipeline/schemas/design.schema.yaml
- backend/app/harnesses/model.py
outputs_produced:
- .cronos/pipeline/arc6-executor/design-report-arc6-executor.md
blockers: []
next_consumer: implementation
coverage_summary:
  searched:
  - backend/app/harnesses/
  - backend/app/worker.py
  - backend/app/trace_parser.py
  - backend/app/storage.py
  - backend/app/models.py
  - backend/app/api/tools.py
  - backend/tests/
  excluded:
  - 'frontend/: backend-only feature; TracePanel.tsx backward-compat only (parent_run_id=None
    path)'
  - 'tools/: adoption-specific; agent resolution handled via api/tools.py'
  strategies:
  - memory_retrieval
  - read_targeted
  - grep_symbol
iterations:
- id: I1
  type: data
  scope_files:
  - backend/app/trace_parser.py
  - backend/tests/test_trace_parser.py
  validation_command: cd backend && pytest tests/test_trace_parser.py -v
  max_diff_lines: 200
  depends_on: []
- id: I2
  type: backend
  scope_files:
  - backend/app/harnesses/interpolate.py
  - backend/tests/test_harness_interpolate.py
  validation_command: cd backend && pytest tests/test_harness_interpolate.py -v
  max_diff_lines: 250
  depends_on: []
- id: I3
  type: backend
  scope_files:
  - backend/app/harnesses/brief_composer.py
  - backend/tests/test_harness_brief_composer.py
  validation_command: cd backend && pytest tests/test_harness_brief_composer.py -v
  max_diff_lines: 250
  depends_on: []
- id: I4
  type: backend
  scope_files:
  - backend/app/harnesses/run_state.py
  - backend/tests/test_harness_run_state.py
  validation_command: cd backend && pytest tests/test_harness_run_state.py -v
  max_diff_lines: 300
  depends_on: []
- id: I5
  type: backend
  scope_files:
  - backend/app/harnesses/executor.py
  - backend/tests/test_harness_executor.py
  validation_command: cd backend && pytest tests/test_harness_executor.py -v
  max_diff_lines: 600
  depends_on:
  - I1
  - I2
  - I3
  - I4
- id: I6
  type: backend
  scope_files:
  - backend/tests/test_harness_executor_e2e.py
  validation_command: cd backend && pytest tests/test_harness_executor_e2e.py -v
  max_diff_lines: 400
  depends_on:
  - I5
risks:
- description: run_agent and _finalize_child are methods on the Worker class in worker.py;
    calling them from a new module risks circular imports or requires passing a Worker
    handle through HarnessExecutor.execute(). If the reuse boundary is wrong, R8 review
    fails and the executor either duplicates worker logic or cannot run in isolation.
  severity: high
  mitigation: I5 must inject the Worker instance (or a small WorkerProtocol with the
    two callables) as a constructor argument of HarnessExecutor; tests stub WorkerProtocol.
    The implementor MUST NOT copy run_agent/_finalize_child bodies into executor.py
    — review verdict (R8) explicitly checks this.
- description: Calling run_agent + _finalize_child synchronously inside the harness
    execute() loop (R9) can starve the space's serial worker for the harness's full
    wall-clock duration, blocking unrelated tasks behind it. If the harness is long,
    the queue appears hung.
  severity: medium
  mitigation: I5 wraps each Agent node call in an asyncio shield-free await; before
    and after each node it publishes a 'harness_node_progress' lifecycle event so
    the worker queue observers can render progress. I6 e2e test asserts a competing
    task enqueued during a harness run executes AFTER the harness completes (FIFO
    preserved).
- description: extract_run_trace has four call sites (trace_parser.py self, worker.py,
    test_trace_parser.py, test_arc5_e2e.py). Adding parent_run_id as a positional
    arg would break them. R6 requires it as a default-None kwarg, but if the implementor
    inserts it positionally the entire test suite (1500+ tests) goes red.
  severity: high
  mitigation: I1 scope explicitly forbids positional arg changes — parent_run_id MUST
    be added as a keyword-only argument with default None. I1 validation runs the
    existing trace_parser tests unchanged to prove backward-compat; arc5_e2e and worker.py
    callers are NOT in I1 scope.
- description: Atomic write via tmpfile + os.replace can leak partial state if process
    is killed between tmpfile-write and replace; on restart the executor may resume
    from stale 'in_progress' state that diverges from actual TaskStore state (child
    task may have completed). R7 restart-safety becomes fragile.
  severity: medium
  mitigation: 'I4 treats ''in_progress'' nodes as pending on resume (re-execute),
    per analysis assumption. I5 reconciliation step: before re-executing an in_progress
    node, query TaskStore for the recorded child_task_id; if it exists and is DONE,
    mark the node done and skip. I4 unit test covers the in_progress→reconcile path.'
- description: Variable interpolation uses safe_substitute, but Harness.variables
    and upstream-output scopes can have key collisions (e.g. a node id literally named
    'lang' colliding with a root variable 'lang'). Analysis R4 says 'upstream output
    wins on collision', but that semantic is non-obvious and easy to invert.
  severity: low
  mitigation: I2 documents the precedence (root variables substituted FIRST, then
    upstream outputs override) in module docstring and asserts it in a dedicated unit
    test 'test_collision_upstream_wins'. I5 wires the merge in the documented order.
- description: 'Open question from analysis: fail-fast vs. continue-after-node-failure
    is unresolved. If the implementor picks the wrong default, R3 acceptance (''executor
    continues to subsequent nodes (or halts per fail-fast policy)'') is ambiguous
    and review may reject.'
  severity: medium
  mitigation: I5 implementor MUST default to fail-fast (halt remaining nodes, mark
    them 'skipped' with reason='upstream_failed') because this matches existing _run_goal
    semantics in worker.py. I5 test 'test_executor_fail_fast_on_node_failure' locks
    the behavior. Decision recorded here so review (R8) can verify.
metrics:
  tool_calls: 9
  files_read: 4
  memory_hits: 6
  iterations_planned: 6
---

## Summary

The arc6-executor design splits the new `backend/app/harnesses/executor.py` interpreter into four independent foundation modules plus the executor itself plus an end-to-end test. The data-layer change (RunTrace.parent_run_id, I1), the interpolation helper (I2), the brief composer (I3), and the run-state persistence (I4) are all parallelizable in layer 0; the `HarnessExecutor` class (I5) integrates them and reuses `run_agent` / `_finalize_child` via dependency injection rather than direct import, sidestepping the circular-import risk that the Worker class boundary creates. The end-to-end test (I6) locks the 3-node linear acceptance criterion (R10) and the FIFO worker-contention invariant (R9). Fail-fast on node failure is the chosen default (mirrors `_run_goal`); this resolves one of the two analysis open questions and is encoded as risk mitigation rather than a separate iteration.

## Components

### Data
- `RunTrace.parent_run_id` (backend/app/trace_parser.py): new optional `str | None` field on the Pydantic model, default `None`; persisted in the trace JSON; populated only when an Agent task is run from inside a harness.
- `extract_run_trace(...)`: gains a keyword-only argument `parent_run_id: str | None = None`; assigned onto the returned RunTrace; positional signature preserved for the four existing callers.

### Backend
- `backend/app/harnesses/interpolate.py`: pure function `interpolate(template: str, root_vars: dict, upstream_outputs: dict) -> tuple[str, list[str]]` using `string.Template.safe_substitute`; merges scopes with documented precedence (root first, upstream overrides on collision); returns interpolated text plus list of unresolved placeholder names for warning logs.
- `backend/app/harnesses/brief_composer.py`: pure function `compose_brief(node: HarnessNode, interpolated_prompt: str, agent_entry: AiToolEntry | None) -> str`; prepends `/<skill-name>` for skill agent_refs; embeds resolved agent reference in the brief body; returns a string ready to pass to `TaskStore.create(brief=...)`.
- `backend/app/harnesses/run_state.py`: `RunState` dataclass + `load(path)` / `save_atomic(path, state)` functions; uses tmpfile + `os.replace`; schema matches scout finding section 7 (`nodes_executed` keyed by node id with `status`, `child_task_id`, `output`).
- `backend/app/harnesses/executor.py`: `HarnessExecutor` class with `__init__(self, store: TaskStore, worker_protocol: WorkerProtocol, tools_resolver: Callable)` and `async execute(self, run_goal_id: str, harness: Harness, space: Space) -> RunState`. Walks edge-based Kahn topo-sort over `harness.nodes`; for Agent nodes: composes brief, creates child Task, calls `worker_protocol.run_agent`, then `worker_protocol.finalize_child`, captures `RunTrace.final_text_snippet` into the variable scope, persists run-state, advances; for control-flow nodes: records `status='skipped'` and follows outgoing edges; reuses analysis fail-fast default.

## Implementation plan

| ID  | Type    | Depends on    | Scope files (abridged)                                                 | Validation                                                  |
|-----|---------|---------------|------------------------------------------------------------------------|-------------------------------------------------------------|
| I1  | data    | -             | backend/app/trace_parser.py, backend/tests/test_trace_parser.py        | cd backend && pytest tests/test_trace_parser.py -v          |
| I2  | backend | -             | backend/app/harnesses/interpolate.py, tests/test_harness_interpolate.py| cd backend && pytest tests/test_harness_interpolate.py -v   |
| I3  | backend | -             | backend/app/harnesses/brief_composer.py, tests/test_harness_brief_composer.py | cd backend && pytest tests/test_harness_brief_composer.py -v |
| I4  | backend | -             | backend/app/harnesses/run_state.py, tests/test_harness_run_state.py    | cd backend && pytest tests/test_harness_run_state.py -v     |
| I5  | backend | I1, I2, I3, I4| backend/app/harnesses/executor.py, tests/test_harness_executor.py      | cd backend && pytest tests/test_harness_executor.py -v      |
| I6  | backend | I5            | backend/tests/test_harness_executor_e2e.py                             | cd backend && pytest tests/test_harness_executor_e2e.py -v  |

Requirement coverage map (every R<N> from analysis is covered):

- R1 (DAG topo walk) -- I5
- R2 (Agent node → child Task) -- I5
- R3 (brief composition + agent_ref resolution) -- I3 (composer), I5 (resolution wiring)
- R4 (variable interpolation) -- I2 (helper), I5 (scope lifecycle)
- R5 (control-flow stub as skipped) -- I5
- R6 (RunTrace.parent_run_id) -- I1
- R7 (atomic run-state persistence) -- I4 (module), I5 (call sites)
- R8 (reuse run_agent + _finalize_child) -- I5 (verified at review phase)
- R9 (no new worker lane) -- I5 (no asyncio.create_task), I6 (FIFO assertion)
- R10 (3-node linear e2e) -- I6

## Risks

| Risk                                                                                                                | Severity | Mitigation                                                                                                                  |
|---------------------------------------------------------------------------------------------------------------------|----------|-----------------------------------------------------------------------------------------------------------------------------|
| Worker class methods (run_agent, _finalize_child) tightly coupled; naive import risks circular import or test isolation failure | high     | Inject WorkerProtocol into HarnessExecutor constructor; tests stub it; implementor must not copy logic into executor.py     |
| Synchronous in-worker execution can starve queue for long harnesses                                                 | medium   | Publish progress events; I6 asserts FIFO ordering of a competing queued task                                                |
| extract_run_trace callers break if parent_run_id added positionally                                                 | high     | Keyword-only with default None; I1 reuses existing trace_parser tests unchanged                                             |
| Atomic write race vs. crash between tmpfile and replace; stale in_progress state on resume                          | medium   | Treat in_progress as pending on resume; reconcile via TaskStore.get(child_task_id) before re-execution                      |
| Variable scope collision semantics non-obvious                                                                      | low      | Root-first / upstream-overrides documented in I2 docstring + unit test                                                      |
| Fail-fast vs. continue undecided in analysis                                                                        | medium   | Default to fail-fast (matches _run_goal); locked in I5 test test_executor_fail_fast_on_node_failure                         |

## Assumptions

- `WorkerProtocol` is a minimal `typing.Protocol` (or duck-typed callable pair) — not a refactor of the Worker class. The implementor defines it inside executor.py; worker.py is not modified.
- The Worker instance threading is: `Worker._run_goal` detects a goal with a `harness_id` (or a new `type='harness_run'`) marker, instantiates `HarnessExecutor(store, self, tools_resolver)`, and awaits `execute()`. The actual integration glue into worker.py is OUT of scope for arc6.2 and belongs to a downstream arc6.3 or wiring task — I5 ships executor.py as a callable library, I6 tests it directly via a constructed WorkerProtocol stub.
- I5 uses `string.Template` (not f-strings) so that unresolved placeholders survive `safe_substitute` rather than raising.
- Edge-based Kahn topo-sort over `Harness.nodes + Harness.edges` is implemented inside executor.py; `_topo_children` from worker.py is NOT reused (it operates on TaskStore children, which do not exist until the harness runs).
- Variable scope is in-memory during execution; it is mirrored into the run-state file under `nodes_executed[node_id].output` so resume can reconstruct it.
- On resume, in_progress nodes are reconciled (re-execute or accept existing child) per the run-state mitigation; done/skipped/failed nodes are not re-executed.
- Lifecycle event publishing for harness nodes is best-effort (progress events for queue observers) but not a load-bearing requirement of arc6.2; full event surface is deferred to arc6.3.

## Open questions

- Wiring point into `worker._run_goal` (detection of "this goal is a harness run"): is the trigger a new `Task.type='harness_run'` value, a `harness_id` field on Task, or a sentinel in `Task.brief`? This is intentionally deferred to the arc6.3 wiring task; arc6.2 ships executor.py as a library and tests it directly.
- Should run-state file be exposed via API (`GET /api/harness-runs/{run_id}`)? Analysis marked this out-of-scope for arc6.2. Confirmed deferred.

## Next consumer brief

Implementors: read `iterations[]` first (your atomic units), then `iterations[N].scope_files` (your hard diff boundary), then `iterations[N].validation_command` (what the tester will run verbatim), then `risks[]` (the failure modes you must defensively code against). Layer 0 has four independent iterations (I1, I2, I3, I4) — they can run in parallel. I5 integrates all four and reuses Worker callables via constructor injection (`WorkerProtocol` — see Assumptions); the implementor MUST NOT copy `run_agent` or `_finalize_child` bodies into executor.py (R8 review check). Cross-iteration invariants not derivable from YAML: (a) I1 keyword-only `parent_run_id` argument signature (positional break = test suite red); (b) I2 precedence rule = root vars first, upstream outputs override on collision; (c) I5 fail-fast default on Agent node failure (decision captured in risks[]). Unresolved: the worker.py integration glue (wiring `_run_goal` to call HarnessExecutor) is OUT of scope for arc6.2 and deferred to a follow-up wiring task — do not modify worker.py in any iteration of this design.
