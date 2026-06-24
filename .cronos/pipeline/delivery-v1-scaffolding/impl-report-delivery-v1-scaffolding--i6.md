---
cc_version: '1.0'
agent: pipeline-implementor
slug: delivery-v1-scaffolding--i6
goal_slug: delivery-v1-scaffolding
phase: implementation
iteration_id: I6
status: done
confidence: 0.98
scope_files:
- packages/delivery-workflow/lib/telemetry/__init__.py
- packages/delivery-workflow/lib/telemetry/sink.py
- packages/delivery-workflow/tests/test_telemetry.py
files_changed:
- packages/delivery-workflow/lib/telemetry/__init__.py
- packages/delivery-workflow/lib/telemetry/sink.py
- packages/delivery-workflow/tests/test_telemetry.py
validation_command: cd packages/delivery-workflow && python -m pytest tests/test_telemetry.py -v
validation_command_passed: true
metrics:
  diff_lines_added: 120
  diff_lines_removed: 1
  test_count: 20
  tests_passing: 20
---

## Summary

Implemented `lib/telemetry` (R12/R13): `TelemetrySink` accumulates per-node telemetry and cumulative `usd_spent`; raises `BudgetExceededSignal` when `usd_ceiling` is breached. `TelemetrySink` satisfies the `TelemetryOps` runtime-checkable Protocol from `interface.py`. Optional `StateStore` integration persists per-node telemetry and cumulative `usd_spent` to `state.json` atomically after each emit.

## Changes

### `lib/telemetry/sink.py` (new)
- `BudgetExceededSignal(Exception)` — carries `usd_spent` and `usd_ceiling` as attributes; human-readable message with both values.
- `TelemetrySink` — accumulates `usd_spent` across `emit()` calls; stores per-node data (returning copies from `node_data()`); raises `BudgetExceededSignal` only when `usd_ceiling > 0.0` and cumulative spend exceeds it; optionally persists via `StateStore`.

### `lib/telemetry/__init__.py` (updated)
- Replaced placeholder comment with public exports: `TelemetrySink`, `BudgetExceededSignal`.

### `tests/test_telemetry.py` (new, 20 tests)
- R12: usd accumulation, missing-usd-key handling, multi-node cumulation, node_data copy semantics, retry overwrite.
- R13: signal raised on breach, carries correct amounts, fires after accumulation, not raised at exactly ceiling, not raised when ceiling=0.
- Protocol conformance: `isinstance(sink, TelemetryOps)`.
- StateStore integration: node telemetry persisted, budget.usd_spent persisted, unknown-node budget update, no-store path.

## Validation

```
20 passed in 0.07s
```
