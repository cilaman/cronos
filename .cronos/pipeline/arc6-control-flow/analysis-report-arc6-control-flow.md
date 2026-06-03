---
cc_version: '1.0'
agent: pipeline-analyst
slug: arc6-control-flow
phase: analysis
status: done
confidence: 0.88
inputs_used:
- .cronos/pipeline/arc6-control-flow/scout-report-arc6-control-flow.md
- backend/app/pipeline/CONTRACT.md
- backend/app/pipeline/verify.py
- backend/app/pipeline/schemas/analysis.schema.yaml
outputs_produced:
- .cronos/pipeline/arc6-control-flow/analysis-report-arc6-control-flow.md
blockers: []
next_consumer: design
request: "Implement the three control-flow evaluators in the interpreter. These run\n\
  **in-process; never a subprocess, never a child task.**\n\n- **Decision:** branch\
  \ on the upstream Agent signal — STATUS marker (already in\n  `AgentResult.status`),\
  \ regex on `final_text_snippet`, or harness-variable compare.\n  Define precedence\
  \ + missing-signal behaviour; pick the outgoing edge by `condition` label.\n- **Wait:**\
  \ human (map to `TaskState.WAITING` + resume via the existing reply/`pending_messages`\n\
  \  mechanism), time (resume after N), or upstream signal.\n- **Aggregator:** join\
  \ N upstreams; emit on **all** or **any** (configurable). Define\n  partial-failure\
  \ semantics.\n- Reject/bound Decision-edge cycles in the 6.1 validator; add an unbounded-wait\
  \ guardrail.\n\nAcceptance: a Decision routes to edge A on `STATUS: DONE`, edge\
  \ B on `STATUS: BLOCKED`;\nAggregator `all` waits for both, `any` fires first; Wait(human)\
  \ parks in WAITING and\nresumes on reply."
has_ui: false
coverage_summary:
  searched:
  - backend/app/harnesses/executor.py (control-flow stub lines 278-287)
  - backend/app/harnesses/model.py (NodeType enum, HarnessEdge.condition)
  - backend/app/agent.py (Status enum, parse_status)
  - backend/app/worker.py (_finalize_child, pending_messages)
  - backend/app/trace_parser.py (RunTrace, exit_reason, final_text_snippet)
  - backend/app/models.py (TaskState, Task.pending_messages)
  - backend/app/pipeline/CONTRACT.md
  - backend/app/pipeline/verify.py
  - backend/app/pipeline/schemas/analysis.schema.yaml
  excluded:
  - frontend/: control-flow evaluation is pure backend interpreter logic; no UI changes
      in this arc
  - tools/adoption.py: unrelated to harness control-flow
  strategies:
  - memory_retrieval
  - read_targeted
traceability:
- requirement_id: R1
  statement: 'The Decision evaluator applies a three-layer signal precedence: (1)
    Status enum from AgentResult.status (DONE/WAIT/BLOCKED), (2) RunTrace.exit_reason
    as fallback when parse_status returns None, (3) regex match on RunTrace.final_text_snippet
    as lowest-precedence tiebreaker.'
  acceptance_criteria:
  - 'Given an upstream Agent that emitted STATUS: DONE, when the Decision evaluator
    runs, then layer-1 signal (Status.DONE) is used for edge selection and layers
    2-3 are not consulted.'
  - Given an upstream Agent with no STATUS marker and exit_code 0 (NO_STATUS), when
    the Decision evaluator runs, then exit_reason from RunTrace is used for edge selection.
  - Given an upstream Agent with no STATUS marker and no useful exit_reason, when
    a Decision edge condition is a regex pattern, then the regex is evaluated against
    final_text_snippet.
  verifying_phase: test
  confidence: 0.92
- requirement_id: R2
  statement: 'Decision edge selection maps each outgoing HarnessEdge.condition label
    against the resolved signal: exact string match for Status/exit_reason values,
    regex match for pattern conditions, and scope-variable comparison for variable-binding
    conditions.'
  acceptance_criteria:
  - Given condition='DONE' on an edge and signal Status.DONE, when edge selection
    runs, then that edge is chosen.
  - Given condition='/success/i' on an edge and final_text_snippet containing 'Success',
    when edge selection runs, then the regex matches and that edge is chosen.
  - Given condition="mode=='auto'" on an edge and harness scope variable mode='auto',
    when edge selection runs, then the variable comparison evaluates true and that
    edge is chosen.
  - When multiple edges match, the first matching edge in iteration order is chosen.
  verifying_phase: test
  confidence: 0.88
- requirement_id: R3
  statement: 'The Decision evaluator handles missing-signal and no-match cases deterministically:
    if no condition matches, the edge with condition=None (default/fallback edge)
    is selected; if no default edge exists, the Decision node fails and fail-fast
    halts the harness.'
  acceptance_criteria:
  - Given all condition labels fail to match and one edge has condition=None, when
    edge selection completes, then the None-condition edge is chosen as the default.
  - Given all condition labels fail to match and no edge has condition=None, when
    edge selection completes, then the Decision node status is set to 'failed' and
    remaining harness nodes are skipped.
  - Given an Agent that crashed (CRASHED exit_reason) with no default edge, when the
    Decision evaluator runs, then the harness halts with a descriptive error.
  verifying_phase: test
  confidence: 0.9
- requirement_id: R4
  statement: The Wait evaluator in human mode transitions the harness run goal to
    TaskState.WAITING, records the waiting Wait-node ID in run_state, and resumes
    execution at the Wait node's outgoing edges when a pending_messages reply arrives.
  acceptance_criteria:
  - Given a Wait node with mode='human', when the evaluator processes it, then the
    harness run goal transitions to TaskState.WAITING and waiting_question is set
    from node.data['waiting_question'].
  - Given the harness run goal is WAITING at a Wait node and a pending_messages reply
    is received, when the executor resumes, then it re-enters the DAG at the Wait
    node's outgoing edges (not from the beginning).
  - No child task is created for a human Wait node; the Wait is in-process only.
  verifying_phase: test
  confidence: 0.88
- requirement_id: R5
  statement: The Wait evaluator in timed mode sleeps in-process for node.data['duration_seconds']
    seconds and proceeds to outgoing edges when the sleep completes.
  acceptance_criteria:
  - Given a Wait node with mode='time' and duration_seconds=N, when the evaluator
    processes it, then execution pauses for N seconds before continuing.
  - No child task or subprocess is spawned for a timed Wait; the sleep occurs in the
    executor process.
  - After the sleep completes, the Wait node status in run_state is set to 'done'
    and outgoing edges are traversed.
  verifying_phase: test
  confidence: 0.92
- requirement_id: R6
  statement: Every Wait node with mode='human' MUST declare a max_wait_seconds bound;
    if the field is absent or None, the validator rejects the harness before execution
    with an 'unbounded human wait' error.
  acceptance_criteria:
  - Given a Wait node with mode='human' and no max_wait_seconds field, when harness
    validation runs, then a HarnessGraphError is raised and the harness is not persisted.
  - Given a Wait node with mode='human' and max_wait_seconds=3600, when harness validation
    runs, then the harness is accepted without error.
  - Timed Wait nodes (mode='time') are not required to have max_wait_seconds.
  verifying_phase: test
  confidence: 0.86
- requirement_id: R7
  statement: The Aggregator evaluator in mode='all' waits until every predecessor
    node has reached a terminal status (done or failed) before proceeding; partial-failure
    of any predecessor marks the Aggregator as failed and halts the harness.
  acceptance_criteria:
  - Given an Aggregator node in mode='all' with two predecessors, when both reach
    status='done', then the Aggregator is marked done and outgoing edges are traversed.
  - Given an Aggregator node in mode='all' and one predecessor reaches status='failed',
    then the Aggregator is marked failed and remaining harness nodes are skipped.
  - The Aggregator output in mode='all' is a concatenation of all predecessors' outputs
    in sorted predecessor-ID order, separated by a delimiter.
  verifying_phase: test
  confidence: 0.9
- requirement_id: R8
  statement: The Aggregator evaluator in mode='any' fires as soon as the first predecessor
    reaches status='done'; remaining predecessors are passively ignored; a failed
    first-completing predecessor marks the Aggregator as failed.
  acceptance_criteria:
  - Given an Aggregator node in mode='any' with two predecessors, when one reaches
    status='done' first, then the Aggregator is immediately marked done and outgoing
    edges are traversed.
  - Remaining predecessors (not yet done) are left in their current state and not
    actively cancelled.
  - Given the only predecessor to complete is status='failed', then the Aggregator
    is marked failed and remaining harness nodes are skipped.
  - The Aggregator output in mode='any' is the single winning predecessor's output.
  verifying_phase: test
  confidence: 0.88
- requirement_id: R9
  statement: All three control-flow node types (Decision, Wait, Aggregator) execute
    in-process inside the HarnessExecutor; they never spawn a subprocess, never create
    a child task, and never invoke the Claude Code CLI.
  acceptance_criteria:
  - Decision, Wait, and Aggregator evaluator code paths contain no subprocess.run
    / asyncio.create_subprocess_* / os.system calls.
  - No new Task or Goal records are created in the database for Decision, Wait, or
    Aggregator nodes.
  - The existing Agent-node execution path (spawning Claude Code CLI) is not reused
    by any control-flow evaluator.
  verifying_phase: review
  confidence: 0.95
- requirement_id: R10
  statement: The HarnessExecutor uses a runtime-gated DAG traversal so that Decision-node
    edge selection dynamically determines which downstream nodes are enqueued, rather
    than pre-computing the full topological order.
  acceptance_criteria:
  - Given a harness with a Decision node whose two outgoing edges lead to different
    Agent nodes, when the Decision routes to edge A, then only the target of edge
    A is added to the execution queue; the target of edge B is never enqueued.
  - The traversal does not require a completed topo-sort of the entire harness before
    execution begins.
  - Aggregator and Wait nodes integrate into the same runtime-gated traversal without
    requiring a separate queue mechanism.
  verifying_phase: test
  confidence: 0.82
- requirement_id: R11
  statement: The harness validator rejects any harness containing a Decision-edge
    cycle via the existing find_cycle() mechanism, surfacing a specific cycle-violation
    error before persistence.
  acceptance_criteria:
  - Given a harness where Decision node D routes to Agent A, and A has an edge back
    to D, when validation runs, then a HarnessGraphError referencing the cycle is
    raised and the harness is not saved.
  - The existing find_cycle() covers Decision edges because they are standard HarnessEdge
    objects in the graph.
  - A harness with no cycles passes validation even if it contains Decision nodes.
  verifying_phase: test
  confidence: 0.88
- requirement_id: R12
  statement: Control-flow nodes (Decision, Wait, Aggregator) record their lifecycle
    in run_state.nodes_executed using NodeState with appropriate statuses ('in_progress'
    while waiting, 'done' or 'failed' on completion), and run_state.json is persisted
    after each transition.
  acceptance_criteria:
  - A Decision node is recorded with status='done' after a routing decision is made.
  - A Wait (human) node is recorded with status='in_progress' while the run goal is
    WAITING, then updated to 'done' after resume.
  - An Aggregator node is recorded with status='in_progress' while awaiting predecessors,
    then 'done' or 'failed' on resolution.
  - run_state.json is persisted via _maybe_save after each status transition.
  verifying_phase: test
  confidence: 0.85
metrics:
  tool_calls: 7
  files_read: 4
  memory_hits: 3
---

## Summary

This feature implements three in-process control-flow evaluators — Decision, Wait, and Aggregator — inside the existing HarnessExecutor, replacing the current silent pass-through stub (executor.py lines 278-287). Decision nodes route DAG execution to exactly one outgoing edge by evaluating a three-layer signal precedence (Status enum, exit_reason fallback, regex on final_text_snippet) against HarnessEdge.condition labels. Wait nodes either park the harness run goal in TaskState.WAITING (human mode, resumable via pending_messages) or sleep in-process for a configured duration (timed mode). Aggregator nodes synchronize N predecessors with configurable all/any semantics and defined partial-failure behavior. The arc6.1 validator gains an unbounded-human-wait guardrail; Decision-edge cycle detection is inherited from the existing find_cycle() mechanism.

has_ui: false

## Scope

### In scope
- Decision evaluator: three-layer signal precedence, condition-label edge selection, default (condition=None) edge fallback, missing-signal fail-fast
- Wait evaluator: human mode (TaskState.WAITING + pending_messages resume) and timed mode (in-process sleep)
- Aggregator evaluator: all/any modes, predecessor discovery via edge traversal, partial-failure semantics, output composition
- Validator guardrail: unbounded human Wait rejection (max_wait_seconds required on human Wait nodes)
- Run-state persistence: NodeState lifecycle tracking for all three evaluator types
- Runtime-gated DAG traversal replacing static Kahn's pre-sort for control-flow paths

### Out of scope
- Frontend visualization of control-flow node states (deferred to a later arc)
- Active cancellation of losing Aggregator predecessors in mode='any'
- Aggregator timeout (timeout_seconds field, if added, is a future enhancement)
- Case-insensitive condition matching on Status labels (exact match required)
- Harness-variable mutation by control-flow nodes (only Agent nodes write to scope)

### Deferred
- Structured (JSON array) Aggregator output format — simple concatenation is MVP
- Upstream-signal Wait mode (Wait on a named upstream node's completion)
- Frontend lifecycle event publishing for control-flow nodes (harness_node_start/end)
- Aggregator timeout with configurable strictness modes

## Requirements

| R# | One-line summary |
|----|------------------|
| R1 | Decision evaluator applies three-layer signal precedence: Status enum > exit_reason > regex on final_text_snippet |
| R2 | Decision edge selection matches condition labels by type: exact match, regex, or scope-variable comparison |
| R3 | Decision handles missing/no-match cases: default (None-condition) edge or fail-fast harness halt |
| R4 | Wait (human) mode transitions run goal to TaskState.WAITING and resumes via pending_messages at the Wait node |
| R5 | Wait (timed) mode sleeps in-process for duration_seconds and proceeds to outgoing edges |
| R6 | Unbounded human Wait rejected at validation time if max_wait_seconds is absent or None |
| R7 | Aggregator (all mode) waits for every predecessor; partial predecessor failure halts the harness |
| R8 | Aggregator (any mode) fires on first-done predecessor; remaining predecessors are passively ignored |
| R9 | All three evaluators are in-process only: no subprocess, no child task, no CLI invocation |
| R10 | Executor uses runtime-gated traversal so Decision routing dynamically determines the enqueued set |
| R11 | Validator rejects Decision-edge cycles via the existing find_cycle() mechanism |
| R12 | Control-flow nodes record NodeState lifecycle transitions in run_state.json at each status change |

## Acceptance criteria

Acceptance criteria for every requirement are listed in the YAML `traceability[]` array (machine-readable source of truth). Compact mirrors for human readers:

- R1 — Layer-1 signal (Status enum) takes precedence; layers 2-3 consulted only when prior layer returns nothing
- R2 — Exact match for DONE/WAIT/BLOCKED, regex eval for pattern conditions, scope dict lookup for variable comparisons
- R3 — None-condition edge is the fallback; if absent, node fails and harness halts with a descriptive error
- R4 — Run goal enters WAITING; waiting_question set from node config; resume re-enters DAG at Wait node's successors
- R5 — Timed sleep runs in-process; Wait node records 'done' after sleep; no subprocess involved
- R6 — Validator raises HarnessGraphError for any human Wait node lacking max_wait_seconds; timed Wait is exempt
- R7 — All predecessors must reach terminal state; first failure marks Aggregator failed; output is sorted concatenation
- R8 — First done predecessor triggers Aggregator completion; others passively left; failed first-completer fails Aggregator
- R9 — No subprocess.run, no new Task/Goal DB records, no CLI invocation in any control-flow evaluator path
- R10 — Only the Decision-selected edge's target is enqueued; non-selected branch targets are never enqueued
- R11 — find_cycle() in validator.py covers Decision edges as normal HarnessEdge objects; cycle raises HarnessGraphError
- R12 — NodeState.status cycles through 'in_progress' then 'done'/'failed'; _maybe_save called after each transition

## Traceability

| R# | Verifying phase | Statement |
|----|-----------------|-----------|
| R1 | test | Decision evaluator applies three-layer signal precedence |
| R2 | test | Decision edge selection matches condition labels by type |
| R3 | test | Decision handles missing/no-match cases deterministically |
| R4 | test | Wait (human) mode transitions run goal to TaskState.WAITING and resumes via pending_messages |
| R5 | test | Wait (timed) mode sleeps in-process for duration_seconds |
| R6 | test | Unbounded human Wait rejected at validation if max_wait_seconds absent |
| R7 | test | Aggregator (all) waits for every predecessor; partial failure halts harness |
| R8 | test | Aggregator (any) fires on first-done predecessor; others passively ignored |
| R9 | review | All evaluators in-process only: no subprocess, no child task, no CLI |
| R10 | test | Executor runtime-gated traversal dynamically enqueues only selected edges |
| R11 | test | Validator rejects Decision-edge cycles via existing find_cycle() |
| R12 | test | Control-flow nodes record NodeState lifecycle in run_state.json |

## Assumptions

- Control-flow nodes do not create child tasks — this is stated explicitly in the request and confirmed by the scout; all evaluators are in-process inside HarnessExecutor.
- The existing find_cycle() / Kahn's-based validation in validator.py covers Decision outgoing edges as standard HarnessEdge objects — no separate runtime cycle check is needed.
- has_ui=false rationale: the request and scout explicitly scope this to the backend interpreter; frontend visualization is deferred.
- Status enum case sensitivity: condition labels are matched exactly (e.g., 'DONE' not 'done'); parse_status() uses an exact-case regex.
- Aggregator predecessor discovery traverses Harness.edges in reverse (target == aggregator node ID); no separate predecessor list is stored.
- Harness-variable scope is mutated only by Agent nodes; control-flow nodes read scope but do not add keys.
- Timed Wait is in-process sleep (asyncio.sleep or time.sleep), not a scheduled background task — consistent with the "never a subprocess" constraint.
- For Aggregator mode='any', remaining predecessors are passively ignored (not actively cancelled) — simplest implementation consistent with scout recommendation.
- The scout's finding that executor.py uses a static Kahn's topo-sort (lines 94-135) is taken as accurate; R10 requires a runtime-gated alternative for control-flow paths.
- Memory hits counted: 3 entries from Memory Context (project_arc6_board_setup, project_pipeline_analyst_agent, project_pipeline_architect_agent) referenced via the scout report's inputs_used.

## Open questions

- Should the executor mix the existing static topo-sort (for all-Agent harnesses) with the new runtime-gated traversal (for harnesses containing control-flow nodes), or replace the topo-sort entirely? Recommend: runtime-gated as the single traversal strategy.
- Should Aggregator mode='any' cancel in-flight Agent nodes when the first predecessor completes? This analysis defers active cancellation to a future arc.
- Should Decision condition matching for regex-type conditions support flags (e.g., /i) or be plain Python re.search? Recommend: re.search; Python inline flags ((?i)pattern) are supported natively.
- Human Wait resumption: should the Wait node ID be embedded in waiting_question or stored as a separate field in run_state? Recommend: store as waiting_node_id in run_state to avoid parsing waiting_question.

## Next consumer brief

Read `traceability[]` as the ground truth; `has_ui=false` means backend-only. Key design decision points:

1. **executor.py stub replacement (R1-R3, R9, R10, R12)**: The `if node.type != NodeType.agent` block (lines 278-287) becomes a dispatch table. Design should decide whether to inline evaluators or extract to separate modules (e.g., `decision.py`, `wait.py`, `aggregator.py` in `backend/app/harnesses/`).

2. **Runtime-gated traversal (R10)**: The static `_topo_sort` must be replaced or augmented with a BFS/queue approach where Decision routing determines which nodes enter the ready-queue dynamically. Scout recommends breadth-first with dynamic in-degree decrement.

3. **Wait (human) resume wiring (R4)**: Executor must expose a resume entry point callable from the worker's pending_messages processing path. Design must specify: (a) `waiting_node_id` stored in run_state; (b) worker reads it and calls executor.resume(node_id); (c) executor re-enters traversal from that node's outgoing edges.

4. **Validator guardrail (R6)**: `max_wait_seconds` required on human Wait nodes. This touches `model.py` (HarnessNode data schema) and `validator.py` (new validation rule).

5. **NodeState status lifecycle (R12)**: `in_progress` intermediate status may not exist in the current NodeState — design must confirm or extend the status enum in model.py.

6. **Highest-risk change**: Runtime-gated traversal (R10) affects all harness executions. Design phase must plan a regression test against all-Agent harnesses to confirm no behavioral change.
