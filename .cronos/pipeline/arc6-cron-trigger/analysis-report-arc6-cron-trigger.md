---
cc_version: '1.0'
agent: pipeline-analyst
slug: arc6-cron-trigger
phase: analysis
status: done
confidence: 0.92
inputs_used:
- memory:project_architecture_key_modules
- memory:project_pipeline_analyst_agent
- memory:project_arc6_board_setup
- .cronos/pipeline/arc6-cron-trigger/scout-report-arc6-cron-trigger.md
- backend/app/main.py
- backend/app/harnesses/model.py
- backend/app/harnesses/run_index.py
- backend/pyproject.toml
- backend/app/pipeline/schemas/analysis.schema.yaml
outputs_produced:
- .cronos/pipeline/arc6-cron-trigger/analysis-report-arc6-cron-trigger.md
blockers: []
next_consumer: design
request: "Add a cron scheduler: one `asyncio.create_task(cron_loop, …)` in main.py\
  \ `lifespan`\nalongside the existing `watcher`/`archiver`/`memory_pruner` loops.\n\
  \n- Re-read the canonical harness list each tick (no per-harness timers; no\n  double-registration\
  \ on `watch_spaces_dir` reload). A `cron` Trigger carries its\n  expression in `data`.\n\
  - **Overlap guard:** skip a tick if the harness already has an `active` run (a set\
  \ check;\n  single-process asyncio, no lock).\n- Parse cron expr + timezone correctly.\
  \ Missed ticks across restart are not back-filled —\n  document this.\n\nAcceptance:\
  \ a cron Trigger fires at the scheduled time (shortened interval in tests);\na tick\
  \ during an active run is skipped."
has_ui: false
coverage_summary:
  searched:
  - backend/app/main.py (lifespan context manager, lines 251-365)
  - backend/app/harnesses/model.py (NodeType enum, HarnessNode.data)
  - backend/app/harnesses/run_index.py (read_index, RunSummary.status)
  - backend/pyproject.toml (dependencies — no cron library present)
  - backend/app/pipeline/schemas/analysis.schema.yaml (per-class schema)
  - .cronos/pipeline/arc6-cron-trigger/scout-report-arc6-cron-trigger.md
  excluded:
  - 'frontend/: pure backend feature; has_ui=false'
  - 'backend/app/harnesses/executor.py: execution logic is design-phase concern, not
    a requirement boundary'
  - 'backend/tests/: test strategy captured in requirements, not examined here'
  strategies:
  - memory_retrieval
  - read_targeted
traceability:
- requirement_id: R1
  statement: A `cron_loop` coroutine is registered as an `asyncio.create_task()` in
    the `lifespan` context manager in `main.py`, alongside the existing `watcher`,
    `archiver`, and `memory_pruner` tasks, and is shut down cleanly via the shared
    `stop_event`.
  acceptance_criteria:
  - Given the application starts, when lifespan startup completes, then a task named
    `cron` exists in the running asyncio event loop.
  - Given the application shuts down, when `stop_event.set()` is called, then the
    cron_loop terminates within the 5-second graceful-shutdown timeout used by sibling
    loops.
  - The cron_loop signature accepts harness_store, space_store, spaces_dir, interval_seconds,
    and stop_event parameters (matching the pattern of sibling loops in main.py).
  verifying_phase: test
  confidence: 0.95
- requirement_id: R2
  statement: On every tick, the cron_loop re-reads the canonical harness list from
    HarnessStore for each active space rather than maintaining per-harness state,
    so harness additions, edits, and deletions made between ticks are picked up without
    a restart.
  acceptance_criteria:
  - Given a harness with a cron trigger is added while the loop is running, when the
    next tick fires, then the new harness is evaluated.
  - Given watch_spaces_dir reloads harness definitions, when the cron_loop ticks,
    then no duplicate asyncio tasks or per-harness timers are created.
  - The cron_loop stores no per-harness asyncio.Task references between ticks.
  verifying_phase: test
  confidence: 0.93
- requirement_id: R3
  statement: A HarnessNode with type='trigger' carries its cron schedule in data['expression']
    (standard 5-field POSIX cron syntax) and optionally data['timezone'] (canonical
    IANA name, defaulting to 'UTC').
  acceptance_criteria:
  - 'Given a trigger node with data={''expression'': ''0 9 * * *'', ''timezone'':
    ''America/New_York''}, when the cron_loop evaluates it, then expression and timezone
    parse without error.'
  - 'Given a trigger node with data={''expression'': ''*/5 * * * *''} (no timezone
    key), when evaluated, then UTC is used as default.'
  - Given a trigger node with a malformed expression, when evaluated, then the loop
    logs a warning and skips that trigger without crashing.
  verifying_phase: test
  confidence: 0.9
- requirement_id: R4
  statement: Before firing a harness run, the cron_loop checks whether the harness
    already has a run with status='running' in its per-harness run index; if so, the
    current tick is skipped for that harness (overlap guard).
  acceptance_criteria:
  - Given a run index pre-seeded with a status='running' entry for a harness, when
    a cron tick fires for that harness, then no new run is created.
  - Given a harness whose run index has no status='running' entry, when a cron tick
    fires, then a new run is created.
  - The overlap check is a scan of run_index.read_index() output with no asyncio lock
    (single-process asyncio; no race condition).
  verifying_phase: test
  confidence: 0.95
- requirement_id: R5
  statement: Cron expressions are parsed using croniter (MIT) and timezones resolved
    using python-dateutil; both packages are added as runtime dependencies in backend/pyproject.toml.
  acceptance_criteria:
  - After the change, `pip install -e .` in the backend installs croniter and python-dateutil
    without extra steps.
  - The cron_loop correctly fires a `*/1 * * * *` expression within 60 seconds of
    the scheduled minute boundary.
  - An unknown IANA timezone name produces a log warning and falls back to UTC rather
    than raising an exception.
  verifying_phase: test
  confidence: 0.92
- requirement_id: R6
  statement: Missed ticks that would have fired while the server was offline are not
    back-filled on restart; the cron_loop evaluates only the current time on each
    tick and makes no attempt to catch up to the past.
  acceptance_criteria:
  - Given the server restarts after a 2-hour outage and a harness has a cron expression
    that would have fired 3 times during the outage, when the server starts, then
    no retroactive runs are created.
  - A code comment in the cron_loop implementation explicitly documents the no-backfill
    design decision.
  verifying_phase: review
  confidence: 0.95
- requirement_id: R7
  statement: A pytest test file (e.g. backend/tests/test_cron_loop.py) verifies that
    a cron trigger fires a harness run at the scheduled time using a shortened poll
    interval.
  acceptance_criteria:
  - Given a harness with a cron trigger, when the test uses a sub-second or mocked
    interval, then run_index.read_index() shows a new run entry within the test timeout.
  - The test passes in under 10 seconds without real wall-clock waiting.
  verifying_phase: test
  confidence: 0.88
- requirement_id: R8
  statement: 'A pytest test verifies the overlap guard: when a harness already has
    an active run (status=''running''), a subsequent cron tick does not enqueue a
    second run.'
  acceptance_criteria:
  - Given a run index pre-seeded with a status='running' entry for a harness, when
    the cron_loop ticks, then read_index() still contains exactly one status='running'
    entry (no new run appended).
  - The test is deterministic and does not rely on real-time scheduling.
  verifying_phase: test
  confidence: 0.92
metrics:
  tool_calls: 9
  files_read: 6
  memory_hits: 3
---

## Summary

The feature adds a `cron_loop` background task to `main.py`'s `lifespan`, following the existing `asyncio.create_task` pattern used by `watcher`, `archiver`, and `memory_pruner`. On each poll tick the loop re-reads all harnesses from `HarnessStore` (stateless — no per-harness timer registration), finds `trigger` nodes whose `data['expression']` matches the current time, skips any harness with a `status='running'` entry in its run index (overlap guard), and enqueues a new harness run for the rest. Missed ticks across a restart are explicitly not back-filled. Two new runtime dependencies (`croniter`, `python-dateutil`) are required; all logic is backend-only (`has_ui=false`).

## Scope

### In scope
- `backend/app/main.py` — add `cron_loop` coroutine and `asyncio.create_task(cron_loop, ...)` in `lifespan`
- `backend/app/harnesses/cron.py` (new) — `cron_loop` implementation: per-tick harness scan, cron expression evaluation, overlap guard, run enqueueing
- `backend/app/harnesses/model.py` — document `trigger` node `data` schema (`expression`, `timezone`) in the module docstring
- `backend/pyproject.toml` — add `croniter` and `python-dateutil` to runtime dependencies
- `backend/tests/test_cron_loop.py` (new) — unit/integration tests for R7 and R8

### Out of scope
- Frontend UI for creating or editing cron trigger nodes (no UI changes required by this request)
- Distributed/multi-process lock mechanisms (single-process asyncio model; overlap guard is a simple status check)
- Cron expression validation at harness-save time (validator.py schema enforcement is a separate concern)
- Back-filling missed ticks (explicitly excluded by the request)
- Quartz-style 6- or 7-field cron expressions (POSIX 5-field only)

### Deferred
- Per-trigger enable/disable flag (`data['enabled']`) — useful but not mentioned in the request
- Persistent last-fire timestamp per trigger (would support deduplication across restarts without back-fill)
- API endpoint to inspect cron trigger next-fire times
- Alerting or notification on cron trigger failures

## Requirements

| R# | One-line summary |
|----|------------------|
| R1 | `cron_loop` registered in `main.py` lifespan alongside existing background tasks |
| R2 | Each tick re-reads canonical harness list (stateless, no per-harness timer) |
| R3 | Cron trigger node carries `expression` and optional `timezone` in `data` dict |
| R4 | Overlap guard skips tick if harness already has `status='running'` run |
| R5 | `croniter` + `python-dateutil` added as runtime deps; timezone fallback to UTC |
| R6 | Missed ticks across restart are not back-filled (documented in code) |
| R7 | Test: cron trigger fires at scheduled time with shortened poll interval |
| R8 | Test: tick during active run is skipped (overlap guard verified) |

## Acceptance criteria

| R# | Acceptance criteria |
|----|---------------------|
| R1 | App starts → task named `cron` exists in asyncio event loop; shutdown → terminates within 5s via stop_event |
| R2 | Harness added at runtime picked up next tick; no duplicate tasks on watch_spaces_dir reload |
| R3 | `expression`+`timezone` parsed from node data; malformed expression logs warning, skips, does not crash |
| R4 | Harness with `status='running'` run not re-enqueued; harness with no running run is enqueued |
| R5 | `croniter`+`python-dateutil` in pyproject.toml; unknown timezone falls back to UTC with warning |
| R6 | No retroactive runs after restart outage; no-backfill decision documented in code comment |
| R7 | Pytest test fires run at scheduled time using shortened interval, completes in <10s |
| R8 | Pytest test confirms overlap guard: single active run not duplicated by subsequent tick |

## Findings

### F1 — Lifespan task pattern

`backend/app/main.py` lines 304–338 confirm the exact pattern `cron_loop` must follow:
- `asyncio.create_task(loop_func(..., stop_event), name="...")` at startup
- Loop body: `while not stop_event.is_set(): ... try: await asyncio.wait_for(stop_event.wait(), timeout=interval) except asyncio.TimeoutError: pass`
- Graceful shutdown: `stop_event.set()` + `asyncio.wait_for(task, timeout=5.0)` + cancel if timeout

R1 maps directly to this pattern.

### F2 — Trigger node data schema (underdefined)

`backend/app/harnesses/model.py` defines `HarnessNode.data: dict[str, Any]` as a free-form dict. No mandatory fields are currently documented for `type='trigger'` nodes. The analysis adds the convention: `expression` (required, 5-field POSIX cron), `timezone` (optional, IANA name, default UTC). A code-level docstring is the minimum enforcement; formal schema validation in `validator.py` is deferred.

### F3 — Overlap guard via run_index

`backend/app/harnesses/run_index.py` confirms `read_index(space_dir, harness_id)` returns a `list[RunSummary]` where each entry has a `status` field with values `'running'`, `'done'`, `'failed'`, `'cancelled'`. The overlap guard is a linear scan for `status == 'running'`. No asyncio lock is needed (single-process model). The design agent may optimize to an in-memory set if needed.

### F4 — Missing cron dependency

`backend/pyproject.toml` lists no cron-related packages. `croniter` (MIT) and `python-dateutil` (BSD) must be added. `python-dateutil` is likely already a transitive dep of other packages but must be declared explicitly to ensure availability for timezone resolution.

### F5 — No-backfill is by design

The request text explicitly states "Missed ticks across restart are not back-filled — document this." This is a hard requirement (R6), not an open question. The cron_loop must evaluate only the current time; no timestamp persistence is needed.

### F6 — Run enqueueing path

The existing harness-run trigger endpoint (`backend/app/api/harnesses.py` lines 255–322) creates a Cronos task and enqueues it to the worker. The cron_loop must replicate or call a shared helper with the same semantics. Extracting a shared helper is the preferred design (avoids HTTP self-calls). This is a design-phase decision, not a requirement.

## Traceability

| R# | Verifying phase | Request text (verbatim) |
|----|-----------------|-------------------------|
| R1 | test | "one `asyncio.create_task(cron_loop, …)` in main.py `lifespan` alongside the existing `watcher`/`archiver`/`memory_pruner` loops" |
| R2 | test | "Re-read the canonical harness list each tick (no per-harness timers; no double-registration on `watch_spaces_dir` reload)" |
| R3 | test | "A `cron` Trigger carries its expression in `data`" |
| R4 | test | "Overlap guard: skip a tick if the harness already has an `active` run (a set check; single-process asyncio, no lock)" |
| R5 | test | "Parse cron expr + timezone correctly" |
| R6 | review | "Missed ticks across restart are not back-filled — document this" |
| R7 | test | "Acceptance: a cron Trigger fires at the scheduled time (shortened interval in tests)" |
| R8 | test | "a tick during an active run is skipped" |

## Assumptions

- `has_ui=false` rationale: the request specifies only backend asyncio and harness-execution logic; no screen, form, or visual state is implied.
- The cron_loop will live in a new file `backend/app/harnesses/cron.py` and be imported into `main.py`; this avoids growing `main.py` further. The design agent may place it elsewhere.
- The overlap guard uses `run_index.read_index()` directly (I/O on each tick) rather than an in-memory set. This is acceptable at typical harness counts; the design agent may optimize with in-memory caching.
- Harnesses are identified by name (unique per space per `HarnessStore`); `(space_dir, harness_name)` is the composite key used by the overlap guard.
- `croniter` is MIT-licensed with no conflicting transitive dependencies. `python-dateutil` is a safe explicit addition (likely already a transitive dep).
- Standard 5-field POSIX cron syntax (`minute hour day month weekday`) only. Second-level precision and Quartz 6-field syntax are out of scope.
- The poll interval is configurable via `CRONOS_CRON_INTERVAL_SECONDS` env var (default 60 seconds), following the pattern of `CRONOS_MEMORY_PRUNE_INTERVAL` in main.py.
- Test mode uses a shortened interval passed directly to the loop's `interval_seconds` parameter — no global flags or cron library monkey-patching.
- Scout report `status=done`, `confidence=0.92`; this analysis inherits that ceiling.

## Open questions

None. The request text, scout findings, and codebase evidence are sufficient to define all eight requirements without ambiguity.

## Next consumer brief

The **design agent** should read `traceability[]` as the primary requirements source and `## Scope` for hard boundaries.

Key design decisions to resolve:

1. **Module placement**: confirm `cron_loop` in `backend/app/harnesses/cron.py` vs. inline in `main.py`; set `scope_files` accordingly.
2. **Trigger data schema enforcement**: decide whether to add a validator rule in `harnesses/validator.py` or handle schema errors only at runtime (log-and-skip, per R3 AC).
3. **Run enqueueing path**: determine whether `cron_loop` calls a shared helper extracted from `api/harnesses.py:255–322` or replicates the minimal task-creation + worker-enqueue sequence directly.
4. **Overlap guard I/O vs. cache**: R4 specifies a `read_index()` call per harness per tick; design agent may optimize with an in-memory active-run set updated by run-status change hooks.
5. **Poll interval env var**: confirm `CRONOS_CRON_INTERVAL_SECONDS` default=60 and that tests shorten it via the `interval_seconds` parameter.

Unresolved blockers: none. `has_ui=false` confirmed; all 8 requirements map to `test` (R1–R5, R7–R8) or `review` (R6) verification phases.
