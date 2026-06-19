---
agent_mode: auto
agent_model: opus
claude_session_id: null
created_at: '2026-06-05T23:27:19Z'
depends_on:
- 2026-06-05-2327-backend-harness-tools-resolver
feature_key: null
feature_state: null
id: 2026-06-05-2327-integrate-harness-editor-usability
issue_number: null
issue_url: null
manual_order: 0
parent_id: 2026-06-05-2327-harness-editor-usability
pending_messages: []
pr_url: null
priority: 2
proposed_issue_path: null
proposed_pr_path: null
realizes: null
space_id: cronos-development
state: backlog
title: integrate – harness-editor-usability
type: task
updated_at: '2026-06-05T23:34:29Z'
waiting_question: null
---

# Brief

Final integration task for the **Harness editor usability** goal.

Both slices are complete and committed to `feature/harness-editor-usability`:
- Slice A: frontend editor aligned to the backend harness data model.
- Slice B: backend harness tools-resolver implemented.

## Steps
1. Verify the whole suite is green:
   - `cd backend && pytest tests/ --cov=app --cov-report=term-missing` (60% floor).
   - `cd frontend && npm test && npm run build`.
2. Smoke the end-to-end path: create a harness in the editor with a trigger → agent node referencing
   a real agent/skill + a variable, save (no 422), and confirm the saved YAML validates and the
   runtime resolver resolves the agent_ref.
3. Run /goal-finalize to rebase onto main, merge with --no-ff, push, and delete the feature branch.

Then run: /goal-finalize

# History
