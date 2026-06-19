---
agent_mode: auto
agent_model: default
claude_session_id: null
created_at: '2026-06-19T06:41:51Z'
depends_on: []
feature_key: null
feature_state: null
id: 2026-06-19-0641-trust-loop-outcome-linked-confidence
issue_number: null
issue_url: null
manual_order: 0
parent_id: 2026-06-19-0641-trust-loop-supersession
pending_messages: []
pr_url: null
priority: 2
proposed_issue_path: null
proposed_pr_path: null
realizes: null
space_id: cronos-development
state: done
title: trust-loop – outcome-linked confidence
type: goal
updated_at: '2026-06-19T07:26:46Z'
waiting_question: null
---

# Brief

Implement outcome-linked confidence updates for memory items.

When a task completes, the worker checks its RunTrace for retrieved memory IDs (memory_hits). On STATUS: DONE (pass), nudge those memories' confidence up (additive boost, default +0.05, capped at 1.0). On task sent back to BACKLOG from ACTIVE (rework) or STATUS: BLOCKED (failure), nudge confidence down (default -0.1, floored at 0.0).

## Scope
- `backend/app/memory_store.py` — add `nudge_confidence(memory_id, delta)` method
- `backend/app/worker.py` — hook into task completion to call nudge for retrieved memories
- `backend/app/trace_parser.py` — ensure memory_hits IDs are parsed and available on RunTrace
- `backend/tests/test_memory_trust_loop.py` — new test file

## Acceptance
- Pass → confidence increases by delta (capped at 1.0)
- Fail/rework → confidence decreases by |delta| (floored at 0.0)
- Retrieval score correctly uses updated confidence

# History

```
2026-06-19T07:26:46Z [agent]
All tasks complete. Completed 6, skipped 0 already-done.
```
