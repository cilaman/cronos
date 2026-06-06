---
agent_mode: auto
agent_model: opus
claude_session_id: e2290c7d-f7ed-4bbd-a734-f3e70687d28c
created_at: '2026-06-03T11:04:55Z'
depends_on:
- 2026-06-03-1104-pipeline-implementor-6-2-harness-executo
- 2026-06-03-1104-tester-6-2-harness-executor-core-interpr
id: 2026-06-03-1104-pipeline-reviewer-6-2-harness-executor-c
manual_order: 0
parent_id: 2026-06-03-1104-arc6-executor
pending_messages: []
pr_url: null
priority: 2
proposed_pr_path: null
space_id: cronos-development
state: done
title: 'pipeline-reviewer: 6.2 Harness executor core interpreter'
type: task
updated_at: '2026-06-03T20:04:04Z'
waiting_question: null
---

# Brief

# Phase 6 — review: 6.2 Harness executor core interpreter

Goal slug: `arc6-executor` · Pipeline dir: `.cronos/pipeline/arc6-executor/` · Sub-agent: `pipeline-reviewer`.

The review phase is **bounded** by `max_review_attempts` (default 3). Each
attempt uses a compound slug `arc6-executor--attempt<k>`. Loop:

1. **Determine the attempt number.** Read `.cronos/pipeline/arc6-executor/pipeline-state.json`;
   if `phases.review.verify_result.gate_decision in {fail, retry}`, increment
   the last attempt; otherwise start at `1`. Cap at `3`.

2. **Spawn the reviewer** via the `Agent` tool, `subagent_type="pipeline-reviewer"`:

   ```text
   slug              = arc6-executor--attempt<k>
   space             = $SPACE_DIR
   design_report_path = .cronos/pipeline/arc6-executor/design-report-arc6-executor.md
   impl_report_paths = [<paths to every impl-report-arc6-executor--*.md>]
   test_report_path  = .cronos/pipeline/arc6-executor/test-report-arc6-executor.md
   attempt           = <k>
   prior_review_path = .cronos/pipeline/arc6-executor/review-report-arc6-executor--attempt<k-1>.md   # only when k > 1
   ```

3. **Close the gate** with [[pipeline-gate]]:

   ```bash
   TASK_ID=$(basename "$PWD")
   SPACE_DIR=$(echo "$PWD" | sed 's|/.cronos/workspaces/.*||')
   export GOAL_SLUG=arc6-executor
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
2026-06-03T20:04:04Z [agent]
This is attempt 1 (no prior review). Let me spawn the pipeline-reviewer.

Reviewer returned `verdict=pass`. Now close the gate.

Gate PASS — review / arc6-executor (verdict=pass, verifier exit 0).
  artifact: .cronos/pipeline/arc6-executor/review-report-arc6-executor--attempt1.md

STATUS: DONE
```
