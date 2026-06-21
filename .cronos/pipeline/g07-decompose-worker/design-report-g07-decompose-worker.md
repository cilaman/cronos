---
cc_version: "1.0"
agent: pipeline-architect
slug: g07-decompose-worker
phase: design
status: done
confidence: 0.9
inputs_used:
  - .cronos/pipeline/g07-decompose-worker/analysis-report-g07-decompose-worker.md
  - backend/app/worker.py
  - backend/app/harnesses/executor.py
  - backend/app/worker_pool.py
outputs_produced:
  - .cronos/pipeline/g07-decompose-worker/design-report-g07-decompose-worker.md
blockers: []
next_consumer: impl
risks:
  - description: "worker.py is deeply interconnected; naive extraction may break SSE streams or harness execution"
    severity: high
    mitigation: "Extract one module at a time, run full pytest suite after each step"
  - description: "_finalize references 12+ dependencies; extraction requires a context object"
    severity: medium
    mitigation: "Pass stores as constructor args to Finalizer rather than per-call"
  - description: "TYPE_CHECKING guards may hide real circular imports at runtime"
    severity: low
    mitigation: "Remove TYPE_CHECKING guards after extraction and verify import order"
iterations:
  - id: I1
    title: "Full strangler extraction: EventBus + RunSideEffects + HarnessBridge + Finalizer + RunExecutor"
    description: >
      Extract all five collaborators from worker.py in a single iteration using the
      strangler-fig pattern: EventBus first (most self-contained), then RunSideEffects,
      then move _WorkerProtocolAdapter to harnesses/adapter.py (resolves circular import),
      then Finalizer, then RunExecutor. Run the full test suite after each sub-step.
      Write unit tests for each new module targeting ≥85% coverage.
    scope_files:
      - backend/app/worker.py
      - backend/app/event_bus.py
      - backend/app/run_side_effects.py
      - backend/app/finalizer.py
      - backend/app/run_executor.py
      - backend/app/harnesses/executor.py
      - backend/app/harnesses/adapter.py
      - backend/tests/test_event_bus.py
      - backend/tests/test_run_side_effects.py
      - backend/tests/test_finalizer.py
      - backend/tests/test_run_executor.py
    validation_command: "cd backend && pytest tests/ --cov=app --cov-report=term-missing -x -q 2>&1 | tail -30"
    max_diff_lines: 6000
    depends_on: []
    type: refactor
metrics:
  tool_calls: 15
  files_read: 5
  memory_hits: 3
  diff_lines_added: 0
  diff_lines_removed: 0
---

## Summary

G07 decomposes the 2057-line `worker.py` god-object via strangler-fig extraction into five
cohesive collaborators, each in its own module. The central architectural fix is eliminating
`_WorkerProtocolAdapter` by moving it to `harnesses/adapter.py`, which removes the cross-module
adapter pattern and resolves the latent circular-import risk. All extractions preserve existing
behaviour; the full pytest suite must remain green throughout.

## Architecture

### Extraction order (dependency-safe)

1. **EventBus** (`backend/app/event_bus.py`) — most self-contained; owns `_run_buffer`,
   `_subscribers`, `_space_subscribers`, `_run_id_to_space_id`, and all pub/sub methods.
   Worker delegates via `self._bus = EventBus()`.

2. **RunSideEffects** (`backend/app/run_side_effects.py`) — stats/trace/memory recorder.
   Wraps `StatsStore`, `TraceStore`, and memory nudge logic extracted from `_finalize`.

3. **HarnessBridge** (`backend/app/harnesses/adapter.py`) — move `_WorkerProtocolAdapter`
   out of `worker.py`. Expose as `WorkerAdapter`. Worker creates it on demand when calling
   `__execute_harness_run_body`. Remove the `from .harnesses.executor import HarnessExecutor`
   lazy import inside that method by importing at module level (no longer circular after move).

4. **Finalizer** (`backend/app/finalizer.py`) — post-run state machine. Extracts `_finalize`,
   `_finalize_child`, `_persist_cronos_remember_blocks`. Takes a `FinalizerContext` dataclass
   containing stores, event_bus, on_task_state_change callback, space_store, pool, etc.

5. **RunExecutor** (`backend/app/run_executor.py`) — task/goal/feature execution. Extracts
   `_run_task`, `_run_goal`, `_run_feature_decompose` and their helpers. Takes a `RunContext`
   with stores, event_bus, finalizer, harness_store, space_store.

6. **worker.py** — reduced to `Worker.__init__`, `_run_forever`, `_run_one`, lifecycle methods,
   and composition. Target: ≤800 LOC.

### Module dependency graph (no cycles)

```
event_bus.py        (standalone)
run_side_effects.py (→ stats, trace, memory_store)
harnesses/adapter.py (→ event_bus, agent, notifier, models, storage)
finalizer.py        (→ event_bus, run_side_effects, storage, goal_sync, feature_sync, ...)
run_executor.py     (→ event_bus, finalizer, harnesses/adapter, agent, memory_retrieval, ...)
worker.py           (→ event_bus, run_executor, finalizer, run_side_effects)
```

## Iterations

### I1: Full extraction (single iteration)

**Scope:** All five new modules + worker.py + harnesses/adapter.py + four test files.

**Sub-steps (within I1, run tests after each):**

1. Create `event_bus.py`; update Worker to delegate pub/sub to `EventBus`.
2. Create `run_side_effects.py`; update `_finalize` to delegate stats/trace recording.
3. Move `_WorkerProtocolAdapter` to `harnesses/adapter.py` as `WorkerAdapter`;
   update `__execute_harness_run_body` to use `WorkerAdapter`.
4. Create `finalizer.py`; update Worker to delegate `_finalize` and `_finalize_child`.
5. Create `run_executor.py`; update Worker to delegate `_run_task`, `_run_goal`,
   `_run_feature_decompose`.
6. Trim worker.py to ≤800 LOC.
7. Write/update tests for each new module; verify ≥85% per-module coverage.

**Validation command:**
```bash
cd backend && pytest tests/ --cov=app --cov-report=term-missing -x -q 2>&1 | tail -30
```

## Risks

| Risk | Severity | Mitigation |
|------|----------|-----------|
| SSE stream breakage (publish/subscribe contract) | High | Test SSE tests explicitly after EventBus extraction |
| _finalize has 12+ deps; extraction creates a fat context object | Medium | Use dataclass, pass at Finalizer init |
| Circular import reappears if harnesses/adapter.py imports worker.py | Low | adapter.py uses WorkerProtocol (typing.Protocol), not Worker directly |

## Next consumer brief

The implementor agent should:
1. Read `backend/app/worker.py` fully before touching it.
2. Read `backend/app/harnesses/executor.py` lines 89–127 (WorkerProtocol definition).
3. Extract in the order specified (EventBus → RunSideEffects → adapter → Finalizer → RunExecutor).
4. After each extraction sub-step: `cd backend && pytest tests/ -x -q 2>&1 | tail -20`.
5. Write `impl-report-g07-decompose-worker--i1.md` after all sub-steps pass.
6. Self-verify with `python -m app.pipeline.verify --agent implementation --slug g07-decompose-worker--i1`.
