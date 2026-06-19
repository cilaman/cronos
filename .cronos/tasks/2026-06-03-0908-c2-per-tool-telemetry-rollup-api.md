---
agent_mode: auto
agent_model: default
claude_session_id: d6051894-5210-4395-9c7d-cba00124f361
created_at: '2026-06-03T09:08:41Z'
depends_on:
- 2026-06-03-0908-c1-tag-tool-invocations-with-adopted-too
feature_key: null
feature_state: null
id: 2026-06-03-0908-c2-per-tool-telemetry-rollup-api
issue_number: null
issue_url: null
manual_order: 0
parent_id: 2026-06-03-0908-arc-5-c-evolution-tagged-traces-evolve-t
pending_messages: []
pr_url: null
priority: 3
proposed_issue_path: null
proposed_pr_path: null
realizes: null
space_id: cronos-development
state: archived
title: C2 — Per-tool telemetry rollup + API
type: task
updated_at: '2026-06-19T12:17:48Z'
waiting_question: null
---

# Brief

Extend `backend/app/stats.py` `RunStats` with `adopted_tool_uses: dict[str, AdoptedToolRunStats]` where `AdoptedToolRunStats = {calls, errors, kind}`. Tally during existing compute from `RunTrace.tool_calls` filtered on `adopted_tool_id`.

Per-tool aggregation across runs in `TaskStats` / `SpaceStats`:
- `avg_success_rate = 1 - errors/calls`
- `human_rescue_count` — runs ending in WAITING immediately after the adopted tool was the last non-error call (heuristic)

New endpoint `GET /api/spaces/{id}/tools/{kind}/{name}/telemetry?window=30d` → aggregated stats over the window (filter by `started_at`).

## Files

- Modified: `backend/app/stats.py` (add AdoptedToolRunStats, extend RunStats)
- Modified: `backend/app/api/tools.py` (add telemetry endpoint)

## Acceptance

- 3 fixture runs (2 clean, 1 error) → endpoint returns `calls=3, errors=1, avg_success_rate≈0.67`
- `window` param filters by `started_at`
- Empty history → returns zeros, no 500 error

---

## Standing rules

**Branch:** `feature/arc-5-tools`; create from `main` if missing. No branching from other bases; no merging to `main` (manual after arc lands).

**Test gate:** Invoke `test-architect`: "Update tests for this task; add coverage for new code paths (pytest + vitest); run full suites; report pass/fail." Commit only after green.

**Commit message:** `arc-5/<goal>/<n>: <summary>` — include task number in body.

**STATUS:** `STATUS: DONE` on success; `STATUS: BLOCKED` if tests can't be made green (describe blocker above).

# History

```
2026-06-03T14:14:36Z [agent]
I'll start by reading the key files to understand the current state before implementing the changes.

Now let me read the trace parser and the stats storage to understand how RunStats is computed.

Now let me find where RunStats is computed from RunTrace, and look at how the stats API endpoint works.

Let me look at the tools index and the adoption module to understand the adopted tool ID structure.

Let me look at existing tests for stats to understand patterns.

Let me look at the API tools tests and conftest.

I have a clear picture of the implementation. Let me now make the changes.

Now I have enough context. Let me implement all the changes:

Now update `worker.py` to import and compute `adopted_tool_uses`, and expand the trace computation condition:

Now add the telemetry endpoint to `tools.py`:

Now add the telemetry endpoint at the end of `tools.py`:

Now let me write the tests. First, let me check what fixtures are available and how the existing adoption tests look:

Now let me write the test files:

Now write the telemetry endpoint tests:

Now let me run the tests to see if they pass:

All 16 unit tests pass. Now let me run the telemetry API tests:

All 8 tests pass. The coverage failure is just from running a single file (total project coverage needs 60%, which is met when running the full suite). Let me now run the full test suite to verify nothing is broken:

All 1489 tests pass with 83.14% coverage. Now let me invoke the `goal-task-commit` skill to commit these changes:

The standing rules specify `feature/arc-5-tools` explicitly, and that's the current branch. I'll commit to it directly.

Committed and pushed. Now finalize the task:

## Step 1 — Verify completion

All requirements met:
- `AdoptedToolRunStats` model added with `calls`, `errors`, `kind`, `human_rescue`
- `RunStats.adopted_tool_uses` field added
- `compute_adopted_tool_uses()` tallies from `RunTrace.tool_calls` filtered on `adopted_tool_id`
- `human_rescue_count` heuristic implemented
- `GET /api/spaces/{id}/tools/{kind}/{name}/telemetry?window=Nd` endpoint added
- Acceptance criteria verified: 3-run fixture test (calls=3, errors=1, avg≈0.67), window filtering, empty history
- 24 new tests, 1489 total green, 83.14% coverage
- Committed to `feature/arc-5-tools` as `ea572b4`

## Step 3 — Handle git

Goal child — git already handled via `goal-task-commit`. Changes are on `feature/arc-5-tools` at `ea572b4`.

## Step 4 — Write memory

MEMORY[fact]: arc-5/C2 complete (commit ea572b4 on feature/arc-5-tools). Three files modified: `backend/app/stats.py` gained `AdoptedToolRunStats(calls, errors, kind, human_rescue)` model and `compute_adopted_tool_uses(tool_calls, exit_reason)` function; `RunStats` extended with `adopted_tool_uses: dict[str, AdoptedToolRunStats]` field. `backend/app/worker.py` imports `compute_adopted_tool_uses`, expands trace pre-computation condition to include `self.stats_store is not None`, and passes result to `RunStats`. `backend/app/api/tools.py` adds `GET /{space_id}/tools/{kind}/{name}/telemetry?window=Nd` endpoint aggregating calls/errors/human_rescue_count across all task runs in a space; keyed by tool name, kind-filtered. 1489 tests pass, 83.14% coverage.

STATUS: DONE
```
