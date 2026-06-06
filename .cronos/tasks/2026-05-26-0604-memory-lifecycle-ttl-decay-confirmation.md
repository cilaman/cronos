---
agent_mode: plan
agent_model: default
claude_session_id: null
created_at: '2026-05-26T14:25:52Z'
depends_on:
- 2026-05-26-0604-memory-foundation-storage-layer-schema-c
id: 2026-05-26-0604-memory-lifecycle-ttl-decay-confirmation
manual_order: 0
parent_id: null
pending_messages: []
pr_url: null
priority: 1
proposed_pr_path: null
space_id: cronos-development
state: archived
title: Memory Lifecycle — TTL decay, confirmation & lint
type: goal
updated_at: '2026-06-02T22:33:35Z'
waiting_question: null
---

# Brief

Make the Cronos memory subsystem self-curating.

## Objective
Implement score decay (active items live longer, stale items age out), promote unconfirmed → confirmed on repeated successful use, run a periodic lint pass, and archive pruned items.

## Key behaviors
1. Decay: items not accessed recently lose score
2. Access boost: every successful retrieval raises score and extends TTL
3. Confirmation: unconfirmed → confirmed after M successful re-uses
4. Lint: periodic one-shot agent task; produces a report
5. Pruning + archive: items with ttl_until < now AND score < threshold move to archive/

## Prerequisites
Goal A (Memory Foundation) — complete.

# History

```
2026-05-26T21:56:54Z [agent]
Paused: Child 'B6: Lifecycle tests — decay, promotion, archive, lint shape' ended in waiting state. Completed 5, skipped 0 already-done.
```

```
2026-05-26T21:57:46Z [agent]
All tasks complete. Completed 0, skipped 6 already-done.
```
