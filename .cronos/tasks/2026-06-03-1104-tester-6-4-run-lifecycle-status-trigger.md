---
agent_mode: auto
agent_model: sonnet
claude_session_id: 3ee831b6-2d47-4c84-8bdd-0a7cb7fad245
created_at: '2026-06-03T11:04:55Z'
depends_on:
- 2026-06-03-1104-pipeline-implementor-6-4-run-lifecycle-s
id: 2026-06-03-1104-tester-6-4-run-lifecycle-status-trigger
manual_order: 0
parent_id: 2026-06-03-1104-arc6-run-lifecycle
pending_messages: []
pr_url: null
priority: 2
proposed_pr_path: null
space_id: cronos-development
state: done
title: 'tester: 6.4 Run lifecycle status trigger API SSE'
type: task
updated_at: '2026-06-03T22:24:48Z'
waiting_question: null
---

# Brief

# Phase 5 — test: 6.4 Run lifecycle status trigger API SSE

Goal slug: `arc6-run-lifecycle` · Pipeline dir: `.cronos/pipeline/arc6-run-lifecycle/` · Sub-agent: `tester`.

## Step 1 — spawn the tester sub-agent

Use the `Agent` tool with `subagent_type="tester"`. Pass:

```text
space_id  = cronos-development
scope     = full-space
slug      = arc6-run-lifecycle     # makes the tester emit test-report-{slug}.md too
```

The tester runs pytest + vitest, parses coverage, POSTs a TestReport to
`{backend}/api/test-reports`, and (because slug is set) ALSO emits a
CC-v1 `test-report-arc6-run-lifecycle.md` artifact under `.cronos/pipeline/arc6-run-lifecycle/`.

## Step 2 — close the gate

Set the inputs and invoke the [[pipeline-gate]] skill. The gate validates the
artifact, records phase metrics into `pipeline-state.json`, and emits the final
`STATUS:` line for this task.

```bash
TASK_ID=$(basename "$PWD")
SPACE_DIR=$(echo "$PWD" | sed 's|/.cronos/workspaces/.*||')
export GOAL_SLUG=arc6-run-lifecycle
export PHASE=test
export AGENT_NAME=tester
export UPSTREAM_TASK_ID="$TASK_ID"
```

Now invoke `/pipeline-gate`. Do not emit any STATUS line yourself — the gate
emits the final `STATUS: DONE` (pass) or `STATUS: BLOCKED` (fail) for this task.

# History

```
2026-06-03T22:24:48Z [agent]
I'll spawn the tester sub-agent to run the test suite for `arc6-run-lifecycle`, then close the pipeline gate.

Tester passed — 2709 tests, 83.24% coverage, gate_decision=pass. Now closing the pipeline gate.

Both steps passed — VERIFY_EXIT=0, PY_EXIT=0.

gate PASS — test / arc6-run-lifecycle
  artifact: .cronos/pipeline/arc6-run-lifecycle/test-report-arc6-run-lifecycle.md
  2709 tests passed, 83.24% coverage, gate_decision=proceed

STATUS: DONE
```
