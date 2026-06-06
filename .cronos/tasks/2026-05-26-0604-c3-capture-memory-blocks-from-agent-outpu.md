---
agent_mode: auto
agent_model: default
claude_session_id: 0b66dea2-6ec4-42ff-9864-1123324fcb93
created_at: '2026-05-26T14:25:52Z'
depends_on: []
id: 2026-05-26-0604-c3-capture-memory-blocks-from-agent-outpu
manual_order: 0
parent_id: 2026-05-26-0604-memory-integration-inject-into-prompts-c
pending_messages: []
pr_url: null
priority: 1
proposed_pr_path: null
space_id: cronos-development
state: archived
title: 'C3: Capture MEMORY: blocks from agent output and persist as unconfirmed'
type: task
updated_at: '2026-06-02T18:33:35Z'
waiting_question: null
---

# Brief

Create backend/app/memory_parser.py with parse_memory_blocks(text). After a run completes, parse final_text for MEMORY: blocks and persist via MemoryStore as unconfirmed. Document MEMORY: marker format in STATUS_CONTRACT.

# History

```
2026-05-26T16:34:40Z [agent]
Let me explore the relevant parts of the codebase to understand the structure before implementing.

Now let me read the key files directly to understand the exact code I need to modify.

Let me check the main.py wiring and existing tests.

The main.py already imports `MemoryStore` and `memory_router`. Let me check what already exists.

Good, the memory foundation already exists. Let me read the existing memory files to understand what's there.

Now I have everything I need. Let me check the existing test_worker.py briefly to understand test patterns:

Now I have enough context. Let me implement everything:

Now update the STATUS_CONTRACT in agent.py to document the MEMORY: format:

Now update `worker.py` to import `memory_parser` and `MemoryStore`, and add memory capture in `_finalize`:

Now add the memory capture logic in `_finalize`. I'll add it after the trace persistence block:

Now update `worker_pool.py` to accept and pass `memory_store`:

Now wire up `memory_store` in `main.py` where `WorkerPool` is created:

Now let me write tests for `memory_parser.py`:

Now let's run the tests to verify everything works:

The ordering is wrong — fenced blocks are appended before inline blocks. I need a single-pass approach that maintains document order:

All 16 tests pass. Now let me run the full test suite to make sure nothing is broken:

934 tests pass, 0 failures. Let me write a quick summary of what was done:

**STATUS: DONE**

---

## Summary

Implemented C3: MEMORY: block capture from agent output.

**Files created:**
- `backend/app/memory_parser.py` — `parse_memory_blocks(text)` parses inline `MEMORY[kind]: content` markers and ````memory kind` fenced blocks from agent output, returning `MemoryBlock` dataclass objects in document order
- `backend/tests/test_memory_parser.py` — 16 tests covering empty input, all valid kinds, invalid kinds, case insensitivity, fenced blocks, mixed formats, and realistic agent output

**Files modified:**
- `backend/app/agent.py` — Added MEMORY: marker documentation to `STATUS_CONTRACT`, defining all four inline forms (`MEMORY[fact/procedure/observation/reference]:`) and the fenced `\`\`\`memory [kind]` block format
- `backend/app/worker.py` — Added `memory_store: MemoryStore | None` parameter; in `_finalize()`, calls `parse_memory_blocks(result.final_text)` and persists each block via `memory_store.create(confirmed=False)`
- `backend/app/worker_pool.py` — Added `memory_store` parameter, passed through to each `Worker`
- `backend/app/main.py` — Wired `memory_store=memory_store` into `WorkerPool` construction
```

```
2026-05-26T16:52:13Z [user]
Commit and push to goals feature branch - use the same branch for all tasks of this goal
```

```
2026-05-26T16:52:46Z [agent] run=0 model=claude-sonnet-4-6 mode=auto
No existing feature branch. I'll create `feat/memory-integration` for all C-series tasks of this goal.

Committed and pushed to `feat/memory-integration`. All C-series goal tasks should use this branch going forward.
```
