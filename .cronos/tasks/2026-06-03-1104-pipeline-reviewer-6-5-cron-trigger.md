---
agent_mode: auto
agent_model: opus
claude_session_id: e0b48a96-f805-4d3f-82d2-fc7640b61ff3
created_at: '2026-06-03T11:04:55Z'
depends_on:
- 2026-06-03-1104-pipeline-implementor-6-5-cron-trigger
- 2026-06-03-1104-tester-6-5-cron-trigger
feature_key: null
feature_state: null
id: 2026-06-03-1104-pipeline-reviewer-6-5-cron-trigger
issue_number: null
issue_url: null
manual_order: 0
parent_id: 2026-06-03-1104-arc6-cron-trigger
pending_messages: []
pr_url: null
priority: 2
proposed_issue_path: null
proposed_pr_path: null
realizes: null
space_id: cronos-development
state: archived
title: 'pipeline-reviewer: 6.5 Cron trigger'
type: task
updated_at: '2026-06-19T12:17:48Z'
waiting_question: null
---

# Brief

# Phase 6 — review: 6.5 Cron trigger

Goal slug: `arc6-cron-trigger` · Pipeline dir: `.cronos/pipeline/arc6-cron-trigger/` · Sub-agent: `pipeline-reviewer`.

The review phase is **bounded** by `max_review_attempts` (default 3). Each
attempt uses a compound slug `arc6-cron-trigger--attempt<k>`. Loop:

1. **Determine the attempt number.** Read `.cronos/pipeline/arc6-cron-trigger/pipeline-state.json`;
   if `phases.review.verify_result.gate_decision in {fail, retry}`, increment
   the last attempt; otherwise start at `1`. Cap at `3`.

2. **Spawn the reviewer** via the `Agent` tool, `subagent_type="pipeline-reviewer"`:

   ```text
   slug              = arc6-cron-trigger--attempt<k>
   space             = $SPACE_DIR
   design_report_path = .cronos/pipeline/arc6-cron-trigger/design-report-arc6-cron-trigger.md
   impl_report_paths = [<paths to every impl-report-arc6-cron-trigger--*.md>]
   test_report_path  = .cronos/pipeline/arc6-cron-trigger/test-report-arc6-cron-trigger.md
   attempt           = <k>
   prior_review_path = .cronos/pipeline/arc6-cron-trigger/review-report-arc6-cron-trigger--attempt<k-1>.md   # only when k > 1
   ```

3. **Close the gate** with [[pipeline-gate]]:

   ```bash
   TASK_ID=$(basename "$PWD")
   SPACE_DIR=$(echo "$PWD" | sed 's|/.cronos/workspaces/.*||')
   export GOAL_SLUG=arc6-cron-trigger
   export PHASE=review
   export AGENT_NAME=pipeline-reviewer
   export UPSTREAM_TASK_ID="$TASK_ID"
   export ATTEMPT=<k>
   ```

   Invoke `/pipeline-gate`. On `STATUS: DONE`, inspect the reviewer artifact's
   YAML `verdict`:
   - `verdict=pass` → emit `STATUS: DONE`, end the task.
   - `verdict=needs_fix` AND `k < 3` → re-enqueue Phase 4 (impl) by emitting
     `STATUS: BLOCKED` with the reviewer's findings.
   - `verdict=needs_fix` AND `k == 3` → `STATUS: BLOCKED`, attempt cap hit.
   - `verdict=fail` → `STATUS: BLOCKED`, terminal.

   On `STATUS: BLOCKED` from the gate itself (artifact missing / schema
   failure), the gate's status is final — do not overwrite it.

# History

```
2026-06-04T05:50:06Z [agent]
No review phase entry yet, so attempt = 1. Let me check the impl reports and test report.

Reviewer emitted `verdict=pass`. Now closing the gate.

Gate passed. Reviewer verdict was `pass` — proceed to doc phase.

gate PASS — review / arc6-cron-trigger
  artifact: .cronos/pipeline/arc6-cron-trigger/review-report-arc6-cron-trigger--attempt1.md
  verdict: pass (attempt 1/3)

STATUS: DONE
```
