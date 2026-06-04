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

from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from .models import Space, Task


async def mirror_feature_to_github(
    task: "Task",
    *,
    space: "Space",
    reason: Literal["create", "state_change", "edit"],
) -> None:
    """Mirror a feature/fix task to the linked GitHub repository.

    S3 contract — no-op stub.  S3 will implement the actual GitHub API calls.

    Args:
        task:   The feature or fix task to mirror.
        space:  The owning space (provides ``git_repo_url``).
        reason: Why the mirror is being fired — ``"create"`` on POST,
                ``"state_change"`` on feature-state transitions, ``"edit"``
                on title/brief edits.

    Returns:
        None.  S3 may change the return value to an awaitable result but must
        preserve the ``None`` return for the no-op / error-suppression case.
    """
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
