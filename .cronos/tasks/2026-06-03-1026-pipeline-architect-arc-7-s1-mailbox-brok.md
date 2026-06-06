---
agent_mode: auto
agent_model: opus
claude_session_id: null
created_at: '2026-06-03T10:26:56Z'
depends_on:
- 2026-06-03-1026-pipeline-analyst-arc-7-s1-mailbox-broker
id: 2026-06-03-1026-pipeline-architect-arc-7-s1-mailbox-brok
manual_order: 0
parent_id: 2026-06-03-1026-arc7-mailbox-broker
pending_messages: []
pr_url: null
priority: 1
proposed_pr_path: null
space_id: cronos-development
state: backlog
title: 'pipeline-architect: Arc 7/S1 — Mailbox broker + persistence + API'
type: task
updated_at: '2026-06-03T10:26:56Z'
waiting_question: null
---

# Brief

# Phase 3 — design: Arc 7/S1 — Mailbox broker + persistence + API

Goal slug: `arc7-mailbox-broker` · Pipeline dir: `.cronos/pipeline/arc7-mailbox-broker/` · Sub-agent: `pipeline-architect`.

Map every requirement to an iteration. Emits `design-report-{slug}.md` (class=design) with topologically-ordered `iterations[]` and a `risks[]` register.

## Step 1 — spawn the sub-agent

Use the `Agent` tool with `subagent_type="pipeline-architect"` and the brief below.
The sub-agent writes its CC-v1 artifact under `.cronos/pipeline/arc7-mailbox-broker/` and returns a
short conversational summary; do not paraphrase or post-process its output here.

```text
slug   = arc7-mailbox-broker
space  = $SPACE_DIR    (resolved from $PWD as in Step 2)
analysis_report_path = .cronos/pipeline/arc7-mailbox-broker/analysis-report-arc7-mailbox-broker.md
scout_report_path    = .cronos/pipeline/arc7-mailbox-broker/scout-report-arc7-mailbox-broker.md
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
export GOAL_SLUG=arc7-mailbox-broker
export PHASE=design
export AGENT_NAME=pipeline-architect
export UPSTREAM_TASK_ID="$TASK_ID"
```

Now invoke `/pipeline-gate`. Do not emit any STATUS line yourself — the gate
emits the final `STATUS: DONE` (pass) or `STATUS: BLOCKED` (fail) for this task.

# History
