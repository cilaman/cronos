---
agent_mode: auto
agent_model: default
claude_session_id: null
created_at: '2026-05-26T14:25:52Z'
depends_on:
- 2026-05-26-0604-a2-implement-memorystore-i-o-atomic-writ
id: 2026-05-26-0604-a3-generate-and-maintain-index-md-per-sc
manual_order: 0
parent_id: 2026-05-26-0604-memory-foundation-storage-layer-schema-c
pending_messages: []
pr_url: null
priority: 1
proposed_pr_path: null
space_id: cronos-development
state: archived
title: 'A3: Generate and maintain index.md per scope'
type: task
updated_at: '2026-06-02T14:33:35Z'
waiting_question: null
---

# Brief

Add rebuild_index(scope) helper to MemoryStore. Groups items by kind. MERGED to main as the most complete implementation (315-line MemoryStore, 35 tests).

# History
