---
agent_mode: auto
agent_model: sonnet
claude_session_id: 3aeca6eb-c896-4ecd-adda-b9f02995d1cd
created_at: '2026-06-19T06:41:51Z'
depends_on:
- 2026-06-19-0641-architect-trust-loop
feature_key: null
feature_state: null
id: 2026-06-19-0641-impl-trust-loop
issue_number: null
issue_url: null
manual_order: 0
parent_id: 2026-06-19-0641-trust-loop-outcome-linked-confidence
pending_messages: []
pr_url: null
priority: 2
proposed_issue_path: null
proposed_pr_path: null
realizes: null
space_id: cronos-development
state: done
title: impl – trust-loop
type: task
updated_at: '2026-06-19T07:10:29Z'
waiting_question: null
---

# Brief

CC-v1 impl phase for: trust-loop – outcome-linked confidence.

Scout report: `.cronos/pipeline/trust-loop-supersession/scout-report-trust-loop-supersession.md`
Agent contract: `.claude/agents/pipeline-implementor.md`
Artifact output: `.cronos/pipeline/trust-loop-supersession/impl-report-trust-loop--i1.md`

Feature scope:
- `backend/app/memory_store.py` — `nudge_confidence(memory_id, delta)` method
- `backend/app/worker.py` — post-task-completion hook to nudge retrieved memory confidence
- `backend/app/trace_parser.py` — ensure memory_hits IDs available on RunTrace
- `backend/tests/test_memory_trust_loop.py` — new tests covering pass/fail/rework nudge paths


This is the FIRST code-modifying task in this goal tree. Run `/goal-branch-setup` BEFORE writing any code to create feature/trust-loop-supersession. After implementing, run `/goal-task-commit` then `/pipeline-gate`.

Then run: /pipeline-gate

# History

```
2026-06-19T07:10:29Z [agent]
I'll start by running `/goal-branch-setup` to create the feature branch, then read the relevant files.

Feature branch set up. Now let me read the relevant source files and the scout report.

Now let me read trace_parser.py and the relevant part of worker.py.

Let me read more of worker.py to see how the trace and run result are handled.

Now let me check the existing test files for memory patterns and the design report.

Let me check for existing test assertions about memory_used with .md extension:

Now I have all the information needed. Let me implement all 4 iterations:

**I1**: Fix `_memory_slug()` in trace_parser.py to strip `.md`
**I2**: Add `nudge_confidence()` to memory_store.py
**I3**: Add nudge hook in worker._finalize() + widen trace guard
**I4**: Create test file

Let me start with the implementation:

Now add `nudge_confidence` to memory_store.py — I'll add it right after the `record_use` method:

Now modify worker.py: widen the trace guard and add the nudge hook after trace persist:

Now add the nudge hook after trace persist (after `await self.trace_store.save_run(...)` block and before the `MEMORY:` block capture):

Now create the test file:

Now let me run the validation commands from the design to verify:

Let me check TaskStore's constructor:

I need to fix `_make_worker` — `TaskStore` only takes `spaces_dir`. Let me simplify it to use a mock store:

All I3 tests pass. Now run the full test file:

My test was wrong — the regex `_MEMORY_FILE_RE` only matches `.md` files. Fix the test:

All 16 tests pass. Now run the full backend test suite to check for regressions:

Good — 2585 passed, 1 pre-existing failure unrelated to my changes. Let me confirm it was pre-existing:

Confirmed pre-existing. Now let me write the impl report artifact and run `/goal-task-commit` and `/pipeline-gate`.

Let me first check the design's artifact naming: `impl-report-trust-loop--i1.md`:

Now run `/goal-task-commit`:

Good. Now stage and commit:

Wait — the commit went to `main` not the feature branch. This is the known worktree issue. Let me fix it using git plumbing:

The commit went to `main` accidentally. I'll reset it and re-apply to the feature branch using git plumbing:

The feature branch is now correct and main is restored. Now push:

Branch pushed. Now run `/pipeline-gate`:

The verifier expects `impl-report-trust-loop-supersession--i1.md` (full goal slug). My file was named incorrectly. Let me rename it:

Also need to fix the slug in the artifact header — it says `slug: trust-loop--i1` but should be `trust-loop-supersession--i1`:

Also need to update the `outputs_produced` field to reference the correct filename:

Now re-run verify:

Need to add `iteration_id` and diff metrics to the artifact header. Let me check the impl schema:

Let me get actual diff counts and fix the artifact header:

Now update the artifact header with the missing fields:

Verify passes. Now run the state writer:

Both VERIFY_EXIT=0 and PY_EXIT=0. Now commit the artifact fix and finalize:

I need to commit from the workspace worktree (which is on `feature/trust-loop-supersession`), not from the main worktree:

Good — the workspace worktree is on `feature/trust-loop-supersession`. Let me use plumbing to create the follow-up commit on the feature branch:

Feature branch pushed. Now run `/task-finalize`:

## Step 1 — Verify completion

All objectives met:
- `nudge_confidence(scope, item_id, delta)` added to `memory_store.py` ✓
- `_memory_slug()` fixed in `trace_parser.py` to emit bare IDs ✓
- Trust-loop nudge hook added in `worker._finalize()` after trace persist ✓
- Trace-computation guard widened with `or self.memory_store is not None` ✓
- 16 tests in `test_memory_trust_loop.py` — all pass ✓
- Full backend suite: 2585 passed, 1 pre-existing failure (unrelated) ✓
- Pipeline gate: PROCEED (VERIFY_EXIT=0, PY_EXIT=0) ✓

## Step 3 — Handle git

Goal child task — git already handled via `/goal-task-commit` (feature branch committed and pushed).

## Step 4 — Write memory

MEMORY[fact]: trust-loop impl landed: `nudge_confidence(scope, item_id, delta)` in memory_store.py uses path.exists() under lock (no ref_count/confirmed mutation); `_memory_slug()` in trace_parser.py now strips .md so memory_used contains bare IDs; worker._finalize() gains trust-loop nudge block after trace persist (+0.05 on DONE, -0.1 on BLOCKED), trace guard widened with `or self.memory_store is not None`; 16 tests in test_memory_trust_loop.py; branch feature/trust-loop-supersession

MEMORY[observation]: pipeline-gate artifact must be named `impl-report-{full_goal_slug}--{iter_id_lower}.md` (e.g. `impl-report-trust-loop-supersession--i1.md`), not a shortened slug; missing `iteration_id` and `diff_lines_added/removed` in metrics header cause verify exit 1; `outputs_produced[0]` must be the canonical artifact path itself

STATUS: DONE
```
