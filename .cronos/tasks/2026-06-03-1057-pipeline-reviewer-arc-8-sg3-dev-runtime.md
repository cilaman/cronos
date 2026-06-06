---
agent_mode: auto
agent_model: opus
claude_session_id: null
created_at: '2026-06-03T10:57:16Z'
depends_on:
- 2026-06-03-1057-pipeline-implementor-arc-8-sg3-dev-runti
- 2026-06-03-1057-tester-arc-8-sg3-dev-runtime-api-sse-log
id: 2026-06-03-1057-pipeline-reviewer-arc-8-sg3-dev-runtime
manual_order: 0
parent_id: 2026-06-03-1057-arc8-dev-api
pending_messages: []
pr_url: null
priority: 2
proposed_pr_path: null
space_id: cronos-development
state: backlog
title: 'pipeline-reviewer: Arc 8/SG3 — dev runtime API + SSE log stream'
type: task
updated_at: '2026-06-03T10:57:16Z'
waiting_question: null
---

# Brief

# Phase 6 — review: Arc 8/SG3 — dev runtime API + SSE log stream

Goal slug: `arc8-dev-api` · Pipeline dir: `.cronos/pipeline/arc8-dev-api/` · Sub-agent: `pipeline-reviewer`.

The review phase is **bounded** by `max_review_attempts` (default 3). Each
attempt uses a compound slug `arc8-dev-api--attempt<k>`. Loop:

1. **Determine the attempt number.** Read `.cronos/pipeline/arc8-dev-api/pipeline-state.json`;
   if `phases.review.verify_result.gate_decision in {fail, retry}`, increment
   the last attempt; otherwise start at `1`. Cap at `3`.

2. **Spawn the reviewer** via the `Agent` tool, `subagent_type="pipeline-reviewer"`:

   ```text
   slug              = arc8-dev-api--attempt<k>
   space             = $SPACE_DIR
   design_report_path = .cronos/pipeline/arc8-dev-api/design-report-arc8-dev-api.md
   impl_report_paths = [<paths to every impl-report-arc8-dev-api--*.md>]
   test_report_path  = .cronos/pipeline/arc8-dev-api/test-report-arc8-dev-api.md
   attempt           = <k>
   prior_review_path = .cronos/pipeline/arc8-dev-api/review-report-arc8-dev-api--attempt<k-1>.md   # only when k > 1
   ```

3. **Close the gate** with [[pipeline-gate]]:

   ```bash
   TASK_ID=$(basename "$PWD")
   SPACE_DIR=$(echo "$PWD" | sed 's|/.cronos/workspaces/.*||')
   export GOAL_SLUG=arc8-dev-api
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
