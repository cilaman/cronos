---
agent_mode: auto
agent_model: default
claude_session_id: 62422251-4bf2-4ea6-9a19-f6888b5c31b2
created_at: '2026-06-03T16:32:50Z'
depends_on: []
id: 2026-06-03-1632-cannot-start-goal
manual_order: 0
parent_id: null
pending_messages: []
pr_url: null
priority: 3
proposed_pr_path: null
space_id: cronos-development
state: archived
title: Cannot start goal
type: task
updated_at: '2026-06-04T10:28:28Z'
waiting_question: null
---

# Brief

The goal 2026-06-03-1104-arc-6-harnesses cannot be started, it returns an error regarding a dependency but I cannot see the real reason.

# History

```
2026-06-03T16:37:07Z [agent] run=0 model=claude-sonnet-4-6 mode=auto
I'll investigate the dependency error preventing goal `2026-06-03-1104-arc-6-harnesses` from starting.

The error points to a dependency on `2026-06-03-1104-pipeline-doc-sync-6-8-live-execution-ove`. Let me investigate that task.

The error indicates that when trying to run the goal, a dependency check fails. Let me look at the worker code to understand the logic.

Now let me look at the `_run_goal` function in worker.py to understand how it handles goal execution.

The problem is clear: the integration task depends on a leaf task from inside a subgoal (not a sibling), so the topo sort can't order it after the subgoals, and `store.transition()` fails when it tries to activate it first alphabetically. Let me check the full picture and the setup script.

The problem is twofold:
1. The integration task's `depends_on` points to a non-sibling leaf task (inside a subgoal), not to `arc6-live-overlay` which is the correct sibling
2. The 8 subgoals have no sibling deps — they should be chained 6.1→6.2→...→6.8

Let me fix both using the API.

Now fix the subgoal dependency chain (6.1→6.2→...→6.8):

Now let me verify the root goal is no longer blocked and the topo sort will work correctly:

The topo sort is now correct. The root goal is in `waiting` with a stale error message. I need to transition it back to `backlog` so it can be started:

The goal is back in `backlog` state with no error message. Let me do a final verification:

The goal is ready. Here's the summary of what was wrong and what was fixed:

**Root cause:** The Arc 6 setup script made two mistakes:

1. **Integration task's `depends_on` pointed to a non-sibling** — it referenced `pipeline-doc-sync-6-8` which is a leaf task *inside* the `arc6-live-overlay` subgoal, not a sibling of the integration task. The `_topo_children` function ignores non-sibling deps for ordering, so the integration task got `in_degree=0` and sorted alphabetically before all subgoals (since `arc-6-integration` < `arc6-*`). When the worker tried to activate it first, `store.transition()` correctly blocked it with "unmet dependencies."

2. **The 8 subgoals had no sibling deps** — they'd run in alphabetical order (arc6-control-flow first) rather than the intended sequential 6.1→6.2→...→6.8 order.

**Fixes applied via API:**
- Integration task now depends on `arc6-live-overlay` (the correct sibling)
- Subgoals now have a proper dependency chain: harness-model → executor → control-flow → run-lifecycle → cron-trigger → event-triggers → visual-editor → live-overlay → integration task
- Root goal moved from `waiting` back to `backlog`

The goal can now be started normally.

STATUS: DONE
```
