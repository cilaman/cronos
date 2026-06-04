---
cc_version: '1.0'
agent: pipeline-analyst
slug: arc6-executor
phase: analysis
status: done
confidence: 0.88
inputs_used:
- memory:project_pipeline_analyst_agent
- memory:project_arc6_board_setup
- memory:project_pipeline_schemas
- memory:project_pipeline_verifier
- .cronos/pipeline/arc6-executor/scout-report-arc6-executor.md
- backend/app/harnesses/model.py
- backend/app/trace_parser.py
- backend/app/worker.py
outputs_produced:
- .cronos/pipeline/arc6-executor/analysis-report-arc6-executor.md
blockers: []
next_consumer: design
request: "Build the runtime in `backend/app/harnesses/executor.py`. A run is a Task\
  \ (`type=goal`);\n**only Agent nodes become child tasks.**\n\n- **Do NOT reuse `_run_goal`\
  \ wholesale** (only recurse/`run_agent` branches exist). Build\n  a **new stateful\
  \ DAG interpreter** walking the graph: at an Agent node, materialise/enqueue\n \
  \ a child Task and await its terminal state (reuse `run_agent` + `_finalize_child`\
  \ + the\n  topo-sort from `_topo_children` [worker.py:51]). Stub control-flow nodes\
  \ as pass-through\n  here (6.3 implements them) so a linear all-Agent harness runs\
  \ end to end.\n- **Agent binding:** compose `agent_ref` + `prompt_template` + resolved\
  \ `variable_bindings`\n  into the child Task `brief` (skills get a `/<name>` prefix);\
  \ resolve `agent_ref` against\n  api/tools.py. No new `--agent` flag.\n- **Variable/data\
  \ passing:** define how an upstream node's output (child\n  `RunTrace.final_text_snippet`\
  \ / STATUS) flows into a downstream node's `prompt_template`\n  variables.\n- **`parent_run_id`:**\
  \ optional field on `RunTrace` (trace_parser.py:110); thread through\n  `extract_run_trace`,\
  \ set on each Agent child, persist in the trace JSON without breaking\n  TracePanel.tsx.\n\
  - Run state (per-node status, chosen edges, child ids) persists at\n  `{space}/.cronos/harness-runs/<run_id>.json`\
  \ (restart-safe).\n- Address worker contention: a run holds the space's single serial\
  \ worker\n  (worker_pool.py) for its whole duration -- avoid starving normal tasks.\n\
  \nAcceptance: a 3-node linear harness expands to a goal + 3 child tasks in topo\
  \ order; each\nchild's `parent_run_id` = run id; an upstream output is interpolated\
  \ into the next prompt;\nrun-state file reflects per-node status."
has_ui: false
coverage_summary:
  searched:
  - backend/app/harnesses/
  - backend/app/worker.py
  - backend/app/trace_parser.py
  - backend/app/storage.py
  - backend/app/models.py
  - backend/app/api/tools.py
  excluded:
  - frontend/: backend-only feature; TracePanel.tsx compatibility is a backward-compat
      constraint, not new UI work
  - tools/adoption.py: adoption-specific; agent resolution covered by api/tools.py
  strategies:
  - memory_retrieval
  - read_targeted
  - grep_symbol
traceability:
- requirement_id: R1
  statement: executor.py provides a HarnessExecutor class with an async execute(run_goal_id,
    harness, space) entry-point that walks the harness DAG in topological order derived
    from HarnessEdge references and returns only after all nodes reach a terminal
    state.
  acceptance_criteria:
  - Given a Harness with N Agent nodes and no cycles, when execute() is called, then
    nodes are visited in topological order consistent with harness edges.
  - execute() does not call _run_goal; it is a self-contained DAG interpreter.
  - execute() returns only after every node has reached status done, skipped, or failed.
  verifying_phase: test
  confidence: 0.92
- requirement_id: R2
  statement: For each Agent node encountered during DAG traversal, the executor materialises
    a child Task (type='task', parent_id=run_goal_id) via TaskStore.create() and awaits
    its terminal state using run_agent then _finalize_child.
  acceptance_criteria:
  - Given a harness with 3 Agent nodes, when execute() completes, then exactly 3 child
    tasks exist with parent_id equal to the run goal id.
  - Each child Task is created before run_agent is called for that node.
  - Child tasks are created with type='task' (not 'goal').
  verifying_phase: test
  confidence: 0.9
- requirement_id: R3
  statement: The executor composes each Agent child Task brief from the node's agent_ref,
    prompt_template, and resolved variable_bindings; skills receive a leading /<name>
    prefix; agent_ref is resolved via api/tools.py; an unresolvable agent_ref marks
    the node failed without crashing the executor.
  acceptance_criteria:
  - Given a node with agent_ref='pipeline-scout' and prompt_template='Analyse {target}',
    when the child task is created, its brief contains the resolved agent reference
    and interpolated prompt.
  - Given a node with a skill agent_ref, the child task brief is prefixed with /<skill-name>.
  - An unresolvable agent_ref causes the node to be recorded as failed in the run-state
    file; the executor continues to subsequent nodes (or halts per fail-fast policy).
  verifying_phase: test
  confidence: 0.85
- requirement_id: R4
  statement: The executor resolves {node_id.output} and {node_id.STATUS} placeholders
    in each node's prompt_template by substituting the upstream RunTrace.final_text_snippet
    and exit_reason respectively; root Harness.variables are substituted first; unresolved
    placeholders are preserved as literal text and a warning is logged.
  acceptance_criteria:
  - Given a downstream node prompt_template containing {upstream_id.output}, when
    the upstream Agent node completes, the downstream child task brief contains the
    upstream RunTrace.final_text_snippet.
  - Given a downstream node prompt_template containing {upstream_id.STATUS}, the placeholder
    is replaced with the upstream node exit_reason string.
  - Root-level harness variables are substituted before upstream output variables;
    a key collision favors the upstream output value.
  - Unresolved placeholders are left as-is (safe_substitute behaviour) and a warning
    is logged; interpolation does not raise an exception.
  verifying_phase: test
  confidence: 0.82
- requirement_id: R5
  statement: 'Control-flow nodes (trigger, decision, wait, aggregator) are treated
    as no-op pass-throughs: the executor records them as status=skipped in the run-state
    file and immediately follows their outgoing edges without creating any child Task.'
  acceptance_criteria:
  - Given a harness containing a decision node between two Agent nodes, when execute()
    runs, no child Task is created for the decision node.
  - The decision node entry in the run-state file has status='skipped'.
  - The executor visits Agent nodes downstream of the skipped control-flow node.
  verifying_phase: test
  confidence: 0.95
- requirement_id: R6
  statement: RunTrace gains an optional parent_run_id field (str | None, default None)
    populated by extract_run_trace when a parent_run_id keyword argument is supplied;
    the field is persisted in the trace JSON; existing callers passing no parent_run_id
    are unaffected.
  acceptance_criteria:
  - RunTrace model has a parent_run_id field of type str | None with default None.
  - extract_run_trace accepts an optional parent_run_id keyword argument and assigns
    it to the returned RunTrace.
  - When a harness child task completes, its persisted trace JSON contains parent_run_id
    equal to the run goal id.
  - When parent_run_id is None (normal non-harness run), the trace JSON contains null
    or omits the field and the existing TracePanel.tsx renders without error.
  verifying_phase: test
  confidence: 0.88
- requirement_id: R7
  statement: The executor persists run state to {space_dir}/.cronos/harness-runs/{run_id}.json
    after each node state change using an atomic write (tmpfile + os.replace); the
    file records per-node status, child_task_id, and output snippet; nodes already
    done or skipped are not re-executed on restart.
  acceptance_criteria:
  - After each Agent node completes or is skipped, the run-state JSON file is updated
    atomically via tmpfile+os.replace.
  - 'The run-state file contains a nodes_executed dict keyed by node id with fields:
    status (pending/in_progress/done/skipped/failed), child_task_id (Agent nodes only),
    and output (final_text_snippet or empty string).'
  - On executor restart with an existing run-state file, nodes with status done or
    skipped are not re-executed.
  - The file path is {space_dir}/.cronos/harness-runs/{run_id}.json.
  verifying_phase: test
  confidence: 0.88
- requirement_id: R8
  statement: executor.py reuses run_agent and _finalize_child from worker.py for Agent
    node execution without duplicating their logic.
  acceptance_criteria:
  - executor.py imports and calls run_agent (from worker.py or a shared extraction)
    for Agent node execution.
  - executor.py imports and calls _finalize_child for post-run cleanup and state transitions.
  - No copy-paste of run_agent or _finalize_child logic exists in executor.py.
  verifying_phase: review
  confidence: 0.9
- requirement_id: R9
  statement: The executor runs within the existing space worker's serial queue without
    creating a new asyncio Task, thread, or worker lane; normal tasks enqueued while
    a harness is running wait in FIFO order behind it.
  acceptance_criteria:
  - No new asyncio Task, thread, or worker_pool entry is created by executor.py for
    harness-level scheduling.
  - Child Agent tasks are executed by calling run_agent directly inside the executor,
    not by enqueuing them to the worker queue and yielding.
  - A normal task enqueued while a harness is running does not execute until the harness
    finishes.
  verifying_phase: test
  confidence: 0.8
- requirement_id: R10
  statement: A 3-node linear harness (Agent-Agent-Agent) expands to a run goal plus
    exactly 3 child tasks in topological order; each child RunTrace has parent_run_id
    equal to the run goal id; the second node brief contains the first node output;
    and the run-state file shows all nodes at status=done.
  acceptance_criteria:
  - Given a 3-node linear harness with sequential edges, when execute() completes,
    the store contains 3 child tasks with parent_id=run_goal_id appearing in topological
    order.
  - The second child task brief includes the first child RunTrace.final_text_snippet
    substituted for its placeholder.
  - All three children RunTrace JSONs contain parent_run_id = run_goal_id.
  - The run-state file nodes_executed dict has all three node ids at status=done.
  verifying_phase: test
  confidence: 0.88
metrics:
  tool_calls: 8
  files_read: 4
  memory_hits: 4
---

## Summary

The arc6-executor feature introduces `backend/app/harnesses/executor.py`, a new stateful DAG interpreter that drives harness runs as goal hierarchies. Only Agent-type nodes produce child Tasks; control-flow nodes (trigger, decision, wait, aggregator) are stubbed as pass-throughs in this iteration. The executor reuses existing worker infrastructure (`run_agent`, `_finalize_child`) while adding three new cross-cutting concerns: variable interpolation between node outputs, a `parent_run_id` field on `RunTrace`, and atomic run-state persistence at `.cronos/harness-runs/{run_id}.json` for restart safety. Worker contention is addressed by executing the harness synchronously within the existing serial worker queue rather than introducing a parallel lane.

## Scope

### In scope
- New `backend/app/harnesses/executor.py` module with `HarnessExecutor` class
- Edge-based topological sort of harness nodes for execution ordering
- Agent node materialisation as child Tasks via TaskStore.create()
- Brief composition from agent_ref + prompt_template + resolved variable_bindings; skill prefix rule
- Agent resolution via api/tools.py _scan_category lookup
- Variable interpolation: Harness.variables (root scope) + upstream RunTrace.final_text_snippet / exit_reason
- Control-flow node stub (trigger, decision, wait, aggregator) recorded as skipped
- RunTrace.parent_run_id optional field + extract_run_trace keyword argument
- Atomic run-state persistence at {space}/.cronos/harness-runs/{run_id}.json
- Restart-safe resume (skip already-done and already-skipped nodes on re-entry)
- Serial execution within existing worker queue (no new worker lane)

### Out of scope
- Full control-flow node logic (guard evaluation, wait/resume, aggregation) -- deferred to arc6.3
- New frontend UI components (TracePanel.tsx compatibility is a backward-compat constraint only)
- New --agent CLI flag on Claude Code invocation
- Parallel multi-branch harness execution
- Run-state file API endpoint or query index

### Deferred
- Decision/wait/aggregator node full semantics (arc6.3)
- Fan-out / parallel branch execution
- Run-state file serving via API (potential arc6.4+ concern)
- Harness-level retry logic on Agent node failure

## Requirements

| R# | One-line summary |
|----|------------------|
| R1 | HarnessExecutor.execute() walks harness DAG in topological edge order and returns after all nodes reach terminal state |
| R2 | Each Agent node is materialised as a child Task via TaskStore.create() before run_agent is called |
| R3 | Child Task brief is composed from agent_ref + prompt_template + variable_bindings; skill prefix rule enforced |
| R4 | Upstream Agent node output (final_text_snippet / exit_reason) is interpolated into downstream node prompt_template |
| R5 | Control-flow nodes are stubbed as skipped pass-throughs; no child Task is created for them |
| R6 | RunTrace gains optional parent_run_id field threaded through extract_run_trace and persisted in trace JSON |
| R7 | Run state is atomically persisted per-node to {space}/.cronos/harness-runs/{run_id}.json after each state change |
| R8 | executor.py reuses run_agent and _finalize_child from worker.py without duplicating their logic |
| R9 | The executor holds the existing serial worker for the run's duration; no new worker lane is introduced |
| R10 | A 3-node linear harness produces goal + 3 child tasks in topo order with parent_run_id set and upstream output interpolated |

## Acceptance criteria

Acceptance criteria for every requirement are listed in the YAML `traceability[]` array (the machine-readable source of truth). The body summary below mirrors them in compact form for the human reader.

- R1 -- execute() visits nodes in harness-edge topological order; terminates only when all nodes are done/skipped/failed; never calls _run_goal
- R2 -- 3-Agent harness yields exactly 3 child tasks; each created before run_agent; all have type='task'
- R3 -- Brief contains resolved agent_ref + interpolated prompt; skill refs prefixed with /<name>; unresolvable agent_ref marks node failed without crashing executor
- R4 -- {node_id.output} replaced by upstream RunTrace.final_text_snippet; {node_id.STATUS} by exit_reason; unresolved placeholders left as-is with warning logged
- R5 -- No child Task created for control-flow nodes; run-state records status='skipped'; downstream Agent nodes still execute
- R6 -- RunTrace.parent_run_id is str|None default None; extract_run_trace accepts it as kwarg; harness children trace JSON contains matching run_goal_id; TracePanel unaffected when None
- R7 -- Run-state JSON updated atomically after each node; nodes_executed dict has status/child_task_id/output; done/skipped nodes not re-executed on restart; path is .cronos/harness-runs/{run_id}.json
- R8 -- executor.py imports and calls run_agent + _finalize_child from worker.py; no duplicated logic
- R9 -- No new asyncio Task or pool entry; child agents run sequentially via direct run_agent call; queued normal tasks wait until harness finishes
- R10 -- End-to-end: 3 child tasks in topo order, parent_run_id correct on all traces, second brief contains first output, run-state shows all done

## Traceability

The full requirement to acceptance criteria to verifying_phase map is the YAML `traceability[]` array. Downstream agents read the YAML directly; this section exists so a human reader sees the same routing table without parsing YAML.

| R# | Verifying phase | Statement |
|----|-----------------|-----------|
| R1 | test | HarnessExecutor.execute() walks harness DAG in topological order and returns after all nodes reach terminal state |
| R2 | test | Each Agent node is materialised as a child Task via TaskStore.create() before run_agent is called |
| R3 | test | Child Task brief is composed from agent_ref + prompt_template + variable_bindings; skill prefix rule enforced |
| R4 | test | Upstream Agent node output is interpolated into downstream node prompt_template |
| R5 | test | Control-flow nodes are stubbed as skipped pass-throughs; no child Task is created for them |
| R6 | test | RunTrace gains optional parent_run_id field threaded through extract_run_trace and persisted in trace JSON |
| R7 | test | Run state is atomically persisted per-node to {space}/.cronos/harness-runs/{run_id}.json after each state change |
| R8 | review | executor.py reuses run_agent and _finalize_child from worker.py without duplicating their logic |
| R9 | test | The executor holds the existing serial worker for the run's duration; no new worker lane is introduced |
| R10 | test | A 3-node linear harness produces goal + 3 child tasks in topo order with parent_run_id set and upstream output interpolated |

## Assumptions

- has_ui=false rationale: the entire feature is a new backend module; TracePanel.tsx compatibility is a backward-compatibility constraint (parent_run_id=None must not break existing rendering), not new UI work.
- Agent binding is done purely via brief interpolation, not a new Task field or --agent CLI flag, consistent with existing worker.py patterns and scout finding section 5.
- Variable interpolation uses Python string.Template safe_substitute semantics; unresolved placeholders are preserved as literal text and logged as warnings rather than raising exceptions.
- The topological sort for harness DAG traversal is derived from HarnessEdge source/target references (not from sibling task depends_on). _topo_children (worker.py:75) is referenced in the request as a reuse point but its signature operates on TaskStore child tasks; the executor will build its own edge-based topo-sort over Harness.nodes since child Tasks do not exist yet when ordering is computed.
- The run-state file is internal (not exposed via API); no index or query endpoint is in scope for this iteration.
- Scout status=done (confidence 0.88) -- analysis confidence matches scout's upper bound.
- Control-flow node stubs are silent (no lifecycle events required) in arc6.2; arc6.3 will add event publishing.
- On restart, a node recorded as in_progress is treated as pending and re-executed (crash-recovery assumption).

## Open questions

- Should the executor publish lifecycle events (goal_child_start / goal_child_end analogues) for harness nodes in arc6.2, or are those deferred to arc6.3 alongside full control-flow support? This affects whether run-state changes are observable via SSE in this iteration.
- When an Agent node fails (_finalize_child returns a non-DONE state or DONE with error exit_reason), should the executor halt immediately (fail-fast) or continue to remaining nodes? The request acceptance criteria imply all nodes complete, but failure semantics for error cases are not specified.

## Next consumer brief

Read `traceability[]` first (R1-R10 ground truth), then `has_ui` (false -- pure backend), then `## Scope` for in/out/deferred boundaries.

Key design decisions for the architect:

1. **run_agent / _finalize_child coupling (R8, highest risk)**: Both are defined within the Worker class scope in worker.py. The architect must decide whether to extract them to a shared module, pass the Worker instance to HarnessExecutor, or invoke them via the Worker's public interface. This choice determines whether executor.py can be tested in isolation.

2. **DAG topo-sort (R1)**: Must operate on HarnessEdge objects before child Tasks exist. The architect should implement a standalone edge-based Kahn's algorithm over Harness.nodes/edges rather than reusing _topo_children (which operates on TaskStore).

3. **Variable scope lifecycle (R4)**: A mutable scope dict must accumulate upstream outputs as nodes complete. The architect should define when the scope is created (run start), how it is updated (after each Agent node's _finalize_child), and whether it is checkpointed in the run-state file.

4. **extract_run_trace backward compatibility (R6)**: The new parent_run_id kwarg must default to None. All existing callers must be identified and verified (no positional argument breakage).

5. **Restart-resume edge case (R7)**: Nodes recorded as in_progress at crash time should be re-executed. The design must handle partial trace state for those nodes.

6. **Resolve open questions** (fail-fast vs. continue; lifecycle event publishing) before implementation begins.
