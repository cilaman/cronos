---
agent_mode: auto
agent_model: sonnet
claude_session_id: a28aa3c1-5fab-4404-89c8-6a14202727c2
created_at: '2026-05-30T14:37:55Z'
depends_on:
- 2026-05-30-1437-4-1-retro-phase-agent
id: 2026-05-30-1437-4-2-known-issues-store
manual_order: 0
parent_id: 2026-05-30-1437-self-improvement-loop-retro-known-issues
pending_messages: []
pr_url: null
priority: 2
proposed_pr_path: null
space_id: cronos-development
state: done
title: 4.2 known-issues store
type: task
updated_at: '2026-05-30T22:30:57Z'
waiting_question: null
---

# Brief

Create `backend/app/pipeline/known-issues.md` (the F-NN catalog) + a small `pipeline-issue` helper that appends an entry from a retro finding (status, affects, severity, workaround). Mirror Delivery Notes `known-issues.md`.

## Acceptance
- Helper appends a well-formed F-NN entry; file is version-controlled.

## Reference material (read by absolute path)
- Delivery Notes contract: `/data/spaces/delivery-notes/.ai/framework/agent-contract-v1.md`
- Delivery Notes orchestrator: `/data/spaces/delivery-notes/.claude/agents/pipeline-orchestrator.md`
- Delivery Notes known-issues (F-NN): `/data/spaces/delivery-notes/.ai/framework/known-issues.md`
- Cronos primitives: `backend/app/{agent,worker,goal_sync,storage,models,trace_store,trace_parser,memory_store,memory_retrieval}.py`
- Memory entries `delivery-notes-pipeline` and `delivery-notes-pipeline-cronos-mapping` surface the design rationale via retrieval.

# History

```
2026-05-30T22:30:57Z [agent]
I'll read the reference materials to understand the F-NN format before implementing.

Now let me look at the state_writer to understand patterns, then check tests to understand what testing is expected.

Now let me check the test file for pipeline state writer to understand testing patterns, and check if there's already a known-issues test file:

Now I have everything I need. Let me implement the two deliverables:

1. `backend/app/pipeline/known-issues.md` - the F-NN catalog (seeded with initial entries)
2. `backend/app/pipeline/known_issues.py` - helper that appends entries
3. `backend/tests/test_pipeline_known_issues.py` - tests

Now write the tests:

Now let's run the tests to verify everything passes:

All 32 tests pass. The coverage floor failure is just from running only this subset — `known_issues.py` itself shows 100% coverage. Let me verify the full suite still passes the 60% floor:

1229 tests pass, 82% coverage (well above the 60% floor). `known_issues.py` is at 100% coverage. Now finalize the task:

Goal child task — delegating to goal-task-commit.

The feature branch `feature/self-improvement-loop-retro-known-issues` already exists. Let me check it out and run tests.

The feature branch is locked by another worktree. I'll copy the new files there and commit via that worktree path, per the documented procedure.

Pushed. Now write memory and emit STATUS.

MEMORY[fact]: `backend/app/pipeline/known-issues.md` created — Cronos-native F-NN catalog (seeded with F-01/F-02); `backend/app/pipeline/known_issues.py` is the `pipeline-issue` helper exposing `append_issue(title, description, *, affects, severity, workaround, status, path, today)` → F-NN string; also runnable as `python -m app.pipeline.known_issues append ...`; 32 tests in `backend/tests/test_pipeline_known_issues.py`, 100% module coverage.

STATUS: DONE
```
