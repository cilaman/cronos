---
agent_mode: plan
agent_model: default
claude_session_id: a21f921a-5fa5-4cd2-bae7-873842910f74
created_at: '2026-05-27T13:49:15Z'
depends_on: []
id: 2026-05-27-1349-task-status-problems
manual_order: 0
parent_id: null
pending_messages: []
pr_url: null
priority: 3
proposed_pr_path: null
space_id: cronos-development
state: archived
title: Task status problems
type: task
updated_at: '2026-06-04T10:26:21Z'
waiting_question: null
---

# Brief

Switching task status is now depending on the texting of the last agent output. If some reason the texting is not standard, the task ends up in waiting. Propose some more reliable mechanism how to work with task state.

# History

```
2026-05-27T14:12:51Z [agent] run=0 model=claude-sonnet-4-6 mode=plan agents=explore,tester
Let me explore the codebase to understand the current task status mechanism.

Now let me read the actual implementation files to understand the exact code.

Let me check the recent git history for relevant changes and read the worker's finalize_child logic:

Let me look at how the agent is spawned to understand the full context:

Let me look at the existing tests for parse_status:

Now I have a clear picture of the problem. Let me implement the fix:

**Root cause:** `parse_status()` has a hard 10-line scan window. If the agent writes `STATUS: DONE` and then continues writing 10+ more lines (trailing explanations, summaries, etc.), the STATUS marker is buried and missed. The task then falls into the `else` branch → WAITING.

The 3-pass fallback handles STATUS buried across **turns** but not within a **single turn**.

Now add a regression test that explicitly covers the buried-by-trailing-lines case:

Now run the test suite to confirm everything passes:

All 41 tests pass. Now let me also run the full backend test suite to verify no coverage floor violations:

The first tester agent confirmed all 41 tests pass. Let me verify the final state of the changed files:

The fix is clean. Let me now write up the complete analysis and solution:

---

## Root cause and fix

**Root cause:** `parse_status()` had a hard-coded 10-line scan window:

```python
scan_from = max(0, len(lines) - 10)
for i in range(len(lines) - 1, scan_from - 1, -1):
```

When an agent writes `STATUS: DONE` and then continues with 10+ more lines of trailing text (summaries, explanations, MEMORY blocks, etc.), the marker is buried outside the window and returns `None`. The task then falls through to the default `else` branch in the worker, which sets state to `WAITING`.

The existing 3-pass fallback only helps with STATUS markers buried **across turns**, not within a **single turn**.

**Fix:** Removed the 10-line cap — `parse_status()` now scans all lines backwards (`range(len(lines) - 1, -1, -1)`). Since we scan backwards and take the first match (= the last STATUS marker in the text), trailing text after a STATUS: DONE no longer causes it to be missed.

**Why this is safe:** Scanning backwards and taking the last occurrence is strictly correct. Any STATUS mentioned as an example earlier in the output would be before the real one, so the real one (last occurrence) wins.

**Two new regression tests added:**
- `test_parse_status_buried_by_many_trailing_lines` — STATUS: DONE followed by 15 trailing lines, must still parse correctly
- `test_parse_status_memory_block_before_status` — STATUS: DONE after multiple MEMORY lines

All 41 tests in `test_agent.py` pass.
```
