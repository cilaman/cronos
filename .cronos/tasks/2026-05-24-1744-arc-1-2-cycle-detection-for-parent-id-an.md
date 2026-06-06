---
agent_mode: auto
agent_model: default
claude_session_id: null
created_at: '2026-05-26T15:07:33Z'
depends_on:
- 2026-05-24-1743-arc-1-1-task-model-add-type-parent-id-de
id: 2026-05-24-1744-arc-1-2-cycle-detection-for-parent-id-an
manual_order: 2
parent_id: null
pending_messages: []
pr_url: null
priority: 2
proposed_pr_path: null
space_id: cronos-development
state: archived
title: 'arc-1/2: Cycle detection for parent_id and depends_on'
type: task
updated_at: '2026-06-02T15:33:35Z'
waiting_question: null
---

# Brief

Add validation that prevents creating cycles via `parent_id` or `depends_on`.

## Changes
1. `backend/app/storage.py` — add `validate_parent(task_id, candidate_parent_id)` and `validate_depends_on(task_id, candidate_depends_on)` raising `CycleError` with a message naming the offending path (`A -> B -> A`).
2. Both validators are O(N) using the in-memory index; do NOT re-read markdown files during validation.
3. Validators run scoped to a single `space_id` (cross-space deps and parents also raise).

## Acceptance
- Direct self-reference rejected. Transitive cycle rejected. Cross-space reference rejected.
- Valid hierarchy of depth ≥ 3 with no cycles passes.

## Standing rules
Branch: `feature/arc-1-hierarchy` from `main`. Do NOT merge to `main` — that's manual after the arc lands.
Test gate before commit: invoke the `test-architect` subagent. Only commit after green.
Commit message: `arc-1: <summary>`. STATUS: DONE on success, STATUS: BLOCKED if tests fail.

# History
