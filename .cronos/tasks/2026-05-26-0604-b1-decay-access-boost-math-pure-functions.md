---
agent_mode: auto
agent_model: default
claude_session_id: a276d50c-6bac-4a17-8580-2da69a181083
created_at: '2026-05-26T14:25:52Z'
depends_on: []
id: 2026-05-26-0604-b1-decay-access-boost-math-pure-functions
manual_order: 0
parent_id: 2026-05-26-0604-memory-lifecycle-ttl-decay-confirmation
pending_messages: []
pr_url: null
priority: 1
proposed_pr_path: null
space_id: cronos-development
state: archived
title: 'B1: Decay + access-boost math (pure functions)'
type: task
updated_at: '2026-06-02T21:33:35Z'
waiting_question: null
---

# Brief

Create backend/app/memory_lifecycle.py with pure, testable functions.

Constants: DECAY_HALF_LIFE_DAYS=14, BOOST_FACTOR=1.2, MAX_SCORE=10.0, PRUNE_THRESHOLD=0.1, TTL_EXTENSION_PER_BOOST_DAYS=7, CONFIRM_MIN_USES=3.

Functions: decay(), boost(), should_prune(), should_auto_confirm(). No I/O in this module.

# History

```
2026-05-26T21:20:28Z [agent]
Let me look at the workspace structure and any existing relevant code first.

Now I have everything I need. Let me create the `memory_lifecycle.py` module.

Now let me verify it imports cleanly and run any existing tests.

All checks pass. Let me commit this via the goal-task-commit skill.

I'm on a `cronos/` branch, not a feature branch. I need to run `/goal-branch-setup` first.

On the feature branch. Now let me run the tests before committing.

906 tests pass. Now stage and commit.

Done. `backend/app/memory_lifecycle.py` is committed and pushed to `feature/memory-lifecycle-ttl-decay-confirmation`. The module provides four pure functions (`decay`, `boost`, `should_prune`, `should_auto_confirm`) and all six constants, with no I/O — all 906 existing tests still pass.

**STATUS: DONE**
```
