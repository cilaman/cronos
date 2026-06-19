---
agent_mode: auto
agent_model: default
claude_session_id: b1d18a05-37c2-4ca1-8dcc-27c871631c32
created_at: '2026-06-03T09:08:41Z'
depends_on:
- 2026-06-03-0908-c2-per-tool-telemetry-rollup-api
feature_key: null
feature_state: null
id: 2026-06-03-0908-c3-evolve-tools-agent-scheduled-task-pr
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
title: C3 — evolve-tools agent + scheduled task + PR flow
type: task
updated_at: '2026-06-19T12:17:48Z'
waiting_question: null
---

# Brief

New agent at `.claude/agents/evolve-tools.md` (Cronos's own, not adopted; `agent_mode: plan`). Brief: read per-tool telemetry endpoint for every adopted tool in the space; identify any with `avg_success_rate < 0.6 OR human_rescue_count >= 3` over 30d; output one structured `EVOLVE:` block per tool with revision diff + rationale.

New `backend/app/tools/evolve.py`:
- `async create_evolve_task(space_id)` — creates a `type:task` titled `Evolve adopted tools`, `agent_mode: plan`, brief = per-tool telemetry snapshot.
- `def parse_evolve_blocks(final_text) -> list[EvolveProposal]` — extracts structured `EVOLVE:` blocks.
- `async open_evolve_prs(space_id, proposals)` — per proposal: write revised file to vendored path → bump `local_sha` → set `evolved=true` → route through Arc 4 `autopilot_pr.run_post_done_flow` helpers via a callable `commit_and_open_pr(worktree, branch, title, body)`. Branch: `cronos/evolve/<kind>-<name>-<timestamp>`. PR title: `evolve: {kind}/{name}` with rationale in body.

Scheduling: extend A4 periodic task — additionally create `evolve-tools` tasks **weekly per autopilot-enabled space** (gate: at least one adopted tool with >10 runs in the window).

## Files

- New: `backend/app/tools/evolve.py`
- New: `.claude/agents/evolve-tools.md`
- Modified: `backend/app/api/discovery.py` (extend periodic to schedule evolve-tools tasks)
- Modified: `backend/app/autopilot_pr.py` (refactor commit→PR step into callable `commit_and_open_pr`)

## Acceptance

- Fixture telemetry with one low-success skill → `create_evolve_task` produces a task with correct brief
- Mocked agent emits an `EVOLVE:` block → `open_evolve_prs` writes file, bumps `local_sha`, sets `evolved=true`, returns PR URL (`gh` mocked)
- Weekly scheduler fires only for autopilot-enabled spaces with >10 runs

---

## Standing rules

**Branch:** `feature/arc-5-tools`; create from `main` if missing. No branching from other bases; no merging to `main` (manual after arc lands).

**Test gate:** Invoke `test-architect`: "Update tests for this task; add coverage for new code paths (pytest + vitest); run full suites; report pass/fail." Commit only after green.

**Commit message:** `arc-5/<goal>/<n>: <summary>` — include task number in body.

**STATUS:** `STATUS: DONE` on success; `STATUS: BLOCKED` if tests can't be made green (describe blocker above).

# History

```
2026-06-03T14:32:31Z [agent]
Let me explore the relevant existing code before writing anything.

Good overview. Now let me read the actual implementation files to understand the exact code patterns.

Now I have enough context. Let me read the adoption.py to understand the `_adopt_dir` helper and the space_store.

Now let me look at the existing tests for adoption/discovery to understand test patterns:

Now let me look at a few existing test files to understand test patterns:

Let me check the test conftest to understand available fixtures:

Now I have enough context to write the implementation. Let me write all the code:

Now refactor `autopilot_pr.py` to add `commit_and_open_pr`:

Now add `_schedule_evolve_tasks` to `discovery.py`:

Now add the weekly evolve-tools loop to `main.py`:

Now wire up the `evolve_tools_loop` in the lifespan:

Now I need to fix the `SpaceStore` and `StatsStore` type hints in main.py — they're already imported but not quoted:

Good — `SpaceStore` and `StatsStore` are already imported directly. Let me fix the type hints in `evolve_tools_loop`:

Now write the agent file:

The memory note says agent files need Python file I/O via Bash. Let me use that approach:

Now write the tests:

Now run the tests to see if they pass:

The `task_store` fixture already creates `tmp_path/spaces`. I need to use `tmp_spaces_dir` in the relevant tests:

Let me check how `SpaceStore.update` works:

All 21 new tests pass. Now let me run the full test suite to check coverage:

All 1510 tests pass (21 new + 1489 existing) with 82.73% coverage, well above the 60% floor. Now let me invoke the `task-finalize` skill:

The standing rules specify `feature/arc-5-tools` for this arc. Let me check it out and commit:

Committed and pushed. Now write memory and emit STATUS:

MEMORY[fact]: arc-5/C3 complete (commit 43ef012 on feature/arc-5-tools). Four files modified + two new: `backend/app/tools/evolve.py` (EvolveProposal model, `parse_evolve_blocks`, `create_evolve_task`, `open_evolve_prs`); `.claude/agents/evolve-tools.md` (Sonnet plan-mode agent emitting `EVOLVE:` blocks); `backend/app/autopilot_pr.py` gained public `commit_and_open_pr(worktree, branch, title, body, *, space_dir)` (no-rebase fresh-branch helper); `backend/app/api/discovery.py` gained `_schedule_evolve_tasks(task_store, spaces_dir, *, space_store, stats_store, min_runs=10)` with autopilot + run-count + dedup gates; `backend/app/main.py` gained `evolve_tools_loop` (weekly, `CRONOS_EVOLVE_TOOLS_INTERVAL_HOURS` env var). 21 new tests; 1510 total pass, 82.73% coverage.

STATUS: DONE
```
