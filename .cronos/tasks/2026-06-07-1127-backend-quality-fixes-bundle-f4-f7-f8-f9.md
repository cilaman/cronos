---
agent_mode: auto
agent_model: sonnet
claude_session_id: 552bda08-977c-4eaa-883f-0ccbc36808c6
created_at: '2026-06-07T11:27:14Z'
depends_on:
- 2026-06-07-1127-guard-process-feature-against-double-pro
feature_key: null
feature_state: null
id: 2026-06-07-1127-backend-quality-fixes-bundle-f4-f7-f8-f9
issue_number: null
issue_url: null
manual_order: 0
parent_id: 2026-06-07-1127-fix-features-backend-critical-bugs
pending_messages: []
pr_url: null
priority: 2
proposed_issue_path: null
proposed_pr_path: null
realizes: null
space_id: cronos-development
state: archived
title: Backend quality fixes bundle (F4, F7, F8, F9, F10)
type: task
updated_at: '2026-06-15T05:30:16Z'
waiting_question: null
---

# Brief

## Context

Five P2 quality/reliability issues bundled for a single focused task.

## Changes required

**F4 — validate_realizes cycle check** (`backend/app/storage.py:202-230`):
After the existing 1-hop self-ref check, add a BFS walk starting from `item_id` following each
task's `realizes` pointer. If we ever reach `feature_id`, reject:
```python
raise StorageError(f"Circular realizes reference: {item_id} already transitively realizes {feature_id}")
```
Cap at 50 hops (consistent with `_find_root`). Walk only tasks that exist in `self._tasks`.

**F7 — log WARNING for features with None feature_state** (`backend/app/storage.py:762-763`):
Replace the bare `continue` with:
```python
if task.feature_state is None:
    log.warning("feature_board: task %s (type=%s) has feature_state=None — skipping", task.id, task.type)
    continue
```

**F8 — reject type→feature/fix in update()** (`backend/app/storage.py` in the `update()` method,
around line 934-976):
Find the point where the incoming `type` field is applied. If `updates.get("type") in ("feature", "fix")`
and `task.type not in ("feature", "fix")`, raise:
```python
raise StorageError("Cannot change task type to feature or fix via update(); create a new feature task instead")
```

**F9 — mirror broad-except exc_info** (`backend/app/feature_hooks.py:195-201`):
Change the except block from:
```python
log.warning("mirror_feature_to_github: task=%s reason=%s error=%r", task.id, reason, exc)
```
to:
```python
log.warning("mirror_feature_to_github: task=%s reason=%s error=%r", task.id, reason, exc, exc_info=True)
```

**F10 — remove type:ignore[arg-type]** (`backend/app/api/features.py:86`):
Remove `# type: ignore[arg-type]` from the `mirror_feature_to_github(task, ...)` call. If mypy
still raises, add the correct import (likely `from __future__ import annotations` or fix the
TYPE_CHECKING import in feature_hooks.py) rather than suppressing.

## Acceptance

- `grep "type: ignore" backend/app/api/features.py` returns no hits on the _fire_mirror line
- `cd backend && pytest tests/ -x -q` — all existing tests pass
- Log line in feature_hooks.py includes `exc_info=True`

After tests pass, run /goal-task-commit

# History

```
2026-06-08T05:03:23Z [agent]
I'll read the relevant files to understand the current state before making changes.

Now let me read the `feature_board` method and the `update()` method areas.

Let me check how logging is set up in storage.py, and also get more context on the update() method.

Let me check the `_find_root` method to understand the hop-cap pattern.

Let me check the existing tests for `validate_realizes`.

Let me look at the full context of the `_fire_mirror` function in features.py and the `mirror_feature_to_github` signature.

Now I have enough context. Let me implement all five changes.

**F4** — BFS cycle check in `validate_realizes()`:

**F7** — Replace bare `continue` with log.warning in `feature_board()`:

**F8** — Reject `type→feature/fix` in `update()`:

**F9** — Add `exc_info=True` to the warning in `feature_hooks.py`:

**F10** — Remove `# type: ignore[arg-type]` from `features.py`:

Now let me run the acceptance checks — first verify the type:ignore is gone, then run the tests.

Both checks pass. Now run the test suite:

All 2466 tests pass, 84.77% coverage. All acceptance criteria are met. Now running `/goal-task-commit`.

I need to switch to the feature branch first. Let me check if it exists and check it out.

The feature branch is in another worktree. Let me find those files and copy my changes there.

Committed and pushed to `feature/fix-features-backend-critical-bugs` (commit `d927302`). Now finalizing the task.

## Step 1 — Verify completion

All five fixes were implemented and accepted:
- F4: BFS cycle check in `validate_realizes()` ✓
- F7: `log.warning` in `feature_board()` for `feature_state=None` ✓
- F8: Guard against `type→feature/fix` in `update()` ✓
- F9: `exc_info=True` added to `feature_hooks.py` warning ✓
- F10: `# type: ignore[arg-type]` removed from `features.py` ✓
- 2466 tests pass, 84.77% coverage ✓

## Step 3 — Git

Already handled by `/goal-task-commit` — committed as `d927302` on `feature/fix-features-backend-critical-bugs` and pushed to origin.

## Step 4 — Write memory

Memory written. 

## Step 5 — Emit STATUS: DONE

All five quality fixes (F4, F7, F8, F9, F10) are implemented, all 2466 tests pass, changes committed and pushed to `feature/fix-features-backend-critical-bugs` (commit `d927302`).

STATUS: DONE
```
