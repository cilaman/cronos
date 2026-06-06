---
agent_mode: auto
agent_model: sonnet
claude_session_id: null
created_at: '2026-06-03T10:57:16Z'
depends_on:
- 2026-06-03-1057-pipeline-implementor-arc-8-sg4-devruntim
id: 2026-06-03-1057-tester-arc-8-sg4-devruntimepanel-sidebar
manual_order: 0
parent_id: 2026-06-03-1057-arc8-dev-ui
pending_messages: []
pr_url: null
priority: 2
proposed_pr_path: null
space_id: cronos-development
state: backlog
title: 'tester: Arc 8/SG4 — DevRuntimePanel + sidebar running indicator'
type: task
updated_at: '2026-06-03T10:57:16Z'
waiting_question: null
---

# Brief

# Phase 5 — test: Arc 8/SG4 — DevRuntimePanel + sidebar running indicator

Goal slug: `arc8-dev-ui` · Pipeline dir: `.cronos/pipeline/arc8-dev-ui/` · Sub-agent: `tester`.

## Step 1 — spawn the tester sub-agent

Use the `Agent` tool with `subagent_type="tester"`. Pass:

```text
space_id  = cronos-development
scope     = full-space
slug      = arc8-dev-ui     # makes the tester emit test-report-{slug}.md too
```

The tester runs pytest + vitest, parses coverage, POSTs a TestReport to
the backend API, and (because slug is set) ALSO emits a CC-v1
`test-report-arc8-dev-ui.md` artifact under `.cronos/pipeline/arc8-dev-ui/`.

## Step 2 — close the gate

Set the inputs and invoke the [[pipeline-gate]] skill. The gate validates the
artifact, records phase metrics into `pipeline-state.json`, and emits the final
`STATUS:` line for this task.

```bash
TASK_ID=$(basename "$PWD")
SPACE_DIR=$(echo "$PWD" | sed 's|/.cronos/workspaces/.*||')
export GOAL_SLUG=arc8-dev-ui
export PHASE=test
export AGENT_NAME=tester
export UPSTREAM_TASK_ID="$TASK_ID"
```

Now invoke `/pipeline-gate`. Do not emit any STATUS line yourself — the gate
emits the final `STATUS: DONE` (pass) or `STATUS: BLOCKED` (fail) for this task.

# History
