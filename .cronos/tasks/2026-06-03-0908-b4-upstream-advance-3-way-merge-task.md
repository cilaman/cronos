---
agent_mode: auto
agent_model: default
claude_session_id: 0cbadefb-40b2-45c3-8169-a78b827849aa
created_at: '2026-06-03T09:08:41Z'
depends_on:
- 2026-06-03-0908-a4-refresh-api-periodic-scheduler
- 2026-06-03-0908-b1-adoption-module-manifest-watcher
feature_key: null
feature_state: null
id: 2026-06-03-0908-b4-upstream-advance-3-way-merge-task
issue_number: null
issue_url: null
manual_order: 0
parent_id: 2026-06-03-0908-arc-5-b-adoption-vendor-mount-merge-upst
pending_messages: []
pr_url: null
priority: 3
proposed_issue_path: null
proposed_pr_path: null
realizes: null
space_id: cronos-development
state: archived
title: B4 — Upstream-advance + 3-way merge task
type: task
updated_at: '2026-06-19T12:17:48Z'
waiting_question: null
---

# Brief

Extend the A4 periodic refresh: after `walk_source` upserts new `source_sha`s, scan every space's adopted manifests. For each entry where `manifest.source_url == discovered.source_url AND manifest.source_path == discovered.relative_path AND manifest.source_sha != discovered.source_sha`:

- **Pristine** (`local_sha == base_sha`): overwrite vendored file, update `source_sha` + `base_sha`; log `tool.auto-upgraded`.
- **Locally edited:** create a Cronos task — `title: "Merge upstream changes to {kind}/{name}"`, `type: task`, `parent_id: null`, `agent_mode: plan`. Brief = 3-way diff (base vs upstream vs local) via `git diff --no-index`, includes `source_url`, target `source_sha`, and a Resolve protocol: "Edit the vendored file; mark task DONE — Cronos bumps `base_sha` to upstream and `local_sha` to the resolved file."
- On that task → DONE, post-DONE hook calls `adoption.finalize_merge(space_id, kind, name)`: reads resolved file → sets `base_sha = upstream.source_sha`, `local_sha = sha256(resolved)`, `source_sha = upstream.source_sha`, `evolved = false`.
- **Guard:** if a non-DONE merge task already exists for `(space, kind, name)`, do NOT duplicate — re-render the diff into the existing task's brief.

## Files

- Modified: `backend/app/tools/adoption.py` (add `finalize_merge`)
- Modified: `backend/app/api/discovery.py` (extend refresh to scan adopted manifests)
- Modified: `backend/app/worker.py` (post-DONE hook for merge tasks)

## Acceptance

- Upstream-advance + local-edit fixture → merge task created with readable 3-way diff
- Merge task DONE → manifest bumps correctly (base_sha, local_sha, source_sha)
- Pristine + advance → silent upgrade; manifest reflects new SHAs
- Duplicate guard: second refresh does not create a second merge task

---

## Standing rules

**Branch:** `feature/arc-5-tools`; create from `main` if missing. No branching from other bases; no merging to `main` (manual after arc lands).

**Test gate:** Invoke `test-architect`: "Update tests for this task; add coverage for new code paths (pytest + vitest); run full suites; report pass/fail." Commit only after green.

**Commit message:** `arc-5/<goal>/<n>: <summary>` — include task number in body.

**STATUS:** `STATUS: DONE` on success; `STATUS: BLOCKED` if tests can't be made green (describe blocker above).

# History

```
2026-06-03T13:15:49Z [agent]
I'll start by reading the key files I need to modify for this task.

Now let me look at the worker.py and the discovery module to understand the existing structure.

Let me look at the storage module and existing tests to understand how tasks are created and what test patterns exist.

Let me look at the storage module to understand task creation:

Now let me look at main.py to understand app state and what's accessible:

Let me check the startup section and how discovery loop is called:

Let me check the existing discovery tests and how git diff --no-index is used:

Now let me look at the conftest.py for the test fixtures:

Let me check how TaskStore.all() works and look at how tasks are filtered by space:

Let me check how task briefs are stored to understand if code blocks would cause issues:

I now have enough context to implement. Let me write all the changes:

Now I'll implement all the changes. Starting with `adoption.py`:

Now update `api/discovery.py` to add the scan logic:

Now update `main.py` to pass `task_store` and `spaces_dir` to the discovery loop:

Now update the `discoverer` task creation in the startup to pass `task_store` and `spaces_dir`:

Now add the type annotation import in main.py for the new signature:

Now add the post-DONE merge finalize hook in `worker.py`. First let me add the regex and helper near the top, then the hook in `_finalize`:

Now add the post-DONE merge finalize hook in `_finalize()`. Let me find the right location:

Now let's run the existing tests to make sure nothing is broken:

The test patches `run_refresh_if_unlocked` with a function that doesn't accept the new kwargs. Let me update the affected test:

All 33 existing tests pass. Now let me write the new tests. First, let me check what test files exist for the worker:

Now I have enough context to write the new tests. Let me add them:

Now add tests for the discovery scan logic and the worker hook. Let me add to the discovery test file:

Now let's run the tests:

The worker calls `finalize_merge` with the default `SPACES_DIR` instead of the test's `spaces_dir`. I need to thread `spaces_dir` through the worker using `self.store.spaces_dir`:

All 43 tests pass. Let me now invoke the test-architect to run the full test suite:

All 1450 tests pass, 82.92% coverage. Time to finalize.

Goal child — delegate to goal-task-commit:

Not on the feature branch. Run goal-branch-setup first:

On the feature branch. Now commit the changes:

Committed and pushed. Now write memory and emit STATUS:

MEMORY[fact]: B4 upstream-advance + 3-way merge task merged to `feature/arc-5-tools` (commit 1efba2a). Three files modified: `adoption.py` gained `finalize_merge(space_id, kind, name, upstream_source_sha, *, spaces_dir)` that bumps base_sha/local_sha/source_sha and clears evolved; `api/discovery.py` gained `_scan_adopted_after_refresh` called at end of `_run_refresh` — pristine tools auto-upgrade, evolved tools get a backlog "Merge upstream changes to {kind}/{name}" task with embedded `<!-- merge-meta -->` block; `worker.py` post-DONE hook calls `finalize_merge` via `_parse_merge_meta` when a merge task completes. `main.py` passes `task_store` + `spaces_dir` to the periodic discovery loop. 1450 tests pass, 82.92% coverage.

MEMORY[procedure]: Duplicate-guard pattern for auto-created tasks: search `task_store.all()` by `space_id + title + state not in (done, archived)` before creating; if found, call `task_store.update(existing.id, brief=new_brief)` to refresh without duplication.

Writing to space-root memory for cross-conversation persistence:

Memory written. Task complete.

STATUS: DONE
```
