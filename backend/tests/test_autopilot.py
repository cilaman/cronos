"""Tests for app.autopilot pickup module and Worker on_idle hook integration.

Covers:

- `eligible_backlog()`: filters by state, type, and unmet deps.
- `rank()`: priority ASC, manual_order ASC, created_at ASC.
- `pickup_next()`: gated on space.autopilot and None-space; returns highest
  ranked eligible task or None.
- `start_picked()`: transitions to ACTIVE and enqueues on the worker.
- `Worker.on_idle` hook: invoked exactly when the queue drains, swallows
  exceptions, no-ops when None.
- End-to-end integration: a WorkerPool wired to autopilot picks the next
  task automatically once the current one completes.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from app.agent import AgentResult, Status
from app.autopilot import eligible_backlog, pickup_next, rank, start_picked
from app.models import Space, Task, TaskState
from app.stats_store import StatsStore
from app.storage import TaskStore
from app.trace_store import TraceStore
from app.worker import Worker
from app.worker_pool import WorkerPool

SPACE_ID = "test-space"


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _space(*, autopilot: str = "enabled", space_id: str = SPACE_ID) -> Space:
    """Build a Space model in-memory (no on-disk persistence required)."""
    now = datetime.now(tz=UTC)
    return Space(
        id=space_id,
        name="Test Space",
        color="#15803D",
        icon=None,
        description="",
        created_at=now,
        updated_at=now,
        autopilot=autopilot,
    )


def _make_result(
    *,
    exit_code: int = 0,
    status: Status | None = Status.DONE,
    session_id: str | None = "sess-test",
) -> AgentResult:
    return AgentResult(
        exit_code=exit_code,
        session_id=session_id,
        final_text="done.",
        stderr_tail="",
        status=status,
        context=None,
        raw_events=[],
        stopped=False,
        result_subtype=None,
    )


async def _mark_done(store: TaskStore, task_id: str) -> None:
    """Move a backlog task to DONE via the legal user-transition path."""
    await store.transition(
        task_id,
        TaskState.ACTIVE,
        allowed={(TaskState.BACKLOG, TaskState.ACTIVE)},
    )
    await store.finalize_run(
        task_id,
        new_state=TaskState.DONE,
        session_id=None,
        waiting_question=None,
        history_entry="```\ndone\n```",
    )


# ---------------------------------------------------------------------------
# eligible_backlog()
# ---------------------------------------------------------------------------


async def test_eligible_backlog_returns_backlog_with_no_deps(task_store):
    """A plain BACKLOG task with no deps is eligible."""
    t = await task_store.create(space_id=SPACE_ID, title="Plain", brief="b")

    result = eligible_backlog(SPACE_ID, task_store)

    assert [x.id for x in result] == [t.id]


async def test_eligible_backlog_excludes_goal_type(task_store):
    """A type=goal task is excluded even when it has no deps and is BACKLOG."""
    await task_store.create(
        space_id=SPACE_ID, title="Goal task", brief="g", type="goal"
    )

    result = eligible_backlog(SPACE_ID, task_store)

    assert result == []


async def test_eligible_backlog_excludes_blocked_by_deps(task_store):
    """A task whose dep is still open (BACKLOG) is NOT eligible."""
    dep = await task_store.create(space_id=SPACE_ID, title="Dep", brief="d")
    await task_store.create(
        space_id=SPACE_ID, title="Blocked", brief="b", depends_on=[dep.id]
    )

    result = eligible_backlog(SPACE_ID, task_store)

    # Only `dep` is eligible (no deps of its own); the blocked task is not.
    assert [x.id for x in result] == [dep.id]


async def test_eligible_backlog_includes_task_when_deps_done(task_store):
    """Once every dep reaches DONE, the dependent task becomes eligible."""
    dep = await task_store.create(space_id=SPACE_ID, title="Dep", brief="d")
    t = await task_store.create(
        space_id=SPACE_ID, title="Dependent", brief="b", depends_on=[dep.id]
    )
    await _mark_done(task_store, dep.id)

    result = eligible_backlog(SPACE_ID, task_store)

    # `dep` is DONE now; only `t` (BACKLOG with satisfied deps) is eligible.
    assert [x.id for x in result] == [t.id]


async def test_eligible_backlog_includes_task_when_deps_archived(task_store):
    """ARCHIVED deps are also terminal, so dependents become eligible."""
    dep = await task_store.create(space_id=SPACE_ID, title="Dep", brief="d")
    t = await task_store.create(
        space_id=SPACE_ID, title="Dependent", brief="b", depends_on=[dep.id]
    )
    # Walk BACKLOG -> ACTIVE -> DONE -> ARCHIVED via user transitions.
    await task_store.transition(
        dep.id,
        TaskState.ACTIVE,
        allowed={(TaskState.BACKLOG, TaskState.ACTIVE)},
    )
    await task_store.finalize_run(
        dep.id,
        new_state=TaskState.DONE,
        session_id=None,
        waiting_question=None,
        history_entry="```\ndone\n```",
    )
    await task_store.transition(
        dep.id,
        TaskState.ARCHIVED,
        allowed={(TaskState.DONE, TaskState.ARCHIVED)},
    )

    result = eligible_backlog(SPACE_ID, task_store)

    assert [x.id for x in result] == [t.id]


async def test_eligible_backlog_excludes_non_backlog_states(task_store):
    """Only BACKLOG tasks are eligible — ACTIVE/WAITING/DONE are skipped."""
    t_backlog = await task_store.create(
        space_id=SPACE_ID, title="Backlog", brief="b"
    )
    t_active = await task_store.create(
        space_id=SPACE_ID, title="Active", brief="b"
    )
    await task_store.transition(
        t_active.id,
        TaskState.ACTIVE,
        allowed={(TaskState.BACKLOG, TaskState.ACTIVE)},
    )

    result = eligible_backlog(SPACE_ID, task_store)

    assert [x.id for x in result] == [t_backlog.id]


async def test_eligible_backlog_scoped_to_space(task_store, space_store):
    """Tasks in other spaces are not returned."""
    await space_store.create(
        name="Other", color="#000000", icon=None, description="", space_id="other"
    )
    here = await task_store.create(space_id=SPACE_ID, title="Here", brief="b")
    await task_store.create(space_id="other", title="There", brief="b")

    result = eligible_backlog(SPACE_ID, task_store)

    assert [x.id for x in result] == [here.id]


# ---------------------------------------------------------------------------
# rank()
# ---------------------------------------------------------------------------


def _bare_task(
    *,
    id: str,
    priority: int = 3,
    manual_order: int = 0,
    created_at: datetime | None = None,
) -> Task:
    now = created_at or datetime.now(tz=UTC)
    return Task(
        id=id,
        space_id=SPACE_ID,
        title=id,
        state=TaskState.BACKLOG,
        created_at=now,
        updated_at=now,
        priority=priority,
        manual_order=manual_order,
    )


def test_rank_sorts_by_priority_then_manual_order_then_created_at():
    """rank() sorts by (priority ASC, manual_order ASC, created_at ASC)."""
    t0 = datetime(2026, 1, 1, tzinfo=UTC)
    # priority 1 wins over priority 5
    p1 = _bare_task(id="p1", priority=1, manual_order=99, created_at=t0 + timedelta(days=10))
    p5 = _bare_task(id="p5", priority=5, manual_order=0, created_at=t0)
    # Same priority -> lower manual_order wins
    p3a = _bare_task(id="p3a", priority=3, manual_order=2, created_at=t0)
    p3b = _bare_task(id="p3b", priority=3, manual_order=5, created_at=t0)
    # Same priority + manual_order -> older created_at wins
    p3c_old = _bare_task(id="p3c_old", priority=3, manual_order=10, created_at=t0)
    p3c_new = _bare_task(id="p3c_new", priority=3, manual_order=10, created_at=t0 + timedelta(days=1))

    # Act
    result = rank([p3b, p3c_new, p5, p1, p3a, p3c_old])

    assert [t.id for t in result] == ["p1", "p3a", "p3b", "p3c_old", "p3c_new", "p5"]


def test_rank_empty_returns_empty():
    """rank() with no input returns []."""
    assert rank([]) == []


def test_rank_does_not_mutate_input():
    """rank() returns a new list and leaves the input order untouched."""
    a = _bare_task(id="a", priority=5)
    b = _bare_task(id="b", priority=1)
    original = [a, b]
    ids_before = [t.id for t in original]

    out = rank(original)

    assert [t.id for t in out] == ["b", "a"]
    assert [t.id for t in original] == ids_before  # unchanged


# ---------------------------------------------------------------------------
# pickup_next()
# ---------------------------------------------------------------------------


async def test_pickup_next_disabled_returns_none(task_store):
    """A space with autopilot='disabled' never picks a task."""
    await task_store.create(space_id=SPACE_ID, title="Eligible", brief="b")
    space = _space(autopilot="disabled")

    result = await pickup_next(space, task_store)

    assert result is None


async def test_pickup_next_paused_returns_none(task_store):
    """A space with autopilot='paused' also returns None."""
    await task_store.create(space_id=SPACE_ID, title="Eligible", brief="b")
    space = _space(autopilot="paused")

    result = await pickup_next(space, task_store)

    assert result is None


async def test_pickup_next_none_space_returns_none(task_store):
    """A None space (e.g. lookup miss) safely returns None — does not raise."""
    await task_store.create(space_id=SPACE_ID, title="Eligible", brief="b")

    result = await pickup_next(None, task_store)

    assert result is None


async def test_pickup_next_returns_highest_priority(task_store):
    """Given multiple eligible tasks, the highest-priority one (lowest int) wins."""
    low = await task_store.create(
        space_id=SPACE_ID, title="Low", brief="b", priority=4
    )
    high = await task_store.create(
        space_id=SPACE_ID, title="High", brief="b", priority=2
    )
    space = _space(autopilot="enabled")

    result = await pickup_next(space, task_store)

    assert result is not None
    assert result.id == high.id
    # Sanity: the low-priority task is still in the store, just not picked.
    assert task_store.get(low.id) is not None


async def test_pickup_next_no_eligible_returns_none(task_store):
    """When nothing is eligible (all blocked / goal / non-backlog), returns None."""
    # A goal — excluded by type
    await task_store.create(
        space_id=SPACE_ID, title="Goal", brief="g", type="goal"
    )
    # A blocked task whose dep never reaches a terminal state
    dep = await task_store.create(space_id=SPACE_ID, title="Dep", brief="d")
    await task_store.create(
        space_id=SPACE_ID, title="Blocked", brief="b", depends_on=[dep.id]
    )
    # Move the only otherwise-eligible task out of BACKLOG
    await task_store.transition(
        dep.id,
        TaskState.ACTIVE,
        allowed={(TaskState.BACKLOG, TaskState.ACTIVE)},
    )
    space = _space(autopilot="enabled")

    result = await pickup_next(space, task_store)

    assert result is None


async def test_pickup_next_skips_other_spaces(task_store, space_store):
    """An enabled space only picks its own tasks, not eligibles from other spaces."""
    await space_store.create(
        name="Other", color="#000000", icon=None, description="", space_id="other"
    )
    await task_store.create(space_id="other", title="Other-space", brief="b")
    space = _space(autopilot="enabled")  # space.id = SPACE_ID

    result = await pickup_next(space, task_store)

    assert result is None


# ---------------------------------------------------------------------------
# start_picked()
# ---------------------------------------------------------------------------


class _RecordingWorker:
    """Captures enqueue() calls without spinning up a real worker loop."""

    def __init__(self) -> None:
        self.enqueued: list[tuple[str, str | None]] = []

    async def enqueue(self, task_id: str, user_message: str | None = None) -> None:
        self.enqueued.append((task_id, user_message))


async def test_start_picked_transitions_and_enqueues(task_store):
    """start_picked() must transition to ACTIVE AND enqueue (in that order)."""
    task = await task_store.create(space_id=SPACE_ID, title="Pick me", brief="b")
    fake_worker = _RecordingWorker()

    await start_picked(task, task_store, fake_worker)  # type: ignore[arg-type]

    # State changed via USER_TRANSITIONS (BACKLOG -> ACTIVE).
    assert task_store.get(task.id).state == TaskState.ACTIVE
    # And the worker was enqueued exactly once with the task id and no user_message.
    assert fake_worker.enqueued == [(task.id, None)]


async def test_start_picked_logs_pick_event(task_store, caplog):
    """start_picked() emits a cronos.autopilot INFO log with the task and space ids."""
    import logging

    task = await task_store.create(space_id=SPACE_ID, title="Logged", brief="b")
    fake_worker = _RecordingWorker()

    with caplog.at_level(logging.INFO, logger="cronos.autopilot"):
        await start_picked(task, task_store, fake_worker)  # type: ignore[arg-type]

    autopilot_records = [
        r for r in caplog.record_tuples if r[0] == "cronos.autopilot"
    ]
    assert autopilot_records, "Expected at least one cronos.autopilot log record"
    # Structured assertions on the level and the message arguments.
    assert all(r[1] == logging.INFO for r in autopilot_records)
    combined = " ".join(r[2] for r in autopilot_records)
    assert task.id in combined
    assert SPACE_ID in combined


async def test_start_picked_blocked_by_deps_raises_and_does_not_enqueue(task_store):
    """If the picked task has unmet deps the transition raises and no enqueue happens.

    Locks the safety invariant: pickup_next should never hand us a task with
    open deps, but if it ever did (race / bug), start_picked must fail-loud
    rather than enqueue an illegally-active task.
    """
    from app.storage import InvalidTransition

    dep = await task_store.create(space_id=SPACE_ID, title="Dep", brief="d")
    task = await task_store.create(
        space_id=SPACE_ID, title="Blocked", brief="b", depends_on=[dep.id]
    )
    fake_worker = _RecordingWorker()

    with pytest.raises(InvalidTransition):
        await start_picked(task, task_store, fake_worker)  # type: ignore[arg-type]

    # Task remains in BACKLOG; no enqueue happened.
    assert task_store.get(task.id).state == TaskState.BACKLOG
    assert fake_worker.enqueued == []


# ---------------------------------------------------------------------------
# Worker.on_idle hook
# ---------------------------------------------------------------------------


async def test_on_idle_called_when_queue_drains(task_store, monkeypatch):
    """The on_idle hook fires once after the worker processes its single queued task."""
    import app.worker as worker_module

    async def fake_run_agent(task, *, user_message, on_event, cancel_event=None, space=None, **kwargs):
        return _make_result()

    monkeypatch.setattr(worker_module, "run_agent", fake_run_agent)

    idle_calls: list[Worker] = []

    async def on_idle(w: Worker) -> None:
        idle_calls.append(w)

    worker = Worker(store=task_store, on_idle=on_idle)
    worker.start()
    try:
        task = await task_store.create(space_id=SPACE_ID, title="Drain me", brief="b")
        await task_store.transition(
            task.id,
            TaskState.ACTIVE,
            allowed={(TaskState.BACKLOG, TaskState.ACTIVE)},
        )

        await worker.enqueue(task.id)

        # Wait until the run completes (task -> DONE) AND the queue is drained.
        async with asyncio.timeout(5.0):
            while not idle_calls:
                await asyncio.sleep(0.01)
    finally:
        await asyncio.wait_for(worker.stop(), timeout=5.0)

    assert len(idle_calls) >= 1
    # Identity check: the hook receives THIS worker, not some other instance.
    assert idle_calls[0] is worker


async def test_on_idle_not_called_when_disabled(task_store, monkeypatch):
    """A worker with on_idle=None must process tasks normally and raise nothing."""
    import app.worker as worker_module

    async def fake_run_agent(task, *, user_message, on_event, cancel_event=None, space=None, **kwargs):
        return _make_result()

    monkeypatch.setattr(worker_module, "run_agent", fake_run_agent)

    worker = Worker(store=task_store, on_idle=None)
    worker.start()
    try:
        task = await task_store.create(space_id=SPACE_ID, title="No hook", brief="b")
        await task_store.transition(
            task.id,
            TaskState.ACTIVE,
            allowed={(TaskState.BACKLOG, TaskState.ACTIVE)},
        )
        await worker.enqueue(task.id)

        # Poll until DONE — proves the worker continued to function with no hook.
        async with asyncio.timeout(5.0):
            while task_store.get(task.id).state != TaskState.DONE:
                await asyncio.sleep(0.01)
    finally:
        await asyncio.wait_for(worker.stop(), timeout=5.0)


async def test_on_idle_exception_does_not_kill_loop(task_store, monkeypatch, caplog):
    """If on_idle raises, the loop logs and keeps processing the next task."""
    import logging

    import app.worker as worker_module

    async def fake_run_agent(task, *, user_message, on_event, cancel_event=None, space=None, **kwargs):
        return _make_result()

    monkeypatch.setattr(worker_module, "run_agent", fake_run_agent)

    call_count = 0
    raised = asyncio.Event()

    async def on_idle(w: Worker) -> None:
        nonlocal call_count
        call_count += 1
        raised.set()
        raise RuntimeError("boom")

    worker = Worker(store=task_store, on_idle=on_idle)
    worker.start()
    try:
        # First task — its completion triggers the failing on_idle.
        t1 = await task_store.create(space_id=SPACE_ID, title="T1", brief="b")
        await task_store.transition(
            t1.id, TaskState.ACTIVE, allowed={(TaskState.BACKLOG, TaskState.ACTIVE)}
        )

        with caplog.at_level(logging.ERROR, logger="cronos.worker"):
            await worker.enqueue(t1.id)
            await asyncio.wait_for(raised.wait(), timeout=5.0)

            # Second task — must be processed despite the previous on_idle crash.
            t2 = await task_store.create(space_id=SPACE_ID, title="T2", brief="b")
            await task_store.transition(
                t2.id, TaskState.ACTIVE, allowed={(TaskState.BACKLOG, TaskState.ACTIVE)}
            )
            await worker.enqueue(t2.id)

            async with asyncio.timeout(5.0):
                while task_store.get(t2.id).state != TaskState.DONE:
                    await asyncio.sleep(0.01)
    finally:
        await asyncio.wait_for(worker.stop(), timeout=5.0)

    # Both tasks completed.
    assert task_store.get(t1.id).state == TaskState.DONE
    assert task_store.get(t2.id).state == TaskState.DONE
    # The error was logged on the worker logger at ERROR level.
    error_records = [
        r for r in caplog.record_tuples
        if r[0] == "cronos.worker" and r[1] == logging.ERROR
    ]
    assert error_records, "Expected an ERROR log from cronos.worker after on_idle raised"
    # And on_idle was invoked at least once (post t1) plus likely again after t2.
    assert call_count >= 1


async def test_on_idle_not_called_during_stop(task_store, monkeypatch):
    """When `stop()` drains via the poison pill, on_idle must NOT fire.

    Locks the `not self._stop.is_set()` guard in the finally block — we should
    not trigger autopilot pickups while the worker is shutting down.
    """
    import app.worker as worker_module

    async def fake_run_agent(task, *, user_message, on_event, cancel_event=None, space=None, **kwargs):
        return _make_result()

    monkeypatch.setattr(worker_module, "run_agent", fake_run_agent)

    idle_calls: list[Worker] = []

    async def on_idle(w: Worker) -> None:
        idle_calls.append(w)

    worker = Worker(store=task_store, on_idle=on_idle)
    worker.start()
    # Immediately stop — poison pill is the only message in the queue.
    await asyncio.wait_for(worker.stop(), timeout=5.0)

    # Poison pill `__stop__` short-circuits BEFORE the finally on_idle block.
    assert idle_calls == []


# ---------------------------------------------------------------------------
# End-to-end integration via WorkerPool
# ---------------------------------------------------------------------------


async def test_autopilot_pickup_integration(
    task_store, space_store, monkeypatch
):
    """Pool wired to an autopilot-enabled space auto-picks the next eligible task.

    Setup: two BACKLOG tasks (priority 4 and priority 2). Enable autopilot,
    enqueue the priority-4 task manually so the worker has something to drain,
    then assert the priority-2 task gets picked up automatically and reaches DONE.
    """
    import app.worker as worker_module

    # Flip the test space's autopilot to 'enabled' (default is 'disabled').
    await space_store.set_autopilot(SPACE_ID, "enabled")

    # Create two eligible tasks with distinct priorities.
    low = await task_store.create(
        space_id=SPACE_ID, title="Low prio", brief="b", priority=4
    )
    high = await task_store.create(
        space_id=SPACE_ID, title="High prio", brief="b", priority=2
    )

    run_order: list[str] = []

    async def fake_run_agent(task, *, user_message, on_event, cancel_event=None, space=None, **kwargs):
        run_order.append(task.id)
        return _make_result()

    monkeypatch.setattr(worker_module, "run_agent", fake_run_agent)

    pool = WorkerPool(task_store, space_store)
    try:
        worker = await pool.start_for_space(SPACE_ID)

        # Manually start `low` — auto-pickup should fire after it completes
        # and pick `high` (the only remaining eligible BACKLOG task).
        await task_store.transition(
            low.id, TaskState.ACTIVE, allowed={(TaskState.BACKLOG, TaskState.ACTIVE)}
        )
        await worker.enqueue(low.id)

        async with asyncio.timeout(10.0):
            while task_store.get(high.id).state != TaskState.DONE:
                await asyncio.sleep(0.02)
    finally:
        await asyncio.wait_for(pool.stop_all(), timeout=10.0)

    # Both tasks were processed; `low` (manual enqueue) ran first.
    assert run_order[:2] == [low.id, high.id]
    assert task_store.get(low.id).state == TaskState.DONE
    assert task_store.get(high.id).state == TaskState.DONE


async def test_autopilot_does_not_pick_when_disabled_integration(
    task_store, space_store, monkeypatch
):
    """Pool with autopilot='disabled' must NOT auto-pick a second task."""
    import app.worker as worker_module

    # Leave space.autopilot at its default ('disabled').
    low = await task_store.create(
        space_id=SPACE_ID, title="Manual", brief="b", priority=4
    )
    leftover = await task_store.create(
        space_id=SPACE_ID, title="Leftover", brief="b", priority=2
    )

    run_order: list[str] = []

    async def fake_run_agent(task, *, user_message, on_event, cancel_event=None, space=None, **kwargs):
        run_order.append(task.id)
        return _make_result()

    monkeypatch.setattr(worker_module, "run_agent", fake_run_agent)

    pool = WorkerPool(task_store, space_store)
    try:
        worker = await pool.start_for_space(SPACE_ID)
        await task_store.transition(
            low.id, TaskState.ACTIVE, allowed={(TaskState.BACKLOG, TaskState.ACTIVE)}
        )
        await worker.enqueue(low.id)

        # Wait until the manual task finishes.
        async with asyncio.timeout(5.0):
            while task_store.get(low.id).state != TaskState.DONE:
                await asyncio.sleep(0.02)

        # Give the on_idle hook a chance to fire (and decline to pick).
        await asyncio.sleep(0.2)
    finally:
        await asyncio.wait_for(pool.stop_all(), timeout=10.0)

    # Only the manual task ran; the leftover stays in BACKLOG.
    assert run_order == [low.id]
    assert task_store.get(leftover.id).state == TaskState.BACKLOG


async def test_autopilot_pickup_rereads_space_each_idle(
    task_store, space_store, monkeypatch
):
    """The on_idle closure must re-read the Space (catching mid-run autopilot toggles).

    Start with autopilot disabled; run one task manually; then flip autopilot
    to enabled and enqueue another manual task — after THAT one completes, the
    next idle re-reads the now-enabled space and auto-picks the leftover.
    """
    import app.worker as worker_module

    leftover = await task_store.create(
        space_id=SPACE_ID, title="Leftover", brief="b", priority=2
    )
    manual1 = await task_store.create(
        space_id=SPACE_ID, title="Manual 1", brief="b", priority=4
    )
    manual2 = await task_store.create(
        space_id=SPACE_ID, title="Manual 2", brief="b", priority=4
    )

    run_order: list[str] = []

    async def fake_run_agent(task, *, user_message, on_event, cancel_event=None, space=None, **kwargs):
        run_order.append(task.id)
        return _make_result()

    monkeypatch.setattr(worker_module, "run_agent", fake_run_agent)

    pool = WorkerPool(task_store, space_store)
    try:
        worker = await pool.start_for_space(SPACE_ID)

        # First manual run with autopilot DISABLED — leftover should NOT be picked.
        await task_store.transition(
            manual1.id,
            TaskState.ACTIVE,
            allowed={(TaskState.BACKLOG, TaskState.ACTIVE)},
        )
        await worker.enqueue(manual1.id)

        async with asyncio.timeout(5.0):
            while task_store.get(manual1.id).state != TaskState.DONE:
                await asyncio.sleep(0.02)
        # Let any spurious autopilot pickup attempt drain.
        await asyncio.sleep(0.2)
        assert task_store.get(leftover.id).state == TaskState.BACKLOG

        # Now flip autopilot ON and enqueue manual2 — leftover should follow.
        await space_store.set_autopilot(SPACE_ID, "enabled")
        await task_store.transition(
            manual2.id,
            TaskState.ACTIVE,
            allowed={(TaskState.BACKLOG, TaskState.ACTIVE)},
        )
        await worker.enqueue(manual2.id)

        async with asyncio.timeout(10.0):
            while task_store.get(leftover.id).state != TaskState.DONE:
                await asyncio.sleep(0.02)
    finally:
        await asyncio.wait_for(pool.stop_all(), timeout=10.0)

    assert run_order == [manual1.id, manual2.id, leftover.id]
