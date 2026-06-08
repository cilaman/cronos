from __future__ import annotations

import logging
import os
import re
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

# Regex matching the `YYYY-MM-DD-HHMM-` date prefix used in feature/fix IDs.
_DATE_PREFIX_RE = re.compile(r"^\d{4}-\d{2}-\d{2}-\d{4}-")


async def propagate_to_feature(
    item_id: str,
    store: TaskStore,
    pool: "WorkerPool | None",
) -> None:
    """Propagate a realizing item's new state to the feature/fix it realizes.

    Resolution rules
    ----------------
    1. Walk ``item_id`` up via ``store.get`` until finding the root goal
       (a task whose ``parent_id`` is ``None``).
    2. Read ``root_goal.realizes`` — this is the ``feature_id`` to propagate to.
    3. If ``realizes`` is None/empty → no-op (item is not linked to a feature).
    4. Fetch the feature task; if not found → no-op (stale reference).
    5. If ``item_id`` is NOT the root goal itself (i.e. it's a child task within
       a realizing goal) → no-op; only the root goal's state drives transitions.
    6. Dispatch based on the current item/feature state combination (I3/I4 extend
       this with real transition logic).

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

    # --- Step 6: dispatch on state (placeholders for I3/I4) ---
    item_state = root_goal.state
    feature_state = feature.feature_state

    if item_state == TaskState.WAITING and feature_state == FeatureState.PLANNED:
        # I3: item→WAITING while feature PLANNED → feature→WAITING
        # Also copy item's waiting_question to the feature so the feature
        # card surfaces the blocking question.
        try:
            await store.transition_feature(
                feature_id,
                FeatureState.WAITING,
                allowed=FEATURE_WORKER_TRANSITIONS,
            )
            log.info(
                "feature_sync: feature %s → WAITING (realizing goal %s entered WAITING)",
                feature_id,
                root_goal.id,
            )
            # Copy waiting_question from the item to the feature if present.
            waiting_q = root_goal.waiting_question
            if waiting_q is not None:
                await store.set_feature_waiting_question(feature_id, waiting_q)
        except InvalidTransition:
            # Already WAITING (concurrent race) — idempotent.
            log.debug(
                "feature_sync: feature %s already in WAITING — concurrent race, ignoring",
                feature_id,
            )
        except AttributeError:
            # set_feature_waiting_question not yet on this store version — log
            # the intended question so it is visible in traces.
            log.debug(
                "feature_sync: store has no set_feature_waiting_question; "
                "waiting_question=%r not persisted on feature %s",
                root_goal.waiting_question,
                feature_id,
            )

    elif item_state == TaskState.ACTIVE and feature_state == FeatureState.WAITING:
        # I3: item→ACTIVE while feature WAITING (resume) → feature→PLANNED
        try:
            await store.transition_feature(
                feature_id,
                FeatureState.PLANNED,
                allowed=FEATURE_WORKER_TRANSITIONS,
            )
            log.info(
                "feature_sync: feature %s → PLANNED (realizing goal %s resumed to ACTIVE)",
                feature_id,
                root_goal.id,
            )
        except InvalidTransition:
            # Already PLANNED (concurrent resume) — idempotent.
            log.debug(
                "feature_sync: feature %s already in PLANNED — concurrent race, ignoring",
                feature_id,
            )

    elif item_state in (TaskState.DONE, TaskState.ARCHIVED):
        # I4: done-detection — all realizing items terminal AND feature PLANNED
        #     → attempt PLANNED→DONE if branch is absent on origin.
        if feature_state != FeatureState.PLANNED:
            # Only fire done-detection from PLANNED state.
            return

        # Zero-items guard: never attempt done-detection with no realizing items.
        items = await store.realizing_items(feature_id)
        if not items:
            log.debug(
                "feature_sync: feature %s has no realizing items — done-detection skipped",
                feature_id,
            )
            return

        # All items must be terminal (DONE or ARCHIVED).
        terminal = {TaskState.DONE, TaskState.ARCHIVED}
        non_terminal = [it for it in items if it.state not in terminal]
        if non_terminal:
            log.debug(
                "feature_sync: feature %s has %d non-terminal realizing items — no-op",
                feature_id,
                len(non_terminal),
            )
            return

        # Derive the branch slug: strip the YYYY-MM-DD-HHMM- prefix from feature.id.
        slug = _DATE_PREFIX_RE.sub("", feature.id)

        # Fetch origin before checking branch existence so pruned refs are accurate.
        space_dir = _SPACES_DIR / feature.space_id
        try:
            from .git_ops import fetch_origin as _fetch_origin

            await _fetch_origin(space_dir)
        except Exception:
            log.warning(
                "feature_sync: feature %s — fetch_origin failed; staying PLANNED",
                feature_id,
            )
            return

        # Branch present → stay PLANNED (work may still be on the branch).
        branch_name = f"feature/{slug}"
        from .git_ops import branch_exists_on_origin as _branch_exists_on_origin

        branch_present = await _branch_exists_on_origin(space_dir, branch_name)
        if branch_present:
            log.info(
                "feature_sync: feature %s — branch %r still on origin; staying PLANNED",
                feature_id,
                branch_name,
            )
            return

        # Branch absent → transition to DONE.
        try:
            await store.transition_feature(
                feature_id,
                FeatureState.DONE,
                allowed=FEATURE_WORKER_TRANSITIONS,
            )
            log.info(
                "feature_sync: feature %s → DONE (all realizing items terminal, branch %r absent)",
                feature_id,
                branch_name,
            )
        except InvalidTransition:
            log.debug(
                "feature_sync: feature %s already DONE or invalid transition — concurrent race",
                feature_id,
            )
            return

        # Close the linked GitHub issue (failure does NOT roll back the DONE transition).
        if feature.issue_number is not None:
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

    # All other combinations are no-ops.


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
