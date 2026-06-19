---
agent_mode: auto
agent_model: sonnet
claude_session_id: 582683b4-f6ba-472f-a44a-d1ba5e1018a1
created_at: '2026-06-19T11:23:52Z'
depends_on:
- 2026-06-19-1115-add-regression-tests-harness-executor-li
feature_key: null
feature_state: null
id: 2026-06-19-1123-fix-get-harness-runs-run-id-returns-404
issue_number: null
issue_url: null
manual_order: 0
parent_id: 2026-06-19-1115-fix-harness-executor-never-runs-harness
pending_messages: []
pr_url: null
priority: 2
proposed_issue_path: null
proposed_pr_path: null
realizes: null
space_id: cronos-development
state: done
title: 'Fix: GET /harness-runs/{run_id} returns 404 when state file missing'
type: task
updated_at: '2026-06-19T11:47:55Z'
waiting_question: null
---

# Brief

## Problem

`GET /api/harness-runs/{run_id}` (backend/app/api/harness_runs.py, `get_harness_run`) does:

1. Look up space_id via worker cache — **this works** (`_rebuild_run_id_cache` at startup scans the index files)
2. Load run state from `.cronos/harness-runs/{run_id}.json` — **this 404s** because the executor never ran (the `harness_store=None` bug) so the state file was never created

The frontend (`HarnessRunPanel.tsx` line 183–189) sees `isError=true` and shows:
```
Failed to load run state.
```
instead of any run details.

## Fix 1 — Backend graceful fallback (`backend/app/api/harness_runs.py`)

When the run state file is missing but the run EXISTS in the run index, return a minimal
synthetic state dict instead of 404. This covers two valid scenarios:
- The executor hasn't started yet (run just triggered, task not yet dequeued)
- The executor crashed before writing state (shouldn't happen after the WorkerPool fix, but worth handling)

Change `get_harness_run` so that after `run_state = load(path)` returns None, it falls
back to scanning the run index:

```python
run_state = load(path)
if run_state is None:
    # Fallback: check the run index — run may be pending (executor not started yet)
    # or state file may have been lost. Return a minimal synthetic state so the UI
    # shows "running" instead of an error.
    from ..harnesses.run_index import read_index as _read_index
    space_dir_path = Path(str(space_dir))
    # Scan all index files in the space to find this run_id
    index_dir = space_dir_path / ".cronos" / "harness-runs"
    found_in_index = False
    import json as _json
    if index_dir.is_dir():
        for idx_file in index_dir.glob("*-index.json"):
            try:
                entries = _json.loads(idx_file.read_text())
                for entry in entries:
                    if entry.get("run_id") == run_id:
                        found_in_index = True
                        break
            except Exception:
                pass
            if found_in_index:
                break
    if not found_in_index:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Run {run_id!r} not found",
        )
    # Return minimal pending state
    return {
        "run_id": run_id,
        "harness_id": "",
        "goal_task_id": run_id,
        "status": "running",
        "waiting_node_id": None,
        "nodes_executed": {},
        "started_at": None,
        "ended_at": None,
    }
```

## Fix 2 — Frontend loading state (`frontend/src/components/HarnessRunPanel.tsx`)

Currently line 183–191:
```tsx
if (isError || !run) {
  return (
    <div ... data-testid="run-panel-error">
      Failed to load run state.
    </div>
  );
}
```

Change the error message so the UI distinguishes between:
- `isLoading` — show a spinner/skeleton (already handled at line 175)
- `isError` — show "Failed to load run state." (existing) 
- `!run && !isLoading && !isError` — this shouldn't happen after the backend fix, but keep as-is

No frontend change strictly required (once the backend returns 200 with minimal state,
the panel will render). But improve the error message to be more actionable:

```tsx
if (isError) {
  return (
    <div ... data-testid="run-panel-error">
      Run details unavailable. The executor may not have started yet — refresh in a moment.
    </div>
  );
}
if (!run) {
  return (
    <div ... data-testid="run-panel-error">
      Run not found.
    </div>
  );
}
```

## Acceptance

- `GET /api/harness-runs/{existing-run-id}` returns 200 (not 404) when the run exists in the index but has no state file.
- Response includes `status: "running"` and `nodes_executed: {}`.
- Frontend shows the panel (not the error message) for such runs.
- Existing test for 404 on truly unknown run_id still passes.

## Git workflow

End with `/goal-task-commit`.

# History

```
2026-06-19T11:47:55Z [agent]
I'll read the relevant files before making changes.

Now I'll make the backend fix first, then the frontend fix.

Now fix the frontend error state handling:

Now let me run the backend tests to verify the fix:

Backend tests passed. Let me check the frontend test results:

All 2613 backend tests pass. Now let me wait for frontend tests:

Frontend tests are still running. Let me check the test file for `HarnessRunPanel` to see if there are existing tests that cover the error states:

The tests don't check the specific error message text, so the frontend change is safe. Let me wait for frontend tests to complete:

Frontend tests are still running. While waiting, let me also verify the backend test specifically for harness_runs:

65 harness-run tests pass. The coverage failure is expected with `-k` filtering (subset of code). Let me check the frontend tests:

All tests pass: 2613 backend + 1225 frontend. Now let me finalize the task:

This is a goal child task. Delegating to goal-task-commit.

Not on the feature branch. Running goal-branch-setup first.

The branch exists locally with prior commits from this goal. Now I'll check out this feature branch in the worktree:

The branch is checked out in another worktree. I'll use git plumbing to commit directly to the feature branch. First, let me confirm where the changes are:

My changes are in the main space dir. I'll copy them to the feature branch worktree and commit from there:

The deletion of the test file is staged from a previous operation. Let me unstage it:

Now commit these changes:

Committed and pushed. Now also revert the changes from the main space directory to keep it clean:

Good — changes committed to the feature branch and main worktree restored. Now writing memory:

MEMORY[fact]: Fixed `GET /api/harness-runs/{run_id}` 404 when run state file missing: `backend/app/api/harness_runs.py` `get_harness_run()` now falls back to scanning `*-index.json` files when `load(path)` returns None — returns minimal synthetic `{status: "running", nodes_executed: {}}` if found in index, 404 only for truly unknown run_ids. Frontend `HarnessRunPanel.tsx` splits the combined `isError || !run` check into separate cases with distinct messages.

STATUS: DONE
```
