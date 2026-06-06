---
agent_mode: auto
agent_model: haiku
claude_session_id: null
created_at: '2026-06-03T10:26:56Z'
depends_on:
- 2026-06-03-1026-pipeline-reviewer-arc-7-s2-mcp-mail-tool
id: 2026-06-03-1026-pipeline-doc-sync-arc-7-s2-mcp-mail-tool
manual_order: 0
parent_id: 2026-06-03-1026-arc7-agent-mail-tools
pending_messages: []
pr_url: null
priority: 1
proposed_pr_path: null
space_id: cronos-development
state: backlog
title: 'pipeline-doc-sync: Arc 7/S2 — MCP mail tools + mount into agent runs'
type: task
updated_at: '2026-06-03T10:26:56Z'
waiting_question: null
---

# Brief

# Phase 7 — doc: Arc 7/S2 — MCP mail tools + mount into agent runs

Goal slug: `arc7-agent-mail-tools` · Pipeline dir: `.cronos/pipeline/arc7-agent-mail-tools/` · Sub-agent: `pipeline-doc-sync`.

Update documentation for the implementation diff. Emits `doc-report-{slug}.md`
(class=doc). **IMPORTANT: Do NOT call /goal-finalize after the gate passes.**
The `feature/arc-7-messaging` branch is shared across all Arc 7 subgoals and
will be manually merged to `main` only after all four subgoals complete.

## Step 1 — spawn the sub-agent

Use the `Agent` tool with `subagent_type="pipeline-doc-sync"` and the brief below.

```text
slug   = arc7-agent-mail-tools
space  = $SPACE_DIR
review_report_path = .cronos/pipeline/arc7-agent-mail-tools/review-report-arc7-agent-mail-tools--attempt<final_k>.md
impl_report_paths  = [<paths to every impl-report-arc7-agent-mail-tools--*.md>]
```

## Step 2 — close the gate

Set the inputs and invoke the [[pipeline-gate]] skill. The gate validates the
artifact, records phase metrics into `pipeline-state.json`, and emits the final
`STATUS:` line for this task.

```bash
TASK_ID=$(basename "$PWD")
SPACE_DIR=$(echo "$PWD" | sed 's|/.cronos/workspaces/.*||')
export GOAL_SLUG=arc7-agent-mail-tools
export PHASE=doc
export AGENT_NAME=pipeline-doc-sync
export UPSTREAM_TASK_ID="$TASK_ID"
```

Now invoke `/pipeline-gate`. Do not emit any STATUS line yourself — the gate
emits the final `STATUS: DONE` (pass) or `STATUS: BLOCKED` (fail) for this task.


After the gate passes (STATUS: DONE from pipeline-gate), this task is complete.
Do NOT call /goal-finalize — the arc branch is managed manually.

# History
