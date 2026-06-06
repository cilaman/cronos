---
agent_mode: auto
agent_model: sonnet
claude_session_id: null
created_at: '2026-06-03T10:26:56Z'
depends_on:
- 2026-06-03-1026-pipeline-implementor-arc-7-s2-mcp-mail-t
id: 2026-06-03-1026-tester-arc-7-s2-mcp-mail-tools-mount-int
manual_order: 0
parent_id: 2026-06-03-1026-arc7-agent-mail-tools
pending_messages: []
pr_url: null
priority: 1
proposed_pr_path: null
space_id: cronos-development
state: backlog
title: 'tester: Arc 7/S2 — MCP mail tools + mount into agent runs'
type: task
updated_at: '2026-06-03T10:26:56Z'
waiting_question: null
---

# Brief

# Phase 5 — test: Arc 7/S2 — MCP mail tools + mount into agent runs

Goal slug: `arc7-agent-mail-tools` · Pipeline dir: `.cronos/pipeline/arc7-agent-mail-tools/` · Sub-agent: `tester`.

## Step 1 — spawn the tester sub-agent

Use the `Agent` tool with `subagent_type="tester"`. Pass:

```text
space_id  = cronos-development
scope     = full-space
slug      = arc7-agent-mail-tools
```

The tester runs pytest + vitest, parses coverage, POSTs a TestReport, and
emits CC-v1 `test-report-arc7-agent-mail-tools.md` under `.cronos/pipeline/arc7-agent-mail-tools/`.

## Step 2 — close the gate

Set the inputs and invoke the [[pipeline-gate]] skill. The gate validates the
artifact, records phase metrics into `pipeline-state.json`, and emits the final
`STATUS:` line for this task.

```bash
TASK_ID=$(basename "$PWD")
SPACE_DIR=$(echo "$PWD" | sed 's|/.cronos/workspaces/.*||')
export GOAL_SLUG=arc7-agent-mail-tools
export PHASE=test
export AGENT_NAME=tester
export UPSTREAM_TASK_ID="$TASK_ID"
```

Now invoke `/pipeline-gate`. Do not emit any STATUS line yourself — the gate
emits the final `STATUS: DONE` (pass) or `STATUS: BLOCKED` (fail) for this task.

# History
