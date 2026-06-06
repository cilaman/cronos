---
agent_mode: auto
agent_model: opus
claude_session_id: null
created_at: '2026-06-03T10:57:16Z'
depends_on:
- 2026-06-03-1057-pipeline-analyst-arc-8-sg3-dev-runtime-a
id: 2026-06-03-1057-pipeline-architect-arc-8-sg3-dev-runtime
manual_order: 0
parent_id: 2026-06-03-1057-arc8-dev-api
pending_messages: []
pr_url: null
priority: 2
proposed_pr_path: null
space_id: cronos-development
state: backlog
title: 'pipeline-architect: Arc 8/SG3 — dev runtime API + SSE log stream'
type: task
updated_at: '2026-06-03T10:57:16Z'
waiting_question: null
---

# Brief

# Phase 3 — design: Arc 8/SG3 — dev runtime API + SSE log stream

Goal slug: `arc8-dev-api` · Pipeline dir: `.cronos/pipeline/arc8-dev-api/` · Sub-agent: `pipeline-architect`.

Map every requirement to an iteration. Emits `design-report-{slug}.md` (class=design) with topologically-ordered `iterations[]` and a `risks[]` register.

## Step 1 — spawn the sub-agent

Use the `Agent` tool with `subagent_type="pipeline-architect"` and the brief below.
The sub-agent writes its CC-v1 artifact under `.cronos/pipeline/arc8-dev-api/` and returns a
short conversational summary; do not paraphrase or post-process its output here.

```text
slug   = arc8-dev-api
space  = $SPACE_DIR    (resolved from $PWD as in Step 2)
analysis_report_path = .cronos/pipeline/arc8-dev-api/analysis-report-arc8-dev-api.md
scout_report_path    = .cronos/pipeline/arc8-dev-api/scout-report-arc8-dev-api.md
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
export GOAL_SLUG=arc8-dev-api
export PHASE=design
export AGENT_NAME=pipeline-architect
export UPSTREAM_TASK_ID="$TASK_ID"
```

Now invoke `/pipeline-gate`. Do not emit any STATUS line yourself — the gate
emits the final `STATUS: DONE` (pass) or `STATUS: BLOCKED` (fail) for this task.

# History
