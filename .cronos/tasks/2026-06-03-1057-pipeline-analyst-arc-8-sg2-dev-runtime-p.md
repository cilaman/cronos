---
agent_mode: auto
agent_model: sonnet
claude_session_id: null
created_at: '2026-06-03T10:57:16Z'
depends_on:
- 2026-06-03-1057-pipeline-scout-arc-8-sg2-dev-runtime-pro
id: 2026-06-03-1057-pipeline-analyst-arc-8-sg2-dev-runtime-p
manual_order: 0
parent_id: 2026-06-03-1057-arc8-dev-process
pending_messages: []
pr_url: null
priority: 2
proposed_pr_path: null
space_id: cronos-development
state: backlog
title: 'pipeline-analyst: Arc 8/SG2 — dev runtime process manager + health poller'
type: task
updated_at: '2026-06-03T10:57:16Z'
waiting_question: null
---

# Brief

# Phase 2 — analysis: Arc 8/SG2 — dev runtime process manager + health poller

Goal slug: `arc8-dev-process` · Pipeline dir: `.cronos/pipeline/arc8-dev-process/` · Sub-agent: `pipeline-analyst`.

Decompose the verbatim request into atomic, testable requirements `R<N>`. Determines `has_ui`, scope, traceability. Emits `analysis-report-{slug}.md` (class=analysis).

## Step 1 — spawn the sub-agent

Use the `Agent` tool with `subagent_type="pipeline-analyst"` and the brief below.
The sub-agent writes its CC-v1 artifact under `.cronos/pipeline/arc8-dev-process/` and returns a
short conversational summary; do not paraphrase or post-process its output here.

```text
slug   = arc8-dev-process
space  = $SPACE_DIR    (resolved from $PWD as in Step 2)
request = (verbatim text of .cronos/pipeline/arc8-dev-process/request.md — do not paraphrase)
scout_report_path = .cronos/pipeline/arc8-dev-process/scout-report-arc8-dev-process.md
```

Wait for the sub-agent to return. Do not read the artifact body yourself — the
gate (Step 2) verifies it mechanically.

## Step 2 — close the gate

Set the inputs and invoke the [[pipeline-gate]] skill. The gate validates the
artifact, records phase metrics into `pipeline-state.json`, and emits the final
`STATUS:` line for this task.

```bash
TASK_ID=$(basename "$PWD")
SPACE_DIR=$(echo "$PWD" | sed 's|/.cronos/workspaces/.*||')
export GOAL_SLUG=arc8-dev-process
export PHASE=analysis
export AGENT_NAME=pipeline-analyst
export UPSTREAM_TASK_ID="$TASK_ID"
```

Now invoke `/pipeline-gate`. Do not emit any STATUS line yourself — the gate
emits the final `STATUS: DONE` (pass) or `STATUS: BLOCKED` (fail) for this task.

# History
