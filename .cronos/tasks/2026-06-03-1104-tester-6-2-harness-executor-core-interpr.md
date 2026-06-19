---
agent_mode: auto
agent_model: sonnet
claude_session_id: 7718ffa7-4c3f-4d95-8085-c8f347db2695
created_at: '2026-06-03T11:04:55Z'
depends_on:
- 2026-06-03-1104-pipeline-implementor-6-2-harness-executo
feature_key: null
feature_state: null
id: 2026-06-03-1104-tester-6-2-harness-executor-core-interpr
issue_number: null
issue_url: null
manual_order: 0
parent_id: 2026-06-03-1104-arc6-executor
pending_messages: []
pr_url: null
priority: 2
proposed_issue_path: null
proposed_pr_path: null
realizes: null
space_id: cronos-development
state: archived
title: 'tester: 6.2 Harness executor core interpreter'
type: task
updated_at: '2026-06-19T12:17:48Z'
waiting_question: null
---

# Brief

# Phase 5 — test: 6.2 Harness executor core interpreter

Goal slug: `arc6-executor` · Pipeline dir: `.cronos/pipeline/arc6-executor/` · Sub-agent: `tester`.

## Step 1 — spawn the tester sub-agent

Use the `Agent` tool with `subagent_type="tester"`. Pass:

```text
space_id  = cronos-development
scope     = full-space
slug      = arc6-executor     # makes the tester emit test-report-{slug}.md too
```

The tester runs pytest + vitest, parses coverage, POSTs a TestReport to
`{backend}/api/test-reports`, and (because slug is set) ALSO emits a
CC-v1 `test-report-arc6-executor.md` artifact under `.cronos/pipeline/arc6-executor/`.

## Step 2 — close the gate

Set the inputs and invoke the [[pipeline-gate]] skill. The gate validates the
artifact, records phase metrics into `pipeline-state.json`, and emits the final
`STATUS:` line for this task.

```bash
TASK_ID=$(basename "$PWD")
SPACE_DIR=$(echo "$PWD" | sed 's|/.cronos/workspaces/.*||')
export GOAL_SLUG=arc6-executor
export PHASE=test
export AGENT_NAME=tester
export UPSTREAM_TASK_ID="$TASK_ID"
```

Now invoke `/pipeline-gate`. Do not emit any STATUS line yourself — the gate
emits the final `STATUS: DONE` (pass) or `STATUS: BLOCKED` (fail) for this task.

# History

```
2026-06-03T19:59:25Z [agent]
I'll spawn the tester sub-agent for arc6-executor, then close the pipeline gate.

Tests passed — 2467 tests, 83.33% coverage. Now closing the pipeline gate.

Both VERIFY_EXIT and PY_EXIT are 0. Gate passes.

gate PASS — test / arc6-executor
  artifact: .cronos/pipeline/arc6-executor/test-report-arc6-executor.md

STATUS: DONE
```
