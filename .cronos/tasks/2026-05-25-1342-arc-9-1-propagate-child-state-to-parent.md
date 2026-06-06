---
agent_mode: auto
agent_model: default
claude_session_id: null
created_at: '2026-05-26T15:07:33Z'
depends_on: []
id: 2026-05-25-1342-arc-9-1-propagate-child-state-to-parent
manual_order: 1
parent_id: 2026-05-25-1341-arc-9-goal-processing-ux-sync
pending_messages: []
pr_url: null
priority: 2
proposed_pr_path: null
space_id: cronos-development
state: archived
title: 'arc-9/1: Propagate child state → parent + goal in WAITING'
type: task
updated_at: '2026-06-02T15:33:35Z'
waiting_question: null
---

# Brief

Add parent-goal state synchronization so goals surface correctly in the Active lane when children are running.

## Changes
1. New `backend/app/goal_sync.py` with `propagate_to_parent(child_id, store, worker_pool)`.
2. Rules: child ACTIVE → parent WAITING→ACTIVE; child DONE/ARCHIVED → parent ACTIVE + re-enqueue via `worker_pool.enqueue(space_id, parent_id)`.
3. Add `parent_to_resume: str | None` to `ReplyOutcome`.
4. Hook into `apply_reply` endpoint and `_finalize` in `worker.py`.
5. Add pool back-ref to Worker so `_finalize` can trigger the goal's re-run.


Branch: `feature/arc-9-goal-ux`. Test gate: invoke `test-architect` before commit. Commit prefix: `arc-9:`.

# History
