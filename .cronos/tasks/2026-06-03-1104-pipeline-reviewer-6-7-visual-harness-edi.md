---
agent_mode: auto
agent_model: opus
claude_session_id: af7f4138-b2b7-47f2-a74f-fedc26053df4
created_at: '2026-06-03T11:04:56Z'
depends_on:
- 2026-06-03-1104-pipeline-implementor-6-7-visual-harness
- 2026-06-03-1104-tester-6-7-visual-harness-editor-react-f
feature_key: null
feature_state: null
id: 2026-06-03-1104-pipeline-reviewer-6-7-visual-harness-edi
issue_number: null
issue_url: null
manual_order: 0
parent_id: 2026-06-03-1104-arc6-visual-editor
pending_messages: []
pr_url: null
priority: 2
proposed_issue_path: null
proposed_pr_path: null
realizes: null
space_id: cronos-development
state: archived
title: 'pipeline-reviewer: 6.7 Visual harness editor React Flow'
type: task
updated_at: '2026-06-19T12:17:48Z'
waiting_question: null
---

# Brief

# Phase 6 — review: 6.7 Visual harness editor React Flow

Goal slug: `arc6-visual-editor` · Pipeline dir: `.cronos/pipeline/arc6-visual-editor/` · Sub-agent: `pipeline-reviewer`.

The review phase is **bounded** by `max_review_attempts` (default 3). Each
attempt uses a compound slug `arc6-visual-editor--attempt<k>`. Loop:

1. **Determine the attempt number.** Read `.cronos/pipeline/arc6-visual-editor/pipeline-state.json`;
   if `phases.review.verify_result.gate_decision in {fail, retry}`, increment
   the last attempt; otherwise start at `1`. Cap at `3`.

2. **Spawn the reviewer** via the `Agent` tool, `subagent_type="pipeline-reviewer"`:

   ```text
   slug              = arc6-visual-editor--attempt<k>
   space             = $SPACE_DIR
   design_report_path = .cronos/pipeline/arc6-visual-editor/design-report-arc6-visual-editor.md
   impl_report_paths = [<paths to every impl-report-arc6-visual-editor--*.md>]
   test_report_path  = .cronos/pipeline/arc6-visual-editor/test-report-arc6-visual-editor.md
   attempt           = <k>
   prior_review_path = .cronos/pipeline/arc6-visual-editor/review-report-arc6-visual-editor--attempt<k-1>.md   # only when k > 1
   ```

3. **Close the gate** with [[pipeline-gate]]:

   ```bash
   TASK_ID=$(basename "$PWD")
   SPACE_DIR=$(echo "$PWD" | sed 's|/.cronos/workspaces/.*||')
   export GOAL_SLUG=arc6-visual-editor
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
2026-06-04T08:17:32Z [agent]
No prior review phase — this is attempt 1. Let me gather all impl report paths and spawn the reviewer.

Reviewer returned `verdict=pass`. Now closing the gate.

Gate PASS and verdict=pass. Phase is review (not retro), so Steps 3b/3c skip.

gate PASS — review / arc6-visual-editor
  artifact: .cronos/pipeline/arc6-visual-editor/review-report-arc6-visual-editor--attempt1.md
  reviewer verdict: pass (no blocking findings)

STATUS: DONE
```
