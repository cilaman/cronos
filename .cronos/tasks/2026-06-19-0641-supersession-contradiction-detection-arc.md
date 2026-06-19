---
agent_mode: auto
agent_model: default
claude_session_id: null
created_at: '2026-06-19T06:41:51Z'
depends_on:
- 2026-06-19-0641-trust-loop-outcome-linked-confidence
feature_key: null
feature_state: null
id: 2026-06-19-0641-supersession-contradiction-detection-arc
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
title: supersession – contradiction detection + archiving
type: goal
updated_at: '2026-06-19T08:44:22Z'
waiting_question: null
---

# Brief

Wire the unused `links` field for memory supersession.

On memory write, scan existing memories in the same scope for contradictions (same key/name/slug with different content). When a contradiction is detected, archive the old memory and set bidirectional links: old memory gets `links.superseded_by = new_id`, new memory gets `links.supersedes = [old_id]`.

## Scope
- `backend/app/memory_store.py` — `detect_contradictions(new_item)` + supersession logic in `write_memory()`
- `backend/app/models.py` — document `links` field schema (`{"superseded_by": str}` / `{"supersedes": list[str]}`)
- `backend/tests/test_memory_supersession.py` — new test file

## Acceptance
- Writing a memory that contradicts an existing one archives the old one
- Old memory's `links` contains `{"superseded_by": new_id}`
- New memory's `links` contains `{"supersedes": [old_id]}`
- Non-contradicting writes proceed unchanged
- Archived superseded memories excluded from retrieval results

# History

```
2026-06-19T08:03:19Z [agent]
Paused: Child 'review – supersession' ended in waiting state. Completed 4, skipped 0 already-done.
```

```
2026-06-19T08:44:22Z [agent]
All tasks complete. Completed 1, skipped 5 already-done.
```
