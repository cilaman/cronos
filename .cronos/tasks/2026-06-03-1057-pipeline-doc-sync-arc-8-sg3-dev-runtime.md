---
agent_mode: auto
agent_model: haiku
claude_session_id: null
created_at: '2026-06-03T10:57:16Z'
depends_on:
- 2026-06-03-1057-pipeline-reviewer-arc-8-sg3-dev-runtime
id: 2026-06-03-1057-pipeline-doc-sync-arc-8-sg3-dev-runtime
manual_order: 0
parent_id: 2026-06-03-1057-arc8-dev-api
pending_messages: []
pr_url: null
priority: 2
proposed_pr_path: null
space_id: cronos-development
state: backlog
title: 'pipeline-doc-sync: Arc 8/SG3 — dev runtime API + SSE log stream'
type: task
updated_at: '2026-06-03T10:57:16Z'
waiting_question: null
---

# Brief

# Phase 7 — doc: Arc 8/SG3 — dev runtime API + SSE log stream

Goal slug: `arc8-dev-api` · Pipeline dir: `.cronos/pipeline/arc8-dev-api/` · Sub-agent: `pipeline-doc-sync`.

Update documentation for the implementation diff. Emits `doc-report-{slug}.md` (class=doc)
with `intentionally_not_updated[]` always present. **Intermediate phase** — commits
to `feature/arc-8-dev-runtimes` but does NOT merge to main (SG4's doc phase does that).

## Step 1 — spawn the sub-agent

Use the `Agent` tool with `subagent_type="pipeline-doc-sync"` and the brief below.
The sub-agent writes its CC-v1 artifact under `{PIPELINE_REL}/` and returns a
short conversational summary; do not paraphrase or post-process its output here.

```text
slug   = arc8-dev-api
space  = $SPACE_DIR    (resolved from $PWD as in Step 2)
review_report_path = .cronos/pipeline/arc8-dev-api/review-report-arc8-dev-api--attempt<final_k>.md
impl_report_paths  = [<paths to every impl-report-arc8-dev-api--*.md>]
```

Wait for the sub-agent to return. Do not read the artifact body yourself — the
gate (Step 2) verifies it mechanically.

## Step 2 — close the gate (on PASS continue to Step 3)

Set the inputs and invoke the [[pipeline-gate]] skill. The gate validates the
artifact and records phase metrics into `pipeline-state.json`.

```bash
TASK_ID=$(basename "$PWD")
SPACE_DIR=$(echo "$PWD" | sed 's|/.cronos/workspaces/.*||')
export GOAL_SLUG=arc8-dev-api
export PHASE=doc
export AGENT_NAME=pipeline-doc-sync
export UPSTREAM_TASK_ID="$TASK_ID"
```

Invoke `/pipeline-gate`. Check the outcome:
- **Exit 0 (pass)**: gate records state — do NOT emit STATUS yet, continue to Step 3.
- **Any other exit**: gate emits `STATUS: BLOCKED` — this is the final status; stop.

## Step 3 — commit to the shared feature branch

This is an **intermediate** subgoal (Arc 8 SG1-SG3). Do **not** merge to main —
SG4's doc phase handles the final `/goal-finalize` merge.

Invoke `/goal-task-commit` to push any documentation changes to
`feature/arc-8-dev-runtimes` (the skill resolves the root umbrella goal dynamically).

Then emit: `STATUS: DONE`

# History
