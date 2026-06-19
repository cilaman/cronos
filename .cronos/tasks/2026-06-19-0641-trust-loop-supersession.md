---
agent_mode: auto
agent_model: default
claude_session_id: null
created_at: '2026-06-19T06:41:51Z'
depends_on: []
feature_key: null
feature_state: null
id: 2026-06-19-0641-trust-loop-supersession
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
title: Trust loop + supersession
type: goal
updated_at: '2026-06-19T08:44:22Z'
waiting_question: null
---

# Brief

Add two complementary improvements to the Cronos memory system.

## Sub-goals

### trust-loop
Make confidence outcome-linked: when a task that retrieved memory M passes (STATUS: DONE), nudge M's confidence up; on rework (task sent back to BACKLOG from ACTIVE) or failure (STATUS: BLOCKED), nudge confidence down. Today confidence is author-asserted once (1.0 agent / 0.8 retro), multiplies the retrieval score, and is never updated after creation.

### supersession
Wire the unused `links` field: on memory write, detect memories that contradict the new one and archive the old one with a bidirectional link. This prevents stale conflicting memories from accumulating in retrieval results.

## Pipeline artifacts

All artifacts at `.cronos/pipeline/trust-loop-supersession/`.

## Acceptance

- Memory confidence scores are updated after task outcomes (pass nudges up, fail/rework nudges down, bounded to [0.0, 1.0])
- Contradicting memories are archived on write with bidirectional links
- All backend tests pass with ≥60% coverage

# History

```
2026-06-19T08:03:19Z [agent]
Paused: Sub-goal 'supersession – contradiction detection + archiving' ended in waiting state. Completed 2, skipped 0 already-done.
```

```
2026-06-19T08:36:19Z [agent]
Waiting for in-flight child task to complete. Completed 0, skipped 2 already-done.
```

```
2026-06-19T08:44:22Z [agent]
All tasks complete. Completed 0, skipped 3 already-done.
```
