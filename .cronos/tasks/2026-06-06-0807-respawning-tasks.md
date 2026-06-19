---
agent_mode: auto
agent_model: opus-4-8
claude_session_id: 55ee3a31-e5f1-4b79-b501-8d2bdd643168
created_at: '2026-06-06T08:07:48Z'
depends_on: []
feature_key: null
feature_state: null
id: 2026-06-06-0807-respawning-tasks
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
updated_at: '2026-06-13T08:30:16Z'
waiting_question: null
---

# Brief

Some tasks and goal executed recently are respawning to active and waiting after app upgrade. Seems like the state is not persisted correctly

# History

```
2026-06-06T08:29:34Z [agent] run=0 model=claude-opus-4-8 mode=auto
I'll investigate why tasks/goals respawn to active/waiting after an app upgrade. Let me start by understanding how state is persisted and loaded.

Let me investigate how the worker recovers state on startup, since the respawning happens after restart.

Let me look at the startup logic in main.py and how the worker pool resumes tasks on boot.

The recovery re-enqueues ACTIVE tasks — that's intended. The bug is that recently-DONE tasks come back. Let me look at how state transitions get persisted to disk.

State is markdown-on-disk + SQLite index. Let me look at how state is read on startup (reload_all/board) and the write path in transition/finalize_run.

Writes are atomic and markdown is authoritative. Let me check how the store loads on startup — whether it trusts markdown or possibly-stale SQLite — and how dump/parse round-trips `state`.

Startup reads state from markdown (authoritative), so a respawn means markdown said ACTIVE/WAITING at restart. Let me trace the goal lifecycle in the worker to see how a "done" goal could be left ACTIVE/WAITING on disk.

Let me look at goal_sync propagation and how/where the goal gets set ACTIVE, plus the enqueue path.

Let me look at the worker's main run loop, where it dequeues and where propagate_to_parent is called.

Let me find the main loop and the dequeue→ACTIVE→run→finalize path.

Let me look at the upgrade webhook mechanism to understand the restart timing relative to in-flight finalization.

The upgrade does `git reset --hard origin/main` + rebuild + `systemctl restart`. So the container is killed; in-flight agent runs die. Let me confirm what `board.active` contains and check the graceful-shutdown path.

`board.active` includes ACTIVE goals and tasks. Let me check the worker stop path and how SIGTERM is handled during restart.

This is promising — `upgrade.sh` runs `git reset --hard origin/main` in the space directory. If task `.md` files are git-tracked, that reset would revert recent on-disk state changes. Let me check whether task state files are tracked in git.

`/data` is the container data volume, but the cronos-development space *is* this git repo. Let me check whether `.cronos/` task files are git-tracked — if so, `git reset --hard` in upgrade.sh would revert their state.

Confirmed — `.cronos/` is git-tracked (1551 files). Let me confirm task state files specifically are tracked and check the worker's commit pattern.

Root cause confirmed: 428 task `.md` files (with `state:` frontmatter) are git-tracked under `.cronos/tasks/`, and `upgrade.sh` runs `git reset --hard origin/main` in the space directory. Let me verify the deployment topology — whether the data volume and the code checkout are the same directory.

Let me verify the actual topology — whether the live runtime data the container reads is the same as the git-tracked files, and whether `data/` is tracked.

Let me check the smoking gun — whether the live space (main worktree) currently has uncommitted state changes to tracked task files that a `reset --hard` would revert.

Confirmed. 9 tracked task files have uncommitted modifications in the live space. Let me verify these are state changes that `reset --hard` would revert.

Root cause is definitively confirmed. The committed copy says `state: active`, the live working copy says `state: done` — `git reset --hard origin/main` in `upgrade.sh` reverts it, so the task respawns to active on restart. Let me scope which `.cronos/` subdirs are tracked runtime state.

Root cause is definitively confirmed. Here's the diagnosis:

## Root cause: `git reset --hard` in upgrade.sh reverts live task state

The cronos-development space directory **is** a git working tree, and the live task-state files (`.cronos/tasks/*.md`, whose `state:` frontmatter the worker reads on startup and rewrites on every transition) are **git-tracked** (428 files).

The chain:
1. Worker writes a task `active → done` to `.cronos/tasks/<id>.md` on disk (uncommitted working-tree change). Persistence here is correct — atomic write.
2. `upgrade.sh` runs `git reset --hard origin/main`, which **discards all uncommitted working-tree changes** to tracked files.
3. Every task `.md` reverts to its last-committed state (often `active`/`waiting`/`backlog` from when it was committed mid-flight).
4. On restart, `reload_all` reads the reverted markdown; the startup recovery loop (`main.py:503`) re-enqueues every `ACTIVE` task → they re-run → "respawning to active and waiting."

**Smoking gun** I verified in the live space right now:
```
.cronos/tasks/2026-06-05-2327-harness-editor-usability.md
  committed: state: active
  working:   state: done      ← reset --hard would revert done → active
```
9 tracked task files currently carry uncommitted `done`/state changes that the next upgrade would wipe. The same applies to `.cronos/traces/`, `stats/`, `harness-runs/`, etc. (all tracked runtime state), but tasks/goals are what respawn.

There's no backend persistence bug — the corruption is external (the deploy script). Two ways to fix it, with a real trade-off, so I'd like your call before changing anything:

The interactive prompt didn't return an answer (worker context). I'll implement the lowest-risk fix that fully resolves the brief: harden the upgrade script to preserve live runtime state across `git reset --hard`. Let me check both upgrade scripts first.

Both `upgrade.sh` (active, via webhook) and `deploy/upgrade.sh` (canonical, installed to host) run `git reset --hard origin/main`. I'll add runtime-state preservation to both. Let me start a task list and implement.

I'll implement the fix directly. Editing the active `upgrade.sh` first.

Now the canonical `deploy/upgrade.sh`:

Now let me validate both scripts with `bash -n` and a functional dry-run of the preserve/restore logic in a throwaway git repo.

Let me functionally verify the preserve→reset→restore logic protects a tracked task file's live state from `git reset --hard`, using a throwaway repo.

The fix works: after the upgrade, **code updates to v2** (upgrade succeeds) while **live task state stays `done`** (no respawn). Without the restore, the task reverts `done → active` — exactly the bug.

Let me check there are no other `git reset --hard` paths against the space that could cause the same clobber.

Only the two upgrade scripts reset the space repo (discovery.py resets a separate tool-source clone). Both are fixed. Let me check whether this task is standalone or under a goal before finalizing.

This is a standalone task (no parent goal). Let me invoke the mandatory finalize skill to handle verification, git, memory, and the STATUS marker.

This is a standalone task. My edits are in the workspace worktree; I need them committed to `main` in the space dir. I'll copy only the two changed files (not `git add -A`, which would sweep in live task-state churn — the exact noise this fix is about). Let me check the space dir's branch and current diff first.

The space dir is on a stale feature branch with live task-state changes — I won't disturb it. Instead I'll commit the two files from this workspace worktree and push directly to `main` (`HEAD:main`), which is how prior tasks landed on main without checking it out. Let me verify the workspace's git status and that it's based on current main.

Clean — only my two files are modified, and HEAD is exactly origin/main. I'll commit and push directly to main.

Pushed to main (`8c2c416..6146654`). Let me record this non-obvious root cause in auto-memory for future sessions.

## Summary

**Root cause:** Not a backend persistence bug — the corruption was external. The cronos-development space directory *is* the git working tree, and the worker writes live task/goal `state:` into git-**tracked** files at `.cronos/tasks/*.md`. The upgrade scripts ran `git reset --hard origin/main`, which discards uncommitted working-tree changes — reverting completed tasks from `done` back to their last-committed state (`active`/`waiting`). On restart, `main.py`'s recovery loop re-enqueues every ACTIVE task, so they re-run and respawn. I verified the smoking gun live: a task whose working copy said `state: done` while `git show HEAD:` said `state: active`.

**Fix (commit `6146654`, pushed to main):** Both `upgrade.sh` and `deploy/upgrade.sh` now snapshot `.cronos/{tasks,traces,stats,harness-runs,test-reports}` before the reset and restore them after. Workspaces are excluded (they hold git worktrees). I verified the logic in a throwaway repo: code updates correctly while live task state survives.

**Two caveats for the operator:**
1. The **first** upgrade after this commit still executes the *old* on-disk `upgrade.sh` (bash already loaded it), so it will clobber currently-live states one last time. Commit current task states or run the new `upgrade.sh` manually for the cutover. I did **not** auto-trigger the upgrade for this reason.
2. The deeper fix is to stop git-tracking `.cronos/` runtime state entirely (gitignore + `git rm --cached`), but that carries one-time cutover deletion risk and changes what `goal-task-commit` commits — a decision worth your call rather than doing unilaterally.

MEMORY[observation]: Respawning tasks after upgrade were caused by `git reset --hard origin/main` in upgrade.sh/deploy/upgrade.sh reverting git-tracked `.cronos/tasks/*.md` state (the space dir is the git working tree; worker writes `state:` into tracked files). Backend atomic writes were never buggy.
MEMORY[fact]: Fixed in commit 6146654 — both upgrade scripts snapshot `.cronos/{tasks,traces,stats,harness-runs,test-reports}` before reset and restore after; workspaces excluded (git worktrees).
MEMORY[procedure]: When committing a fix from a workspace worktree to main here, add specific files (never `git add -A` — it sweeps in live `.cronos/tasks` state churn) and push with `git push origin HEAD:main`.

STATUS: DONE
```
