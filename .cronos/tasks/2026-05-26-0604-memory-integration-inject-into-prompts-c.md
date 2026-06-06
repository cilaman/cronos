---
agent_mode: plan
agent_model: default
claude_session_id: null
created_at: '2026-05-26T14:25:52Z'
depends_on:
- 2026-05-26-0604-memory-foundation-storage-layer-schema-c
id: 2026-05-26-0604-memory-integration-inject-into-prompts-c
manual_order: 0
parent_id: null
pending_messages: []
pr_url: null
priority: 1
proposed_pr_path: null
space_id: cronos-development
state: archived
title: Memory Integration — inject into prompts, capture from runs
type: goal
updated_at: '2026-06-02T20:33:35Z'
waiting_question: null
---

# Brief

Connect the Cronos memory subsystem to the agent execution loop.

## Objective
On task start, retrieve top-N relevant memory items and inject them into the agent prompt. Define a MEMORY: marker convention for agents to write new items. The worker writes captured candidates as unconfirmed. Extend RunTrace with memory_injected, memory_used, memory_written arrays.

## Prerequisite
Goal A (Memory Foundation) must be complete.

Commit and push to goals feature branch feat/memory-integration

# History

```
2026-05-26T16:34:40Z [agent]
Paused: Child 'C3: Capture MEMORY: blocks from agent output and persist as unconfirmed' ended in waiting state. Completed 0, skipped 1 already-done.
```

```
2026-05-26T20:26:48Z [agent]
All tasks complete. Completed 1, skipped 4 already-done.
```
