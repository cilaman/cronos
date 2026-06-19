---
agent_mode: auto
agent_model: default
claude_session_id: null
created_at: '2026-06-07T11:29:31Z'
depends_on: []
feature_key: null
feature_state: null
id: 2026-06-07-1129-feature-module-test-coverage-gaps
issue_number: null
issue_url: null
manual_order: 0
parent_id: null
pending_messages: []
pr_url: null
priority: 3
proposed_issue_path: null
proposed_pr_path: null
realizes: null
space_id: cronos-development
state: archived
title: Feature Module Test Coverage Gaps
type: goal
updated_at: '2026-06-16T06:30:16Z'
waiting_question: null
---

# Brief

Write missing tests identified in the Features test coverage audit. The audit found
5 P1 gaps (real bugs hidden by absent coverage) and 8 P2 gaps (TOCTOU error paths and edge cases).

## Child tasks

1. **Feature sync untested paths** — P1-A (waiting_question AttributeError recovery), P1-D
   (propagate_to_feature with non-existent item_id), P1-E (_find_root cycle guard), P2-F
   (ACTIVE-resume concurrent race), P2-G (done-detection DONE concurrent race)
2. **API error paths and hooks** — P1-B (mirror error callback), P1-C (DELETE 501), P2-A
   (StorageError on create), P2-B (space-not-found after feature-found — 3 endpoints),
   P2-C (TaskNotFound TOCTOU in state-change), P2-D (TaskNotFound in patch_feature),
   P2-E (feature-not-found after set_realizes), P2-H (configure_store not tested)

# History

```
2026-06-09T06:05:17Z [agent]
All tasks complete. Completed 2, skipped 0 already-done.
```
