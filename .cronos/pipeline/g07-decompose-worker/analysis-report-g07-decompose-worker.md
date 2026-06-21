---
cc_version: '1.0'
agent: pipeline-analyst
slug: g07-decompose-worker
phase: analysis
status: done
confidence: 0.92
inputs_used:
- memory:project-g08-durable-queue-impl
- memory:project-architecture-key-modules
- .cronos/pipeline/cronos-remediation-plan/scout-report-cronos-remediation-plan.md
- .cronos/workspaces/2026-06-20-1427-create-remedy-goals/REMEDIATION-PLAN.md
- backend/app/worker.py
- backend/app/worker_pool.py
- backend/app/harnesses/executor.py
outputs_produced:
- .cronos/pipeline/g07-decompose-worker/analysis-report-g07-decompose-worker.md
blockers: []
next_consumer: design
request: 'G07: Decompose worker.py god-object (strangler extraction). Reduce the 1,966-line
  worker.py to a thin orchestration shell by extracting cohesive collaborators: RunExecutor,
  Finalizer, EventBus, HarnessBridge, RunSideEffects (each unit-tested to ≥85%). Remove
  circular-import workarounds (_WorkerProtocolAdapter, injected closure, lazy imports).
  Keep full suite green throughout. worker.py target < 800 LOC.'
has_ui: false
coverage_summary:
  searched:
  - backend/app/worker.py (lines 1–400, structure scan)
  - backend/app/worker_pool.py (full)
  - backend/app/harnesses/executor.py (lines 1–300, WorkerProtocol + HarnessExecutor)
  - .cronos/pipeline/cronos-remediation-plan/scout-report-cronos-remediation-plan.md
    (G07 findings)
  - .cronos/workspaces/2026-06-20-1427-create-remedy-goals/REMEDIATION-PLAN.md (G07
    acceptance criteria)
  excluded:
  - frontend/: backend-only refactor, no UI involved
  - backend/app/harnesses/ (other modules): executor.py is the only cross-boundary
      file in scope
  strategies:
  - memory_retrieval
  - read_targeted
traceability:
- requirement_id: R1
  statement: A new backend/app/run_executor.py module encapsulates all task/goal/feature-decompose
    execution logic extracted from worker.py (_run_task, _run_goal, _run_feature_decompose),
    and Worker delegates to it.
  acceptance_criteria:
  - Given the extraction is complete, backend/app/worker.py no longer contains _run_task,
    _run_goal, or _run_feature_decompose function bodies.
  - backend/app/run_executor.py exists and contains the extracted logic with a documented
    public interface.
  - 'Existing integration behaviour is unchanged: the full backend pytest suite passes.'
  verifying_phase: test
  confidence: 0.9
- requirement_id: R2
  statement: A new backend/app/finalizer.py module encapsulates all post-run side-effects
    and state transitions extracted from worker.py (_finalize, _finalize_child, _persist_cronos_remember_blocks,
    memory/trust nudges), and Worker delegates to it.
  acceptance_criteria:
  - Given the extraction is complete, _finalize and _finalize_child function bodies
    are absent from worker.py.
  - backend/app/finalizer.py exists and contains the extracted logic.
  - Memory/trust nudge behaviour (confidence ±0.05/±0.1) is preserved and covered
    by existing or new tests.
  verifying_phase: test
  confidence: 0.9
- requirement_id: R3
  statement: A new backend/app/event_bus.py module encapsulates all SSE pub/sub machinery
    and the run-id reverse-lookup cache extracted from worker.py (_subscribers, _space_subscribers,
    _run_buffer, _publish, _run_id_to_space_id, _rebuild_run_id_cache, register_run,
    lookup_space_id), and Worker holds an EventBus instance.
  acceptance_criteria:
  - Given the extraction is complete, _subscribers, _space_subscribers, _run_buffer,
    and _run_id_to_space_id dicts are not defined directly on the Worker class.
  - backend/app/event_bus.py exposes a public EventBus class with publish(), subscribe(),
    unsubscribe(), register_run(), and lookup_space_id() methods.
  - SSE streams (task and space) are unaffected; all SSE integration tests pass.
  verifying_phase: test
  confidence: 0.88
- requirement_id: R4
  statement: 'The circular-import boundary between worker.py and harnesses/executor.py
    is resolved: _WorkerProtocolAdapter is removed from worker.py; the harness bridge
    is relocated so that HarnessExecutor communicates via EventBus or a dedicated
    HarnessBridge without importing from worker.py.'
  acceptance_criteria:
  - _WorkerProtocolAdapter class is absent from backend/app/worker.py.
  - The injected _on_task_state_change closure and all lazy imports introduced to
    avoid circular dependencies are removed.
  - harnesses/executor.py does not import from backend/app/worker.py (verified by
    grep).
  - worker.py does not use TYPE_CHECKING guard imports solely to avoid circular imports
    with executor (the guards may remain for WorkerPool type hints).
  verifying_phase: review
  confidence: 0.85
- requirement_id: R5
  statement: A new backend/app/run_side_effects.py module encapsulates stats recording,
    trace storage, and adopted-tool telemetry side-effects extracted from worker.py,
    and Worker delegates to it.
  acceptance_criteria:
  - backend/app/run_side_effects.py exists and receives AgentResult/RunTrace to compute
    and persist RunStats and AdoptedToolRunStats.
  - StatsStore and TraceStore interactions are centralised in RunSideEffects; Worker
    no longer imports stats/trace modules directly.
  - Stats recorded per task are numerically identical before and after extraction
    (regression test or manual comparison).
  verifying_phase: test
  confidence: 0.85
- requirement_id: R6
  statement: After all extractions, backend/app/worker.py is ≤ 800 lines of code,
    containing only the queue loop (_run_forever, _run_one), Worker.__init__ wiring,
    and thin delegation calls to the extracted collaborators.
  acceptance_criteria:
  - wc -l backend/app/worker.py reports ≤ 800.
  - Worker.__init__ no longer accepts more than 8 constructor parameters (deduplication
    of injected stores into a context object is acceptable).
  - No substantial business logic (decision trees, state-machine transitions, memory
    parsing) remains inline in worker.py.
  verifying_phase: review
  confidence: 0.9
- requirement_id: R7
  statement: Each extracted module (run_executor.py, finalizer.py, event_bus.py, harness_bridge.py
    if created, run_side_effects.py) has dedicated unit tests achieving ≥ 85% line
    coverage.
  acceptance_criteria:
  - pytest --cov=app/run_executor --cov=app/finalizer --cov=app/event_bus --cov=app/run_side_effects
    reports ≥ 85% for each module individually.
  - New test files follow the naming convention test_<module>.py under backend/tests/.
  - worker.py overall coverage rises from its 71% baseline (measured after extraction).
  verifying_phase: test
  confidence: 0.88
- requirement_id: R8
  statement: The complete backend test suite remains green at every incremental extraction
    step (no phase of the strangler refactor introduces a red build).
  acceptance_criteria:
  - pytest tests/ --cov=app reports 0 failures after each individual extraction (R1
    through R5).
  - The existing --cov-fail-under=60 floor (or the raised floor from G13 if landed)
    is met throughout.
  - No import errors are introduced at any intermediate step.
  verifying_phase: test
  confidence: 0.95
metrics:
  tool_calls: 9
  files_read: 6
  memory_hits: 2
---

## Summary

G07 decomposes the 1,966-line `worker.py` god-object using strangler-fig extraction into five cohesive collaborators — `RunExecutor`, `Finalizer`, `EventBus`, `HarnessBridge`, and `RunSideEffects` — each covered at ≥ 85% and each resolving one tight coupling. The central structural fix is relocating the circular-import boundary between `worker.py` and `harnesses/executor.py`: `_WorkerProtocolAdapter` and the injected `_on_task_state_change` closure move out of `worker.py` so that the executor no longer needs to call back into the worker module. The refactor is incremental (one module at a time, suite green throughout) and backend-only with no frontend impact. The goal has a hard LOC target (≤ 800) and a measurable coverage lift from the current 71% baseline.

## Scope

### In scope
- Extract `_run_task`, `_run_goal`, `_run_feature_decompose` → `run_executor.py`
- Extract `_finalize`, `_finalize_child`, `_persist_cronos_remember_blocks`, memory/trust nudges → `finalizer.py`
- Extract SSE pub/sub machinery and run-id reverse-lookup cache → `event_bus.py`
- Remove `_WorkerProtocolAdapter` from `worker.py`; resolve circular import with `harnesses/executor.py` via bridge relocation
- Extract stats/trace/adopted-tool side-effects → `run_side_effects.py`
- Reduce `worker.py` to ≤ 800 LOC thin shell
- Unit-test every extracted module to ≥ 85% coverage
- Keep full backend test suite green at every extraction step

### Out of scope
- `worker_pool.py` structural changes (it is already thin and well-scoped)
- Frontend changes (this is a backend-only refactor)
- Behaviour changes or feature additions during extraction
- Raising the overall coverage floor (that is G13)
- Durable queue changes (that is G08, already landed; lease/heartbeat logic must be preserved, not moved)

### Deferred
- Further decomposition of `harnesses/executor.py` beyond removing the circular import
- Async event bus (current pub/sub is in-memory synchronous; upgrading to an async queue is a separate design decision)
- `WorkerPool` restructuring once `Worker` is slimmer

## Requirements

| R# | One-line summary |
|----|------------------|
| R1 | Extract task/goal/feature-decompose execution into run_executor.py |
| R2 | Extract post-run state transitions and side-effects into finalizer.py |
| R3 | Extract SSE pub/sub machinery and run-id cache into event_bus.py |
| R4 | Remove _WorkerProtocolAdapter and resolve worker↔executor circular import |
| R5 | Extract stats/trace/telemetry side-effects into run_side_effects.py |
| R6 | Reduce worker.py to ≤ 800 LOC thin orchestration shell |
| R7 | Unit-test each extracted module to ≥ 85% line coverage |
| R8 | Full backend suite stays green at every incremental extraction step |

## Acceptance criteria

Acceptance criteria for every requirement are listed in the YAML `traceability[]` array. Compact summary:

- R1 — `_run_task`, `_run_goal`, `_run_feature_decompose` absent from worker.py; `run_executor.py` exists; suite passes.
- R2 — `_finalize` and `_finalize_child` bodies absent from worker.py; `finalizer.py` exists; memory/trust nudge tests pass.
- R3 — SSE dicts not directly on Worker; `event_bus.py` exposes `EventBus` with publish/subscribe/register_run; all SSE tests pass.
- R4 — `_WorkerProtocolAdapter` absent from worker.py; no lazy imports for circular avoidance; executor does not import from worker.py (grep-verified).
- R5 — `run_side_effects.py` exists; StatsStore/TraceStore interactions centralised there; Worker no longer imports stats modules directly.
- R6 — `wc -l backend/app/worker.py` ≤ 800; no substantial business logic inline.
- R7 — ≥ 85% line coverage on each extracted module; test files under `backend/tests/test_<module>.py`; worker.py coverage rises from 71%.
- R8 — 0 failures at each incremental extraction step; no import errors.

## Traceability

| R# | Verifying phase | Statement |
|----|-----------------|-----------|
| R1 | test | Extract task/goal/feature-decompose execution into run_executor.py |
| R2 | test | Extract post-run state transitions and side-effects into finalizer.py |
| R3 | test | Extract SSE pub/sub machinery and run-id cache into event_bus.py |
| R4 | review | Remove _WorkerProtocolAdapter and resolve worker↔executor circular import |
| R5 | test | Extract stats/trace/telemetry side-effects into run_side_effects.py |
| R6 | review | Reduce worker.py to ≤ 800 LOC thin orchestration shell |
| R7 | test | Unit-test each extracted module to ≥ 85% line coverage |
| R8 | test | Full backend suite stays green at every incremental extraction step |

## Assumptions

- `has_ui: false` — G07 is a pure backend structural refactor. No frontend files are touched; no UI hotspots were identified in the scout or the remediation plan.
- G08 (durable queue) has already landed (memory:project-g08-durable-queue-impl confirms task_leases table + heartbeat + reaper are in worker.py). The lease/heartbeat logic inside `Worker.__init__` and `_run_forever` must be preserved during extraction; it is not being moved or rearchitected here.
- The five collaborator names (`RunExecutor`, `Finalizer`, `EventBus`, `HarnessBridge`, `RunSideEffects`) from the goal brief are provisional design labels, not fixed module names. The architect agent chooses final names; the analyst uses them only as cluster anchors.
- `_topo_children` (lines 205–243 in worker.py) is a pure-function utility used by `_run_goal`. It travels with `RunExecutor` or becomes a standalone utility; the implementor decides during R1.
- `resolve_tool` (lines 246–273 in worker.py) is already a dependency of `HarnessExecutor` via the `tools_resolver` callable. It may be moved or remain in worker.py depending on the harness bridge design; flagged as a design-phase decision.
- The `_on_task_state_change` injected closure (passed to Worker constructor) is the mechanism that triggers harness event dispatch from task-state changes. Resolving R4 means replacing this injection with an event-subscription model; the exact mechanism is a design decision.
- The `worker_pool.py` module is already correctly scoped (151 LOC, single responsibility) and is in scope only to the extent that its `Worker` import chain must remain importable after extraction.
- Coverage baseline of 71% for worker.py is from the scout report (sourced from the remediation plan, commit a724133). The actual current coverage should be re-measured by the implementor before starting.

## Open questions

- None. The acceptance criteria are unambiguous and the five clusters have verified code evidence in the scout report. The design agent has full latitude on module layout and the circular-import resolution mechanism.

## Next consumer brief

**Design agent should read:** `traceability[]` for all 8 requirements; `## Scope` for the hard OUT-of-scope constraints (no behaviour change, G08 heartbeat preserved, worker_pool.py untouched).

**Key design decisions to make:**
1. **Circular-import resolution for R4.** Two main options: (a) move `_WorkerProtocolAdapter` into `harnesses/executor.py` or a new `harness_bridge.py` so executor pulls from there rather than worker; (b) introduce a publish/subscribe event bus (`EventBus` from R3) that `HarnessExecutor` subscribes to, removing the need for a back-pointer entirely. Option (b) is architecturally cleaner but requires wiring the `_on_task_state_change` closure as an EventBus subscriber.
2. **Extraction order (incremental safety).** Recommended order: R3 (EventBus first — most self-contained), then R4 (HarnessBridge — resolves circular import early), then R2 (Finalizer), then R5 (RunSideEffects), then R1 (RunExecutor — largest and most coupled), then verify R6 LOC target. R8 is validated at each step.
3. **`resolve_tool` placement.** Currently in worker.py lines 246–273; used by harness executor via `tools_resolver` callable. Could move to `harness_bridge.py` or `harnesses/executor.py` without circular import risk. Flag in design if staying in worker.py keeps it above 800 LOC.
4. **Constructor simplification for R6.** `Worker.__init__` currently accepts 9 parameters. Grouping stores into a `WorkerContext` dataclass is one approach; the architect should decide whether this is within scope or deferred.
5. **Risk:** worker.py currently contains the G08 heartbeat loop inside `_run_forever`. The extraction of `_run_forever` into `RunExecutor` (R1) must carry the heartbeat/reaper wiring with it — or keep `_run_forever` in worker.py and extract only the task-execution paths. The design must be explicit about this boundary.
