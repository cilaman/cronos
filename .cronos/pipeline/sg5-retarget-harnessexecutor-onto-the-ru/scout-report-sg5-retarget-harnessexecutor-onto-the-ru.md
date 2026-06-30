---
cc_version: "1.0"
agent: pipeline-scout
slug: sg5-retarget-harnessexecutor-onto-the-ru
phase: scout
status: done
confidence: 0.92
inputs_used:
  - .cronos/pipeline/sg5-retarget-harnessexecutor-onto-the-ru/request.md
  - backend/app/harnesses/executor.py
  - backend/app/harnesses/model.py
  - backend/app/harnesses/run_state.py
  - backend/app/harnesses/adapter.py
  - backend/app/run_executor.py
  - packages/delivery-workflow/ir.py
  - packages/delivery-workflow/interface.py
  - packages/delivery-workflow/state_types.py
outputs_produced:
  - .cronos/pipeline/sg5-retarget-harnessexecutor-onto-the-ru/scout-report-sg5-retarget-harnessexecutor-onto-the-ru.md
blockers: []
next_consumer: analysis
coverage_summary:
  searched:
    - backend/app/harnesses/
    - backend/app/run_executor.py
    - packages/delivery-workflow/
    - backend/tests/test_harness*.py
    - .cronos/harnesses/ (fixture inventory)
  excluded:
    - frontend/: harness visualization, not relevant to compiler/executor unification
    - deploy/: not relevant to code architecture
    - .git/: metadata only
  strategies:
    - memory_retrieval
    - glob_structural
    - grep_symbol
    - read_targeted
brief: "Retarget HarnessExecutor onto the runner — the unification. End-state: HarnessExecutor.execute = load harness → Compiler B → runner.run(ir, CronosAdapter). Key scope: Compiler B (Harness model → IR), runtime state reconciliation (RunState → WorkflowState), migration (parity-gated with fixture compilation tests)."
metrics:
  tool_calls: 15
  files_read: 9
  memory_hits: 0
---

## Summary

The HarnessExecutor (executor.py, ~1440 LOC) is a mature **runtime-gated BFS** harness interpreter supporting trigger, agent, decision, wait (human+timed), and aggregator nodes with loop convergence (I6+), cancellation, and resume semantics. The Harness model (model.py) defines nodes (5 types), edges, variables, and metadata. RunState (run_state.py) captures node-by-node execution snapshots with atomic JSON persistence. The runner (SG4, packages/delivery-workflow/) is an app-free portable IR-driven execution engine with WorkflowState, ExecutorInterface (dispatchAgent, runGate, evalCondition, escalate, events), and LoopPolicy. **Compiler B** must map Harness → IR (1:1 node/edge/data/loop mapping). **State reconciliation** requires RunState ↔ WorkflowState bidirectional mapping. **10 YAML fixtures** inventory harness designs (trigger+agent, decision, aggregator, wait). **WorkerAdapter** currently bridges Worker ↔ WorkerProtocol (run_agent, finalize_child, _publish). Integration strategy: load-harness → Compiler B → runner.run(ir, CronosAdapter, InitialState) with parity gate before cutover.

## Coverage

### Searched
- backend/app/harnesses/ — executor.py, model.py, run_state.py, adapter.py (full read)
- backend/app/run_executor.py — harness execution lifecycle (lines 296–402 read)
- packages/delivery-workflow/ — ir.py, interface.py, state_types.py (core contracts)
- backend/tests/test_harness*.py — 20 test files enumerated
- .cronos/harnesses/ — 10 YAML fixtures inventoried

### Excluded
- frontend/: node visualization (out-of-scope)
- deploy/, .git/: not relevant to execution architecture

### Strategies
- memory_retrieval: no prior work on runner-harness mapping found in memory context
- glob_structural: found harnesses/ module, run_executor.py, packages/delivery-workflow
- grep_symbol: located HarnessExecutor invocation in run_executor.py lines 296–402
- read_targeted: deep read of executor.py (all), model.py (all), run_state.py (all), IR types, WorkerAdapter

## Findings

### 1. Current HarnessExecutor Architecture (BFS Runtime)

**Entry**: `HarnessExecutor.execute(run_goal_id, harness: Harness, space: Space) → RunState`
- Lines 283–712: main BFS loop with cancel-race guards, resume paths, fail-fast semantics.
- Graph construction (lines 186–218): adjacency maps (node_by_id, in_degree, successors, outgoing_edges).
- Node dispatch (lines 533–651): 5 node types via dedicated evaluators.
  - **Agent** (534–552): runs child task via WorkerProtocol.run_agent(), loop-aware (I6).
  - **Decision** (554–582): conditional branching on agent output.
  - **Wait** (584–596): human-park (sets waiting_node_id) or timed-sleep.
  - **Aggregator** (598–611): mode='all'|'any', verdict-driven fire.
  - **Trigger** (613–630): entry-point pass-through.
- Resume paths: waiting_node_id routing (lines 408–430), in_progress reconciliation (lines 355–374).
- Cancel guard: reloads RunState.status before each node; halts if 'cancelled' (lines 473–492).
- Events: _publish_event() (lines 718–721) emits node_transition, edge_chosen, run_status to SSE subscribers.

**WorkerProtocol** (lines 91–129): duck-typed protocol with 3 methods.
- `run_agent(task_id, **kwargs) → RunTrace`: runs child task, extracts final_text.
- `finalize_child(task_id, trace: RunTrace) → TaskState`: returns DONE or WAITING.
- `_publish(task_id, event: dict) → None`: broadcasts SSE event.

**RunState persistence**: atomic JSON I/O (run_state.py, lines 174–199) to `.cronos/harness-runs/{run_goal_id}.json`.

### 2. Harness Model Input Shape

**HarnessNode** (model.py, lines 132–142):
```
id: str
type: NodeType (enum: agent, trigger, decision, wait, aggregator)
position: {x, y} (canvas only)
ports: dict[str, dict] (port metadata)
data: dict (node-specific config)
label: str
```

**HarnessEdge** (lines 152–159):
```
id: str
source: NodeRef (node_id, port_id)
target: NodeRef (node_id, port_id)
condition: str | None (guard expression)
```

**Harness** (lines 166–224):
```
name, description, nodes[], edges[], variables (root dict), version, created_at, updated_at
```

**data dict conventions** (model.py docstring, lines 15–104):
- **Agent**: agent_ref, prompt_template; optional loop sub-object with until, stall[], max, on_exhaust.
- **Wait**: mode ('human'|'timed'), duration_seconds, waiting_question, max_wait_seconds.
- **Aggregator**: mode ('all'|'any').
- **Decision**: no extra fields (condition on HarnessEdge).
- **Trigger**: cron → expression, timezone; webhook → kind, webhook_path, auth_token; file-change → watch_pattern, debounce_seconds; task-state-change → watched_state.

### 3. Intermediate Representation (IR) Shape

**IRNode** (ir.py, lines 44–64):
```
id: str
kind: Literal["agent", "gate", "human", "decision", "wait", "aggregator", "trigger"]
data: dict (raw spec config)
loop: LoopPolicy | None
```

**IREdge** (lines 68–88):
```
source: str (node_id)
target: str (node_id)
when: str (condition, "" = unconditional)
port: str | None (visualizer hint)
```

**IRGraph** (lines 92–136):
```
nodes: list[IRNode]
edges: list[IREdge]
variables: dict (root defaults)
metadata: dict (budget, name, etc.)
entry_nodes property: computes entry-point IDs via forward-edge filtering
```

**LoopPolicy** (lines 15–40):
```
until: str (condition)
stall: list[str] (heuristic names)
max: int (backstop)
on_exhaust: Literal["escalate", "stop"]
```

### 4. ExecutorInterface (Runtime Contract)

**interface.py**:
```python
class ExecutorInterface(Protocol):
    state: StateOps
    telemetry: TelemetryOps
    dispatchAgent(agent_ref: str, inputs: dict) → AgentResult
    runGate(gate: dict, artifact_paths: list[str]) → GateResult
    evalCondition(expr: str, scope: dict) → bool
    escalate(node_id: str, reason: str) → None
```

**StateOps**: read() → WorkflowState, write(patch: dict) → None.
**TelemetryOps**: emit(node_id: str, data: dict[str, float]) → None.

### 5. State Mapping: RunState → WorkflowState

**RunState** (run_state.py, lines 74–113):
```
run_id, harness_id, goal_task_id
nodes_executed: dict[node_id → NodeState]
status: 'running'|'done'|'failed'|'cancelled'
waiting_node_id: str | None (human-wait routing)
```

**NodeState** (lines 56–70):
```
status: 'pending'|'in_progress'|'done'|'failed'|'skipped'
child_task_id, output, reason, started_at, ended_at, wake_at
attempt: int (loop attempt counter)
prior_finding_ids: list[str] (recurring_findings stall detection)
```

**WorkflowState** (state_types.py, lines 24–29):
```
spec: str (harness YAML source)
run_id, status: 'running'|'done'|'failed'|'blocked'|'escalated'
budget: BudgetState (usd_ceiling, usd_spent)
nodes: dict[node_id → NodeState]  # runner's NodeState (different schema!)
```

**Impedance mismatch**:
- RunState.nodes_executed[node_id].status uses flat values; WorkflowState.nodes[node_id].status is same.
- RunState has harness_id, goal_task_id; WorkflowState has spec, budget.
- RunState.waiting_node_id is unique to human-wait routing; WorkflowState has no analog (runner escalates instead).
- RunState.status has 'cancelled'; WorkflowState has 'blocked'|'escalated'.

### 6. WorkerAdapter Bridge (Current)

**adapter.py** (lines 26–126): adapts Worker to WorkerProtocol.
- `run_agent()` (lines 44–76): calls `run_agent()` from agent.py directly, returns RunTrace.
- `finalize_child()` (lines 78–122): calls store.finalize_run(), transitions task to DONE|WAITING.
- `_publish()` (lines 124–126): delegates to worker._bus.publish().

**HarnessExecutor instantiation** (run_executor.py, lines 348–354):
```python
_adapter = WorkerAdapter(self._worker)
executor = HarnessExecutor(
    self.store,
    _adapter,
    _tools_resolver,
    event_worker=_adapter,
)
result_state = await executor.execute(task_id, harness, space)
```

### 7. Fixture Inventory

**10 YAML harness files** in `.cronos/harnesses/`:
- **trigger-agent**: test-harness.yml (cron trigger → agent tester).
- **single-agent**: test2.yml (agent only, no edges).
- **minimal**: f.yml, first.yml, first-harness.yml, first-harness-2.yml (stub harnesses).
- **unnamed**: ggg.yml, my-hrns.yml, my-hrnss.yml (test fixtures).
- **2-node**: test-harness-2.yml (likely trigger → agent).

**Coverage gap**: No fixtures with decision, aggregator, wait (human+timed), or loop convergence visible. Test suite has deeper coverage (20 test_harness*.py files).

### 8. Compiler B Specification

**Input**: Harness (model.py).
**Output**: IRGraph (ir.py).

**1:1 Mappings**:
| Harness | IR | Notes |
|---------|-----|-------|
| HarnessNode.type | IRNode.kind | agent→agent, trigger→trigger, decision→decision, wait→human or wait (mode-dependent?), aggregator→aggregator |
| HarnessNode.data | IRNode.data | pass-through; agent_ref/prompt_template, mode/duration_seconds, etc. |
| HarnessNode.data.loop | IRNode.loop | construct LoopPolicy(until, stall[], max, on_exhaust) |
| HarnessEdge.source.node_id | IREdge.source | direct |
| HarnessEdge.target.node_id | IREdge.target | direct |
| HarnessEdge.condition | IREdge.when | condition string (empty "" if None) |
| HarnessEdge.source.port_id, target.port_id | IREdge.port | port label tuple (source_port, target_port) or None |
| Harness.variables | IRGraph.variables | direct pass-through |
| Harness.name/description | IRGraph.metadata | name, description in metadata dict |

**Open Q**: Wait node mapping — HarnessNode.type='wait' has mode field in data. IRNode.kind should be 'human' (mode='human') or keep IRNode.kind='wait' (mode='timed')? Current IR defines 'wait' as single kind; runner likely dispatches on data.mode.

### 9. Integration Points & Handoff

**Current flow** (run_executor.py, lines 321–402):
1. Load Harness from harness_store.
2. Instantiate WorkerAdapter, HarnessExecutor.
3. Call executor.execute(task_id, harness, space).
4. Receive RunState.
5. Finalize goal task DONE|WAITING based on RunState.status and waiting_node_id.

**Target flow** (proposed):
1. Load Harness from harness_store.
2. **Compiler B**: Harness → IRGraph.
3. **CronosAdapter**: implement ExecutorInterface (dispatchAgent, runGate, evalCondition, escalate, state, telemetry).
4. **State wrap**: RunState → WorkflowState (InitialState constructor).
5. Call runner.run(ir_graph, cronos_adapter, initial_state).
6. Receive WorkflowState.
7. **Reconcile back**: WorkflowState → RunState (parity gate).
8. Finalize goal task as above.

**Events op reconciliation**: Runner emits via events op; CronosAdapter.telemetry.emit() forwards to worker._bus.publish (matching _publish signature).

**CronosAdapter scope**: Reuse WorkerAdapter logic (run_agent, finalize_child) + add ExecutorInterface methods (evalCondition → decision.eval_condition, escalate → park in WAITING).

### 10. Critical Risks & Assumptions

**Risk R1**: Wait node semantic divergence. HarnessExecutor.waiting_node_id is a **run-level routing key** (single source of truth per §run_state.py:35–42). The runner may not preserve this abstraction — it escalates instead. **Mitigation**: CronosAdapter.escalate() must map to task WAITING transition + set waiting_node_id for resume; runner's escalate() should NOT be called for human Wait nodes.

**Risk R2**: Loop bookkeeping (attempt counter, prior_finding_ids). RunState.NodeState tracks loop state (lines 66–70, run_state.py). Runner's LoopPolicy and NodeState (state_types.py) differ. **Mitigation**: CronosAdapter state reads/writes must preserve loop metadata across runner boundaries.

**Risk R3**: Port/edge metadata loss. HarnessEdge.source.port_id and target.port_id are consumed during IR construction but discarded by runner (IREdge.port is visualization-only hint). HarnessExecutor's outgoing_edges_map uses full edges for decision routing. **Mitigation**: IR must preserve port IDs in edge metadata; CronosAdapter can ignore them (executor does not re-inspect).

**Risk R4**: Cycle support. Current executor rejects cycles (topo-sort). Runner supports cycles. No regression per §5.4, but new capability requires careful testing on cyclic harnesses (none exist yet).

**Risk R5**: Cancel-race guard. HarnessExecutor reloads RunState at BFS boundaries (lines 473–492) to detect concurrent cancellation. **Mitigation**: CronosAdapter.escalate() or state patch mechanism must atomically update WorkflowState.status; runner's cancel semantics must align.

**Assumption A1**: runner.run() is **idempotent on resume** — calling it twice with same IRGraph + WorkflowState produces same result. Used for wait-human resume (initial_run=False path in run_executor.py:430).

**Assumption A2**: InitialState can be None or persisted WorkflowState. Runner must support both fresh-start and resume-from-disk.

### 11. Verification Plan Sketch

**Phase 1 — Compiler B Unit Tests**:
- For each of 10 YAML fixtures, compile to IRGraph.
- Assert IRNode.kind, IREdge.source/target, LoopPolicy match expected shape.
- Test edge cases: no edges, multiple predecessors, loop config.

**Phase 2 — Parity Test** (gate before cutover):
- Select 2–3 representative harnesses (trigger+agent, decision+aggregator, human-wait).
- Run through old BFS executor, capture RunState snapshots + events.
- Run through Compiler B + runner(CronosAdapter), capture WorkflowState snapshots + events.
- Assert:
  - Node execution order identical.
  - Event stream semantics match (node_transition, edge_chosen, run_status).
  - Final state verdicts match (done vs failed).
  - Human-wait parking + resume path works.

**Phase 3 — Integration Tests**:
- HarnessExecutor instantiation swapped to CompilerB + runner.
- Existing test suite (test_harness_executor.py, test_harness_acceptance.py, etc.) run unchanged.
- 100% test pass required before production cutover.

## Assumptions

- Compiler B is a **synchronous pure function** (Harness → IRGraph) with no app imports; lives in backend/app/harnesses/compiler.py (import-bounded).
- CronosAdapter **reuses WorkerAdapter.run_agent/finalize_child** logic; new code only implements ExecutorInterface dispatch methods + state wrapping.
- Runner's escalate() method is called **only for loop exhaustion** (per §5.3 step 4); human-wait logic remains in CronosAdapter (no change to executor.waiting_node_id routing).
- RunState and WorkflowState are **independently persisted**; migration writes WorkflowState to new location (.cronos/workflow-runs/) and reads back RunState for resume compatibility (one-shot migration or shadow mode with CRONOS_HARNESS_RUNNER flag).
- Port IDs in HarnessEdge are **purely informational** for visualizer; executor does not use them for routing decisions (verified by executor.py: outgoing_edges_map keyed by node_id, not port).

## Open questions

- Wait node kind: should HarnessNode.type='wait' compile to IRNode.kind='human' (mode='human') or keep IRNode.kind='wait'? Runner's dispatch logic unknown; recommend reading runner source or asking SG4 owner.
- Loop max default: HarnessNode data has no explicit max; executor defaults to 10 (line 795, executor.py). IR LoopPolicy.max defaults to 5 (ir.py:39). Confirm Compiler B should use 10 or let runner define default.
- Event semantics: runner may emit different event schema than executor (_publish events). Confirm CronosAdapter telemetry.emit signature matches worker._bus.publish format, or add adapter shim.
- Parity test harness selection: Design phase (analyst/architect) should identify representative harnesses exercising all node types + loop convergence + decision routing.

## Next consumer brief

**Analysis phase** should focus on:
1. **Compiler B detailed spec**: confirm 1:1 mapping table (§8) with SG4 owner for any IR schema surprises.
2. **State reconciliation strategy**: design RunState ↔ WorkflowState bidirectional mapping, including loop bookkeeping, wait routing, and cancellation.
3. **CronosAdapter interface surface**: list all ExecutorInterface methods + signatures; identify gaps vs WorkerAdapter.
4. **Parity test plan**: select 3–5 representative harnesses covering trigger, agent, decision, aggregator, wait, loop; define assertion set for event/state/verdict equivalence.
5. **Migration safety**: design one-shot migration or shadow-mode cutover with CRONOS_HARNESS_RUNNER flag; ensure drain of in-flight runs before cutover.
6. **Fixture coverage audit**: current 10 YAML fixtures lack decision, aggregator, wait, loop diversity; recommend backfilling test harnesses or designing new ones for Compiler B unit tests.

See `.cronos/pipeline/sg5-retarget-harnessexecutor-onto-the-ru/request.md` for full spec; references span executor.py (1440 LOC), model.py (225 LOC), run_state.py (200 LOC), and packages/delivery-workflow/ core contracts.
