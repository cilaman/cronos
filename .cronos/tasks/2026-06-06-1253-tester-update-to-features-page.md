---
agent_mode: auto
agent_model: sonnet
claude_session_id: f99e6837-6c04-4eea-9a83-7a9fe1940ffc
created_at: '2026-06-06T12:53:57Z'
depends_on:
- 2026-06-06-1253-pipeline-implementor-update-to-features
feature_key: null
feature_state: null
id: 2026-06-06-1253-tester-update-to-features-page
issue_number: null
issue_url: null
manual_order: 0
parent_id: 2026-06-06-1253-features-board-redesign
pending_messages: []
pr_url: null
priority: 2
proposed_issue_path: null
proposed_pr_path: null
realizes: null
space_id: cronos-development
state: archived
title: 'tester: Update to Features page'
type: task
updated_at: '2026-06-13T14:30:16Z'
waiting_question: null
---

# Brief

# Phase 5 — test: Update to Features page

Goal slug: `features-board-redesign` · Pipeline dir: `.cronos/pipeline/features-board-redesign/` · Sub-agent: `tester`.

## Step 1 — spawn the tester sub-agent

Use the `Agent` tool with `subagent_type="tester"`. Pass:

```text
space_id  = cronos-development
scope     = full-space
slug      = features-board-redesign     # makes the tester emit test-report-{slug}.md too
```

The tester runs pytest + vitest, parses coverage, POSTs a TestReport to
`{backend}/api/test-reports`, and (because slug is set) ALSO emits a
CC-v1 `test-report-features-board-redesign.md` artifact under `.cronos/pipeline/features-board-redesign/`.

## Step 2 — close the gate

Set the inputs and invoke the [[pipeline-gate]] skill. The gate validates the
artifact, records phase metrics into `pipeline-state.json`, and emits the final
`STATUS:` line for this task.

```bash
TASK_ID=$(basename "$PWD")
SPACE_DIR=$(echo "$PWD" | sed 's|/.cronos/workspaces/.*||')
export GOAL_SLUG=features-board-redesign
export PHASE=test
export AGENT_NAME=tester
export UPSTREAM_TASK_ID="$TASK_ID"
```

Now invoke `/pipeline-gate`. Do not emit any STATUS line yourself — the gate
emits the final `STATUS: DONE` (pass) or `STATUS: BLOCKED` (fail) for this task.

# History

```
2026-06-06T13:54:45Z [agent]
I'll spawn the tester sub-agent first, then close the pipeline gate.

The tester completed and wrote the CC-v1 artifact. Now I'll close the pipeline gate.

Verify passed. Now recording state and log.

Both `VERIFY_EXIT=0` and `PY_EXIT=0`. Gate passes.

gate PASS — test / features-board-redesign
  artifact: .cronos/pipeline/features-board-redesign/test-report-features-board-redesign.md

STATUS: DONE
```
