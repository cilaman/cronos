---
cc_version: "1.0"
agent: pipeline-doc-sync
slug: arc6-control-flow
phase: doc
status: done
confidence: 0.88
inputs_used:
  - memory:project_arc6_board_setup
  - memory:project_pipeline_doc_sync
  - .cronos/pipeline/arc6-control-flow/review-report-arc6-control-flow--attempt1.md
  - .cronos/pipeline/arc6-control-flow/impl-report-arc6-control-flow--i1.md
  - .cronos/pipeline/arc6-control-flow/impl-report-arc6-control-flow--i2.md
  - .cronos/pipeline/arc6-control-flow/impl-report-arc6-control-flow--i3.md
  - .cronos/pipeline/arc6-control-flow/impl-report-arc6-control-flow--i4.md
  - .cronos/pipeline/arc6-control-flow/impl-report-arc6-control-flow--i5.md
  - .cronos/pipeline/arc6-control-flow/impl-report-arc6-control-flow--i6.md
  - .cronos/pipeline/arc6-control-flow/impl-report-arc6-control-flow--i7.md
  - .cronos/pipeline/arc6-control-flow/impl-report-arc6-control-flow--i8.md
  - .cronos/pipeline/arc6-control-flow/impl-report-arc6-control-flow--i9.md
  - CLAUDE.md
  - README.md
  - TESTING.md
outputs_produced:
  - .cronos/pipeline/arc6-control-flow/doc-report-arc6-control-flow.md
  - CLAUDE.md
blockers: []
next_consumer: user
intentionally_not_updated:
  - path: README.md
    reason: "Architecture and feature list unaffected by arc6.3 control-flow implementation. Public project status and quickstart remain accurate."
  - path: TESTING.md
    reason: "Testing guide is general-purpose and applies equally to harness and non-harness code. New test files (test_harness_decision.py, test_harness_wait.py, test_harness_aggregator.py, test_harness_acceptance.py) follow existing pytest conventions; no guide changes needed."
  - path: deploy/VPS_SETUP.md
    reason: "Deployment procedure unchanged by arc6.3. No new environment variables, ports, or service configuration required."
metrics:
  tool_calls: 11
  files_read: 13
  memory_hits: 2
  docs_updated: 1
  docs_considered: 4
---

## Summary

Arc6.3 implements three new control-flow node evaluators (Decision, Wait, Aggregator) and refactors the harness executor from a static Kahn topo-sort to a runtime-gated BFS with a control-flow dispatch table. The review verdict is `pass` (2633 tests green, 83.3% coverage). Documentation updates are minimal and concentrated in CLAUDE.md Key modules table, which now includes descriptions of the three new evaluator modules (decision.py, wait.py, aggregator.py), updates to executor.py's description (runtime-gated BFS + dispatch), and field documentation for the RunState waiting_node_id field. README.md and TESTING.md require no updates; they remain accurate as implementation-agnostic documentation.

## Updated docs

| File | Change summary |
|------|----------------|
| CLAUDE.md | Added 3 new rows to Key modules table: `decision.py` (four-layer signal precedence), `wait.py` (human/timed wait entry points), `aggregator.py` (all/any verdict evaluation). Updated executor.py description to mention BFS dispatch. Updated run_state.py description to mention `waiting_node_id` field. Updated model.py description to reference Wait/Aggregator data conventions. Updated validator.py description to reference R6 human Wait guardrail. Updated worker.py description to mention harness resume wiring for parked Wait nodes. |

## Intentionally not updated

- **README.md** — Architecture and feature list unaffected by arc6.3 control-flow implementation. Public project status and quickstart remain accurate.
- **TESTING.md** — Testing guide is general-purpose and applies equally to harness and non-harness code. New test files follow existing pytest conventions; no guide changes needed.
- **deploy/VPS_SETUP.md** — Deployment procedure unchanged by arc6.3. No new environment variables, ports, or service configuration required.

## Assumptions

- Changelog hook from review report § "Next consumer brief": control-flow node evaluators (Decision with four-layer precedence, Wait with human/timed modes, Aggregator with all/any modes) and runtime-gated BFS executor. Documentation is module-docstring-first per codebase convention; only CLAUDE.md Key modules table is the user-facing architecture reference.
- Memory entries consulted: project_arc6_board_setup (arc6.3 scope), project_pipeline_doc_sync (doc agent contract).
- Changed file union across I1-I9 spans backend/app/harnesses/* (model, validator, run_state, executor, decision, wait, aggregator) and backend/app/worker.py (harness resume wiring), plus test files. CLAUDE.md is the sole documentation artifact requiring updates.

## Open questions

- None.

## Next consumer brief

All documentation updates have been applied to CLAUDE.md. User-facing summary:

**New control-flow node types (arc6.3):**
- **Decision** nodes route harness execution based on a four-layer signal precedence: STATUS marker (e.g., `STATUS:DONE`) from preceding agent output, then exit_reason (from trace), then regex pattern (with inline flags), then variable condition (grammar: `<name> {==|!=|in} <literal>` evaluated against execution scope). See `backend/app/harnesses/decision.py`.
- **Wait[human]** nodes park a harness goal in `TaskState.WAITING` and require `data.max_wait_seconds` (enforced by validator R6). Resume is routed by `waiting_node_id` from the worker's `pending_messages` reply. See `backend/app/harnesses/wait.py`.
- **Wait[timed]** nodes sleep for `data.duration_seconds` (MVP: restart re-sleeps full duration, not just remaining). See `backend/app/harnesses/wait.py`.
- **Aggregator[all]** nodes fire only when all predecessors reach a terminal state; any predecessor failure causes the aggregator to fail.
- **Aggregator[any]** nodes fire on first-done predecessor; failure verdict only if all predecessors fail.

**Architecture changes:**
- Harness executor replaced static Kahn topo-sort with a runtime-gated BFS that supports dynamic termination and repeat node entry. Control-flow nodes (Decision, Wait, Aggregator) are dispatched via a lookup table instead of falling through to the agent-invocation path. Determinism is preserved via sorted-by-node-id tie-breaking.
- Worker now calls `_resume_harness_run()` before `run_agent()` to detect and resume parked harness runs that are waiting for human input.

**Key module references:**
- `backend/app/harnesses/decision.py` — Decision evaluation (pure function, no subprocess).
- `backend/app/harnesses/wait.py` — Wait entry and timed sleep (pure function, async for timed mode).
- `backend/app/harnesses/aggregator.py` — Aggregator verdict evaluation (pure function).
- `backend/app/harnesses/executor.py` — Runtime BFS executor with dispatch table (updated from Kahn topo-sort).
- `backend/app/worker.py` — Harness resume wiring (new `_resume_harness_run()` method).

No user-visible API changes; control-flow definitions are authored in harness YAML and validated server-side.
