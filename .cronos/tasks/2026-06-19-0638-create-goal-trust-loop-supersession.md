---
agent_mode: auto
agent_model: default
claude_session_id: ecd99686-796f-406f-8e0e-99158f278bee
created_at: '2026-06-19T06:38:54Z'
depends_on: []
feature_key: null
feature_state: null
id: 2026-06-19-0638-create-goal-trust-loop-supersession
issue_number: null
issue_url: null
manual_order: 0
parent_id: null
pending_messages: []
pr_url: null
priority: 3
proposed_issue_path: null
proposed_pr_path: null
realizes: null
space_id: cronos-development
state: done
title: 'Create goal: Trust loop + supersession'
type: task
updated_at: '2026-06-19T06:43:01Z'
waiting_question: null
---

# Brief

Create cronos goal for following memory related functionality, use CC v1 pipeline:
Make confidence outcome-linked: when a task that retrieved memory M passes, nudge M up; on rework/failure, nudge down. Today confidence is author-asserted once (1.0 agent / 0.8 retro), multiplies the retrieval score, and reflects nothing. Wire the unused links field for supersession: on write, detect contradicting memories and archive the old one with a link.

# History

```
2026-06-19T06:43:01Z [agent] run=0 model=claude-sonnet-4-6 mode=auto
I'll invoke the `create-goal` skill to set up the CC v1 pipeline goal for trust loop + supersession.

Now I'll write and execute the Python script to create the goal structure via the API.

Let me verify the structure looks correct.

Goal is created and verified. Now I'll finalize this task.

Only memory item score-updates from memory retrieval — no code changes to commit. This is an analysis/planning task.

## Step 4 — Write memory

Memory written. 

MEMORY[fact]: Trust loop + supersession goal created as `2026-06-19-0641-trust-loop-supersession`. CC v1 pipeline: shared scout (haiku) → sub-goal A "trust-loop" (6 phases, impl runs `/goal-branch-setup` first) → sub-goal B "supersession" (6 phases, depends on SG A; doc runs `/goal-finalize`). Artifacts at `.cronos/pipeline/trust-loop-supersession/`. Branch: `feature/trust-loop-supersession`.

STATUS: DONE
```
