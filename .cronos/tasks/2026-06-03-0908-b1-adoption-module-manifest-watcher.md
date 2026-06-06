---
agent_mode: auto
agent_model: default
claude_session_id: 2c3a5b93-c456-4c68-bab5-f0c16e436264
created_at: '2026-06-03T09:08:41Z'
depends_on:
- 2026-06-03-0908-a3-discovered-tools-sqlite-index-upsert
id: 2026-06-03-0908-b1-adoption-module-manifest-watcher
manual_order: 0
parent_id: 2026-06-03-0908-arc-5-b-adoption-vendor-mount-merge-upst
pending_messages: []
pr_url: null
priority: 3
proposed_pr_path: null
space_id: cronos-development
state: done
title: B1 — Adoption module + manifest + watcher
type: task
updated_at: '2026-06-03T12:37:20Z'
waiting_question: null
---

# Brief

New `backend/app/tools/adoption.py`. Pydantic `AdoptionManifest` fields: `source_url, source_slug, source_path, source_sha, adopted_at, base_sha, local_sha, evolved, kind, name` (YAML-round-tripped, atomic tmpfile+os.replace).

- `async adopt(space_id, source_slug, kind, name) -> AdoptionManifest` — copies file (or skill dir verbatim) from discovery clone into `{space}/.cronos/tools/<kind>/<name>/`. Skill dirs preserve structure; flat files go to `<kind>/<name>.md`. Writes `manifest.yml`. Raises if already adopted.
- `async unadopt(space_id, kind, name)` — soft-delete to `{space}/.cronos/tools/.trash/<kind>/<name>-<ts>/` (matches `space_storage.py` trash pattern).
- `def recompute_local_sha(space_id, kind, name)` — sha256 of file (or canonicalised directory hash); updates manifest.
- Hook the existing `watch_spaces_dir` watcher in `main.py` for `.cronos/tools/**` changes; call `recompute_local_sha` (throttled 1/s per file).

## Files

- New: `backend/app/tools/adoption.py`
- Modified: `backend/app/main.py` (extend watcher for `.cronos/tools/**`)

## Acceptance

- `adopt` copies file + manifest with correct hashes
- Edit adopted file on disk → `local_sha` flips within 2s (watcher)
- `unadopt` soft-deletes (trash pattern, recoverable)
- Adopting already-adopted item raises an error

---

## Standing rules

**Branch:** `feature/arc-5-tools`; create from `main` if missing. No branching from other bases; no merging to `main` (manual after arc lands).

**Test gate:** Invoke `test-architect`: "Update tests for this task; add coverage for new code paths (pytest + vitest); run full suites; report pass/fail." Commit only after green.

**Commit message:** `arc-5/<goal>/<n>: <summary>` — include task number in body.

**STATUS:** `STATUS: DONE` on success; `STATUS: BLOCKED` if tests can't be made green (describe blocker above).

# History

```
2026-06-03T12:37:20Z [agent]
I'll start by exploring the codebase to understand existing patterns before implementing.

Good. Now let me read the key files directly to get exact code I need to follow.

Now let me read space_storage.py for directory resolution and trash patterns, and check existing tests structure.

Now let me look at existing tests for the tools module:

Let me check how space_storage.py handles YAML serialization and look at the tools/__init__.py:

Now I have all I need. Let me implement `adoption.py` and update `main.py`:

Now update `main.py` to add the watcher hook:

Now let me invoke the test-architect to write and run tests:

All 1405 tests green with 82.77% coverage. Now let me finalize the task:

This is a goal child task. Delegating to goal-task-commit:

Not on the feature branch. Running goal-branch-setup first:

The main worktree is already on `feature/arc-5-tools` (per the task standing rules). The changes were made there. Let me commit directly to that branch:

Committed and pushed to `feature/arc-5-tools`. Now writing memory and emitting STATUS:

MEMORY[fact]: `backend/app/tools/adoption.py` created (arc-5/B1, commit ed63a77 on `feature/arc-5-tools`). Provides `AdoptionManifest(BaseModel)` with source_url/slug/path/sha, adopted_at, base_sha, local_sha, evolved, kind, name fields. Functions: `async adopt(space_id, source_slug, kind, name, *, spaces_dir, discovery_base, db_path)` copies file or skill-dir into `{space}/.cronos/tools/{kind}/{name}/` + writes manifest.yml; `async unadopt(space_id, kind, name)` soft-deletes to `.cronos/tools/.trash/{kind}/{name}-{ts}/`; `def recompute_local_sha(...)` recomputes sha256 excluding manifest.yml and updates evolved flag. All three accept optional keyword-only path overrides for testability. `main.py` watcher extended to call `recompute_local_sha` on `.cronos/tools/**` changes (throttled 1/s per item). 14 new tests, 1405 total, 82.77% coverage.

Writing to the space-root memory path instead (which is what the harness injects into future runs):

Memory written. Returning to task-finalize to emit the final STATUS.

STATUS: DONE
```
