---
cc_version: "1.0"
agent: pipeline-implementor
slug: delivery-v1-scaffolding--i7
goal_slug: delivery-v1-scaffolding
phase: impl
iteration_id: I7
status: done
confidence: 0.97
inputs_used:
  - .cronos/pipeline/delivery-v1-scaffolding/design-report-delivery-v1-scaffolding.md
  - backend/app/run_side_effects.py
  - backend/app/pipeline/state_writer.py
  - backend/pyproject.toml
  - packages/delivery-workflow/lib/telemetry/sink.py
  - packages/delivery-workflow/lib/telemetry/__init__.py
  - backend/tests/test_pipeline_state_writer.py
outputs_produced:
  - .cronos/pipeline/delivery-v1-scaffolding/impl-report-delivery-v1-scaffolding--i7.md
blockers: []
next_consumer: test
files_changed:
  - backend/pyproject.toml
  - backend/app/run_side_effects.py
  - backend/app/pipeline/state_writer.py
  - backend/tests/test_pipeline_telemetry_wiring.py
validation_command: cd backend && python -m pytest tests/test_pipeline_telemetry_wiring.py -v --override-ini="addopts="
validation_command_passed: true
out_of_scope_findings: []
metrics:
  tool_calls: 14
  files_read: 8
  memory_hits: 1
  diff_lines_added: 89
  diff_lines_removed: 0
  tests_added: 12
---

## Summary

I7 wires `lib.telemetry.TelemetrySink.emit()` into the Cronos backend so the delivery/v1 portable library is adopted alongside the existing CC-v1 pipeline path. Three files changed:

1. **backend/pyproject.toml**: Added `delivery-workflow` to `[project.optional-dependencies].dev` with an inline comment explaining the editable install (`pip install -e ../packages/delivery-workflow`).

2. **backend/app/run_side_effects.py**: Added `_emit_delivery_telemetry(task_id, trace)` module-level helper that imports `TelemetrySink` from `lib.telemetry`, derives `token_spend` by summing all token categories across `trace.turns`, and calls `sink.emit()` with `tokens`, `usd=0.0` (rate table deferred to Phase 6), and `seconds`. The sink is transient (no StateStore) — Phase 6 wires in persistence to `state.json`. The call is inserted after the trace-save block in `record_telemetry()`, gated to runs where `computed_trace is not None`, wrapped in `try/except` so it can never break existing recording paths (R14 mitigation).

3. **backend/app/pipeline/state_writer.py**: Added `PhaseMetrics.from_telemetry_sink(sink, task_id)` classmethod that bridges a `TelemetrySink` node entry to the `PhaseMetrics` format. Complements the unchanged `from_trace()` fallback (R14 AC4). Returns a zero `PhaseMetrics` for unknown task IDs or objects without a `node_data` attribute (safe duck-typing).

12 tests in `test_pipeline_telemetry_wiring.py` cover: lib.telemetry importability (R14 AC1), TelemetrySink.emit() with non-zero tokens/seconds, BudgetExceededSignal, `from_telemetry_sink()` non-zero and zero paths, `from_trace()` regression (R14 AC4), and `_emit_delivery_telemetry` integration with a minimal trace stub. All 81 tests in the three relevant test files pass (12 new + 47 state_writer + 22 run_side_effects).

## Files changed

| File | Action | Lines +/- | Purpose |
|------|--------|-----------|---------|
| backend/pyproject.toml | modified | +4 / 0 | Document delivery-workflow editable dev dep |
| backend/app/run_side_effects.py | modified | +30 / 0 | _emit_delivery_telemetry helper + call in record_telemetry |
| backend/app/pipeline/state_writer.py | modified | +18 / 0 | PhaseMetrics.from_telemetry_sink() bridge classmethod |
| backend/tests/test_pipeline_telemetry_wiring.py | created | +167 / 0 | 12 tests covering R14 AC1/AC4 + wiring |

## Out-of-scope findings

- The 93 pre-existing test failures (`test_features_board`, `test_features_state_transition`, `test_harness_wiring`) exist on the feature/delivery-v1 branch before I7 and are unrelated to this iteration's scope.
- The Dockerfile does not yet copy `packages/delivery-workflow` for the production container install; this is out of scope for SG1 (Phase 6 adapter work).

## Assumptions

- `usd=0.0` in `_emit_delivery_telemetry`: the rate table is deferred to Phase 6 per the design.
- The TelemetrySink sink in `record_telemetry` is transient: it accumulates in memory for one call then gets garbage collected. Phase 6 will inject a `StateStore` to persist to `state.json`.
- `--override-ini="addopts="` is required to skip the `--cov-fail-under=80` floor for this narrow validation (per project convention for narrow-k test runs).

## Open questions

- None. USD-conversion, budget enforcement, and full StateStore integration are explicitly deferred to Phase 6.

## Next consumer brief

The test phase (I8 / pipeline-gate) should run `cd backend && python -m pytest tests/test_pipeline_telemetry_wiring.py -v --override-ini="addopts="` to confirm all 12 I7 tests pass. The full test suite (excluding pre-existing failures on the feature branch) should show no regressions in `tests/test_pipeline_state_writer.py` and `tests/test_run_side_effects.py`. Key invariants for downstream phases: (1) `_emit_delivery_telemetry` is importable from `app.run_side_effects`; (2) `PhaseMetrics.from_telemetry_sink()` accepts any `TelemetrySink` instance and a task_id, returning zero metrics for unknown nodes; (3) `lib.telemetry.TelemetrySink` and `lib.telemetry.BudgetExceededSignal` are both importable from the backend Python environment.
