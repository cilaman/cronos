from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING

from .feature_state import FEATURE_WORKER_TRANSITIONS
from .models import FeatureState, TaskState
from .storage import InvalidTransition, TaskNotFound, TaskStore

if TYPE_CHECKING:
    from .worker_pool import WorkerPool

log = logging.getLogger("cronos.feature_sync")

_DATA_DIR = Path(os.environ.get("CRONOS_DATA_DIR", "/data"))
_SPACES_DIR = _DATA_DIR / "spaces"


async def propagate_to_feature(
    item_id: str,
    store: TaskStore,
    pool: "WorkerPool | None",
) -> None:
    """Propagate a realizing item's new state to the feature/fix it realizes.

    State derivation rules (applied to ALL realizing items for the feature)
    -----------------------------------------------------------------------
    - No realizing items          → no-op (feature stays BACKLOG)
    - All items DONE or ARCHIVED  → DONE
    - Any item ACTIVE             → PROCESSING
    - Any item WAITING (no ACTIVE)→ WAITING
    - All items BACKLOG           → PLANNED
    - Mixed non-terminal states   → no-op

    On DONE: linked GitHub issue is closed (failure does not roll back).
    On WAITING: waiting_question copied from the first WAITING item that has one.

    Called after ``goal_sync.propagate_to_parent`` in both ``worker._finalize``
    and the ``api/tasks.py`` reply path.  Errors are caught by the caller's
    try/except and logged — never re-raised.
    """
    # --- Step 1: resolve root goal ---
    root_goal = await _find_root(item_id, store)
    if root_goal is None:
        return

    # --- Step 2 & 3: check realizes link ---
    feature_id = root_goal.realizes
    if not feature_id:
        return

    # --- Step 4: fetch the feature task ---
    feature = store.get(feature_id)
    if feature is None:
        log.debug(
            "feature_sync: item %s root goal %s has realizes=%r but feature not found — no-op",
            item_id,
            root_goal.id,
            feature_id,
        )
        return

    # --- Step 5: only root-goal transitions propagate ---
    if item_id != root_goal.id:
        log.debug(
            "feature_sync: item %s is a child of realizing goal %s — no-op",
            item_id,
            root_goal.id,
        )
        return

    # --- Step 6: derive target feature_state from all realizing items ---
    items = await store.realizing_items(feature_id)

    if not items:
        log.debug(
            "feature_sync: feature %s has no realizing items — no-op",
            feature_id,
        )
        return

    states = {item.state for item in items}
    _terminal = frozenset({TaskState.DONE, TaskState.ARCHIVED})

    if all(s in _terminal for s in states):
        target = FeatureState.DONE
    elif TaskState.ACTIVE in states:
        target = FeatureState.PROCESSING
    elif TaskState.WAITING in states:
        target = FeatureState.WAITING
    elif all(s == TaskState.BACKLOG for s in states):
        target = FeatureState.PLANNED
    else:
        # Mixed non-terminal states (e.g. some done, some backlog) — no-op.
        log.debug(
            "feature_sync: feature %s has mixed states %s — no-op",
            feature_id,
            {s.value for s in states},
        )
        return

    current = feature.feature_state
    if current == target:
        return

    try:
        await store.transition_feature(feature_id, target, allowed=FEATURE_WORKER_TRANSITIONS)
        log.info(
            "feature_sync: feature %s %s → %s (realizing goal %s)",
            feature_id,
            current.value if current else "?",
            target.value,
            root_goal.id,
        )
    except InvalidTransition:
        log.debug(
            "feature_sync: transition %s → %s not allowed — concurrent race or invalid",
            current,
            target,
        )
        return

    # WAITING: copy waiting_question from the first WAITING item that has one.
    if target == FeatureState.WAITING:
        waiting_q = next(
            (
                item.waiting_question
                for item in items
                if item.state == TaskState.WAITING and item.waiting_question
            ),
            None,
        )
        if waiting_q is not None:
            try:
                await store.set_feature_waiting_question(feature_id, waiting_q)
            except AttributeError:
                log.debug(
                    "feature_sync: store has no set_feature_waiting_question; "
                    "waiting_question=%r not persisted on feature %s",
                    waiting_q,
                    feature_id,
                )

    # DONE: close the linked GitHub issue (failure does NOT roll back the transition).
    if target == FeatureState.DONE and feature.issue_number is not None:
        space_dir = _SPACES_DIR / feature.space_id
        try:
            from . import git_issues

            await git_issues.gh_issue_close(space_dir, feature.issue_number)
            log.info(
                "feature_sync: closed issue #%d for feature %s",
                feature.issue_number,
                feature_id,
            )
        except Exception:
            log.warning(
                "feature_sync: gh_issue_close failed for feature %s issue #%d — DONE not rolled back",
                feature_id,
                feature.issue_number,
            )


async def _find_root(item_id: str, store: TaskStore):
    """Walk the parent chain from ``item_id`` to the root (no parent_id).

    Returns the root Task, or None if ``item_id`` is not found.
    Guards against infinite loops (max 50 hops).
    """
    current_id = item_id
    max_hops = 50
    for _ in range(max_hops):
        task = store.get(current_id)
        if task is None:
            return None
        if task.parent_id is None:
            return task
        current_id = task.parent_id
    # Cycle guard: should not happen in a valid DAG
    log.warning("feature_sync: parent chain exceeded %d hops from %s — aborting", max_hops, item_id)
    return None
