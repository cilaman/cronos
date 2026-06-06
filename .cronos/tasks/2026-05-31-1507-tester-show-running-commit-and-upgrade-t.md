---
agent_mode: auto
agent_model: sonnet
claude_session_id: 8f81e6e5-8fee-45cb-a38a-ce1c3910c4aa
created_at: '2026-05-31T15:07:53Z'
depends_on:
- 2026-05-31-1507-pipeline-implementor-show-running-commit
id: 2026-05-31-1507-tester-show-running-commit-and-upgrade-t
manual_order: 0
parent_id: 2026-05-31-1507-showing-commit
pending_messages: []
pr_url: null
priority: 2
proposed_pr_path: null
space_id: cronos-development
state: done
title: 'tester: Show running commit and upgrade time in the sidebar'
type: task
updated_at: '2026-05-31T16:01:53Z'
waiting_question: null
---

# Brief

# Phase 5 — test: Show running commit and upgrade time in the sidebar

Goal slug: `showing-commit` · Pipeline dir: `.cronos/pipeline/showing-commit/` · Sub-agent: `tester`.

## Step 1 — spawn the tester sub-agent

Use the `Agent` tool with `subagent_type="tester"`. Pass:

```text
space_id  = cronos-development
scope     = full-space
slug      = showing-commit     # makes the tester emit test-report-{slug}.md too
```

The tester runs pytest + vitest, parses coverage, POSTs a TestReport to
`{backend}/api/test-reports`, and (because slug is set) ALSO emits a
CC-v1 `test-report-showing-commit.md` artifact under `.cronos/pipeline/showing-commit/`.

## Step 2 — close the gate

Set the inputs and invoke the [[pipeline-gate]] skill. The gate validates the
artifact, records phase metrics into `pipeline-state.json`, and emits the final
`STATUS:` line for this task.

```bash
TASK_ID=$(basename "$PWD")
SPACE_DIR=$(echo "$PWD" | sed 's|/.cronos/workspaces/.*||')
export GOAL_SLUG=showing-commit
export PHASE=test
export AGENT_NAME=tester
export UPSTREAM_TASK_ID="$TASK_ID"
```

Now invoke `/pipeline-gate`. Do not emit any STATUS line yourself — the gate
emits the final `STATUS: DONE` (pass) or `STATUS: BLOCKED` (fail) for this task.

# History

```
2026-05-31T16:01:53Z [agent]
I'll spawn the tester sub-agent first, then close the gate with the pipeline-gate skill.

Tests passed — 1934 tests, 82.54% coverage. Now closing the gate.

gate PASS — test / showing-commit
  artifact: .cronos/pipeline/showing-commit/test-report-showing-commit.md

STATUS: DONE
```
