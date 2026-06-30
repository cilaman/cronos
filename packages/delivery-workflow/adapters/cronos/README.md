# Cronos Adapter — ExecutorInterface Implementation

The Cronos adapter implements the 6-operation `ExecutorInterface` for the Cronos task-management backend. This adapter is the portability seam that allows the delivery/v1 portable core to execute on Cronos without tight coupling.

**Location:** `packages/delivery-workflow/adapters/cronos/`

**Status:** Delivered as G6.1; end-to-end SDLC milestone (G6.2) verified.

## Overview

The adapter translates the portable `ExecutorInterface` into concrete Cronos backend operations:

| Portable Op | Cronos Implementation | Maps To |
|---|---|---|
| `dispatchAgent` | `CronosAdapter.dispatchAgent()` async | TaskStore: create child task, poll state, load trace, parse delivery_status |
| `runGate` | `CronosAdapter.runGate()` | app.pipeline.gate: run contract checks + outcome re-execution |
| `evalCondition` | `CronosAdapter.evalCondition()` | app.harnesses.decision: evaluate conditional edges |
| `state.read/write` | `CronosStateOps` | lib/state/StateStore + EventLog: atomic state.json + events.jsonl |
| `telemetry.emit` | `CronosTelemetryOps` | lib/telemetry/TelemetrySink: accumulate tokens/USD with ceiling |
| `escalate` | `CronosAdapter.escalate()` async | TaskStore: park tracking task → WAITING + waiting_question |

## Design Principles

- **Single module** (`adapter.py`): All app.* imports are lazy (inside methods) so importing the bundle core never pulls in the Cronos backend.
- **Async dispatch, sync others**: `dispatchAgent` is `async def` for the poll loop; other ops are sync.
- **Atomic state**: `state.write()` uses read-modify-write with `StateStore` + append-only `EventLog`.
- **Budget enforcement**: `TelemetrySink` raises `BudgetExceededSignal` on ceiling breach; `escalate` parks the run.
- **Delivery status fallback**: If trace parsing fails, scan pipeline artifacts for trailing `delivery_status` fence.

## Module: `CronosAdapter`

```python
class CronosAdapter(ExecutorInterface):
    def __init__(
        self,
        store: app.storage.TaskStore,          # Cronos task CRUD
        trace_store: app.trace_store.TraceStore, # Run trace persistence
        space_id: str,                         # Cronos space for task creation
        run_dir: Path,                         # Workflow run directory (state.json + events.jsonl)
        tracking_task_id: str | None = None,  # Optional task for escalation
        usd_ceiling: float = 0.0,              # Budget ceiling (0.0 = disabled)
        token_cost_usd: float = 0.0,           # Per-token rate for telemetry
        poll_interval: float = 2.0,            # Poll interval (seconds)
        timeout: float = 300.0,                # Max wait for child task (seconds)
    )
```

Internally wires:
- `self.state: StateOps` → `CronosStateOps(_state_store, _event_log)`
- `self.telemetry: TelemetryOps` → `CronosTelemetryOps(_sink)`

## Operation Details

### 1. dispatchAgent — Async Child Task Orchestration

```python
async def dispatchAgent(self, agent_ref: str, inputs: dict[str, Any]) -> AgentResult
```

**Flow:**
1. Build brief from `agent_ref` + artifact paths in inputs
2. Create child agent-task via `store.create()` (title: `[delivery] {agent_ref}`)
3. Transition parent goal to ACTIVE (if in BACKLOG)
4. Poll `store.get(child_id)` every `poll_interval` seconds until DONE/WAITING/ARCHIVED
5. On timeout: escalate + raise `TimeoutError`
6. On DONE: load trace from trace_store, parse `delivery_status`, return `AgentResult`
7. On WAITING: return `AgentResult(status="blocked", open_questions=[waiting_question])`

**Telemetry:** Sums per-turn tokens from trace; calculates USD via `token_cost_usd` rate.

**Delivery Status Parsing (DD-05):**
1. Primary: parse `delivery_status` fence from trace's `final_text_snippet` (500 chars)
2. Fallback: scan newest `*.md` file in `run_dir` (catches clipped long traces)
3. Fallback: return `AgentResult(status="failed")` with error question

**Result fields:**
```python
class AgentResult:
    status: str                  # "done" | "blocked" | "failed"
    artifact_paths: list[str]    # Produced deliverables
    produces: str                # Semantic label (e.g., "design-report")
    fields: dict[str, str]       # delivery_status metadata (phase, version, etc.)
    open_questions: list[str]    # Blockers or errors
    telemetry: TelemetryData     # tokens, usd, seconds
```

### 2. runGate — Artifact Verification

```python
def runGate(self, gate: dict[str, Any], artifact_paths: list[str]) -> GateResult
```

**Flow:**
1. Delegate to `app.pipeline.gate.runGate()` with gate config + artifact paths
2. Map Cronos result type to portable `GateResult`
3. Write gate outcome to `state.json` (node status + gate result)

**Result fields:**
```python
class GateResult:
    decision: str                # "proceed" | "fail" | "escalate"
    errors: list[str]            # Validation errors
    evidence: dict[str, Any]     # Check results (normalized, schema-validated, etc.)
```

### 3. evalCondition — Conditional Edge Evaluation

```python
def evalCondition(self, expr: str, scope: dict[str, Any]) -> bool
```

**Flow:**
1. Coerce all scope values to strings (for whitelisted grammar)
2. Delegate to `lib.conditions.eval_condition(expr, flat_scope)`
3. Return boolean result

**Grammar (from harnesses.decision):**
- Dotted path identifiers: `foo.bar`
- Hyphenated identifiers: `foo-bar`
- Operators: `==`, `!=`, `in`
- Conjunction: `&&`
- Parentheses for grouping

**Example:**
```python
expr = "exit_reason == 'SUCCESS' && has_ui == 'true'"
scope = {"exit_reason": "SUCCESS", "has_ui": "true", ...}
result = adapter.evalCondition(expr, scope)  # → True
```

### 4. state.read / state.write — Atomic State Management

Implemented by `CronosStateOps`:

```python
class CronosStateOps(StateOps):
    def read(self) -> WorkflowState
    def write(self, patch: dict[str, Any]) -> None
```

**read():** Returns `WorkflowState` loaded from `state.json` (via `StateStore`).

**write(patch):** Atomically applies a patch:
- Top-level updates (`"status"`: "blocked", etc.)
- Per-node updates (`"nodes": {"node_id": {"status": "done", "artifact_paths": [...], ...}}`)
- Creates new nodes if absent; updates existing nodes with change detection
- Appends `node_transition` events to `events.jsonl` on status change

**State shape (from `lib/state`):**
```python
@dataclass
class WorkflowState:
    spec: str | dict                        # The workflow spec
    run_id: str                             # Unique run ID
    status: str                             # "pending" | "running" | "done" | "failed" | "blocked"
    budget: BudgetState                     # USD ceiling + cumulative spend
    nodes: dict[str, NodeState]             # Per-node status, attempts, artifacts, gate results

@dataclass
class NodeState:
    status: str                             # "pending" | "running" | "done" | "failed" | "needs_fix"
    attempt: int                            # Retry count (for loop convergence)
    artifact_paths: list[str]               # Produced deliverables
    gate: dict[str, Any] | None            # Gate verification result
```

### 5. telemetry.emit — Token and Cost Tracking

Implemented by `CronosTelemetryOps`:

```python
class CronosTelemetryOps(TelemetryOps):
    def emit(self, node_id: str, data: dict[str, float]) -> None
    @property
    def usd_spent(self) -> float
```

**emit(node_id, data):**
- Records per-node telemetry: `{"tokens": N, "usd": 0.XX, "seconds": T}`
- Accumulates in `TelemetrySink`; persists to `state.json` via `StateStore`
- Raises `BudgetExceededSignal` if `usd_spent >= usd_ceiling`

**usd_spent:** Returns cumulative USD spent across all nodes (cached from sink).

**Token cost calculation (from dispatchAgent):**
```python
tokens = sum(turn.input_tokens + turn.output_tokens for turn in trace.turns)
usd = tokens * token_cost_usd
```

### 6. escalate — Blocking Escalation (Human Intervention)

```python
def escalate(self, node_id: str, reason: str) -> None
async def _escalate_async(self, node_id: str, reason: str)
```

**Flow:**
1. Set `state.status = "blocked"`
2. Transition tracking task → WAITING (via `store.finalize_run()`)
3. Set `waiting_question` to the reason string
4. Idempotent: no-op if task already WAITING

**Usage:**
- Called by the executor when `BudgetExceededSignal` is raised
- Called by `dispatchAgent` timeout handler
- Routes the run to human review on the Cronos board (task moves to WAITING lane)

## Integration Points

### State Management (G6.1 I1)

**`CronosStateOps` depends on:**
- `lib.state.store.StateStore` — atomic read/write to `state.json`
- `lib.state.events.EventLog` — append-only `events.jsonl` for audit trail

**Atomic write guarantees:**
- State is read from disk, patched in memory, written back atomically (tempfile + `os.replace`)
- Node transitions are appended to events log with type + status

### Gate Engine (G6.1 I2)

**`runGate()` delegates to:**
- `app.pipeline.gate.runGate()` — the Cronos gate engine (G2)
- Maps Cronos `GateResult` type to portable `GateResult` type
- Writes outcome to state (node status + gate metadata)

### Decision Logic (G6.1 I3)

**`evalCondition()` delegates to:**
- `lib.conditions.eval_condition()` — portable condition evaluator with `||` (OR-of-ANDs) support
- Supports dotted paths, hyphenated identifiers, `==` / `!=` / `in`, `&&`, parentheses

### Telemetry (G6.1 I4)

**`CronosTelemetryOps` depends on:**
- `lib.telemetry.sink.TelemetrySink` — accumulates tokens/USD with optional state_store persistence
- Optional `StateStore` integration for atomic budget updates to `state.json`
- Raises `BudgetExceededSignal` on ceiling breach → routes to `escalate()`

### Task Dispatch (G6.1 I5)

**`dispatchAgent()` depends on:**
- `app.storage.TaskStore` — task CRUD + state transitions
- `app.trace_store.TraceStore` — load run traces
- `lib.delivery_status.parse_delivery_status()` — parse artifact fences
- Task polling loop (every `poll_interval` seconds)

### Escalation (G6.1 I6)

**`escalate()` depends on:**
- `app.storage.TaskStore.finalize_run()` — transition task to WAITING
- Sets `waiting_question` field for human review
- Updates workflow state to "blocked"

## End-to-End SDLC Example (G6.2)

The adapter is verified by a synthetic workflow (§12 of spec) that exercises all 6 ops:

**Workflow:**
```yaml
nodes:
  scout:
    agent: pipeline-scout
    on_success: analyst
  analyst:
    agent: pipeline-analyst
    on_success: design_gate
  design_gate:
    gate: { schema: analysis-report }
    on_proceed: architect
    on_fail: architect   # Route failures to architect for re-think
  architect:
    agent: pipeline-architect
    condition: exit_reason == 'SUCCESS'
  impl:
    agent: pipeline-implementor
    loop: { until: attempt >= 3 }  # Retry loop
  ...
```

**Test coverage (test_cronos_adapter_e2e_sdlc.py):**
- 60+ tests across 7 test files (condition, dispatch, gate, escalate, state, telemetry, e2e)
- Monkeypatched `store` + `trace_store` for deterministic replay
- Verifies gate routing, loop convergence, budget enforcement, escalation

**State reconstruction:**
- `state.json` captures all node statuses and gate results
- `events.jsonl` records all node transitions for replay
- Budget tracking: cumulative tokens/USD per node

## Error Handling

**dispatchAgent:**
- Task disappears → return `AgentResult(status="failed")`
- Timeout → escalate + raise `TimeoutError`
- No delivery_status → return `AgentResult(status="failed")`

**evalCondition:**
- Syntax error in expression → propagates from `eval_condition()`
- Missing scope variable → false (safe default per grammar)

**escalate:**
- No tracking_task_id → log warning, state marked blocked only
- Task already WAITING → idempotent no-op
- Store error → logged, escalation may be incomplete

**runGate:**
- Gate engine errors → mapped to `GateResult(decision="escalate")`
- Missing gate config → handled by gate engine

## Import Boundary

The adapter is explicitly **allowed** to import `app.*` (Cronos internals). This is declared in:
- `.importlinter`: `cronos/` subtree is excluded from the "no app.*" rule
- `__init__.py` comment and docstring

All `app.*` imports in `adapter.py` are **lazy** (inside methods), so importing the bundle core never transitively pulls in Cronos. This enables the portable core to be adopted by any runtime.

## Files

- `adapter.py` — Main implementation (480 LOC)
- `fixtures/sdlc_ping.yaml` — Synthetic test workflow (§12)
- `__init__.py` — Module marker + docstring

## Testing

**Test files (backend/tests/):**
- `test_cronos_adapter_condition.py` — evalCondition with dotted/hyphenated identifiers
- `test_cronos_adapter_dispatch.py` — dispatchAgent flow + telemetry
- `test_cronos_adapter_gate.py` — runGate result mapping
- `test_cronos_adapter_escalate.py` — escalate idempotence + WAITING transition
- `test_cronos_adapter_state_telemetry.py` — CronosStateOps + CronosTelemetryOps
- `test_cronos_adapter_integration.py` — Dispatch + gate + condition chaining
- `test_cronos_adapter_e2e_sdlc.py` — Full workflow execution with loops, gates, routing

**Run:**
```bash
cd backend
pytest tests/test_cronos_adapter_*.py -v
```

## Status: Delivered

- **G6.1 — Cronos adapter** ✓ All 6 ops implemented + 60+ tests
- **G6.2 — End-to-end SDLC milestone** ✓ Verified on Cronos
- **Review verdict:** PASS (attempt1, commit 3432044)
- **Test verdict:** PASS (commit cf3a91f)

**=== delivery/v1 done on Cronos ===**
