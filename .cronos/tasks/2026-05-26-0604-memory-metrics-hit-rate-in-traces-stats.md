---
agent_mode: plan
agent_model: default
claude_session_id: null
created_at: '2026-05-26T14:25:52Z'
depends_on:
- 2026-05-26-0604-memory-foundation-storage-layer-schema-c
- 2026-05-26-0604-memory-integration-inject-into-prompts-c
id: 2026-05-26-0604-memory-metrics-hit-rate-in-traces-stats
manual_order: 0
parent_id: null
pending_messages: []
pr_url: null
priority: 1
proposed_pr_path: null
space_id: cronos-development
state: archived
title: Memory Metrics — hit rate in traces, stats & UI browser
type: goal
updated_at: '2026-06-03T05:33:36Z'
waiting_question: null
---

# Brief

Make memory effectiveness visible across Cronos.

## Objective
Compute memory_hit_rate in trace_parser.py. Aggregate per-task and per-space in stats. Add hit-rate chip to TracePanel and memory section to StatsPage. Add memory browser at /memory.

## Prerequisites
- Goal A (Memory Foundation) — for the CRUD API
- Goal C (Memory Integration) — for memory_injected, memory_used, memory_written in RunTrace

# History

```
2026-05-26T22:14:53Z [agent]
Paused: Child 'D5: Memory browser page — list, filter, confirm/reject' ended in waiting state. Completed 1, skipped 0 already-done.
```

```
2026-05-27T04:52:00Z [agent]
Paused: Child 'D6: Metrics tests — hit rate computation and UI' ended in waiting state. Completed 3, skipped 2 already-done.
```

```
2026-05-27T05:17:34Z [agent]
All tasks complete. Completed 0, skipped 6 already-done.
```
