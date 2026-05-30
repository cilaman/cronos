# CC-v1 pipeline — end-to-end smoke run (task 3.5)

**Date:** 2026-05-30
**Driver:** [`run_smoke.py`](./run_smoke.py)
**Result:** PASS (both scenarios)

## Scope

This smoke run exercises the same code path the `pipeline-gate` skill takes —
`python -m app.pipeline.verify --normalize --json`, then
`app.pipeline.state_writer.{update_phase, record_phase_log}` — against two
scratch spaces, one with seven valid CC-v1 artifacts and one with a deliberately
broken design artifact. It does NOT spawn real sub-agents and does NOT POST to
the Cronos board, because the Cronos worker is not available inside an agent
task; substituting hand-crafted artifacts for agent output isolates the
verify + gate + state-writer contract, which is exactly what the acceptance
criteria measure.

> Scaffold + run a trivial feature request in a scratch space. Assert: every
> artifact passes verify, the DAG advances on green, and a deliberately-broken
> artifact halts the DAG (STATUS: BLOCKED). Capture evidence in the
> pipeline-state.json + phases-log.jsonl.

## Scenario A — green path

* **Scratch space:** `smoke/green-space/`
* **Goal slug:** `smoke-csv-export-green`
* **Request:** "Add a 'Download CSV' button to the dashboard so users can export
  the currently visible task list to a CSV file."
* **Artifacts:** the seven in-repo goldens
  (`backend/app/pipeline/fixtures/golden/{research,analysis,design,implementation,test,review,doc}.md`),
  with the YAML `slug:` line and outputs_produced rewritten to the goal slug
  (and the `--i1` / `--attempt1` fan-out suffixes for impl and review).

| # | Phase            | Verify exit | Gate decision | Phase status |
|---|------------------|-------------|---------------|--------------|
| 1 | research         | 0           | proceed       | done         |
| 2 | analysis         | 0           | proceed       | done         |
| 3 | design           | 0           | proceed       | done         |
| 4 | implementation   | 0           | proceed       | done         |
| 5 | test             | 0           | proceed       | done         |
| 6 | review (attempt1)| 0           | proceed       | done         |
| 7 | doc              | 0           | proceed       | done         |

* `pipeline-state.json`: 7 phases recorded, telemetry
  `{phases_completed: 7, phases_failed: 0, phases_escalated: 0, phases_retried: 0}`.
* `phases-log.jsonl`: 7 lines, all `gate_decision=proceed`, all
  `status=done`. Timestamps strictly increasing, proving the DAG advanced in
  dependency order.
* All seven CC-v1 artifacts live under
  `smoke/green-space/.cronos/pipeline/smoke-csv-export-green/`.

## Scenario B — broken artifact halts the DAG

* **Scratch space:** `smoke/broken-space/`
* **Goal slug:** `smoke-csv-export-broken`
* **Mutation:** the design artifact's YAML header field `cc_version: '1.0'` is
  rewritten to `cc_version: '9.9'` — a value the verifier rejects via
  `_check_cc_version` (`backend/app/pipeline/verify.py:352`). This is the kind
  of mistake a buggy agent would make.

| # | Phase    | Verify exit | Gate decision | Phase status | Driver action               |
|---|----------|-------------|---------------|--------------|-----------------------------|
| 1 | research | 0           | proceed       | done         | continue                    |
| 2 | analysis | 0           | proceed       | done         | continue                    |
| 3 | design   | 1           | fail          | blocked      | **halt — no downstream run**|

* `pipeline-state.json`: exactly three phases recorded
  (`research`, `analysis`, `design`); telemetry
  `{phases_completed: 2, phases_failed: 1}`.
* `phases-log.jsonl`: exactly three lines, the third with
  `gate_decision=fail`, `status=blocked`.
* No `impl-report-*.md`, `test-report-*.md`, `review-report-*.md`, or
  `doc-report-*.md` exist under the broken pipeline dir — the DAG was halted
  before any downstream phase wrote an artifact.
* The gate's recorded `verify_result.errors[]` is
  `["cc_version='9.9' not supported by this verifier (expected '1.0')"]`,
  which is what the gate would echo before emitting `STATUS: BLOCKED`.

## Mapping to `pipeline-gate` STATUS line emission

The smoke driver records the same `gate_decision` the `pipeline-gate` skill
records, using the same `state_writer.PhaseEntry`/`PhaseVerifyResult` data
classes. The status line the skill would emit follows directly:

| Verify exit | gate_decision recorded | STATUS line emitted |
|-------------|------------------------|---------------------|
| 0           | proceed                | `STATUS: DONE`       |
| 1           | fail                   | `STATUS: BLOCKED`    |
| 2           | escalate               | `STATUS: BLOCKED`    |
| 3           | retry                  | `STATUS: BLOCKED`    |

The green run exclusively yields exit 0 / proceed (→ `STATUS: DONE`); the
broken run yields exit 1 / fail on the design gate (→ `STATUS: BLOCKED`),
which under Cronos's `parse_status` keeps the design task in `waiting` and
prevents `goal_sync.propagate_to_parent` from activating any dependent task.
That is the exact halt behaviour the brief requires.

## What was simulated vs. exercised end-to-end

* **Exercised end-to-end** (real code path):
  * `app.pipeline.verify` CLI invocation, including `--normalize`
  * `app.pipeline.state_writer.init_pipeline` / `update_phase` / `record_phase_log`
  * Atomic writes to `pipeline-state.json` and JSONL appends to `phases-log.jsonl`
  * Rolling telemetry recomputation across phases
  * Gate decision routing from verify outcome to phase status
  * Canonical artifact path resolution per class (including `--i1`, `--attempt1`)
* **Simulated** (would need the Cronos worker to exercise live):
  * Sub-agent spawning (no real scout/analyst/architect/... ran — goldens used)
  * Cronos goal/task POSTs (the scaffold's API calls would pollute the real
    board; the smoke driver calls `init_pipeline` directly instead)
  * `STATUS:`-line parsing by `agent.py::parse_status` (the gate's STATUS
    contract is exercised by the test suite, e.g. `tests/test_agent_parse_status.py`)
  * Real `PhaseMetrics.from_trace` (no upstream `RunTrace` exists — the
    driver passes a zero-valued `PhaseMetrics()`). The trace-derived metrics
    path is exercised by `tests/test_pipeline_state_writer.py`.

## Artifacts

* `smoke-result.json` — full driver output (all per-phase outcomes, both
  pipeline-state summaries, both phases-log dumps).
* `green-space/.cronos/pipeline/smoke-csv-export-green/` — 7 artifacts +
  state + log + request.
* `broken-space/.cronos/pipeline/smoke-csv-export-broken/` — 3 artifacts +
  state + log + request (design artifact is the broken one).

## Re-running the smoke

```bash
cd backend && python ../smoke/run_smoke.py
# exit code 0 iff every assertion in assert_green() + assert_broken() passes
```

`assert_green` requires: 7 phases recorded; 7 log lines; every phase's
`gate_decision == "proceed"` and `status == "done"`; every verify CLI exit
code is 0; telemetry shows `phases_completed=7, phases_failed=0`.

`assert_broken` requires: the driver loop halts after design; exactly the three
phases `{research, analysis, design}` recorded; design's `status == "blocked"`,
`gate_decision == "fail"`, and verify CLI exit code is 1.
