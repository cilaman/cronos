---
agent_mode: auto
agent_model: opus
claude_session_id: 196502e6-2062-4d6b-990a-d55fb29551c7
created_at: '2026-06-03T16:31:36Z'
depends_on:
- 2026-06-03-1631-pipeline-implementor-features-fixes-s5-f
- 2026-06-03-1631-tester-features-fixes-s5-features-board
feature_key: null
feature_state: null
id: 2026-06-03-1631-pipeline-reviewer-features-fixes-s5-feat
issue_number: null
issue_url: null
manual_order: 0
parent_id: 2026-06-03-1631-featurefix-board-ui
pending_messages: []
pr_url: null
priority: 2
proposed_issue_path: null
proposed_pr_path: null
realizes: null
space_id: cronos-development
state: archived
title: 'pipeline-reviewer: Features&Fixes/S5 — Features board, Tasks rename, cards'
type: task
updated_at: '2026-06-19T12:17:48Z'
waiting_question: null
---

# Brief

# Phase 6 — review: Features&Fixes/S5 — Features board, Tasks rename, cards

Goal slug: `featurefix-board-ui` · Pipeline dir: `.cronos/pipeline/featurefix-board-ui/` · Sub-agent: `pipeline-reviewer`.

Bounded by `max_review_attempts=3`. Each attempt slug: `featurefix-board-ui--attempt<k>`.

1. Determine attempt number from `.cronos/pipeline/featurefix-board-ui/pipeline-state.json`.
2. Spawn reviewer via `Agent` tool, `subagent_type="pipeline-reviewer"`:
   ```text
   slug               = featurefix-board-ui--attempt<k>
   space              = $SPACE_DIR
   design_report_path = .cronos/pipeline/featurefix-board-ui/design-report-featurefix-board-ui.md
   impl_report_paths  = [all impl-report-featurefix-board-ui--*.md]
   test_report_path   = .cronos/pipeline/featurefix-board-ui/test-report-featurefix-board-ui.md
   attempt            = <k>
   prior_review_path  = .cronos/pipeline/featurefix-board-ui/review-report-featurefix-board-ui--attempt<k-1>.md  # k>1 only
   ```
3. Close gate:
   ```bash
   TASK_ID=$(basename "$PWD")
   SPACE_DIR=$(echo "$PWD" | sed 's|/.cronos/workspaces/.*||')
   export GOAL_SLUG=featurefix-board-ui
   export PHASE=review
   export AGENT_NAME=pipeline-reviewer
   export UPSTREAM_TASK_ID="$TASK_ID"
   export ATTEMPT=<k>
   ```
   Invoke `/pipeline-gate`. On pass: `verdict=pass` → `STATUS: DONE`.
   `verdict=needs_fix` AND k<3 → `STATUS: BLOCKED` (re-enqueue impl). k==3 → `STATUS: BLOCKED`.
   `verdict=fail` → `STATUS: BLOCKED` (terminal).

When you end up in `STATUS: BLOCKED` and you need to respawn implementor in order to FIX findings, you have the permission to do so. You can re-spawn implementor and tester up to 3 times in order to satisfy passing requirements

# History

```
2026-06-05T14:13:05Z [agent]
This is attempt 1. Let me spawn the reviewer.

Reviewer returned verdict=pass. Now I close the gate.

Gate passed. Verifier exit 0, state recorded.

gate PASS — review / featurefix-board-ui
  artifact: .cronos/pipeline/featurefix-board-ui/review-report-featurefix-board-ui--attempt1.md

STATUS: DONE
```
