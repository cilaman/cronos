---
agent_mode: auto
agent_model: opus
claude_session_id: 16bdc753-4e52-4bfe-9e68-e39d25a04b7c
created_at: '2026-06-03T11:04:55Z'
depends_on:
- 2026-06-03-1104-pipeline-implementor-6-3-control-flow-no
- 2026-06-03-1104-tester-6-3-control-flow-node-semantics
id: 2026-06-03-1104-pipeline-reviewer-6-3-control-flow-node
manual_order: 0
parent_id: 2026-06-03-1104-arc6-control-flow
pending_messages: []
pr_url: null
priority: 2
proposed_pr_path: null
space_id: cronos-development
state: done
title: 'pipeline-reviewer: 6.3 Control flow node semantics'
type: task
updated_at: '2026-06-03T21:14:00Z'
waiting_question: null
---

# Brief

# Phase 6 — review: 6.3 Control flow node semantics

Goal slug: `arc6-control-flow` · Pipeline dir: `.cronos/pipeline/arc6-control-flow/` · Sub-agent: `pipeline-reviewer`.

The review phase is **bounded** by `max_review_attempts` (default 3). Each
attempt uses a compound slug `arc6-control-flow--attempt<k>`. Loop:

1. **Determine the attempt number.** Read `.cronos/pipeline/arc6-control-flow/pipeline-state.json`;
   if `phases.review.verify_result.gate_decision in {fail, retry}`, increment
   the last attempt; otherwise start at `1`. Cap at `3`.

2. **Spawn the reviewer** via the `Agent` tool, `subagent_type="pipeline-reviewer"`:

   ```text
   slug              = arc6-control-flow--attempt<k>
   space             = $SPACE_DIR
   design_report_path = .cronos/pipeline/arc6-control-flow/design-report-arc6-control-flow.md
   impl_report_paths = [<paths to every impl-report-arc6-control-flow--*.md>]
   test_report_path  = .cronos/pipeline/arc6-control-flow/test-report-arc6-control-flow.md
   attempt           = <k>
   prior_review_path = .cronos/pipeline/arc6-control-flow/review-report-arc6-control-flow--attempt<k-1>.md   # only when k > 1
   ```

3. **Close the gate** with [[pipeline-gate]]:

   ```bash
   TASK_ID=$(basename "$PWD")
   SPACE_DIR=$(echo "$PWD" | sed 's|/.cronos/workspaces/.*||')
   export GOAL_SLUG=arc6-control-flow
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
2026-06-03T21:14:00Z [agent]
No review entry in `phases` → this is **attempt 1**. Let me check the impl reports list.

Now I'll spawn the pipeline-reviewer for attempt 1.

Reviewer wrote artifact with verdict=pass. Now close the gate.

Task tracking isn't needed for this short workflow. Closing the gate now.

Verifier exit 0. Recording state now.

Gate PASS. Verdict from reviewer artifact is `verdict=pass` — end the task.

gate PASS — review / arc6-control-flow (verdict=pass)
  artifact: .cronos/pipeline/arc6-control-flow/review-report-arc6-control-flow--attempt1.md

STATUS: DONE
```
