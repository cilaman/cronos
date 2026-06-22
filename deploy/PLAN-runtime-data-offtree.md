# Plan: Move runtime state out of the git working tree (Option B)

**Status:** Proposed — not implemented.
**Author/date:** drafted 2026-06-19.

## Problem / root cause

Old, already-closed or deleted tasks and goals reappear in the GUI after
application updates.

The source of truth for the board is **Markdown files on disk** (one `.md` per
task/goal under `.cronos/tasks/`; deletion is a soft-move to `.cronos/.trash/`).
The SQLite file `cronos-index.db` is only a throwaway index — `TaskStore.reload_all()`
([backend/app/storage.py:649](../backend/app/storage.py#L649)) wipes and rebuilds it
from the `.md` files on every startup.

The deployment couples this state to git in the worst possible way:

- The **repo checkout *is* a Cronos space.** `/opt/cronos/.cronos/` holds
  `space.yml`, `tasks/`, `harnesses/`, `traces/`, `stats/`, `pipeline/`, `qa/`,
  `issues/`, `.trash/` — **all tracked in git** (436 task files + the rest).
- The upgrade path runs `git reset --hard origin/main` **inside that live space**
  ([deploy/upgrade.sh:39-40](upgrade.sh#L39-L40)), reverting every tracked runtime
  file to the committed snapshot.
- The existing mitigation snapshots only **5 dirs** (`tasks`, `traces`, `stats`,
  `harness-runs`, `test-reports`) and restores them
  ([upgrade.sh:24-48](upgrade.sh#L24-L48)). Everything else tracked under `.cronos/`,
  plus any gap/failure in that hack, reverts to the committed state — resurrecting
  old/closed/deleted items. That partial-coverage band-aid is the leak.

## Objective

Make `git reset --hard` (and any other git op during upgrade) structurally
incapable of touching board state, by relocating all mutable runtime data to a
path git never sees. Then delete the snapshot/restore hack from `upgrade.sh`.

## Target architecture

- **Container path stays `/data`** (`CRONOS_DATA_DIR=/data` unchanged → zero
  backend code change; [agent.py:18](../backend/app/agent.py#L18),
  [main.py:49](../backend/app/main.py#L49)).
- **Host source moves off-tree:** `/opt/cronos/data` → **`/var/lib/cronos/data`**
  (outside any git repo).
- **The `cronos-development` space stops being the repo root.** It becomes a normal
  space under the off-tree data dir
  (`/var/lib/cronos/data/spaces/cronos-development/.cronos/…`), and code work happens
  in per-task git worktrees of a *separately cloned* repo — already how repo-linked
  spaces work ([git_ops.clone_into_space](../backend/app/git_ops.py#L136),
  [_worktree_path](../backend/app/git_ops.py#L220)).

The crux: today the code checkout and the live space are the same directory.
Option B's real work is **decoupling those two roles**. Pointing the bind mount
elsewhere is the easy 20%; relocating the dev space is the 80%.

## Decision: host bind-path, not a named volume

Use host path `/var/lib/cronos/data`, not a Docker named volume. Rationale:
[backup.sh](backup.sh) already tars a host directory
(`${CRONOS_DATA_DIR:-/opt/cronos/data}`), [VPS_SETUP.md](VPS_SETUP.md) documents a
host path, and a host path stays inspectable/greppable. A named volume would force
backup.sh and the docs to change more.

(Alternative: a named volume `cronos_data`. Only the migration copy step changes —
`mv` becomes `docker run … cp`; everything else is identical.)

## Phase 0 — Verify the live topology on the VPS (must run before touching anything)

The committed compose only mounts `./data:/data`, yet upgrade.sh treats the repo-root
`.cronos/` as live. Resolve that discrepancy on the box first:

1. `docker compose -f docker-compose.yml -f docker-compose.prod.yml config`
   → confirm the actual `backend` volume mounts and `CRONOS_DATA_DIR`.
2. On the host: `ls -la /opt/cronos/data/spaces` and
   `cat /opt/cronos/data/spaces/*/.cronos/space.yml` — does the live
   `cronos-development` space live under `data/spaces/…` or at the repo root `.cronos/`?
3. Confirm which directory the worker actually writes to (`stat` the newest file under
   both `/opt/cronos/.cronos/tasks` and `/opt/cronos/data/spaces/*/.cronos/tasks`).
4. Check for symlinks/extra mounts tying the repo root into the container.

The runbook below branches on the answer (case A: dev space already under `data/`;
case B: dev space *is* the repo root). Finalize exact `mv` paths once known.

## File changes (code/config — one PR)

1. **docker-compose.yml** — `./data:/data` → `${CRONOS_HOST_DATA_DIR:-./data}:/data`;
   set `CRONOS_HOST_DATA_DIR=/var/lib/cronos/data` in the VPS `.env`. Dev keeps `./data`.
2. **deploy/upgrade.sh** — delete the entire `RUNTIME_STATE_DIRS` snapshot/restore block
   ([lines 17-49](upgrade.sh#L17-L49)). With data off-tree, `git reset --hard` is safe
   and the hack is dead weight (and a future bug source).
3. **deploy/backup.sh** — default `SRC` → `/var/lib/cronos/data` (or set `CRONOS_DATA_DIR`
   in the backup unit env). Verify `cronos-backup.service` passes the new path.
4. **.gitignore** — add `/.cronos/` and `/data/` (keep `!data/.gitkeep` if needed).
5. **`git rm -r --cached .cronos data/tasks data/workspaces`** — untrack the 436 board
   files + legacy `data/` trees so they leave the reset target. Files stay on disk.
6. **Docs** — update [VPS_SETUP.md](VPS_SETUP.md) (data path, mkdir/chown of
   `/var/lib/cronos`, backup path) and the `data/` line in CLAUDE.md / README.

## Migration runbook (VPS — scheduled downtime)

1. Announce downtime; `sudo systemctl stop cronos.service`.
2. **Backup first:** `sudo systemctl start cronos-backup.service` (or manual `tar`)
   → confirm tarball in `/var/backups/cronos/`.
3. `sudo install -d -o cronos -g cronos /var/lib/cronos/data`.
4. **Move live data** (paths finalized from Phase 0):
   - Always: `mv /opt/cronos/data/* /var/lib/cronos/data/` (spaces, index db,
     tool_sources.yml).
   - **Case B (repo root is the dev space):** relocate `/opt/cronos/.cronos` →
     `/var/lib/cronos/data/spaces/cronos-development/.cronos`; ensure `space.yml` is
     intact so the loader registers it. Drop `workspaces/` (per-task worktrees) — they
     regenerate, never copied ([upgrade.sh:23](upgrade.sh#L23) already excludes them).
5. Pull the code-change PR; set `.env` `CRONOS_HOST_DATA_DIR=/var/lib/cronos/data`.
6. `git reset --hard origin/main` is now harmless to data.
7. `docker compose … up -d --build`.
8. Verify (below). Keep old `/opt/cronos/data` one window as safety; delete after a
   clean upgrade cycle.

## Verification (acceptance criteria)

1. GUI shows the same task/goal counts as before migration.
2. Delete a throwaway task → gone from GUI.
3. **Regression test:** run `deploy/upgrade.sh` (or `git fetch && git reset --hard
   origin/main` + restart) and confirm the deleted task **stays deleted** and no
   archived/closed item reverts to active. This proves the bug is fixed.
4. `git status` in `/opt/cronos` is clean after an upgrade.
5. Nightly backup writes a tarball of the new path.

## Rollback

Data is only *moved*, plus a fresh backup exists. To revert: stop stack,
`mv /var/lib/cronos/data/* /opt/cronos/data/`, unset `CRONOS_HOST_DATA_DIR`,
`git revert` the PR, restart. Pre-migration tarball is the last resort.

## Risks / open questions

- **Phase 0 outcome** decides step 4's exact paths — don't migrate before running it.
- **Per-task worktrees** under `.cronos/workspaces/` must be recreated post-move, not
  copied (code treats them as disposable).
- **`cronos-development` repo link:** after decoupling, (re)link the space to the
  GitHub repo so agents clone/worktree into the off-tree space — confirm repo URL/branch
  in its `space.yml`.
- **Local dev** keeps `./data` (the `:-./data` default) — ensure it is gitignored so the
  same problem doesn't recur locally.
