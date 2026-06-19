---
agent_mode: auto
agent_model: sonnet
claude_session_id: null
created_at: '2026-06-05T23:35:07Z'
depends_on:
- 2026-06-05-2335-auto-repair-missing-sibling-deps-in-run-2b00
feature_key: null
feature_state: null
id: 2026-06-05-2335-tests-auto-repair-sibling-deps
issue_number: null
issue_url: null
manual_order: 0
parent_id: 2026-06-05-2335-auto-repair-missing-sibling-deps-in-run
pending_messages: []
pr_url: null
priority: 1
proposed_issue_path: null
proposed_pr_path: null
realizes: null
space_id: cronos-development
state: backlog
title: 'tests: auto-repair sibling deps'
type: task
updated_at: '2026-06-05T23:35:07Z'
waiting_question: null
---

# Brief

# Tests for auto-repair of missing sibling deps

Verify the fix introduced in task `2026-06-05-2335-auto-repair-missing-sibling-deps-in-run-2b00` (`_run_goal` auto-repair).

## Test cases to add in `backend/tests/`

File: `backend/tests/test_worker_sibling_dep_repair.py` (new file)

### Test 1 — auto-repair triggers and repairs

Setup:
- Root goal with two sub-goals: `sg_a` (no deps) and `sg_b` (no sibling deps,
  but its first child has `depends_on=[sg_a_doc_id]`).
- All tasks in backlog.

Invoke `_run_goal(root_goal_id)`.

Assert:
- `sg_b.depends_on` now contains `sg_a_id` (sibling dep was added).
- Warning log was emitted containing `"Auto-repaired"`.
- `sg_a` ran before `sg_b`.

### Test 2 — already-correct sibling deps not touched

Setup:
- Root goal with two sub-goals: `sg_a` (no deps) and `sg_b` (already has
  `depends_on=[sg_a_id]`).

Assert:
- No auto-repair warning emitted.
- Normal execution order preserved.

### Test 3 — repair capped at 1 attempt

Setup:
- A child whose dep can't be resolved to a sibling.

Assert:
- Goal fails cleanly (no infinite loop).
- `failed_child_id` is set.

## Run

```bash
cd /data/spaces/cronos-development/backend
pytest tests/test_worker_sibling_dep_repair.py -v --tb=short
```

Coverage must remain ≥ 60%:
```bash
pytest tests/ --cov=app --cov-report=term-missing --cov-fail-under=60
```

# History
