---
agent_mode: auto
agent_model: default
claude_session_id: null
created_at: '2026-06-18T16:06:02Z'
depends_on: []
feature_key: null
feature_state: null
id: 2026-06-18-1606-memory-bug-fixing
issue_number: null
issue_url: null
manual_order: 0
parent_id: null
pending_messages: []
pr_url: null
priority: 2
proposed_issue_path: null
proposed_pr_path: null
realizes: null
space_id: cronos-development
state: done
title: memory bug fixing
type: goal
updated_at: '2026-06-18T18:49:27Z'
waiting_question: null
---

# Brief

# Pipeline goal: Fix memory scoring and injection bugs

Pipeline run scaffolded by `/pipeline-scaffold`.

## Request

# Memory Bug Fixes

Three critical correctness bugs in the memory system that defeat its purpose.

## Bug 1 — Multiplicative boost from zero (memory_lifecycle.py)

boost() computes min(score * 1.2, 10.0). New items are created with score=0.0, and 0.0 * 1.2 = 0.0 forever. Fix: use additive boost so zero-scored items can actually rise. Add test for boost(0.0, ...).

## Bug 2 — decay() is dead code (memory_lifecycle.py)

decay() is defined but never called. Wire it into MemoryStore.get() before boost() so scores actually age.

## Bug 3 — Injection drops the body (agent.py build_prompt())

build_prompt() only injects first body line if it differs from title. Full body (file paths, procedures, etc.) never reaches the agent. Fix: include full body in memory context.

## Test gaps to fill

- boost(0.0, ...) case
- decay applied at get() time
- full body in build_prompt() memory section
- should_prune() correctly protects boosted items

## Files to change

- backend/app/memory_lifecycle.py (bugs 1 + 2 definition side)
- backend/app/memory_store.py (bug 2 call site)
- backend/app/agent.py (bug 3)
- backend/tests/test_memory_lifecycle.py (new tests)
- backend/tests/test_memory_store.py (new tests)
- backend/tests/test_agent.py (new tests)

All changes on a single feature branch: feature/memory-bug-fixing

## Child tasks (one per CC-v1 phase)

1. scout    — pipeline-scout    (research)
2. analysis — pipeline-analyst  (analysis)
3. design   — pipeline-architect(design)
4. impl     — pipeline-implementor (implementation; may fan out per iteration)
5. test     — tester            (test)
6. review   — pipeline-reviewer (review; may loop on verdict=needs_fix)
7. doc      — pipeline-doc-sync (doc; terminal)

Each phase task ends by invoking `/pipeline-gate` which closes the gate from
the artifact YAML header.

# History

```
2026-06-18T18:49:27Z [agent]
All tasks complete. Completed 7, skipped 0 already-done.
```
