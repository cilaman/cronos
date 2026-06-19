---
agent_mode: auto
agent_model: default
claude_session_id: null
created_at: '2026-06-07T11:27:14Z'
depends_on: []
feature_key: null
feature_state: null
id: 2026-06-07-1127-fix-features-backend-critical-bugs
issue_number: null
issue_url: null
manual_order: 0
parent_id: null
pending_messages: []
pr_url: null
priority: 1
proposed_issue_path: null
proposed_pr_path: null
realizes: null
space_id: cronos-development
state: archived
title: Fix Features Backend Critical Bugs
type: goal
updated_at: '2026-06-15T05:30:16Z'
waiting_question: null
---

# Brief

Three P1 bugs silently break the WAITING state display, enable double-processing
of features, and create data integrity gaps. All are pure backend fixes with no new UI required.

## Findings fixed

- **F1** `set_feature_waiting_question` missing from storage.py — feature WAITING question silently dropped
- **F2** `FeatureRead` missing `waiting_question` — frontend can never display why a feature is blocked
- **F3** `process_feature` double-fires when already PROCESSING — can spawn duplicate decomposition agents
- **F4** `validate_realizes` only blocks 1-hop self-cycles — longer cycles constructible
- **F7** `feature_board` silently drops features with `feature_state=None` — invisible data loss
- **F8** `update()` allows `type→feature/fix` without setting `feature_key` / `feature_state`
- **F9** Mirror error logging uses `log.warning` without `exc_info` — tracebacks silently dropped
- **F10** `_fire_mirror` carries a bare `# type: ignore[arg-type]`

## Child tasks

1. Implement `set_feature_waiting_question` + expose `waiting_question` in FeatureRead (F1, F2)
2. Guard `process_feature` against double-processing with 409 (F3)
3. Backend quality bundle: validate_realizes cycle check, feature_board warning, update() guard, log exc_info, remove type:ignore (F4, F7, F8, F9, F10)

# History

```
2026-06-08T05:03:23Z [agent]
All tasks complete. Completed 3, skipped 0 already-done.
```
