---
agent_mode: auto
agent_model: sonnet
claude_session_id: null
created_at: '2026-06-03T10:26:56Z'
depends_on:
- 2026-06-03-1026-pipeline-architect-arc-7-s1-mailbox-brok
id: 2026-06-03-1026-pipeline-implementor-arc-7-s1-mailbox-br
manual_order: 0
parent_id: 2026-06-03-1026-arc7-mailbox-broker
pending_messages: []
pr_url: null
priority: 1
proposed_pr_path: null
space_id: cronos-development
state: backlog
title: 'pipeline-implementor: Arc 7/S1 — Mailbox broker + persistence + API'
type: task
updated_at: '2026-06-03T10:26:56Z'
waiting_question: null
---

# Brief

# Phase 4 — implementation: Arc 7/S1 — Mailbox broker + persistence + API

Goal slug: `arc7-mailbox-broker` · Pipeline dir: `.cronos/pipeline/arc7-mailbox-broker/` · Sub-agent: `pipeline-implementor`.

Execute every entry of the design's `iterations[]` array. Each iteration gets
its own implementor invocation AND its own [[pipeline-gate]] call — fan-out
slugs are `arc7-mailbox-broker--<iter_id_lower>` (e.g. `arc7-mailbox-broker--i1`).

## Step 1 — set up the feature branch (once, shared across all Arc 7 subgoals)

The Arc 7 shared branch is `feature/arc-7-messaging`. If it does not yet exist,
create it from `main`. If already set up by a prior subgoal, simply check it out.
Use [[goal-branch-setup]] with slug `arc-7-messaging` (not the subgoal slug).

## Step 2 — read the design report and topologically order iterations

Read `.cronos/pipeline/arc7-mailbox-broker/design-report-arc7-mailbox-broker.md`'s YAML header. Extract
`iterations[]` and group by `depends_on` into topological layers. Pick the
lowest layer not yet executed.

## Step 3 — for EACH iteration in the chosen layer

For each iteration `iter`:

1. **Spawn the implementor** via the `Agent` tool, `subagent_type="pipeline-implementor"`:

   ```text
   slug                 = arc7-mailbox-broker--<iter.id.lower()>
   space                = $SPACE_DIR
   design_report_path   = .cronos/pipeline/arc7-mailbox-broker/design-report-arc7-mailbox-broker.md
   iteration_id         = <iter.id>
   prior_iteration_results = [<paths to impl-report-arc7-mailbox-broker--*.md for satisfied deps>]
   ```

2. **Close the per-iteration gate** with [[pipeline-gate]]:

   ```bash
   TASK_ID=$(basename "$PWD")
   SPACE_DIR=$(echo "$PWD" | sed 's|/.cronos/workspaces/.*||')
   export GOAL_SLUG=arc7-mailbox-broker
   export PHASE=implementation
   export AGENT_NAME=pipeline-implementor
   export UPSTREAM_TASK_ID="$TASK_ID"
   export ITERATION_ID=<iter.id>
   ```

   Invoke `/pipeline-gate`. If `STATUS: BLOCKED`, halt the loop.

## Step 4 — commit + final status

If every iteration's gate passed:
1. Invoke `/goal-task-commit` to push changes to `feature/arc-7-messaging`.
2. Emit `STATUS: DONE` listing the iteration ids that ran.

# History
