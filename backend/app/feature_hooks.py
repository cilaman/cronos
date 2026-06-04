"""S3/S4 contract shims for feature/fix tasks.

These functions are no-op stubs that lock in the call signatures required by
later pipeline stages.  S2 callers ``await`` them directly; S3 and S4 will
replace the bodies with real logic without changing any call site.

**S3 contract** — DO NOT change ``mirror_feature_to_github`` signature without
an S3 design change request.

**S4 contract** — DO NOT change ``enqueue_feature_decomposition`` signature
without an S4 design change request.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from .models import Space, Task
    from .storage import TaskStore

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level store reference — set by main.py or injected by tests.
#
# main.py should call ``configure_store(task_store)`` during lifespan startup
# so that mirror_feature_to_github can persist issue refs to disk.  Tests
# inject a mock TaskStore (or AsyncMock stand-in) directly via:
#
#     import app.feature_hooks as fh
#     fh._task_store = mock_store
#
# When _task_store is None the mirror still writes the MD fallback file but
# skips the set_issue_refs call (graceful degradation during test isolation
# or misconfiguration).
# ---------------------------------------------------------------------------

_task_store: "TaskStore | None" = None


def configure_store(store: "TaskStore") -> None:
    """Wire a TaskStore instance into the module for use by mirror hooks.

    Called by main.py during lifespan startup.  Idempotent — may be called
    multiple times (e.g. during test setup).
    """
    global _task_store
    _task_store = store


_DATA_DIR = Path(os.environ.get("CRONOS_DATA_DIR", "/data"))
_SPACES_DIR = _DATA_DIR / "spaces"


async def mirror_feature_to_github(
    task: "Task",
    *,
    space: "Space",
    reason: Literal["create", "state_change", "edit"],
) -> None:
    """Mirror a feature/fix task to the linked GitHub repository.

    S3 implementation — one-way mirror with MD fallback.

    Ordering (R6 — MD write STRICTLY before gh call):
      1. Early-return if task.type not in ("feature", "fix").
      2. Compute space_dir from space.id.
      3. Create .cronos/issues/ directory.
      4. Write MD fallback to .cronos/issues/{task.id}.md  ← FIRST
      5. Call gh_issue_upsert  ← SECOND
      6. Persist via set_issue_refs (issue_num+url on success; None+md_path on failure).
      7. If reason=="state_change" AND feature_state==DONE AND issue_number set →
         call gh_issue_close.

    Stale issue_number (R11): if gh edit returns (None, None) when
    task.issue_number was set, set_issue_refs clears the number and stores
    the MD path instead.  The orphaned upstream issue is an accepted tradeoff
    (one-way mirror, no reconciliation).

    git_repo_url=None (R9): does NOT cause an early return.  gh_issue_upsert
    will return (None, None) internally (detect_github_remote returns None),
    and the MD fallback path is persisted via set_issue_refs.

    Exception handling (R8): the entire body is wrapped in a broad try/except;
    the function ALWAYS returns None.  Exceptions are logged at WARNING level
    with task.id and reason for audit.

    Args:
        task:   The feature or fix task to mirror.
        space:  The owning space (provides ``git_repo_url``).
        reason: Why the mirror is being fired — ``"create"`` on POST,
                ``"state_change"`` on feature-state transitions, ``"edit"``
                on title/brief edits.

    Returns:
        None.
    """
    # (1) Type guard — only mirror feature and fix tasks.
    if task.type not in ("feature", "fix"):
        return None

    try:
        from . import git_issues
        from .models import FeatureState

        # (2) Compute space directory.
        space_dir = _SPACES_DIR / space.id

        # (3) Ensure .cronos/issues/ exists.
        issues_dir = space_dir / ".cronos" / "issues"
        issues_dir.mkdir(parents=True, exist_ok=True)

        # (4) Write MD fallback FIRST (R6: before any gh call).
        proposed_path = issues_dir / f"{task.id}.md"
        md_content = f"# {task.feature_key}: {task.title}\n\n{task.brief or ''}\n"
        proposed_path.write_text(md_content, encoding="utf-8")

        # (5) Call gh_issue_upsert SECOND.
        issue_num, issue_url = await git_issues.gh_issue_upsert(
            space_dir,
            title=task.title,
            body=task.brief or "",
            labels=[task.type],
            issue_number=task.issue_number,
        )

        # (6) Persist via set_issue_refs.
        store = _task_store
        if store is not None:
            if issue_num is not None:
                # gh succeeded: persist number + url, clear proposed_issue_path.
                await store.set_issue_refs(
                    task.id,
                    issue_number=issue_num,
                    issue_url=issue_url,
                    proposed_issue_path=None,
                )
            else:
                # gh returned (None, None) — could be: no gh, no remote, timeout,
                # rc!=0 (stale issue_number), or unexpected stdout.
                # Persist MD fallback path; clear issue refs (R11: stale number cleared).
                await store.set_issue_refs(
                    task.id,
                    issue_number=None,
                    issue_url=None,
                    proposed_issue_path=str(proposed_path),
                )
        else:
            log.warning(
                "mirror_feature_to_github: _task_store not configured — "
                "set_issue_refs skipped for task=%s",
                task.id,
            )

        # (7) Close issue on DONE state_change (R7).
        if (
            reason == "state_change"
            and task.feature_state == FeatureState.DONE
            and task.issue_number is not None
        ):
            await git_issues.gh_issue_close(space_dir, task.issue_number)

    except Exception as exc:  # noqa: BLE001
        log.warning(
            "mirror_feature_to_github: task=%s reason=%s error=%r",
            task.id,
            reason,
            exc,
        )

    return None


async def enqueue_feature_decomposition(task: "Task") -> None:
    """Enqueue a feature/fix task for S4 decomposition processing.

    S4 contract — no-op stub.  S4 will implement the actual worker enqueue
    logic (e.g. posting a message to a queue or spawning a sub-agent).

    Args:
        task: The feature or fix task to decompose.

    Returns:
        None.
    """
    return None
