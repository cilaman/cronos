---
agent_mode: auto
agent_model: opus
claude_session_id: 66812c9f-5e0e-405b-9849-da38255ebbc4
created_at: '2026-06-03T11:04:55Z'
depends_on:
- 2026-06-03-1104-pipeline-analyst-6-4-run-lifecycle-statu
feature_key: null
feature_state: null
id: 2026-06-03-1104-pipeline-architect-6-4-run-lifecycle-sta
issue_number: null
issue_url: null
manual_order: 0
parent_id: 2026-06-03-1104-arc6-run-lifecycle
pending_messages: []
pr_url: null
priority: 2
proposed_issue_path: null
proposed_pr_path: null
realizes: null
space_id: cronos-development
state: archived
title: 'pipeline-architect: 6.4 Run lifecycle status trigger API SSE'
type: task
updated_at: '2026-06-19T12:17:48Z'
waiting_question: null
---

# Brief

# Phase 3 — design: 6.4 Run lifecycle status trigger API SSE

Goal slug: `arc6-run-lifecycle` · Pipeline dir: `.cronos/pipeline/arc6-run-lifecycle/` · Sub-agent: `pipeline-architect`.

Map every requirement to an iteration. Emits `design-report-{slug}.md` (class=design) with topologically-ordered `iterations[]` and a `risks[]` register.

## Step 1 — spawn the sub-agent

Use the `Agent` tool with `subagent_type="pipeline-architect"` and the brief below.
The sub-agent writes its CC-v1 artifact under `.cronos/pipeline/arc6-run-lifecycle/` and returns a
short conversational summary; do not paraphrase or post-process its output here.

```text
slug   = arc6-run-lifecycle
space  = $SPACE_DIR    (resolved from $PWD as in Step 2)
analysis_report_path = .cronos/pipeline/arc6-run-lifecycle/analysis-report-arc6-run-lifecycle.md
scout_report_path    = .cronos/pipeline/arc6-run-lifecycle/scout-report-arc6-run-lifecycle.md
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
export GOAL_SLUG=arc6-run-lifecycle
export PHASE=design
export AGENT_NAME=pipeline-architect
export UPSTREAM_TASK_ID="$TASK_ID"
```

Now invoke `/pipeline-gate`. Do not emit any STATUS line yourself — the gate
emits the final `STATUS: DONE` (pass) or `STATUS: BLOCKED` (fail) for this task.

# History

```
2026-06-03T21:31:17Z [agent]
I'll spawn the pipeline-architect sub-agent for the design phase.

The architect emitted and self-verified the design report. Now closing the gate.

The shell env didn't persist. Let me re-export and run again.

Verifier exited 0 (proceed). Now recording state via state_writer.

gate PASS — design / arc6-run-lifecycle
  artifact: .cronos/pipeline/arc6-run-lifecycle/design-report-arc6-run-lifecycle.md

STATUS: DONE
```
