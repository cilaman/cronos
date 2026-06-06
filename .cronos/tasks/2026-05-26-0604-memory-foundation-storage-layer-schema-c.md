---
agent_mode: plan
agent_model: default
claude_session_id: null
created_at: '2026-05-26T14:25:52Z'
depends_on: []
id: 2026-05-26-0604-memory-foundation-storage-layer-schema-c
manual_order: 0
parent_id: null
pending_messages: []
pr_url: null
priority: 1
proposed_pr_path: null
space_id: cronos-development
state: archived
title: Memory Foundation — storage layer, schema & CRUD
type: goal
updated_at: '2026-06-02T14:33:35Z'
waiting_question: null
---

# Brief

Introduce the persistent memory storage layer for Cronos.

## Objective
Define the `MemoryItem` Pydantic model in `backend/app/models.py`, implement `MemoryStore` mirroring the patterns of `backend/app/trace_store.py` and `backend/app/stats_store.py`. Persist items as markdown-with-frontmatter. Expose REST CRUD under `/api/memory`. No retrieval logic yet — just storage.

## Status
Goal A is substantially complete: a2 (MemoryStore I/O) and a3 (index.md generation) were merged to main. a1 (schema skeleton) and a4/a5 were subsumed by the more complete a3 implementation. The memory API and store exist in main.

# History
