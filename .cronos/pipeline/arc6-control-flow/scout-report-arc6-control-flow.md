---
cc_version: '1.0'
agent: pipeline-scout
slug: arc6-control-flow
phase: scout
status: done
confidence: 0.86
inputs_used:
- memory:project_arc6_board_setup
- memory:project_pipeline_analyst_agent
- memory:project_pipeline_architect_agent
- backend/app/harnesses/model.py
- backend/app/harnesses/executor.py
- backend/app/agent.py
- backend/app/worker.py
- backend/app/trace_parser.py
- backend/app/models.py
- .cronos/pipeline/arc6-executor/scout-report-arc6-executor.md
- .cronos/pipeline/arc6-executor/analysis-report-arc6-executor.md
- .cronos/pipeline/arc6-executor/design-report-arc6-executor.md
outputs_produced:
- .cronos/pipeline/arc6-control-flow/scout-report-arc6-control-flow.md
blockers: []
next_consumer: analysis
coverage_summary:
  searched:
  - backend/app/harnesses/ (model.py, executor.py)
  - backend/app/agent.py (Status enum, parse_status)
  - backend/app/worker.py (_finalize_child, trace extraction)
  - backend/app/trace_parser.py (RunTrace model, exit_reason field)
  - backend/app/models.py (Task, TaskState enum)
  excluded:
  - frontend/: control-flow is backend interpreter logic, no UI changes in 6.3
  - tools/adoption.py: not relevant to control-flow evaluation
  strategies:
  - memory_retrieval
  - glob_structural
  - grep_symbol
  - read_targeted
brief: Research how control-flow nodes (Decision, Wait, Aggregator) are structured
  in the interpreter. Identify signal sources (STATUS, exit_reason, text regex), edge
  routing, task state mapping, cycle/wait guardrails, and existing hooks for control-flow
  evaluation.
metrics:
  tool_calls: 20
  files_read: 9
  memory_hits: 3
---


## Summary

The arc6-control-flow feature implements three in-process evaluators (Decision, Wait, Aggregator) that plug into the existing HarnessExecutor's DAG traversal without spawning child tasks. Control-flow nodes are currently stubbed as silent pass-throughs in executor.py (lines 278–287). The interpreter receives three signal sources for routing decisions: `AgentResult.status` / `RunTrace.exit_reason` (DONE/WAIT/BLOCKED parsed from agent output), regex matching on `final_text_snippet`, and harness-variable comparison. Decision nodes branch edges based on conditions; Wait nodes map to TaskState.WAITING with `pending_messages` for human resumption or sleep for timed waits; Aggregator nodes merge N upstreams (all vs. any semantics). Validator.py already enforces DAG acyclicity (R5); cycle detection for Decision edges is inherited from the broader harness validation. Unbounded waits are bound by explicit timeout or human response mechanism.

## Coverage

### Searched
- **backend/app/harnesses/model.py** (L24–31): NodeType enum defines `agent`, `trigger`, `decision`, `wait`, `aggregator` node categories.
- **backend/app/harnesses/executor.py** (L278–287): Current control-flow stub; marked as pass-through, status='skipped'.
- **backend/app/agent.py** (L60–96): Status enum (DONE, WAIT, BLOCKED); parse_status() scans final text in reverse, extracts status marker and context line.
- **backend/app/worker.py** (L660–740, parse_status call sites): _finalize_child() reads parse_status() result, maps Status.DONE→TaskState.DONE, Status.WAIT→TaskState.WAITING, Status.BLOCKED→TaskState.WAITING. Context line becomes waiting_question.
- **backend/app/trace_parser.py** (L123–155): RunTrace model includes `exit_reason: str` (parsed from agent output), `final_text_snippet: str` (last text before end), `parent_run_id: str|None`. exit_reason values: "DONE", "WAIT", "BLOCKED", "CRASHED", "NO_STATUS", "KILLED_BY_USER", "TURN_LIMIT", etc.
- **backend/app/models.py** (L10–15): TaskState enum: BACKLOG, ACTIVE, WAITING, DONE, ARCHIVED. Task has `pending_messages: list[str]` for queuing human replies.
- **Arc6 prior phase reports** (executor scout/analysis/design): executor.py lines 293–304 interpolate prompt_template using root Harness.variables + upstream node outputs; edge-based topo-sort (Kahn's algorithm); fail-fast on upstream failure.

### Excluded
- **frontend/**: Control-flow evaluation is a backend interpreter concern; UI visualization deferred.
- **tools/adoption.py**: Not relevant to control-flow node semantics.
- **test files**: Deferred to verifier phase; implementation tests will validate behavior.

### Strategies
- **memory_retrieval**: 3 hits (arc6 board setup, analyst/architect agent docs, prior executor phase reports confirm state-of-the-art).
- **glob_structural**: Located harnesses/, agent.py, worker.py, trace_parser.py, models.py as control-flow core.
- **grep_symbol**: Searched for Status enum, parse_status, TaskState.WAITING, exit_reason, pending_messages to understand signal flow.
- **read_targeted**: Depth-read model.py, executor.py stub, agent.py Status + parse_status, worker.py finalize logic, trace_parser.py RunTrace.

## Findings

### 1. Signal Sources: Three-Layer Precedence

The interpreter has three sources for routing decisions, with a **defined evaluation order**:

#### Layer 1: AgentResult.status (Highest Precedence)
- **Source**: `backend/app/agent.py:parse_status()` parses the agent's final text for `STATUS: DONE|WAIT|BLOCKED` markers.
- **Enum**: `Status(str, Enum)` with values `DONE`, `WAIT`, `BLOCKED` (L60–64).
- **Parsing logic** (L69–96):
  - Scans the last 10 lines of agent output in reverse to find the last valid `STATUS:` marker (regex L66: `^\s*\*{0,3}STATUS:\s*(DONE|WAIT|BLOCKED)\*{0,3}\s*$`).
  - Returns a tuple `(status, context_line)` — context is the immediately preceding non-blank line (used as waiting_question or blocker reason).
  - If no marker found, returns `(None, None)`.
- **Persistence**: The status is extracted during `_finalize_child()` (worker.py:660–740) and converted to task state transitions.
  - `Status.DONE` → `TaskState.DONE`
  - `Status.WAIT` → `TaskState.WAITING` (context_line stored as waiting_question)
  - `Status.BLOCKED` → `TaskState.WAITING` (context_line stored as waiting_question)

#### Layer 2: RunTrace.exit_reason (Fallback Signal)
- **Source**: `backend/app/trace_parser.py:RunTrace` field `exit_reason: str` (L134).
- **Values** (inferred from worker.py:488–491, trace_parser.py logic):
  - `"DONE"` — agent output parse_status → DONE (or STATUS not present but exit_code == 0).
  - `"WAIT"` — agent output parse_status → WAIT.
  - `"BLOCKED"` — agent output parse_status → BLOCKED.
  - `"CRASHED"` — exit_code != 0 (process killed, segfault, etc.).
  - `"NO_STATUS"` — exit_code == 0 but no STATUS marker found (agent ran to completion without explicit marker).
  - `"KILLED_BY_USER"` — user stopped the agent mid-run.
  - `"TURN_LIMIT"` — agent hit conversation turn limit.
  - Special values: `"TIMEOUT"`, `"ERROR"`, etc. (see trace_parser parse logic).
- **Rationale**: exit_reason is a computed field derived from parse_status output + exit code + other runtime signals. For Decision node routing, **prefer Status.DONE|WAIT|BLOCKED if present**; fall back to exit_reason only when parse_status returned None.

#### Layer 3: Regex on final_text_snippet (Lowest Precedence)
- **Source**: `RunTrace.final_text_snippet: str` (L146) — the last text output before the run ended, truncated to ~1000 chars (trace_parser.py:76–92).
- **Use case**: When parse_status returns None and you need a secondary signal. Example: Decision node with condition `"final_text_contains('Success')"` would regex-match the final_text_snippet.
- **Implementation note**: This is a tiebreaker; agent output should always provide a STATUS marker for deterministic routing.

### 2. Decision Node (Conditional Branching)

**Structure** (model.py:24–31, HarnessNode):
- `type: NodeType = decision`
- `data: dict` contains node-specific config (e.g., guard expression, condition metadata).
- `ports: dict[str, dict]` — outbound ports, one per edge (in/out).
- `edges` in Harness reference this node's source ports via `HarnessEdge.source.node_id` + `source.port_id`.

**Routing Logic**:
Each outgoing edge has an optional `condition: str | None` (model.py:68). The executor should:
1. Evaluate the node's upstream Agent output using the three-layer precedence above.
2. For each outgoing edge, check its condition label against the signal.
3. **Precedence for condition matching**:
   - **Exact match on Status.DONE|WAIT|BLOCKED**: e.g., condition="DONE" matches status==Status.DONE.
   - **Regex match on final_text_snippet**: e.g., condition="contains('Success')" or condition="/^error:/i" (regex flags).
   - **Harness-variable compare**: e.g., condition="mode=='production'" evaluates a variable binding.
   - **Missing signal → default edge**: If no upstream signal (parse_status returned None and no variables match), pick edge with condition=None (the "otherwise" edge) if it exists; else halt with error.

**Missing-Signal Behavior**:
- If no Signal is available (Agent crashed with NO_STATUS, CRASHED), check for a condition=None edge (default/fallback edge).
- If no default edge exists, **the Decision node fails** and fail-fast halts the harness (consistent with executor.py:389–400 for other node failures).

**Cycle Detection for Decision Edges**:
- validator.py already runs `find_cycle()` on the full harness (line 120) using Kahn's algorithm over all edges.
- **Decision-specific cycles**: If a Decision edge creates a backward edge (e.g., Decision→A→...→Decision), the full DAG cycle check catches it before execution.
- **Prevention**: The validator rejects any harness with a cycle at creation time (HarnessGraphError raised in store.py); arc6.3 does not need to re-check at runtime.

### 3. Wait Node (Human / Timed Pause)

**Structure** (model.py):
- `type: NodeType = wait`
- `data: dict` contains wait-mode config: `mode` ("human" | "time"), and mode-specific fields:
  - `mode="human"`: `waiting_question: str` (prompt to present to user).
  - `mode="time"`: `duration_seconds: int` (sleep duration).

**Mapping to TaskState.WAITING**:
Wait nodes **do not create child tasks**. Instead, the executor:
1. Records the Wait node status as `skipped` in run_state.json (for arc6.2 compat; arc6.3 implements full Wait semantics).
2. **Human wait** (arc6.3):
   - Create a **pseudo-task** (or mark the run goal as WAITING) with `waiting_question` set to node.data["waiting_question"].
   - Store the node_id in the run-state so that on resume (via pending_messages reply), the executor knows which Wait node to continue from.
   - Map `pending_messages` input → continue signal; re-enter executor at the Wait node's outgoing edges.
3. **Timed wait** (arc6.3):
   - Sleep for `node.data["duration_seconds"]` seconds.
   - When sleep completes, proceed to outgoing edges.

**Unbounded-Wait Guardrail**:
- Human waits are bounded by **explicit timeout or user override** (future enhancement; not in arc6.3 scope).
- Timed waits are bounded by the specified duration; no unbounded sleep.
- **Recommendation for arc6.3 design**: Add an optional `max_wait_seconds: int` field to the Wait node's data; if duration exceeds it, halt with error.

### 4. Aggregator Node (N-Input Join)

**Structure** (model.py):
- `type: NodeType = aggregator`
- `data: dict` contains aggregation config:
  - `mode: str` — "all" (wait for all upstreams DONE) or "any" (fire on first upstream DONE).
  - `timeout_seconds: int | None` — optional timeout for waiting.

**Execution Semantics**:

#### `mode="all"` (All Upstreams Must Complete)
- The executor waits until **all** predecessor nodes (nodes with edges targeting this Aggregator) have reached `status == done` in run_state.nodes_executed.
- Once all predecessors are done, the Aggregator node is marked done and execution proceeds to outgoing edges.
- **Partial-failure handling**: If any predecessor reaches `status == failed`, the Aggregator node is marked failed and fail-fast halts the harness.
- **Output composition**: The aggregator's output is a concatenation (or structured merge) of all upstream final_text_snippets. Recommend:
  ```
  output = "\n---\n".join([
      f"[{pred_id}] {run_state.nodes_executed[pred_id].output}"
      for pred_id in sorted(upstreams)
  ])
  ```

#### `mode="any"` (First Upstream Wins)
- The executor fires as soon as **any** predecessor reaches `status == done`.
- Once one predecessor is done, the Aggregator node is marked done; other upstreams are cancelled (skipped).
- **Partial-failure handling**: If the first predecessor to complete is marked failed, the Aggregator is marked failed (fail-fast halts).
- **Output composition**: Use the single upstream's output.

**Identifying Predecessors**:
- Traverse `Harness.edges` for all edges with `target.node_id == aggregator_node_id`; collect source node IDs.
- Wait for those source nodes in run_state.nodes_executed to reach a terminal state (done, failed, or skipped).

**Timeout Behavior**:
- If `mode="all"` and upstreams do not all complete within `timeout_seconds`, mark Aggregator as `skipped` with reason="timeout" and proceed (or mark failed, depending on strictness).
- For arc6.3, recommend: timeout → fail the Aggregator (strict mode).

### 5. Integration with Executor DAG Traversal

**Topo-Sort & Execution Flow** (executor.py:173–402):
Currently (arc6.2), the executor walks the harness graph using Kahn's algorithm (_topo_sort, L94–135):
1. Builds adjacency list from `Harness.edges` source→target node pairs.
2. Computes in-degree for each node.
3. Processes nodes in topological order: zero in-degree first.

**For Arc6.3 Control-Flow Integration**:
1. **Decision nodes** insert into the topo-sort normally; when reached, evaluate the condition and **only follow the matching outgoing edge** (update the queue / in-degree counts dynamically, or post-process the topo-sort to select edges).
   - **Post-process approach (simpler)**: Compute full topo-sort first; at execution time, gate the target node's execution based on the Decision condition.
2. **Wait nodes** block execution at the node (no child task created); if mode="human", transition the harness run goal to WAITING and wait for a resume signal.
3. **Aggregator nodes** synchronize on multiple predecessors; wait until all (or any) predecessors reach a terminal state before proceeding.

**Dynamic Topo-Sort Challenge**:
- Kahn's algorithm assumes a **static DAG**. If Decision nodes dynamically choose edges, the topo-sort must be recomputed per execution path (or use a path-aware topo-sort).
- **Recommendation**: Use a **breadth-first traversal with state tracking** instead of pre-computed Kahn's sort:
  ```python
  ready_nodes = [start_node_id]  # zero in-degree nodes
  while ready_nodes:
    node = ready_nodes.pop(0)
    execute(node)
    # Determine outgoing edges based on control-flow decision
    for edge in selected_outgoing_edges:
      target_id = edge.target.node_id
      if decrement_in_degree(target_id) == 0:
        ready_nodes.append(target_id)
  ```

### 6. Variable Scope & Output Passing

**Scope Lifecycle** (executor.py:248–249):
- Initialized at harness run start: `scope = dict(harness.variables)`.
- After each Agent node completes, upstream output is added: `scope[node_id] = trace.final_text_snippet`.
- **Decision / Aggregator / Wait nodes do not add to scope** (they don't produce new outputs; they route/merge existing ones).

**Control-Flow Nodes Reading Scope**:
- **Decision**: Evaluate condition using scope + upstream signals.
  - Example: condition=`"status_is('DONE') and var_equals('mode', 'auto')"` reads both the upstream Status and the harness variable "mode".
- **Aggregator**: Read upstreams' outputs from scope (keys = predecessor node_ids).
  - Example: merge outputs like `scope[upstream_id_1] + scope[upstream_id_2]`.
- **Wait**: No scope changes; just pause.

### 7. Task State Mapping for Control-Flow Nodes

**Current Arc6.2 Behavior** (executor.py:280–287):
```python
if node.type != NodeType.agent:
    log.debug("Node %s is control-flow (%s) — stub pass-through.", node_id, node.type)
    state.nodes_executed[node_id] = NodeState(
        status="skipped",
        reason="control_flow_stub",
    )
    _maybe_save(state, run_state_path)
    continue
```

**For Arc6.3**:
- **Decision**: No task created. Record as `status="done"` (or `status="control_flow_decision"` if arc6.3 adds intermediate statuses).
- **Wait (human)**: Mark harness run goal as `TaskState.WAITING` (not the Wait node itself). Wait node is marked `status="in_progress"` until a reply arrives via `pending_messages`.
- **Wait (time)**: Sleep, then mark node `status="done"`.
- **Aggregator**: No task created. Mark as `status="in_progress"` while waiting for upstreams; then `status="done"` when condition met.

**Fail-Fast on Control-Flow Node Failure** (executor.py:268–275):
If a control-flow node fails (e.g., timeout on Aggregator), `upstream_failed = True` halts remaining nodes:
```python
if upstream_failed:
    state.nodes_executed[node_id] = NodeState(
        status="skipped",
        reason="upstream_failed",
    )
    _maybe_save(state, run_state_path)
    continue
```

### 8. Existing Hooks for Control-Flow Evaluation

**executor.py Integration Points**:
1. **Post-topo-sort, pre-execution** (L254): Insert control-flow logic here to reorder / filter edges.
2. **Node type dispatch** (L280): Replace the stub `if node.type != NodeType.agent` with actual control-flow evaluators.
3. **Per-node state tracking** (run_state.json): Use `NodeState.status` and `reason` fields to record control-flow outcomes.

**worker.py Integration Points**:
- `parse_status()` already extracts Status markers; no changes needed.
- `_finalize_child()` maps Status → TaskState; control-flow nodes bypass this (no child task).
- `pending_messages` mechanism (Task.pending_messages: list[str]) is ready for Wait (human) resumption.

### 9. Unbounded-Wait and Cycle Detection Summary

**Cycle Detection**:
- validator.py:find_cycle() uses BFS to detect cycles in the edge DAG.
- **Decision edge cycles** (e.g., Decision→A→Decision) are caught by the full DAG cycle check; no special rule needed.
- **Prevention at creation time**: HarnessStore.create() calls validate_graph() before persistence; any cycle raises HarnessGraphError.

**Unbounded-Wait Guardrail** (Arc6.3 Requirement):
- Human Wait: Recommend adding `max_wait_seconds: int | None` to Wait node data; if missing/None, halt with error "unbounded human wait".
- Timed Wait: Duration is explicit; no unbounded case.
- **Aggregator timeout**: Existing `timeout_seconds` field (if present) bounds the wait; if missing, use a default (e.g., 3600s = 1 hour) or halt with error.

### 10. Precedence & Error Cases

**Decision Condition Evaluation Order**:
1. Parse Status marker from upstream Agent's final output.
2. If no Status marker, check exit_reason field.
3. If no signal available, use condition=None (default) edge.
4. If condition is a regex, match against final_text_snippet.
5. If condition is a variable compare, evaluate using scope dict.

**Missing/Conflicting Signals**:
- No upstream signal + no default edge → Decision fails, fail-fast halts harness.
- Multiple matching edges → Pick the first edge in iteration order (or halt with error "ambiguous routing").

---

## Assumptions

- **Control-flow nodes do not create child tasks** in either arc6.2 (stubs) or arc6.3 (full implementation). They are in-process evaluators only.
- **Status enum (DONE/WAIT/BLOCKED) is the primary signal source** for Decision routing. parse_status() is the canonical parser; exit_reason is a fallback.
- **Harness-variable scope persists across all nodes** and accumulates upstream outputs. Scope is checkpointed in run_state.json (via nodes_executed output field).
- **Cycle detection (R5) is solved at harness creation time** by validator.py; arc6.3 does not need runtime cycle checks.
- **Unbounded waits are prevented by design** (explicit duration for timed waits, explicit max_wait for human waits) or will cause arc6.3 design to add guardrails.
- **Aggregator output is a merge (concatenation) of upstream outputs**, not a structured format (e.g., JSON array). Simplicity first; can refine in arc6.4.
- **Decision edges with condition=None are treated as default/fallback edges** when no other condition matches.
- **Fail-fast semantics apply to control-flow node failures** (Aggregator timeout, Decision missing signal): remaining nodes are marked skipped, harness halts.

---

## Open questions

- Should Decision edge conditions support a **case-insensitive match** on Status (e.g., condition="done" vs condition="DONE")? Recommend: exact match (uphold case sensitivity).
- For Aggregator `mode="any"`, should remaining upstreams be **actively cancelled** (marked skipped) or passively ignored? Recommend: passively ignored; no cancellation logic (simplicity).
- Should **Wait (human) resume from pending_messages** happen at the Wait node level (executor continues from the Wait node) or at the harness run goal level (goal's waiting_question queues the Wait node's ID)? Recommend: harness run goal becomes WAITING; resume signal includes Wait node ID; executor continues from that node.
- Should **control-flow nodes publish lifecycle events** (harness_node_start / harness_node_end) for frontend observability? Recommend: arc6.3 publishes them; arc6.2 is silent.
- **Test acceptance**: Should Decision routing be validated with a 3-way harness (Decision → Agent-DONE-branch, Agent-WAIT-branch, Agent-BLOCKED-branch)? Recommend: yes, add to arc6.3 test suite.

---

## Next consumer brief

**Analyst should read**:
1. **Signal sources** (Section 1): Three-layer precedence for routing — Status enum, exit_reason, regex on final_text_snippet.
2. **Decision node routing** (Section 2): condition labels, precedence for matching, missing-signal behavior, inherited cycle detection.
3. **Wait semantics** (Section 3): human vs. time modes, mapping to TaskState.WAITING, unbounded-wait guardrails.
4. **Aggregator join logic** (Section 4): all vs. any modes, predecessor identification, output composition, timeout behavior.
5. **Integration hooks** (Section 8): executor.py lines 254, 280–287, run_state persistence.
6. **Assumptions** (all 7): Especially "control-flow nodes do not create child tasks" and "scope persists across nodes".
7. **Key design challenges**:
   - **Dynamic topo-sort**: Kahn's algorithm assumes static DAG; Decision edges require runtime path selection. Recommend breadth-first with state tracking.
   - **Wait (human) resumption**: Harness run goal must transition to WAITING; pending_messages reply triggers executor re-entry at the Wait node.
   - **Aggregator predecessor tracking**: Must traverse edges in reverse; wait loop must tolerate partial failures.
8. **Test touchpoints**: Decision 3-way routing, Wait (human) pause/resume, Aggregator all/any semantics, fail-fast on node failures, unbounded-wait detection.

**Key decision points for analysis**:
- Confirm the three-layer signal precedence order; adjust if needed (e.g., should regex match be checked before exit_reason?).
- Clarify "default edge" semantics for Decision (what if condition=None edge doesn't exist?).
- Scope accumulation: should control-flow nodes add to scope, or only Agent nodes? (Recommend: only Agent nodes.)
- Dynamic vs. static topo-sort: breadth-first or pre-compute all paths?
- Human Wait resumption: at harness goal level or Wait node level?

**Verification phase**: arc6.3 tester will validate Decision routing with multi-branch harnesses, Wait (human) with pending_messages, Aggregator with all/any semantics, and unbounded-wait detection.

