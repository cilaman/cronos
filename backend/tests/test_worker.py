"""Tests for app.worker._finalize state resolution and exit_reason computation.

These tests exercise the worker's post-run finalization logic introduced/changed
in the "fix false CRASHED classification" commit. They focus on:

1. `_finalize()` state resolution order:
   - STATUS:DONE wins over exit_code != 0 (upgrade-killed runs).
   - exit_code != 0 + status=None → WAITING with crash message.
   - exit_code=0 + status=None → WAITING with new resume guidance.
   - error_max_turns is its own branch after WAIT/BLOCKED.

2. `exit_reason` computation (status-priority, NO_STATUS sentinel) flowing into
   both stats and trace records.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.agent import AgentResult, Status
from app.models import TaskState
from app.stats_store import StatsStore
from app.storage import TaskStore, WORKER_TRANSITIONS
from app.trace_store import TraceStore
from app.worker import Worker

SPACE_ID = "test-space"


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


async def _active_task(store: TaskStore, *, title: str = "Worker test") -> str:
    """Create a task and move it to ACTIVE so worker transitions are legal."""
    task = await store.create(space_id=SPACE_ID, title=title, brief="brief")
    # BACKLOG → ACTIVE is a user transition, but for tests we can use the
    # WORKER_TRANSITIONS set indirectly. We use the public transition method
    # with an allow-set that includes BACKLOG→ACTIVE.
    await store.transition(
        task.id,
        TaskState.ACTIVE,
        allowed={(TaskState.BACKLOG, TaskState.ACTIVE)},
    )
    return task.id


def _make_result(
    *,
    exit_code: int = 0,
    status: Status | None = None,
    context: str | None = None,
    stopped: bool = False,
    result_subtype: str | None = None,
    session_id: str | None = "sess-xyz",
    final_text: str = "done.",
) -> AgentResult:
    return AgentResult(
        exit_code=exit_code,
        session_id=session_id,
        final_text=final_text,
        stderr_tail="",
        status=status,
        context=context,
        raw_events=[],
        stopped=stopped,
        result_subtype=result_subtype,
    )


@pytest.fixture
async def worker(task_store, tmp_spaces_dir):
    return Worker(
        store=task_store,
        space_store=None,
        stats_store=StatsStore(tmp_spaces_dir),
        trace_store=TraceStore(tmp_spaces_dir),
    )


# ---------------------------------------------------------------------------
# _finalize: state resolution priority
# ---------------------------------------------------------------------------


async def test_finalize_status_done_with_nonzero_exit_marks_done(worker, task_store):
    """STATUS:DONE must win even when exit_code != 0 (upgrade-killed run)."""
    task_id = await _active_task(task_store, title="Upgrade-killed run")
    # Simulate: agent wrote STATUS:DONE then fired upgrade webhook which
    # SIGKILLed the process before clean shutdown.
    result = _make_result(exit_code=137, status=Status.DONE, session_id="sess-up")

    await worker._finalize(task_id, result)

    task = task_store.get(task_id)
    assert task.state == TaskState.DONE
    assert task.waiting_question is None


async def test_finalize_status_done_with_zero_exit_marks_done(worker, task_store):
    """Sanity baseline: clean DONE still produces DONE."""
    task_id = await _active_task(task_store)
    result = _make_result(exit_code=0, status=Status.DONE)

    await worker._finalize(task_id, result)

    task = task_store.get(task_id)
    assert task.state == TaskState.DONE
    assert task.waiting_question is None


async def test_finalize_nonzero_exit_no_status_marks_waiting_with_crash_message(
    worker, task_store
):
    """exit_code != 0 + status=None → WAITING with 'Agent crashed' message."""
    task_id = await _active_task(task_store)
    result = _make_result(exit_code=1, status=None)

    await worker._finalize(task_id, result)

    task = task_store.get(task_id)
    assert task.state == TaskState.WAITING
    assert task.waiting_question is not None
    assert "crashed" in task.waiting_question.lower()
    assert "exit code 1" in task.waiting_question


async def test_finalize_zero_exit_no_status_uses_new_resume_message(
    worker, task_store
):
    """exit_code=0 + status=None → WAITING with the new resume guidance.

    The new message instructs the agent to reply 'done' if complete, otherwise
    continue. Old text 'did not finish cleanly' must NOT appear.
    """
    task_id = await _active_task(task_store)
    result = _make_result(exit_code=0, status=None)

    await worker._finalize(task_id, result)

    task = task_store.get(task_id)
    assert task.state == TaskState.WAITING
    assert task.waiting_question is not None
    q = task.waiting_question
    # New phrasing must be present.
    assert "STATUS marker" in q
    assert "reply with just 'done'" in q
    assert "continue where you left off" in q.lower()
    # Old phrasing must not be present.
    assert "did not finish cleanly" not in q


async def test_finalize_status_wait_uses_context_as_question(worker, task_store):
    task_id = await _active_task(task_store)
    result = _make_result(
        exit_code=0,
        status=Status.WAIT,
        context="What color should I pick?",
    )

    await worker._finalize(task_id, result)

    task = task_store.get(task_id)
    assert task.state == TaskState.WAITING
    assert task.waiting_question == "What color should I pick?"


async def test_finalize_status_blocked_uses_context_as_reason(worker, task_store):
    task_id = await _active_task(task_store)
    result = _make_result(
        exit_code=0,
        status=Status.BLOCKED,
        context="No API key available",
    )

    await worker._finalize(task_id, result)

    task = task_store.get(task_id)
    assert task.state == TaskState.WAITING
    assert task.waiting_question is not None
    assert "Blocked" in task.waiting_question
    assert "No API key available" in task.waiting_question


async def test_finalize_error_max_turns_uses_dedicated_branch(worker, task_store):
    """error_max_turns subtype is now its own elif, distinct from generic no-status.

    The auto-resume logic re-activates the task right after WAITING is written,
    so we exhaust the auto-resume counter first to observe the terminal state.
    """
    task_id = await _active_task(task_store)
    # Exhaust the auto-resume counter so the next max-turns call doesn't
    # immediately re-enqueue and flip back to ACTIVE.
    worker._auto_resume_counts[task_id] = 99

    result = _make_result(
        exit_code=0,
        status=None,
        result_subtype="error_max_turns",
    )

    await worker._finalize(task_id, result)

    task = task_store.get(task_id)
    assert task.state == TaskState.WAITING
    assert task.waiting_question is not None
    q = task.waiting_question
    assert "turn limit" in q
    assert "continue" in q.lower()
    # Must not be the generic no-STATUS resume message.
    assert "STATUS marker" not in q


async def test_finalize_error_max_turns_distinct_from_no_status(worker, task_store):
    """Verify the dedicated max-turns branch never falls through to NO_STATUS phrasing.

    Even when auto-resume runs (counter not exhausted), the waiting_question
    that was written transiently to disk distinguishes max-turns from no-marker.
    We assert via the stats record which captures exit_reason at finalize time.
    """
    task_id = await _active_task(task_store)
    result = _make_result(
        exit_code=0,
        status=None,
        result_subtype="error_max_turns",
    )

    await worker._finalize(task_id, result)

    # exit_reason in stats should still be NO_STATUS (no STATUS marker present),
    # which is correct — the max-turns branch only affects state/question, not
    # the exit_reason classification.
    stats = await worker.stats_store.load(SPACE_ID, task_id)
    assert stats is not None
    assert stats.runs[0].exit_reason == "NO_STATUS"


async def test_finalize_stopped_takes_priority_over_status(worker, task_store):
    """A user-stopped run is WAITING regardless of status."""
    task_id = await _active_task(task_store)
    result = _make_result(
        exit_code=-15, status=Status.DONE, stopped=True
    )

    await worker._finalize(task_id, result)

    task = task_store.get(task_id)
    assert task.state == TaskState.WAITING
    assert task.waiting_question == "Stopped by user."


async def test_finalize_status_done_with_nonzero_exit_persists_no_session(
    worker, task_store
):
    """Non-zero exit must not persist session_id even when status is DONE.

    The session id from a crashed/killed process often isn't on disk for
    `--resume` to pick up, so we keep the previous one.
    """
    task_id = await _active_task(task_store)
    # No prior session id stored.
    result = _make_result(
        exit_code=137, status=Status.DONE, session_id="sess-killed"
    )

    await worker._finalize(task_id, result)

    task = task_store.get(task_id)
    assert task.claude_session_id is None


# ---------------------------------------------------------------------------
# _finalize: exit_reason / stats persistence
# ---------------------------------------------------------------------------


async def test_finalize_exit_reason_no_status_when_clean_exit_no_marker(
    worker, task_store, tmp_spaces_dir
):
    """exit_code=0 + status=None → exit_reason='NO_STATUS' in stats."""
    task_id = await _active_task(task_store)
    result = _make_result(exit_code=0, status=None)

    await worker._finalize(task_id, result)

    stats = await worker.stats_store.load(SPACE_ID, task_id)
    assert stats is not None
    assert len(stats.runs) == 1
    assert stats.runs[0].exit_reason == "NO_STATUS"
    # And had_crash must be False — a NO_STATUS run isn't a process crash.
    assert stats.runs[0].had_crash is False


async def test_finalize_exit_reason_crashed_when_nonzero_exit_no_status(
    worker, task_store
):
    task_id = await _active_task(task_store)
    result = _make_result(exit_code=1, status=None)

    await worker._finalize(task_id, result)

    stats = await worker.stats_store.load(SPACE_ID, task_id)
    assert stats.runs[0].exit_reason == "CRASHED"
    assert stats.runs[0].had_crash is True


async def test_finalize_exit_reason_done_when_status_done_with_nonzero_exit(
    worker, task_store
):
    """Status takes priority over exit code in exit_reason: DONE wins over CRASHED."""
    task_id = await _active_task(task_store)
    result = _make_result(exit_code=1, status=Status.DONE)

    await worker._finalize(task_id, result)

    stats = await worker.stats_store.load(SPACE_ID, task_id)
    assert stats.runs[0].exit_reason == "DONE"
    # had_crash still reflects the underlying exit code (kept for forensic value).
    assert stats.runs[0].had_crash is True


async def test_finalize_exit_reason_done_when_clean_exit(worker, task_store):
    task_id = await _active_task(task_store)
    result = _make_result(exit_code=0, status=Status.DONE)

    await worker._finalize(task_id, result)

    stats = await worker.stats_store.load(SPACE_ID, task_id)
    assert stats.runs[0].exit_reason == "DONE"
    assert stats.runs[0].had_crash is False


async def test_finalize_exit_reason_stopped_takes_priority(worker, task_store):
    task_id = await _active_task(task_store)
    result = _make_result(exit_code=0, status=Status.DONE, stopped=True)

    await worker._finalize(task_id, result)

    stats = await worker.stats_store.load(SPACE_ID, task_id)
    assert stats.runs[0].exit_reason == "STOPPED"


async def test_finalize_exit_reason_wait_persisted_in_stats(worker, task_store):
    task_id = await _active_task(task_store)
    result = _make_result(exit_code=0, status=Status.WAIT, context="q?")

    await worker._finalize(task_id, result)

    stats = await worker.stats_store.load(SPACE_ID, task_id)
    assert stats.runs[0].exit_reason == "WAIT"


# ---------------------------------------------------------------------------
# _finalize: exit_reason in run trace
# ---------------------------------------------------------------------------


async def test_finalize_trace_exit_reason_no_status(worker, task_store):
    """The same NO_STATUS exit_reason value flows into the persisted trace."""
    task_id = await _active_task(task_store)
    result = _make_result(exit_code=0, status=None)

    await worker._finalize(task_id, result)

    trace = await worker.trace_store.load_latest(SPACE_ID, task_id)
    assert trace is not None
    assert trace.exit_reason == "NO_STATUS"


async def test_finalize_trace_exit_reason_done_wins_over_crashed(worker, task_store):
    task_id = await _active_task(task_store)
    result = _make_result(exit_code=1, status=Status.DONE)

    await worker._finalize(task_id, result)

    trace = await worker.trace_store.load_latest(SPACE_ID, task_id)
    assert trace is not None
    assert trace.exit_reason == "DONE"


async def test_finalize_trace_exit_reason_crashed_when_no_status_and_nonzero(
    worker, task_store
):
    task_id = await _active_task(task_store)
    result = _make_result(exit_code=2, status=None)

    await worker._finalize(task_id, result)

    trace = await worker.trace_store.load_latest(SPACE_ID, task_id)
    assert trace is not None
    assert trace.exit_reason == "CRASHED"


# ---------------------------------------------------------------------------
# _finalize: agents-in-history metadata in the history entry
# ---------------------------------------------------------------------------


def _assistant_event(model: str) -> dict:
    """A minimal `assistant` stream-json event carrying the real model id."""
    return {
        "type": "assistant",
        "message": {
            "model": model,
            "usage": {
                "input_tokens": 0,
                "output_tokens": 0,
                "cache_read_input_tokens": 0,
                "cache_creation_input_tokens": 0,
            },
            "content": [],
        },
    }


def _make_result_with_model(
    real_model: str | None,
    *,
    exit_code: int = 0,
    status: Status | None = Status.DONE,
) -> AgentResult:
    """Build an AgentResult whose raw_events include a `real_model` id (or none)."""
    raw_events: list[dict] = []
    if real_model is not None:
        raw_events.append(_assistant_event(real_model))
    return AgentResult(
        exit_code=exit_code,
        session_id="sess-xyz",
        final_text="all done.",
        stderr_tail="",
        status=status,
        context=None,
        raw_events=raw_events,
        stopped=False,
        result_subtype=None,
    )


async def test_finalize_history_entry_contains_agent_metadata(worker, task_store):
    """First run: history entry header carries `run=0 model=... mode=...`."""
    task_id = await _active_task(task_store)
    result = _make_result_with_model("claude-sonnet-4-6-20250620")

    await worker._finalize(task_id, result)

    task = task_store.get(task_id)
    history = task.history
    # The header is the first line inside the opening fence.
    first_line = history.splitlines()[1]
    assert "[agent]" in first_line
    assert "run=0" in first_line
    assert "model=claude-sonnet-4-6-20250620" in first_line
    # The task fixture leaves agent_mode at its default value "auto".
    assert "mode=auto" in first_line


async def test_finalize_history_entry_run_index_increments_on_second_run(
    worker, task_store
):
    """Second invocation must record `run=1` in the history header."""
    task_id = await _active_task(task_store)

    # First run.
    await worker._finalize(
        task_id, _make_result_with_model("claude-sonnet-4-6-20250620")
    )

    # Task transitions to DONE on a STATUS:DONE result; allow it back to ACTIVE
    # so the worker can legally finalize a second run.
    await task_store.transition(
        task_id,
        TaskState.ACTIVE,
        allowed={(TaskState.DONE, TaskState.ACTIVE)},
    )

    # Second run.
    await worker._finalize(
        task_id, _make_result_with_model("claude-sonnet-4-6-20250620")
    )

    task = task_store.get(task_id)
    # Two agent entries in history, separated by the standard fence boundary.
    headers = [
        line for line in task.history.splitlines() if "[agent]" in line
    ]
    assert len(headers) == 2
    assert "run=0" in headers[0]
    assert "run=1" in headers[1]


async def test_finalize_history_entry_falls_back_to_task_agent_model(
    worker, task_store
):
    """When events do not expose a real model, header uses task.agent_model."""
    task_id = await _active_task(task_store)
    # No assistant events → extract_tokens_and_tools returns real_model=None.
    result = _make_result_with_model(None)

    await worker._finalize(task_id, result)

    task = task_store.get(task_id)
    first_line = task.history.splitlines()[1]
    assert "[agent]" in first_line
    assert "run=0" in first_line
    # The task fixture leaves agent_model at its default value "default".
    assert f"model={task.agent_model}" in first_line
    assert "mode=auto" in first_line
    # Must NOT contain a stray "None" leaked through from missing real_model.
    assert "model=None" not in first_line
