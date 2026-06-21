"""
backend/app/harnesses/wait — Wait node evaluators for human and timed modes.

Wait nodes pause harness execution in one of two ways:

  * **human** mode — parks the harness run goal in ``TaskState.WAITING`` until
    a human reply arrives via ``pending_messages``.  The executor transitions
    the run goal to WAITING and resumes traversal from the Wait node's outgoing
    edges when a reply arrives.  ``RunState.waiting_node_id`` is set to the
    Wait node's id so the executor knows where to resume (single source of
    truth — do NOT duplicate this routing in the worker).

  * **timed** mode — sleeps in-process until an absolute UTC ``wake_at``
    timestamp, then continues traversal immediately.  The executor computes
    ``wake_at = now + duration_seconds`` on first entry and persists it to
    ``NodeState.wake_at`` so that a restart sleeps only the remaining
    interval rather than the full duration again.

Both functions are **pure** in the sense that they create no child tasks,
spawn no subprocesses, and make no TaskStore calls.  The executor and worker
act on the returned ``WaitOutcome`` / awaited result to update external state.
"""

from __future__ import annotations

import asyncio
import datetime
from dataclasses import dataclass
from enum import Enum

from .model import HarnessNode
from .run_state import RunState


# ---------------------------------------------------------------------------
# WaitOutcome
# ---------------------------------------------------------------------------


class WaitAction(str, Enum):
    """Action the executor should take after ``enter_wait()`` returns."""

    park_waiting = "park_waiting"
    """Transition the harness run goal to ``TaskState.WAITING`` and suspend
    traversal until a human reply arrives."""


@dataclass
class WaitOutcome:
    """Verdict returned by ``enter_wait()`` for human-mode Wait nodes.

    Attributes
    ----------
    action:
        Always ``WaitAction.park_waiting`` for human Wait nodes.  The executor
        should transition the run goal to ``TaskState.WAITING``.
    waiting_node_id:
        The id of the Wait node that triggered this outcome.  The executor
        stores this on ``RunState.waiting_node_id`` (already done by
        ``enter_wait()`` before returning this object) and persists the
        ``RunState`` so that resume routing survives process restarts.
    waiting_question:
        The optional prompt text from ``node.data['waiting_question']``.
        May be ``None`` if the node has no question.  The executor/worker
        can surface this to the human respondent.
    """

    action: WaitAction
    waiting_node_id: str
    waiting_question: str | None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def enter_wait(node: HarnessNode, run_state: RunState) -> WaitOutcome:
    """Evaluate a human-mode Wait node.

    Sets ``run_state.waiting_node_id`` to ``node.id`` and returns a
    ``WaitOutcome`` instructing the executor to park the harness run goal in
    ``TaskState.WAITING``.

    Parameters
    ----------
    node:
        The Wait node being evaluated.  Expected to have
        ``node.data.get('mode') == 'human'``.  The function does not enforce
        the mode constraint — the executor is responsible for dispatching to
        the correct evaluator.
    run_state:
        The current ``RunState`` for this harness run.  **Mutated in place**:
        ``run_state.waiting_node_id`` is set to ``node.id`` before returning.

    Returns
    -------
    WaitOutcome
        Verdict with ``action=WaitAction.park_waiting``.  The executor should
        persist the mutated ``run_state`` and transition the run goal to
        ``TaskState.WAITING``.
    """
    # Set the single source of truth for resume routing.
    run_state.waiting_node_id = node.id

    waiting_question: str | None = node.data.get("waiting_question")

    return WaitOutcome(
        action=WaitAction.park_waiting,
        waiting_node_id=node.id,
        waiting_question=waiting_question,
    )


async def await_timed_wait(node: HarnessNode, wake_at: str | None = None) -> None:
    """Evaluate a timed-mode Wait node by sleeping until ``wake_at``.

    On fresh entry the executor computes ``wake_at = now + duration_seconds``
    and persists it to ``NodeState.wake_at`` before calling this function.
    On resume after a restart the executor passes the stored ``wake_at`` so
    this function sleeps only the remaining interval.

    Parameters
    ----------
    node:
        The Wait node being evaluated.  Expected to have
        ``node.data.get('mode') == 'timed'``.  ``duration_seconds`` is only
        used as a fallback when ``wake_at`` is ``None``.
    wake_at:
        ISO-8601 UTC absolute wake timestamp (``datetime.now(timezone.utc).isoformat()``
        format).  When provided, the sleep duration is ``max(0, wake_at - now)``,
        which correctly handles both mid-sleep restarts (remaining sleep) and
        restarts after the wake time has already passed (0-second sleep / fire
        immediately).  When ``None`` (defensive fallback), falls back to the
        full ``duration_seconds`` from node data.

    Returns
    -------
    None
        Returns after sleeping.  The executor continues traversal from the
        Wait node's outgoing edges immediately after this coroutine completes.
    """
    if wake_at is not None:
        now = datetime.datetime.now(datetime.timezone.utc)
        target = datetime.datetime.fromisoformat(wake_at)
        remaining = max(0.0, (target - now).total_seconds())
        await asyncio.sleep(remaining)
    else:
        raw: float | int | None = node.data.get("duration_seconds")
        duration: float = float(raw) if raw is not None else 0.0
        await asyncio.sleep(duration)
