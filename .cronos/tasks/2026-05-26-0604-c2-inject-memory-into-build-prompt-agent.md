---
agent_mode: auto
agent_model: default
claude_session_id: 8a7e421b-0a74-40c3-9e30-6a09b587efaf
created_at: '2026-05-26T14:25:52Z'
depends_on:
- 2026-05-26-0604-c1-v1-retrieval-keyword-index-walk
id: 2026-05-26-0604-c2-inject-memory-into-build-prompt-agent
manual_order: 0
parent_id: 2026-05-26-0604-memory-integration-inject-into-prompts-c
pending_messages: []
pr_url: null
priority: 1
proposed_pr_path: null
space_id: cronos-development
state: archived
title: 'C2: Inject memory into build_prompt in agent.py'
type: task
updated_at: '2026-06-02T21:33:35Z'
waiting_question: null
---

# Brief

Modify build_prompt() to accept memory_items: list[MemoryItem] and inject as a # Memory section. In worker.py, call retrieve() before run_agent() and pass results to build_prompt().

# History

```
2026-05-26T17:50:46Z [agent] run=0 model=claude-sonnet-4-6 mode=auto agents=explore
I'll explore the codebase to understand the current structure before making changes.

Let me read the actual files to see the current code before making changes.

Now let me check what memory-related files already exist in this workspace.

No memory files exist yet. Let me check models.py and the main.py to understand the full structure.

Let me also check worker_pool.py to understand how Worker is instantiated.

Now I have a complete picture. I'll implement the changes across 7 files:

1. Add `MemoryItem` model to `models.py`
2. Create `memory_store.py`
3. Create `memory_retrieval.py`
4. Modify `agent.py` (`build_prompt` + `run_agent`)
5. Modify `worker.py` (add `memory_store`, call `retrieve`)
6. Modify `worker_pool.py` (thread `memory_store` through)
7. Modify `main.py` (instantiate `MemoryStore`)

Now create `memory_store.py`:

Now create `memory_retrieval.py`:

Now modify `agent.py` — update the import, `build_prompt`, and `run_agent`:

Now modify `worker.py` to import `MemoryStore` and `retrieve`, add the `memory_store` param to Worker, and call `retrieve` before `run_agent`:

Now update `_run_task` to call `retrieve` before `run_agent`:

Now update `_run_goal`'s `run_agent` call for child tasks:

Now update `worker_pool.py` to accept and pass `memory_store`:

Now update `main.py` to instantiate `MemoryStore` and pass it to `WorkerPool`:

Now let me verify the key changes look correct by checking the modified sections:

Good. Now run a quick syntax check to make sure nothing is broken:

All imports pass. Let me also run a quick functional test of the memory injection path:

Everything works. Let me do a final check that the existing tests still pass:

Tests are mocking `run_agent` without accepting `**kwargs`. Let me find and fix all such mocks:

I need to update all `fake_run_agent` signatures in tests to accept the new `memory_items` parameter. The cleanest fix is adding `**kwargs` to each:

There are other mocked agent functions with different names. Let me find and fix them:

Two remaining: `blocking_agent` at line 409 and `max_turns_agent` at line 494. Let me fix them:

All 832 tests pass. Here's a summary of the changes made:

**New files:**
- `backend/app/memory_store.py` — `MemoryStore` class: file-backed JSON storage for `MemoryItem` objects, supporting global (`/data/memory/`) and per-space (`.cronos/memory/`) scopes
- `backend/app/memory_retrieval.py` — `retrieve(task, space_id, store)`: keyword-matching scorer that returns up to 5 relevant `MemoryItem`s for a task

**Modified files:**
- `backend/app/models.py` — added `MemoryKind` enum and `MemoryItem` model
- `backend/app/agent.py` — `build_prompt()` accepts `memory_items: list[MemoryItem] | None` and injects a `# Memory` section; `run_agent()` accepts and forwards `memory_items`
- `backend/app/worker.py` — imports `MemoryStore`/`retrieve`, adds `memory_store` param to `Worker.__init__`, calls `retrieve()` before `run_agent()` in both `_run_task` and `_run_goal` (for child tasks)
- `backend/app/worker_pool.py` — threads `memory_store` through to each `Worker`
- `backend/app/main.py` — instantiates `MemoryStore(SPACES_DIR, DATA_DIR / "memory")` and passes it to `WorkerPool`
- Test files — updated 9 `fake_run_agent` / `blocking_agent` / `max_turns_agent` mocks to accept `**kwargs`

STATUS: DONE
```

```
2026-05-26T20:37:19Z [user]
Commit and push to goals feature branch feat/memory-integration
```

```
2026-05-26T20:39:55Z [agent] run=1 model=claude-sonnet-4-6 mode=auto
Let me check what's already on `feat/memory-integration` before merging:

The `feat/memory-integration` branch is significantly ahead and already has a full memory implementation. Let me check if my changes are already subsumed there:

`feat/memory-integration` already has a more complete version of the same functionality. I'll commit my work, then merge into feat/memory-integration (resolving conflicts in favor of the more complete implementation there):

The branch is checked out in the main worktree. Let me operate from there:

Conflicts as expected. Since `feat/memory-integration` has the more complete implementation, I'll resolve by keeping its version for all conflicting files:

Let me check the full current state of models.py to make sure there's no duplication:

There are duplicate `MemoryKind`/`MemoryItem` definitions in the merged models.py. I need to fix this:

Tests pass. Now complete the merge commit and push:

Done. The merge is pushed to `feat/memory-integration`.

**What landed:** The main contribution from this task branch was updating 9 test mock functions (`fake_run_agent`, `blocking_agent`, `max_turns_agent`) in `test_autopilot.py`, `test_worker.py`, and `test_worker_lifecycle.py` to accept `**kwargs` — making them forward-compatible with the new `memory_items` parameter added to `run_agent()`. The full memory injection implementation (`MemoryItem`, `build_prompt` changes, `retrieve()` call in worker, etc.) was already present on `feat/memory-integration` in a more complete form, so those files were kept as-is during conflict resolution.
```
