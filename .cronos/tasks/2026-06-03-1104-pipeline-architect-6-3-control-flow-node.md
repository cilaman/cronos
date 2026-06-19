---
agent_mode: auto
agent_model: opus
claude_session_id: ae4369b9-0b6d-4a9c-8467-38b404f6f0ae
created_at: '2026-06-03T11:04:55Z'
depends_on:
- 2026-06-03-1104-pipeline-analyst-6-3-control-flow-node-s
feature_key: null
feature_state: null
id: 2026-06-03-1104-pipeline-architect-6-3-control-flow-node
issue_number: null
issue_url: null
manual_order: 0
parent_id: 2026-06-03-1104-arc6-control-flow
pending_messages: []
pr_url: null
priority: 2
proposed_issue_path: null
proposed_pr_path: null
realizes: null
space_id: cronos-development
state: archived
title: 'pipeline-architect: 6.3 Control flow node semantics'
type: task
updated_at: '2026-06-19T12:17:48Z'
waiting_question: null
---

# Brief

# Phase 3 — design: 6.3 Control flow node semantics

Goal slug: `arc6-control-flow` · Pipeline dir: `.cronos/pipeline/arc6-control-flow/` · Sub-agent: `pipeline-architect`.

Map every requirement to an iteration. Emits `design-report-{slug}.md` (class=design) with topologically-ordered `iterations[]` and a `risks[]` register.

## Step 1 — spawn the sub-agent

Use the `Agent` tool with `subagent_type="pipeline-architect"` and the brief below.
The sub-agent writes its CC-v1 artifact under `.cronos/pipeline/arc6-control-flow/` and returns a
short conversational summary; do not paraphrase or post-process its output here.

```text
slug   = arc6-control-flow
space  = $SPACE_DIR    (resolved from $PWD as in Step 2)
analysis_report_path = .cronos/pipeline/arc6-control-flow/analysis-report-arc6-control-flow.md
scout_report_path    = .cronos/pipeline/arc6-control-flow/scout-report-arc6-control-flow.md
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
export GOAL_SLUG=arc6-control-flow
export PHASE=design
export AGENT_NAME=pipeline-architect
export UPSTREAM_TASK_ID="$TASK_ID"
```

Now invoke `/pipeline-gate`. Do not emit any STATUS line yourself — the gate
emits the final `STATUS: DONE` (pass) or `STATUS: BLOCKED` (fail) for this task.

# History

```
2026-06-03T20:20:13Z [agent]
Design report produced and self-verified. Closing the gate now.

gate PASS — design / arc6-control-flow
  artifact: .cronos/pipeline/arc6-control-flow/design-report-arc6-control-flow.md
  normalize: 3 fix(es) applied

STATUS: DONE
```
