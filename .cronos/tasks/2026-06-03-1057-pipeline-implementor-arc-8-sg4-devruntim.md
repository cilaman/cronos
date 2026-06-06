---
agent_mode: auto
agent_model: sonnet
claude_session_id: null
created_at: '2026-06-03T10:57:16Z'
depends_on:
- 2026-06-03-1057-pipeline-architect-arc-8-sg4-devruntimep
id: 2026-06-03-1057-pipeline-implementor-arc-8-sg4-devruntim
manual_order: 0
parent_id: 2026-06-03-1057-arc8-dev-ui
pending_messages: []
pr_url: null
priority: 2
proposed_pr_path: null
space_id: cronos-development
state: backlog
title: 'pipeline-implementor: Arc 8/SG4 — DevRuntimePanel + sidebar running indicator'
type: task
updated_at: '2026-06-03T10:57:16Z'
waiting_question: null
---

# Brief

# Phase 4 — implementation: Arc 8/SG4 — DevRuntimePanel + sidebar running indicator

Goal slug: `arc8-dev-ui` · Pipeline dir: `.cronos/pipeline/arc8-dev-ui/` · Sub-agent: `pipeline-implementor`.

Execute every entry of the design's `iterations[]` array. Each iteration gets
its own implementor invocation AND its own [[pipeline-gate]] call — fan-out
slugs are `arc8-dev-ui--<iter_id_lower>` (e.g. `arc8-dev-ui--i1`).

## Step 1 — set up the feature branch (once)

If this is the first code-changing task in the goal, invoke `/goal-branch-setup`
first so all implementor edits land on `feature/arc-8-dev-runtimes` (the root
umbrella slug — the skill resolves it dynamically via the parent_id chain).

## Step 2 — read the design report and topologically order iterations

Read `.cronos/pipeline/arc8-dev-ui/design-report-arc8-dev-ui.md`'s YAML header. Extract
`iterations[]` and group by `depends_on` into topological layers. Pick the lowest
layer that has not been executed yet.

## Step 3 — for EACH iteration in the chosen layer

For each iteration `iter`:

1. **Spawn the implementor** via the `Agent` tool, `subagent_type="pipeline-implementor"`:

   ```text
   slug                 = arc8-dev-ui--<iter.id.lower()>
   space                = $SPACE_DIR
   design_report_path   = .cronos/pipeline/arc8-dev-ui/design-report-arc8-dev-ui.md
   iteration_id         = <iter.id>
   prior_iteration_results = [<paths to impl-report-arc8-dev-ui--*.md for satisfied deps>]
   ```

2. **Close the per-iteration gate** with [[pipeline-gate]]:

   ```bash
   TASK_ID=$(basename "$PWD")
   SPACE_DIR=$(echo "$PWD" | sed 's|/.cronos/workspaces/.*||')
   export GOAL_SLUG=arc8-dev-ui
   export PHASE=implementation
   export AGENT_NAME=pipeline-implementor
   export UPSTREAM_TASK_ID="$TASK_ID"
   export ITERATION_ID=<iter.id>
   ```

   Then invoke `/pipeline-gate`. If it sets `STATUS: BLOCKED`, **halt the loop**
   and emit `STATUS: BLOCKED` for the whole task.

## Step 4 — commit + final status

If every iteration's gate passed:
1. Invoke `/goal-task-commit` to push all implementor changes to `feature/arc-8-dev-runtimes`.
2. Write a one-line summary listing the iteration ids that ran and emit `STATUS: DONE`.

Otherwise the BLOCKED status from Step 3 is already the task's final status.

# History
