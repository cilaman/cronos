---
agent_mode: auto
agent_model: opus
claude_session_id: 0f8d0d53-5751-4b82-934b-4cbb1b9978c0
created_at: '2026-05-30T14:37:55Z'
depends_on:
- 2026-05-30-1437-4-2-known-issues-store
- 2026-05-30-1437-4-3-memory-write-back
id: 2026-05-30-1437-4-4-auto-improvement-applier
manual_order: 0
parent_id: 2026-05-30-1437-self-improvement-loop-retro-known-issues
pending_messages: []
pr_url: null
priority: 2
proposed_pr_path: null
space_id: cronos-development
state: done
title: 4.4 auto-improvement applier
type: task
updated_at: '2026-05-30T23:13:54Z'
waiting_question: null
---

# Brief

Build a task/skill that, for retro findings of type `normalize rule` or `fixture`, applies the change (adds the normalize rule or the golden/negative fixture) and bumps CC_VERSION — ONLY if the Goal-1 evals still pass. Findings of type prompt/contract are left for human review.

## Acceptance
- A normalize-rule finding is auto-applied and version-bumped only when evals stay green.

## Reference material (read by absolute path)
- Delivery Notes contract: `/data/spaces/delivery-notes/.ai/framework/agent-contract-v1.md`
- Delivery Notes orchestrator: `/data/spaces/delivery-notes/.claude/agents/pipeline-orchestrator.md`
- Delivery Notes known-issues (F-NN): `/data/spaces/delivery-notes/.ai/framework/known-issues.md`
- Cronos primitives: `backend/app/{agent,worker,goal_sync,storage,models,trace_store,trace_parser,memory_store,memory_retrieval}.py`
- Memory entries `delivery-notes-pipeline` and `delivery-notes-pipeline-cronos-mapping` surface the design rationale via retrieval.

# History

```
2026-05-30T23:13:54Z [agent]
Let me check the goal-1 evals (mentioned in the task brief) and how fixtures are structured:

Now I have enough context. Design summary:

1. **`backend/app/pipeline/auto_improver.py`** — core module. Reads retro `findings[]`, filters to auto-applicable recipes (`fix_type=normalize_rule` w/ `target=normalize:strategy_synonym`, or `target=fixture:<path>`), applies changes, bumps `CC_VERSION` across `contract.py`+schemas+fixtures, runs the goal-1 evals, rolls back on failure.
2. **`backend/app/pipeline/normalize_rules.json`** — sidecar registry that `normalize.py` loads at import to merge extra strategy synonyms.
3. **Tests** at `backend/tests/test_auto_improver.py` covering: applied-and-bumped on green; rollback on red; prompt/contract skipped; fixture applied.
4. **Wire** Step 3c in pipeline-gate skill.

Now I'll write the core module. First let me explore how `normalize.py` references `_STRATEGY_SYNONYMS` to plan a non-invasive integration:

Now I'll create the registry JSON, modify `normalize.py` to load it, and write the applier:

Now let me write the auto_improver module:

Now let me update `__init__.py` to export the new module symbols and wire the pipeline-gate skill:

Now wire the applier into the pipeline-gate skill. Let me see the current SKILL.md state:

I'll defer the SKILL.md edit to commit-time (when working against the feature branch which has Step 3b). Let me jump straight to tests:

Now let me check how existing pipeline tests are structured before writing mine:

Now let me write the test file:

Now let me try running the tests:

All 19 tests pass. Now let me verify the broader test suite still passes — especially that my `normalize.py` change doesn't break `test_pipeline_normalize.py` or `test_pipeline_fixtures.py`:

Now let's run the full backend test suite to ensure 60% coverage floor passes and nothing else regresses:

All 1216 tests pass, 82% coverage (well above 60% floor). The `auto_improver.py` itself is at 78% coverage.

Now let me handle the SKILL.md update and commit. The feature branch has Step 3b; I need to switch to it (in the main worktree, since my workspace branched before 4.3) and add Step 3c after it. Let me check the current state:

Good — clean diff with just my additions. Let me also check normalize.py:

Good. Now let me edit the feature branch's `pipeline-gate/SKILL.md` to add Step 3c:

I'll use a Python script via Bash to edit the file (per workspace permissions):

Now let me run the test suite in the feature branch worktree to verify everything still works:

All 1277 tests pass (note: this branch has more tests because of 4.1-4.3). Now let me commit and push:

Now push the feature branch:

Push succeeded. Verify the commit:

Now let me run the task-finalize skill mandatory step. First, let me write a memory entry for this work:

Now let me run the task-finalize skill mandatory step:

Step 1 — verifying completion.

Task brief: Build a task/skill that applies normalize-rule / fixture retro findings, bumps CC_VERSION only when goal-1 evals stay green.
- Module `backend/app/pipeline/auto_improver.py` reads retro findings, dispatches `normalize:strategy_synonym` and `fixture:<rel_path>` recipes, snapshots, bumps version, runs eval command, rolls back on red.
- Wired Step 3c in `.claude/skills/pipeline-gate/SKILL.md` (non-blocking, retro-only).
- 19 tests pass, including the acceptance test asserting apply+bump on green and rollback on red. Full suite 1277 passed, 82% coverage.

Step 2 — no prior trace check needed (fresh task, this is the first run).

Step 3 — git is already handled: I committed b91420e to `feature/self-improvement-loop-retro-known-issues` and pushed it. Let me confirm the task is a goal child and that nothing remains in the workspace:

Goal-child task; commit b91420e is on `feature/self-improvement-loop-retro-known-issues`. The workspace branch shows the same files but they live on the feature branch instead (per the goal feature-branch workflow). Memory written.

MEMORY[fact]: `backend/app/pipeline/auto_improver.py` (task 4.4, commit b91420e on `feature/self-improvement-loop-retro-known-issues`) applies `normalize:strategy_synonym` and `fixture:<rel_path>` retro recipes, bumps `CC_VERSION` one minor across `contract.py` + schemas + fixtures, runs the goal-1 fixture harness, and rolls back the whole touch set on red. Findings of `fix_type ∈ {agent_prompt_refinement, contract_change}` are skipped for human review.

MEMORY[fact]: `backend/app/pipeline/normalize.py` now loads `normalize_rules.json` (sidecar registry) at import-time and merges its `strategy_synonyms` map into `_STRATEGY_SYNONYMS` — that JSON is where the auto-improver persists synonyms learned from retro findings.

MEMORY[procedure]: For goal feature branches checked out in another worktree (`fatal: 'feature/...' is already used by worktree`), don't try to switch — copy files to that worktree's path and commit via `git -C <feature-worktree>`. Then push with the `CRONOS_GIT_TOKEN` auth header dance.

STATUS: DONE
```
