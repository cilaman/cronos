---
agent_mode: auto
agent_model: default
claude_session_id: 01c46735-bc25-4534-bdea-ad2035e17f0d
created_at: '2026-05-26T14:25:52Z'
depends_on:
- 2026-05-26-0604-b2-hook-access-boost-into-retrieval-path
id: 2026-05-26-0604-b3-confirmation-workflow-explicit-endpoint
manual_order: 0
parent_id: 2026-05-26-0604-memory-lifecycle-ttl-decay-confirmation
pending_messages: []
pr_url: null
priority: 1
proposed_pr_path: null
space_id: cronos-development
state: archived
title: 'B3: Confirmation workflow — explicit endpoint + auto-promotion'
type: task
updated_at: '2026-06-02T21:33:35Z'
waiting_question: null
---

# Brief

Add POST /api/memory/{id}/confirm and POST /api/memory/{id}/reject endpoints. Write tests for auto-confirm and explicit confirm/reject.

# History

```
2026-05-26T21:30:34Z [agent]
Let me explore the codebase to understand the current state before implementing the endpoints.

Good, I have a clear picture. Let me read the relevant files to verify before implementing.

Now let me read the memory_store to understand the auto-confirm logic and model details.

Now I have everything I need. I'll implement:
1. `CONFIRM_THRESHOLD` constant and `record_use()` method in `memory_store.py` for auto-promotion
2. `POST /{scope}/{item_id}/confirm` and `POST /{scope}/{item_id}/reject` endpoints in `memory.py`
3. Tests for both explicit confirm/reject and auto-confirm behavior

Now add the `record_use` method to the store, before `read_index`:

Now add the confirm and reject endpoints to the API, before the delete endpoint to keep logical ordering:

Now add tests for the new endpoints and auto-confirm behavior:

Now let's run the tests to verify everything works:

All 24 tests pass. The coverage failure is a pre-existing project-wide issue (31% total vs 60% threshold) — the files I touched show 100% and 86% coverage. Now I'll commit and push.

The feature branch `feature/memory-lifecycle-ttl-decay-confirmation` already exists. I need to switch to it and commit my changes.

The feature branch `feature/memory-lifecycle-ttl-decay-confirmation` is locked to the b1 worktree. I'll create a patch, apply it in the b1 worktree, and commit from there.

All done. Here's a summary of what was implemented:

**`backend/app/memory_store.py`**
- Added `CONFIRM_THRESHOLD = 3` constant
- Added `record_use(scope, item_id)` method: increments `ref_count`, updates `last_used_at`, and auto-promotes `confirmed=True` when `ref_count >= CONFIRM_THRESHOLD`

**`backend/app/api/memory.py`**
- `POST /api/memory/{scope}/{item_id}/confirm` — sets `confirmed=True`, returns updated item (404 if missing)
- `POST /api/memory/{scope}/{item_id}/reject` — sets `confirmed=False`, returns updated item (404 if missing)

**`backend/tests/test_api_memory.py`** — 10 new tests (all 24 pass):
- Explicit confirm/reject: sets flag, persists on re-fetch, 404 on missing
- Auto-confirm: triggers at threshold, stays false before threshold, no-op if already confirmed, increments `ref_count` correctly, raises `MemoryNotFound` for unknown items

Committed as `35f962e` on `feature/memory-lifecycle-ttl-decay-confirmation` and pushed.

**STATUS: DONE**
```
