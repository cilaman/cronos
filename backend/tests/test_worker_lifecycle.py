"""Lifecycle integration tests for Worker and WorkerPool.

Covers:
- worker.start() -> enqueue -> complete -> state transitions, replay buffer,
  subscriber delivery -> worker.stop() exits within 1 second
- Two workers in a WorkerPool run concurrently across different spaces
- Tasks in the same space serialize (serial-per-space invariant)
- Subscriber attached mid-run receives correct replay snapshot then live events
- Slow subscriber (queue capped at 256) gets oldest events dropped, worker not blocked
- stop_for_space cancels an in-flight run within 2 seconds via cancel_event
- _DONE_SENTINEL delivered to every subscriber on run_end
- Auto-resume counter _MAX_AUTO_RESUMES is respected (no infinite loop)
"""

from __future__ import annotations

import asyncio
import time

import pytest

from app.agent import AgentResult, Status
from app.models import TaskState
from app.storage import TaskStore, WORKER_TRANSITIONS
from app.worker import Worker, _DONE_SENTINEL
from app.worker_pool import WorkerPool

SPACE_ID = "test-space"
SPACE_ID_B = "test-space-b"


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


async def _active_task(
    store: TaskStore,
    *,
    space_id: str = SPACE_ID,
    title: str = "Test",
) -> str:
    """Create a task and move it to ACTIVE so worker transitions are legal."""
    task = await store.create(space_id=space_id, title=title, brief="brief")
    await store.transition(
        task.id,
        TaskState.ACTIVE,
        allowed={(TaskState.BACKLOG, TaskState.ACTIVE)},
    )
    return task.id


def _make_result(
    *,
    exit_code: int = 0,
    session_id: str | None = "sess-test",
    final_text: str = "done.",
    stderr_tail: str = "",
    status: Status | None = Status.DONE,
    context: str | None = None,
    raw_events: list | None = None,
    stopped: bool = False,
    result_subtype: str | None = None,
) -> AgentResult:
    return AgentResult(
        exit_code=exit_code,
        session_id=session_id,
        final_text=final_text,
        stderr_tail=stderr_tail,
        status=status,
        context=context,
        raw_events=raw_events if raw_events is not None else [],
        stopped=stopped,
        result_subtype=result_subtype,
    )


async def _drain(q: asyncio.Queue, *, timeout: float = 5.0) -> list[dict]:
    """Collect events from a subscriber queue until _DONE_SENTINEL arrives."""
    events: list[dict] = []
    try:
        async with asyncio.timeout(timeout):
            while True:
                event = await q.get()
                if event is _DONE_SENTINEL:
                    return events
                events.append(event)
    except TimeoutError:
        pytest.fail(f"Timed out after {timeout}s waiting for _DONE_SENTINEL")
        return events  # unreachable but satisfies type checker


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def worker(task_store, tmp_spaces_dir):
    """A fresh Worker that cleans itself up after each test."""
    w = Worker(store=task_store)
    yield w
    if w.is_alive():
        try:
            await asyncio.wait_for(w.stop(), timeout=5.0)
        except (asyncio.TimeoutError, Exception):
            pass


@pytest.fixture
async def pool(task_store, space_store):
    """A fresh WorkerPool that stops all workers after each test."""
    p = WorkerPool(task_store, space_store)
    yield p
    try:
        await asyncio.wait_for(p.stop_all(), timeout=10.0)
    except (asyncio.TimeoutError, Exception):
        pass


# ---------------------------------------------------------------------------
# 1. Bootstrap: basic smoke test with monkeypatched fake_run_agent
# ---------------------------------------------------------------------------


async def test_bootstrap_fake_run_agent(task_store, worker, monkeypatch):
    """Smoke test: worker with a monkeypatched fake completes a run."""
    task_id = await _active_task(task_store)

    async def fake_run_agent(task, *, user_message, on_event, cancel_event=None, space=None):
        await on_event({"type": "text", "text": "hello"})
        return _make_result()

    monkeypatch.setattr("app.worker.run_agent", fake_run_agent)
    worker.start()

    _, q = worker.subscribe(task_id)
    await worker.enqueue(task_id)
    events = await _drain(q)

    types = [e.get("type") for e in events]
    assert "run_start" in types
    assert "run_end" in types
    assert task_store.get(task_id).state == TaskState.DONE


# ---------------------------------------------------------------------------
# 2. Full lifecycle: state transitions, replay buffer, subscriber delivery,
#    stop() exits within 1 second
# ---------------------------------------------------------------------------


async def test_full_lifecycle(task_store, worker, monkeypatch):
    """
    start() -> enqueue -> completion: state transitions are correct, replay
    buffer is populated, subscriber sees all events, stop() returns in < 1 s.
    """
    task_id = await _active_task(task_store, title="Full lifecycle")

    published = [
        {"type": "text", "text": "thinking..."},
        {"type": "text", "text": "done thinking"},
    ]

    async def fake_run_agent(task, *, user_message, on_event, cancel_event=None, space=None):
        for ev in published:
            await on_event(ev)
        return _make_result()

    monkeypatch.setattr("app.worker.run_agent", fake_run_agent)
    worker.start()

    _, q = worker.subscribe(task_id)
    await worker.enqueue(task_id)
    events = await _drain(q)

    # State transition ACTIVE → DONE
    assert task_store.get(task_id).state == TaskState.DONE

    # Lifecycle markers present
    types = [e.get("type") for e in events]
    assert "run_start" in types
    assert "run_end" in types
    run_end = next(e for e in events if e.get("type") == "run_end")
    assert run_end["new_state"] == TaskState.DONE.value

    # Agent events forwarded to subscriber
    texts = [e.get("text") for e in events if e.get("type") == "text"]
    assert "thinking..." in texts
    assert "done thinking" in texts

    # Replay buffer contains what was published during this run
    buf = worker._run_buffer.get(task_id, [])
    assert any(e.get("type") == "run_start" for e in buf)
    assert any(e.get("text") == "thinking..." for e in buf)

    # stop() finishes well within 1 second (no blocking)
    t0 = time.monotonic()
    await asyncio.wait_for(worker.stop(), timeout=2.0)
    assert time.monotonic() - t0 < 1.0


# ---------------------------------------------------------------------------
# 3. WorkerPool: tasks in different spaces run concurrently
# ---------------------------------------------------------------------------


async def test_workerpool_different_spaces_run_concurrently(
    task_store, space_store, pool, monkeypatch
):
    """Two workers in a WorkerPool run concurrently when spaces differ."""
    await space_store.create(
        name="Space B",
        color="#000000",
        icon=None,
        description="",
        space_id=SPACE_ID_B,
    )

    task_a = await _active_task(task_store, space_id=SPACE_ID, title="Task A")
    task_b = await _active_task(task_store, space_id=SPACE_ID_B, title="Task B")

    a_started = asyncio.Event()
    b_started = asyncio.Event()
    both_seen = asyncio.Event()
    release = asyncio.Event()

    async def fake_run_agent(task, *, user_message, on_event, cancel_event=None, space=None):
        if task.id == task_a:
            a_started.set()
        else:
            b_started.set()
        if a_started.is_set() and b_started.is_set():
            both_seen.set()
        await asyncio.wait_for(release.wait(), timeout=5.0)
        return _make_result()

    monkeypatch.setattr("app.worker.run_agent", fake_run_agent)

    worker_a = await pool.start_for_space(SPACE_ID)
    worker_b = await pool.start_for_space(SPACE_ID_B)

    await worker_a.enqueue(task_a)
    await worker_b.enqueue(task_b)

    # Both should start before either finishes (concurrent execution)
    await asyncio.wait_for(both_seen.wait(), timeout=5.0)

    # Unblock both agents so the pool cleanup can finish
    release.set()


# ---------------------------------------------------------------------------
# 4. Serial-per-space: tasks in the same space run one after the other
# ---------------------------------------------------------------------------


async def test_serial_per_space(task_store, worker, monkeypatch):
    """
    The Worker's serial queue means task2 cannot start before task1 finishes,
    even when both are enqueued before the worker starts processing.
    """
    task1 = await _active_task(task_store, title="Task 1")
    task2 = await _active_task(task_store, title="Task 2")

    order: list[tuple[str, str]] = []
    task1_release = asyncio.Event()

    async def fake_run_agent(task, *, user_message, on_event, cancel_event=None, space=None):
        order.append(("start", task.id))
        if task.id == task1:
            await asyncio.wait_for(task1_release.wait(), timeout=5.0)
        order.append(("end", task.id))
        return _make_result()

    monkeypatch.setattr("app.worker.run_agent", fake_run_agent)
    worker.start()

    await worker.enqueue(task1)
    await worker.enqueue(task2)

    # Wait for task1 to start
    async with asyncio.timeout(5.0):
        while ("start", task1) not in order:
            await asyncio.sleep(0.01)

    # task2 must NOT have started while task1 is blocked
    assert ("start", task2) not in order, "task2 started before task1 finished (not serial)"

    # Release task1
    task1_release.set()

    # Wait for task2 to complete
    async with asyncio.timeout(5.0):
        while ("end", task2) not in order:
            await asyncio.sleep(0.01)

    # Verify strict ordering: start1 → end1 → start2 → end2
    assert order.index(("start", task1)) < order.index(("end", task1))
    assert order.index(("end", task1)) < order.index(("start", task2))
    assert order.index(("start", task2)) < order.index(("end", task2))


# ---------------------------------------------------------------------------
# 5. Subscriber attached mid-run receives replay then live events
# ---------------------------------------------------------------------------


async def test_mid_run_subscriber_gets_replay_then_live(task_store, worker, monkeypatch):
    """
    A subscriber attached after some events have been published receives:
    - replay  = all events published before subscribe()
    - live    = events published after subscribe()
    """
    task_id = await _active_task(task_store, title="Mid-run sub")

    pre_ev = {"type": "text", "text": "pre-subscribe"}
    post_ev = {"type": "text", "text": "post-subscribe"}

    can_attach = asyncio.Event()
    can_continue = asyncio.Event()

    async def fake_run_agent(task, *, user_message, on_event, cancel_event=None, space=None):
        await on_event(pre_ev)
        can_attach.set()
        await asyncio.wait_for(can_continue.wait(), timeout=5.0)
        await on_event(post_ev)
        return _make_result()

    monkeypatch.setattr("app.worker.run_agent", fake_run_agent)
    worker.start()
    await worker.enqueue(task_id)

    # Wait until the pre-event has been buffered
    await asyncio.wait_for(can_attach.wait(), timeout=5.0)

    # Subscribe mid-run
    replay, q = worker.subscribe(task_id)

    # Replay must include run_start and the pre-event
    assert any(e.get("type") == "run_start" for e in replay)
    assert any(e.get("text") == "pre-subscribe" for e in replay)
    # Replay must NOT include the post-event (not published yet)
    assert not any(e.get("text") == "post-subscribe" for e in replay)

    # Let the agent continue
    can_continue.set()

    # Live events should include post-event and run_end
    live = await _drain(q)
    assert any(e.get("text") == "post-subscribe" for e in live)
    assert any(e.get("type") == "run_end" for e in live)


# ---------------------------------------------------------------------------
# 6. Slow subscriber does not block the worker
# ---------------------------------------------------------------------------


async def test_slow_subscriber_does_not_block_worker(task_store, worker, monkeypatch):
    """
    A subscriber whose queue fills to capacity (256) gets oldest events
    dropped but must NEVER stall the worker — the run completes normally.

    Note: _publish uses put_nowait + drop-oldest, so it never blocks on
    a full queue. _DONE_SENTINEL is also sent non-blocking (dropped if the
    queue is full). We verify completion via task-state polling rather than
    draining the slow subscriber's queue.
    """
    task_id = await _active_task(task_store, title="Slow sub")

    n_events = 300  # exceeds the 256-event subscriber queue cap

    async def fake_run_agent(task, *, user_message, on_event, cancel_event=None, space=None):
        for i in range(n_events):
            await on_event({"type": "text", "text": f"event {i}"})
        return _make_result()

    monkeypatch.setattr("app.worker.run_agent", fake_run_agent)
    worker.start()

    # Slow subscriber: never drained — must not block the worker
    _, slow_q = worker.subscribe(task_id)

    await worker.enqueue(task_id)

    # Poll until task is DONE; worker must not be blocked by the full queue
    async with asyncio.timeout(10.0):
        while task_store.get(task_id).state != TaskState.DONE:
            await asyncio.sleep(0.05)

    # Slow queue should be full — events were dropped via drop-oldest, not by blocking
    assert slow_q.full()
    assert task_store.get(task_id).state == TaskState.DONE


# ---------------------------------------------------------------------------
# 7. stop_for_space cancels an in-flight run within 2 seconds
# ---------------------------------------------------------------------------


async def test_stop_for_space_cancels_within_2_seconds(
    task_store, space_store, pool, monkeypatch
):
    """stop_for_space sets cancel_event, which unblocks the run within 2 s."""
    task_id = await _active_task(task_store, title="Cancellable task")
    run_started = asyncio.Event()

    async def blocking_agent(task, *, user_message, on_event, cancel_event=None, space=None):
        run_started.set()
        if cancel_event is not None:
            await cancel_event.wait()  # block until cancel_event is set
        return _make_result(
            exit_code=1,
            session_id=None,
            final_text="",
            stderr_tail="cancelled",
            status=None,
            stopped=True,
        )

    monkeypatch.setattr("app.worker.run_agent", blocking_agent)

    w = await pool.start_for_space(SPACE_ID)
    await w.enqueue(task_id)

    # Wait for the agent to actually start executing
    await asyncio.wait_for(run_started.wait(), timeout=5.0)

    t0 = time.monotonic()
    await pool.stop_for_space(SPACE_ID)
    elapsed = time.monotonic() - t0

    assert elapsed < 2.0, f"stop_for_space took {elapsed:.2f}s (> 2s)"


# ---------------------------------------------------------------------------
# 8. _DONE_SENTINEL delivered to every subscriber on run_end
# ---------------------------------------------------------------------------


async def test_done_sentinel_delivered_to_all_subscribers(task_store, worker, monkeypatch):
    """Every subscriber queue receives _DONE_SENTINEL when the run ends."""
    task_id = await _active_task(task_store, title="Sentinel test")

    async def fake_run_agent(task, *, user_message, on_event, cancel_event=None, space=None):
        return _make_result()

    monkeypatch.setattr("app.worker.run_agent", fake_run_agent)
    worker.start()

    # Attach three independent subscribers
    _, q1 = worker.subscribe(task_id)
    _, q2 = worker.subscribe(task_id)
    _, q3 = worker.subscribe(task_id)

    await worker.enqueue(task_id)

    sentinel_count = 0

    async def wait_for_sentinel(q: asyncio.Queue) -> None:
        nonlocal sentinel_count
        while True:
            event = await asyncio.wait_for(q.get(), timeout=5.0)
            if event is _DONE_SENTINEL:
                sentinel_count += 1
                return

    await asyncio.gather(
        wait_for_sentinel(q1),
        wait_for_sentinel(q2),
        wait_for_sentinel(q3),
    )

    assert sentinel_count == 3, f"Expected 3 sentinels, got {sentinel_count}"


# ---------------------------------------------------------------------------
# 9. Auto-resume counter: _MAX_AUTO_RESUMES respected
# ---------------------------------------------------------------------------


async def test_auto_resume_max_count_respected(task_store, worker, monkeypatch):
    """
    When the agent hits error_max_turns repeatedly, the worker auto-resumes
    at most _MAX_AUTO_RESUMES (3) times, then stops — preventing infinite loops.

    The agent is called 4 times total (initial + 3 resumes). After the 4th
    call the task must be WAITING with no further enqueues.
    """
    task_id = await _active_task(task_store, title="Auto-resume test")
    call_count = 0

    async def max_turns_agent(task, *, user_message, on_event, cancel_event=None, space=None):
        nonlocal call_count
        call_count += 1
        return _make_result(
            exit_code=0,
            session_id="sess-mt",
            final_text="hit turn limit",
            status=None,
            stopped=False,
            result_subtype="error_max_turns",
        )

    monkeypatch.setattr("app.worker.run_agent", max_turns_agent)
    worker.start()

    # Subscribe before first enqueue so we receive all SENTINELs
    _, q = worker.subscribe(task_id)
    await worker.enqueue(task_id)

    # Count SENTINELs: one per completed run (initial + 3 auto-resumes = 4)
    sentinels = 0
    _MAX_AUTO_RESUMES = 3
    expected_calls = 1 + _MAX_AUTO_RESUMES

    async with asyncio.timeout(10.0):
        while sentinels < expected_calls:
            event = await q.get()
            if event is _DONE_SENTINEL:
                sentinels += 1

    # Wait briefly to confirm no 5th call sneaks in
    await asyncio.sleep(0.3)

    assert call_count == expected_calls, (
        f"Expected {expected_calls} agent calls, got {call_count}"
    )
    assert task_store.get(task_id).state == TaskState.WAITING, (
        "Task should be WAITING after exhausting auto-resumes"
    )
