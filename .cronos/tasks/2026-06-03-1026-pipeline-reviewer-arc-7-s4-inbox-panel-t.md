---
agent_mode: auto
agent_model: opus
claude_session_id: null
created_at: '2026-06-03T10:26:56Z'
depends_on:
- 2026-06-03-1026-pipeline-implementor-arc-7-s4-inbox-pane
- 2026-06-03-1026-tester-arc-7-s4-inbox-panel-two-task-e2e
id: 2026-06-03-1026-pipeline-reviewer-arc-7-s4-inbox-panel-t
manual_order: 0
parent_id: 2026-06-03-1026-arc7-inbox-ui-e2e
pending_messages: []
pr_url: null
priority: 1
proposed_pr_path: null
space_id: cronos-development
state: backlog
title: 'pipeline-reviewer: Arc 7/S4 — Inbox panel + two-task e2e'
type: task
updated_at: '2026-06-03T10:26:56Z'
waiting_question: null
---

# Brief

# Phase 6 — review: Arc 7/S4 — Inbox panel + two-task e2e

Goal slug: `arc7-inbox-ui-e2e` · Pipeline dir: `.cronos/pipeline/arc7-inbox-ui-e2e/` · Sub-agent: `pipeline-reviewer`.

The review phase is **bounded** by `max_review_attempts` (default 3). Each
attempt uses a compound slug `arc7-inbox-ui-e2e--attempt<k>`. Loop:

1. **Determine attempt number.** Read `.cronos/pipeline/arc7-inbox-ui-e2e/pipeline-state.json`.
   Start at 1, increment if prior attempt gate_decision in {fail, retry}.

2. **Spawn the reviewer** via the `Agent` tool, `subagent_type="pipeline-reviewer"`:

   ```text
   slug              = arc7-inbox-ui-e2e--attempt<k>
   space             = $SPACE_DIR
   design_report_path = .cronos/pipeline/arc7-inbox-ui-e2e/design-report-arc7-inbox-ui-e2e.md
   impl_report_paths = [<paths to every impl-report-arc7-inbox-ui-e2e--*.md>]
   test_report_path  = .cronos/pipeline/arc7-inbox-ui-e2e/test-report-arc7-inbox-ui-e2e.md
   attempt           = <k>
   prior_review_path = .cronos/pipeline/arc7-inbox-ui-e2e/review-report-arc7-inbox-ui-e2e--attempt<k-1>.md
   ```

3. **Close the gate** with [[pipeline-gate]]:

   ```bash
   TASK_ID=$(basename "$PWD")
   SPACE_DIR=$(echo "$PWD" | sed 's|/.cronos/workspaces/.*||')
   export GOAL_SLUG=arc7-inbox-ui-e2e
   export PHASE=review
   export AGENT_NAME=pipeline-reviewer
   export UPSTREAM_TASK_ID="$TASK_ID"
   export ATTEMPT=<k>
   ```

   Invoke `/pipeline-gate`. On `STATUS: DONE`:
   - `verdict=pass` → emit `STATUS: DONE`.
   - `verdict=needs_fix` AND k<3 → emit `STATUS: BLOCKED` with findings.
   - `verdict=needs_fix` AND k==3 → `STATUS: BLOCKED`, cap hit.
   - `verdict=fail` → `STATUS: BLOCKED`, terminal.

# History
