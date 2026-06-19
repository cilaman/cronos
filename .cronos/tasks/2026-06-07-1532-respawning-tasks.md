---
agent_mode: auto
agent_model: default
claude_session_id: 798fbcac-504a-4588-bb56-e043d8cae1b8
created_at: '2026-06-07T15:32:07Z'
depends_on: []
feature_key: null
feature_state: null
id: 2026-06-07-1532-respawning-tasks
issue_number: null
issue_url: null
manual_order: 0
parent_id: null
pending_messages: []
pr_url: null
priority: 3
proposed_issue_path: null
proposed_pr_path: null
realizes: null
space_id: cronos-development
state: archived
title: Respawning tasks
type: task
updated_at: '2026-06-15T05:30:16Z'
waiting_question: null
---

# Brief

After upgrade of the app the tasks and goals keep respawning to various states. 
Upgrade:
rm -rf /home/cronos/.docker
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR" && pwd)"

cd "$REPO_ROOT"

# This repo checkout doubles as the live cronos-development space, so the worker
# writes task/goal state (and traces, stats, harness runs) into git-TRACKED files
# under .cronos/. `git reset --hard` reverts tracked files to the committed
# revision, which would roll completed work back to active/waiting and make it
# "respawn" after the restart. Snapshot these runtime dirs, then restore them
# after the reset so persisted state survives the upgrade. Workspaces are
# excluded on purpose — they contain git worktrees that must not be copied.
RUNTIME_STATE_DIRS=(
  .cronos/tasks
  .cronos/traces
  .cronos/stats
  .cronos/harness-runs
  .cronos/test-reports
)
STATE_BACKUP="$(mktemp -d)"
for d in "${RUNTIME_STATE_DIRS[@]}"; do
  [ -d "$d" ] || continue
  mkdir -p "$STATE_BACKUP/$(dirname "$d")"
  cp -a "$d" "$STATE_BACKUP/$d"
done

echo "==> Fetching latest main..."
git -c safe.directory="$(pwd)" fetch origin
git -c safe.directory="$(pwd)" reset --hard origin/main

echo "==> Restoring live runtime state preserved across the reset..."
for d in "${RUNTIME_STATE_DIRS[@]}"; do
  [ -d "$STATE_BACKUP/$d" ] || continue
  rm -rf "$d"
  mkdir -p "$(dirname "$d")"
  cp -a "$STATE_BACKUP/$d" "$d"
done
rm -rf "$STATE_BACKUP"

echo "==> Resolving build metadata..."
COMMIT_SHA=$(git -c safe.directory="$(pwd)" rev-parse --short HEAD)
BUILD_TIME=$(date -u +%Y-%m-%dT%H:%M:%SZ)
REPO_URL=$(git -c safe.directory="$(pwd)" remote get-url origin | sed -E 's/^git@github\.com:/https:\/\/github.com\//; s/\.git$//')

echo "    commit : $COMMIT_SHA"
echo "    time   : $BUILD_TIME"
echo "    repo   : $REPO_URL"

ENV_FILE=".env"
[ -f "$ENV_FILE" ] || ENV_FILE="/opt/cronos/.env"
[ -f "$ENV_FILE" ] || { echo "ERROR: .env not found at $(pwd)/.env or /opt/cronos/.env"; exit 1; }

echo "==> Building images..."
docker compose \
  --env-file "$ENV_FILE" \
  -f docker-compose.yml \
  -f docker-compose.prod.yml \
  build \
  --build-arg BUILD_COMMIT="$COMMIT_SHA" \
  --build-arg BUILD_TIME="$BUILD_TIME" \
  --build-arg BUILD_REPO_URL="$REPO_URL" \
  --build-arg VITE_BUILD_COMMIT="$COMMIT_SHA" \
  --build-arg VITE_BUILD_TIME="$BUILD_TIME" \
  --build-arg VITE_BUILD_REPO_URL="$REPO_URL"

echo "==> Restarting service..."
sudo systemctl restart cronos.service

echo "==> Upgrade complete (commit $COMMIT_SHA)."

# History

```
2026-06-07T15:51:53Z [agent] run=0 model=claude-sonnet-4-6 mode=auto agents=explore
Let me start by investigating the respawning issue. I'll look at the upgrade script, task storage, and worker to understand what's happening.

I'll explore the codebase to understand what causes tasks to respawn after upgrades.

Let me examine the recent commits and the specific worker code in detail.

Let me read the exact code directly to verify the analysis before designing a fix.

Let me read more of the worker.py around the auto-repair feature and startup code.

Let me read the full `while True` loop added by the auto-repair commit to see the exact structure.

I need to read from the workspace branch, not the main repo.

Now I have a clear understanding of the issue. Let me write the plan.

The root cause: When an upgrade happens while a goal `G` is actively orchestrating a child task `C` (both in ACTIVE state), the upgrade script preserves both as ACTIVE. On restart, `main.py` re-enqueues ALL active tasks. Since the worker is sequential per-space, if `G` is processed before `C`, `_run_goal(G)` finds `C` in ACTIVE state and erroneously treats it as a failure ("Child X is in active state and needs attention"), sending `G` to WAITING. Then `C` runs normally, finishes, `goal_sync` reactivates `G`, and `G` runs again to completion. This ACTIVE→WAITING→ACTIVE→DONE cycle is the "respawning" behavior.

Let me verify the exact line numbers and check existing tests before finalizing the plan.

Now let me verify the exact lines in main.py where the startup code lives in the workspace.

Good. Now let me check if `task_store.board()` has a method to get tasks typed (to check their type).

`TaskSummary` has `type` field directly - no need to call `task_store.get()` in main.py. Let me update the plan with the simpler sorting approach.

Now I have all the exact line numbers. The plan is correct. Let me exit plan mode.

**Plan summary:**

**Root cause:** After upgrade, both a goal `G` and its child `C` are preserved as ACTIVE. On restart, both are re-enqueued. If `G` is processed first (by the sequential per-space worker), `_run_goal()` hits the `child.state != BACKLOG` guard (line 1501), treats `C` in ACTIVE state as a failure, sends `G` to WAITING with "Child X is in active state and needs attention." Then `C` runs, finishes, `goal_sync` reactivates `G`, and `G` runs again to DONE. This ACTIVE→WAITING→ACTIVE→DONE cycle is the respawning.

**Three-part fix** (all in the workspace, `backend/app/worker.py` and `backend/app/main.py`):

1. **`_run_goal()` child loop** — when a child is in ACTIVE state, treat it as "in-flight" rather than a failure: set `fail_reason = None` so the goal goes to WAITING silently (no alarming user-visible error). `goal_sync` handles the re-enqueue when the child finishes.

2. **`_run_goal()` early-exit guard** — add a DONE check at entry so that if `G` gets double-enqueued (by startup + `goal_sync`), the second run is a no-op instead of redundantly writing history.

3. **Startup re-enqueue ordering** (`main.py` lines 503–513) — sort `board.active` so leaf tasks are enqueued before goal tasks. Since the worker is sequential per-space, this means children usually complete before their parent goal is processed, making the whole thing clean in the common case.
```

```
2026-06-07T15:59:40Z [user]
Implement the plan to main
```

```
2026-06-07T16:05:16Z [agent] run=1 model=claude-sonnet-4-6 mode=auto
I'll implement all three parts. Let me start with the two changes to `worker.py` and one to `main.py`.

Now the ACTIVE-child in-flight fix in the loop:

Now fix the summary to handle `fail_reason = None`:

Now fix `main.py` to sort leaf tasks before goal tasks:

Now add a test for the new in-flight ACTIVE child behavior. Let me find the right place in the test file:

Now add a test for the DONE guard:

Now run the tests to verify everything passes:

68 tests pass. The coverage floor failure is only because I ran a subset — let me verify with the full suite:

All 2474 tests pass. Now I'll finalize the task — commit, push to main, and upgrade.

## Step 1 — Verify completion

All three parts implemented and 2474 tests pass. ✓

## Step 3 — Handle git

Only stage the code changes, not the runtime `.cronos/` state files:

The three code files are staged. Committing:

The commit failed because my edits were in the workspace, not the main worktree. Let me check the main repo's state:

Good, changes staged in workspace context. Now commit and push to origin/main:

Pushed to origin/main. Now upgrade the running instance:

## Step 4 — Write memory

MEMORY[fact]: Goal respawning fix: `_run_goal()` in `backend/app/worker.py` now treats ACTIVE children as "in-flight" (fail_reason=None, no waiting_question) instead of "needs attention" error. Added DONE guard at entry. `main.py` startup sorts leaf tasks before goal tasks in re-enqueue order. 2 new tests added.

## Step 5 — Emit STATUS

STATUS: DONE
```

```
2026-06-08T04:39:01Z [user]
What is the commit in main
```

```
2026-06-08T04:39:10Z [agent] run=2 model=claude-sonnet-4-6 mode=auto
`4c6a133` — "fix: prevent goal respawning after upgrade when children are in-flight"
```
