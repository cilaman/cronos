---
cc_version: '1.0'
agent: pipeline-architect
slug: delivery-v1-control-flow
phase: design
status: done
confidence: 0.86
inputs_used:
- memory:pipeline-narrow-k-coverage
- .cronos/pipeline/delivery-v1-control-flow/analysis-report-delivery-v1-control-flow.md
- docs/delivery-pipeline/delivery-v1-docs/delivery-v1-spec.md
- backend/app/harnesses/executor.py
- backend/app/harnesses/decision.py
- backend/app/harnesses/run_state.py
- backend/app/harnesses/model.py
- backend/app/harnesses/validator.py
- backend/app/memory_parser.py
outputs_produced:
- .cronos/pipeline/delivery-v1-control-flow/design-report-delivery-v1-control-flow.md
blockers: []
next_consumer: implementation
coverage_summary:
  searched:
  - backend/app/harnesses/
  - backend/app/memory_parser.py
  excluded:
  - 'frontend/: has_ui=false, no UI surface'
  - 'packages/delivery-workflow/: portable bundle untouched by G3.1-G3.3 (analyst
    scope is backend-only)'
  - 'backend/app/pipeline/: CC-v1 verifier not changed by G3'
  strategies:
  - memory_retrieval
  - read_targeted
  - grep_symbol
iterations:
- id: I1
  type: backend
  scope_files:
  - backend/app/memory_parser.py
  - backend/tests/test_memory_parser.py
  validation_command: cd backend && python -m pytest tests/test_memory_parser.py --override-ini="addopts="
    -v
  max_diff_lines: 220
  depends_on: []
- id: I2
  type: backend
  scope_files:
  - backend/app/harnesses/decision.py
  - backend/tests/test_harness_decision.py
  validation_command: cd backend && python -m pytest tests/test_harness_decision.py
    --override-ini="addopts=" -v
  max_diff_lines: 360
  depends_on: []
- id: I3
  type: data
  scope_files:
  - backend/app/harnesses/run_state.py
  - backend/tests/test_harness_run_state.py
  validation_command: cd backend && python -m pytest tests/test_harness_run_state.py
    --override-ini="addopts=" -v
  max_diff_lines: 200
  depends_on: []
- id: I4
  type: backend
  scope_files:
  - backend/app/harnesses/model.py
  - backend/app/harnesses/validator.py
  - backend/tests/test_harness_validator.py
  validation_command: cd backend && python -m pytest tests/test_harness_validator.py
    --override-ini="addopts=" -v
  max_diff_lines: 200
  depends_on: []
- id: I5
  type: backend
  scope_files:
  - backend/app/harnesses/executor.py
  - backend/tests/test_harness_executor.py
  validation_command: cd backend && python -m pytest tests/test_harness_executor.py
    --override-ini="addopts=" -v
  max_diff_lines: 260
  depends_on:
  - I1
  - I2
- id: I6
  type: backend
  scope_files:
  - backend/app/harnesses/executor.py
  - backend/tests/test_harness_executor_loop.py
  validation_command: cd backend && python -m pytest tests/test_harness_executor_loop.py
    --override-ini="addopts=" -v
  max_diff_lines: 480
  depends_on:
  - I2
  - I3
  - I4
  - I5
- id: I7
  type: backend
  scope_files:
  - backend/tests/test_harness_routing_delivery.py
  validation_command: cd backend && python -m pytest tests/test_harness_routing_delivery.py
    --override-ini="addopts=" -v
  max_diff_lines: 300
  depends_on:
  - I5
risks:
- description: 'G3.3 is the P0 routing unblock: if the loop handler (I6) or any consumer
    of the `until` condition lands before scope enrichment (I5) and the dotted-path
    `eval_condition` (I2), conditional edges keep falling through to the default edge
    and the whole control story stays dead.'
  severity: high
  mitigation: 'The DAG forces ordering: I6 `depends_on` includes I5, and I5 `depends_on`
    includes I1+I2. The reviewer must confirm I5/I7 land and routing is demonstrably
    live (R13) before I6 is gated. Order I1/I2/I5 first per the analyst''s P0 note.'
- description: NodeState gains `attempt` and `prior_finding_ids`, but `RunState.from_dict`
    reconstructs every NodeState field explicitly — an un-updated `from_dict` silently
    drops the new fields on resume, so a re-entered loop loses its attempt count and
    prior F-ids and mis-detects stall.
  severity: medium
  mitigation: I3 updates `from_dict` to read `ns.get('attempt', 0)` and `ns.get('prior_finding_ids',
    [])`; tests assert both the round-trip (R6 ac-1) and legacy-JSON-without-fields
    deserialization (R6 ac-2).
- description: '`eval_condition` splitting on the literal ` && ` corrupts an operand
    whose string literal itself contains ` && ` (e.g. `x == ''a && b''`) — analyst
    open-question 3.'
  severity: medium
  mitigation: No §12 worked-example edge needs an embedded ` && `; I2 documents the
    limitation in the `eval_condition` docstring and adds a regression test pinning
    the documented behaviour, so a future v2 quoting-aware tokenizer is a known follow-up
    rather than a silent footgun.
- description: 'Sandbox escape: a hand-authored or garbled edge condition could attempt
    `__import__`, function calls, or dunder traversal and execute arbitrary code if
    the evaluator ever delegates to `eval()`/`ast`.'
  severity: medium
  mitigation: I2 keeps a whitelist regex + boolean/literal comparison only — NO `eval`.
    Negative tests (R10 ac) assert `eval_condition("__import__('os').system('rm -rf
    /')", {})` returns False AND a WARNING is logged, never executes.
- description: The loop wrapper inside `_execute_agent_node` (I6) runs alongside the
    existing cancel-race guard and load-merge-save resume discipline; a mid-loop cancel
    or restart could double-run an attempt or lose the attempt counter.
  severity: medium
  mitigation: I6 persists `NodeState.attempt`/`prior_finding_ids` via `_maybe_save`
    after every attempt and reconciles `attempt` from the reloaded NodeState before
    re-entering; a cancel-mid-loop test asserts no extra attempt runs after cancellation.
    `on_exhaust='escalate'` routes through the run→WAITING + `waiting_question` path
    (never `done`/`failed`, R5).
metrics:
  tool_calls: 19
  files_read: 8
  memory_hits: 1
  iterations_planned: 7
---

## Summary

This design decomposes SG3's fifteen analyst requirements into seven backend-only
iterations across two workstreams, with the **G3.3 routing unblock as the P0 critical
path**. Four foundation iterations land in parallel (group 0): the `delivery_status`
parser (R14), the sandboxed dotted-path `eval_condition` (R7–R11), the `NodeState`
loop-bookkeeping fields (R6), and the `loop` model + validator pass-through (R1). The
executor then gains scope enrichment from `delivery_status` (I5, R12) — which together
with `eval_condition` makes conditional edges branch on real output (I7, R13/R15) — and
finally the convergence loop handler (I6, R2–R5: exit on `until`/stall/`max`, `recurring_findings`
+ `no_diff_progress`, `on_exhaust`→WAITING). The whole change lives in `backend/app/harnesses/`
+ `backend/app/memory_parser.py`; no bundle, frontend, or CC-v1 verifier code is touched.
The non-obvious tradeoff (risk register) is ordering: the loop must not land before routing.

## Components

### Data
- `NodeState.attempt` / `NodeState.prior_finding_ids` (`backend/app/harnesses/run_state.py`): per-node loop bookkeeping (`attempt: int = 0`, `prior_finding_ids: list[str] = []`); round-trip via `to_dict`/`from_dict`, legacy JSON tolerant (R6).
- `HarnessNode.data['loop']` convention (`backend/app/harnesses/model.py`): `{until, stall[], max, on_exhaust}`; `data` is already an open `dict`, so this documents the sub-object and the validator must pass it through (R1).

### Backend
- `parse_delivery_status_block(text) -> dict | None` (`backend/app/memory_parser.py`): recognizes ` ```delivery_status ` fences, parses JSON, tolerates missing optional fields, lowercase `status`, does NOT validate against `{DONE,WAIT,BLOCKED}` (R14).
- `eval_condition(condition, scope)` (`backend/app/harnesses/decision.py`): replaces `_eval_variable_condition` at the same `edge_matches()` call site; dotted-path `<node>.fields.<k>`/`.status`/`.decision`, hyphenated node-ids, `==`/`!=`/`in`, `&&` conjunction, unquoted `true`/`false`; rejects anything else with a WARNING (R7–R11).
- `_execute_agent_node` scope enrichment (`backend/app/harnesses/executor.py`): after a node reaches DONE, parse `delivery_status` from `trace.final_text_snippet` and populate `scope['<node>.fields.<k>']` + `scope['<node>.status']`, preserving the existing `scope[node_id] = final_text_snippet` (R12).
- `_execute_agent_node` loop handler (`backend/app/harnesses/executor.py`): outer-loop wrapper that re-runs the node, exiting on `until` (via `eval_condition`) OR a stall signal (`recurring_findings` via `prior_finding_ids`; `no_diff_progress` via `fields.diff_bytes`) OR `attempt == max`; `on_exhaust='escalate'` transitions the run goal to WAITING with a descriptive `waiting_question` (R2–R5).

## Implementation plan

| ID  | Type    | Depends on   | Scope files (abridged)                                          | Validation                                                                       |
|-----|---------|--------------|----------------------------------------------------------------|----------------------------------------------------------------------------------|
| I1  | backend | -            | memory_parser.py, tests/test_memory_parser.py                  | cd backend && python -m pytest tests/test_memory_parser.py --override-ini="addopts=" -v |
| I2  | backend | -            | harnesses/decision.py, tests/test_harness_decision.py          | cd backend && python -m pytest tests/test_harness_decision.py --override-ini="addopts=" -v |
| I3  | data    | -            | harnesses/run_state.py, tests/test_harness_run_state.py        | cd backend && python -m pytest tests/test_harness_run_state.py --override-ini="addopts=" -v |
| I4  | backend | -            | harnesses/model.py, harnesses/validator.py, tests/test_harness_validator.py | cd backend && python -m pytest tests/test_harness_validator.py --override-ini="addopts=" -v |
| I5  | backend | I1, I2       | harnesses/executor.py, tests/test_harness_executor.py          | cd backend && python -m pytest tests/test_harness_executor.py --override-ini="addopts=" -v |
| I6  | backend | I2, I3, I4, I5| harnesses/executor.py, tests/test_harness_executor_loop.py     | cd backend && python -m pytest tests/test_harness_executor_loop.py --override-ini="addopts=" -v |
| I7  | backend | I5           | tests/test_harness_routing_delivery.py                         | cd backend && python -m pytest tests/test_harness_routing_delivery.py --override-ini="addopts=" -v |

## Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| Loop/consumer lands before routing (I5/I2) → conditional edges stay dead (P0) | high | DAG forces I6←I5←{I1,I2}; reviewer confirms routing live (R13) before gating I6 |
| `NodeState.attempt`/`prior_finding_ids` dropped by un-updated `from_dict` on resume | medium | I3 updates `from_dict` defaults; round-trip + legacy-JSON tests (R6) |
| `&&` split corrupts operands with embedded ` && ` string literal | medium | Document limitation in `eval_condition` docstring + regression test; no §12 edge needs it |
| Sandbox escape via `__import__`/dunder/function call | medium | Whitelist regex, no `eval`; negative tests assert False + WARNING (R10) |
| Loop wrapper races cancel-guard / resume; lost attempt counter | medium | Persist `attempt`/`prior_finding_ids` each attempt + reconcile on reload; cancel-mid-loop test; escalate→WAITING (R5) |

## Assumptions

- Requirements are taken verbatim from the analysis report's YAML `traceability[]` (R1–R15); the analyst's recommended **outer-loop-wrapper inside `_execute_agent_node`** (Open question 1, Next-consumer-brief decision 1) is adopted over a BFS re-enqueue, to avoid disturbing cancel-race guards and resume reconciliation.
- F-ids are read from `delivery_status.fields['finding_ids']` (`list[str]`) with precedence over `fields['findings'][].id` (analyst assumption 4 / open-question 2); `parse_delivery_status_block` surfaces the raw `fields` dict and the loop handler extracts F-ids.
- Dotted-path scope keys (`"review.fields.verdict"`) coexist with flat keys (`"review"`) in `dict[str, str]` and are invisible to `interpolate.py`'s `Template.safe_substitute` (dots are not valid Template identifiers — analyst assumption 3); no NodeState/scope type change is required for enrichment.
- `no_diff_progress` is best-effort: agents not emitting `fields.diff_bytes` skip the check (analyst assumption 5 / R4 ac-3).
- Per the `pipeline-narrow-k-coverage` memory, each per-iteration `validation_command` appends `--override-ini="addopts="` so the narrow per-file run is not failed by the repo's `--cov-fail-under=80` floor; the full-suite coverage gate is enforced separately at goal-finalize.

## Open questions

- None blocking. The analyst's three open questions are resolved by the assumptions above (loop strategy = outer-wrapper; F-id source = `finding_ids` then `findings[].id`; embedded-` && ` = documented v1 limitation). No two-way-door architecture decision remains.

## Next consumer brief

Read `iterations[]`, each `scope_files`, and each `validation_command` first. The DAG is
two workstreams: routing (I1,I2 → I5 → I7) and convergence (I3,I4 + I2 → I6). **Land I1/I2/I5
before I6** — G3.3 is P0 and the loop's `until` evaluation depends on the routing primitives.
Cross-iteration invariants NOT derivable from the YAML:
- **Scope-key contract (I2 ↔ I5):** dotted keys are EXACTLY `"<node_id>.fields.<name>"`, `"<node_id>.status"`, `"<node_id>.decision"`; `eval_condition` (I2) and the executor enrichment (I5) MUST use the identical literal key format. Scope stays `dict[str, str]`.
- **Parser shape (I1 → I5/I6):** `parse_delivery_status_block` returns a dict exposing `status` and `fields`; the loop handler reads F-ids from `fields['finding_ids']` (fallback `fields['findings'][].id`) and diff size from `fields['diff_bytes']`.
- **Loop semantics (I6):** `max` is a retry backstop — `max=2` escalates on the THIRD attempt (R2 ac-3 / R5 ac-1). `recurring_findings` fires only when the current F-id set is non-empty AND equal to the prior set (R3); `no_diff_progress` fires when current `diff_bytes` is NOT strictly less than prior, and is skipped when absent (R4). `on_exhaust='escalate'` → run goal to `TaskState.WAITING` with a `waiting_question` naming node + attempt count; never `done`/`failed` (R5).
- **Backward compat (I2):** simple non-dotted identifiers must still evaluate (R7 ac-3); do not regress existing `test_harness_decision.py` cases.
