---
agent_mode: auto
agent_model: sonnet
claude_session_id: f1e742da-a1cc-4aea-bab1-bdc9bc0f5891
created_at: '2026-06-03T16:31:36Z'
depends_on:
- 2026-06-03-1631-pipeline-architect-features-fixes-s3-git
feature_key: null
feature_state: null
id: 2026-06-03-1631-pipeline-implementor-features-fixes-s3-g
issue_number: null
issue_url: null
manual_order: 0
parent_id: 2026-06-03-1631-featurefix-github-issues
pending_messages: []
pr_url: null
priority: 2
proposed_issue_path: null
proposed_pr_path: null
realizes: null
space_id: cronos-development
state: archived
title: 'pipeline-implementor: Features&Fixes/S3 — GitHub issue mirror (one-way)'
type: task
updated_at: '2026-06-19T12:17:48Z'
waiting_question: null
---

# Brief

# Phase 4 — implementation: Features&Fixes/S3 — GitHub issue mirror (one-way)

Goal slug: `featurefix-github-issues` · Pipeline dir: `.cronos/pipeline/featurefix-github-issues/` · Sub-agent: `pipeline-implementor`.

Execute every entry of the design's `iterations[]` array. Each iteration gets its own
implementor invocation AND its own [[pipeline-gate]] call.

## Step 1 — set up the feature branch (once)

Invoke `/goal-branch-setup` first so all edits land on `feature/features-and-fixes`.
**The root goal for this entire arc is `features-and-fixes`; goal-branch-setup resolves that
automatically by walking parent_id up to the topmost goal.**

## Step 2 — read design report and topologically order iterations

Read `.cronos/pipeline/featurefix-github-issues/design-report-featurefix-github-issues.md` YAML header. Extract `iterations[]`.
Apply Kahn's algorithm; pick the lowest layer not yet executed.

## Step 3 — for EACH iteration

For each iteration `iter`:

1. Spawn implementor via `Agent` tool, `subagent_type="pipeline-implementor"`:
   ```text
   slug               = featurefix-github-issues--<iter.id.lower()>
   space              = $SPACE_DIR
   design_report_path = .cronos/pipeline/featurefix-github-issues/design-report-featurefix-github-issues.md
   iteration_id       = <iter.id>
   ```

2. Close gate with [[pipeline-gate]]:
   ```bash
   TASK_ID=$(basename "$PWD")
   SPACE_DIR=$(echo "$PWD" | sed 's|/.cronos/workspaces/.*||')
   export GOAL_SLUG=featurefix-github-issues
   export PHASE=implementation
   export AGENT_NAME=pipeline-implementor
   export UPSTREAM_TASK_ID="$TASK_ID"
   export ITERATION_ID=<iter.id>
   ```
   Invoke `/pipeline-gate`. If `STATUS: BLOCKED`, halt.

## Step 4 — commit + final status

If every iteration passed: invoke `/goal-task-commit` to push to `feature/features-and-fixes`.
Emit `STATUS: DONE`.

# History

```
2026-06-04T19:25:32Z [agent]
I'll start by reading the design report to understand the iterations to implement.

The design has 4 iterations: I1 and I2 are independent (layer 0), I3 depends on both, I4 depends on I3. Let me set up the feature branch first.

Setting up the feature branch now.

The feature branch is checked out in another worktree. Per the project pattern, I'll work in the main worktree directly.

Good - S1 and S2 are done. The feature branch is in the S1 worktree. I'll work with files from that worktree. Let me examine the key existing files.

Now I have all the context I need. Let me run I1 and I2 in parallel using implementor sub-agents.

I1 is done. Now running I2 (independent of I1):

Both I1 and I2 are done. Now I need to run pipeline-gate for each. Let me run them in parallel.

Gate I1 PASS. Now gate I2:

Both I1 and I2 gates passed. Now implementing I3 (depends on I1 + I2):

I3 is done. Now running the gate for I3:

Gate I3 PASS. Now implementing I4:

All 4 iterations complete. Running gate for I4:

All 4 gates passed. Now committing to the feature branch:

Good. Let me run the new tests quickly to verify they pass:

All 55 tests pass. Committing to feature branch:

All 4 iterations implemented and gated (I1–I4), committed and pushed to `feature/features-and-fixes`.

**Summary:**
- **I1**: `git_issues.py` — `gh_issue_upsert` + `gh_issue_close` with gh CLI guard, asyncio subprocess, permissive URL regex, 60s timeout, FileNotFoundError catch (15 tests pass)
- **I2**: `storage.py` — `set_issue_refs` method mirroring `set_pr_refs` (7 tests pass)  
- **I3**: `feature_hooks.py` — full `mirror_feature_to_github` body with MD-before-gh ordering, set_issue_refs persistence, conditional close on DONE, broad try/except (12 tests pass)
- **I4**: `test_features_api_mirror_fire.py` — 21 tests verifying all 4 `_fire_mirror` call sites and reason strings

All pipeline gates: PROCEED ✓

STATUS: DONE
```
