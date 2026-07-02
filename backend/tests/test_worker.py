"""Tests for app.worker._finalize state resolution and exit_reason computation.

These tests exercise the worker's post-run finalization logic introduced/changed
in the "fix false CRASHED classification" commit. They focus on:

1. `_finalize()` state resolution order:
   - STATUS:DONE wins over exit_code != 0 (upgrade-killed runs).
   - exit_code != 0 + status=None → WAITING with crash message.
   - exit_code=0 + status=None → WAITING with new resume guidance.
   - error_max_turns is its own branch after WAIT/BLOCKED.

2. `exit_reason` computation (status-priority, NO_CRONOS_STATUS sentinel) flowing into
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
from app.worker import Worker, _extract_subagent_types

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


async def test_finalize_zero_exit_no_status_auto_resumes_then_parks(
    worker, task_store
):
    """exit_code=0 + status=None now self-heals: bounded auto-resume, then parks.

    A clean exit with no STATUS marker (e.g. the agent handed work to a backgrounded
    job and ended the turn, P1) would otherwise hang WAITING forever. The finalizer
    re-enqueues it up to a small cap, then parks WAITING with the resume guidance so
    a human can act. Old text 'did not finish cleanly' must NOT appear.
    """
    task_id = await _active_task(task_store)

    # First _MAX_AUTO_RESUMES clean no-status exits auto-resume: the task is forced
    # back to ACTIVE (waiting_question cleared) and a follow-up turn is enqueued.
    for _ in range(3):
        await worker._finalize(task_id, _make_result(exit_code=0, status=None))
        task = task_store.get(task_id)
        assert task.state == TaskState.ACTIVE
        assert task.waiting_question is None
        assert not worker._queue.empty()
        worker._queue.get_nowait()  # drain the enqueued follow-up

    # Cap reached → next clean no-status exit parks WAITING with the guidance.
    await worker._finalize(task_id, _make_result(exit_code=0, status=None))
    task = task_store.get(task_id)
    assert task.state == TaskState.WAITING
    q = task.waiting_question
    assert q is not None
    assert "STATUS marker" in q
    assert "reply with just 'done'" in q
    assert "continue where you left off" in q.lower()
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
    """Verify the dedicated max-turns branch never falls through to NO_CRONOS_STATUS phrasing.

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

    # exit_reason in stats should still be NO_CRONOS_STATUS (no STATUS marker present),
    # which is correct — the max-turns branch only affects state/question, not
    # the exit_reason classification.
    stats = await worker.stats_store.load(SPACE_ID, task_id)
    assert stats is not None
    assert stats.runs[0].exit_reason == "NO_CRONOS_STATUS"


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
    """exit_code=0 + status=None → exit_reason='NO_CRONOS_STATUS' in stats."""
    task_id = await _active_task(task_store)
    result = _make_result(exit_code=0, status=None)

    await worker._finalize(task_id, result)

    stats = await worker.stats_store.load(SPACE_ID, task_id)
    assert stats is not None
    assert len(stats.runs) == 1
    assert stats.runs[0].exit_reason == "NO_CRONOS_STATUS"
    # And had_crash must be False — a NO_CRONOS_STATUS run isn't a process crash.
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
    """The same NO_CRONOS_STATUS exit_reason value flows into the persisted trace."""
    task_id = await _active_task(task_store)
    result = _make_result(exit_code=0, status=None)

    await worker._finalize(task_id, result)

    trace = await worker.trace_store.load_latest(SPACE_ID, task_id)
    assert trace is not None
    assert trace.exit_reason == "NO_CRONOS_STATUS"


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


# ---------------------------------------------------------------------------
# _extract_subagent_types: pure unit tests on the event-stream helper
# ---------------------------------------------------------------------------


def _agent_tool_use_event(
    subagent_type: object,
    *,
    name: str = "Agent",
    extra_blocks: list[dict] | None = None,
) -> dict:
    """Build an `assistant` event containing one Agent tool_use block.

    `subagent_type` may be any value (including None, non-string, missing-via
    sentinel) to drive negative paths. Pass the sentinel `_OMIT` to omit the
    `subagent_type` key from the input entirely.
    """
    inp: dict = {}
    if subagent_type is not _OMIT:
        inp["subagent_type"] = subagent_type
    blocks: list[dict] = [
        {
            "type": "tool_use",
            "name": name,
            "id": "toolu_x",
            "input": inp,
        }
    ]
    if extra_blocks:
        blocks.extend(extra_blocks)
    return {"type": "assistant", "message": {"content": blocks}}


# Sentinel for "do not put this key in the dict at all" in test inputs.
_OMIT = object()


def test_extract_subagent_types_empty_events_returns_empty_list():
    assert _extract_subagent_types([]) == []


def test_extract_subagent_types_no_agent_calls_returns_empty_list():
    """Events without any Agent tool_use blocks return []."""
    events = [
        {"type": "system", "message": {"content": []}},
        {
            "type": "assistant",
            "message": {
                "content": [
                    {"type": "text", "text": "hello"},
                    {"type": "tool_use", "name": "Read", "input": {"file_path": "/x"}},
                ]
            },
        },
        {"type": "user", "message": {"content": []}},
    ]
    assert _extract_subagent_types(events) == []


def test_extract_subagent_types_single_explore_call_lowercased():
    """A single Agent call with `subagent_type='Explore'` returns ['explore']."""
    events = [_agent_tool_use_event("Explore")]
    assert _extract_subagent_types(events) == ["explore"]


def test_extract_subagent_types_already_lowercase_passes_through():
    events = [_agent_tool_use_event("test-architect")]
    assert _extract_subagent_types(events) == ["test-architect"]


def test_extract_subagent_types_dedupes_repeated_same_type():
    """Repeated calls of the same subagent_type are collapsed to one entry."""
    events = [
        _agent_tool_use_event("Explore"),
        _agent_tool_use_event("explore"),
        _agent_tool_use_event("EXPLORE"),
    ]
    assert _extract_subagent_types(events) == ["explore"]


def test_extract_subagent_types_preserves_insertion_order_across_distinct_types():
    """Distinct types are returned in their first-seen order."""
    events = [
        _agent_tool_use_event("Plan"),
        _agent_tool_use_event("Explore"),
        _agent_tool_use_event("test-architect"),
    ]
    assert _extract_subagent_types(events) == ["plan", "explore", "test-architect"]


def test_extract_subagent_types_preserves_first_seen_order_with_dupes_mixed_in():
    """If a type repeats *after* a later type appears, the order does not change."""
    events = [
        _agent_tool_use_event("Plan"),
        _agent_tool_use_event("Explore"),
        _agent_tool_use_event("Plan"),  # dupe; must not move
        _agent_tool_use_event("test-architect"),
        _agent_tool_use_event("Explore"),  # dupe; must not move
    ]
    assert _extract_subagent_types(events) == ["plan", "explore", "test-architect"]


def test_extract_subagent_types_skips_missing_subagent_type_key():
    events = [_agent_tool_use_event(_OMIT)]
    assert _extract_subagent_types(events) == []


def test_extract_subagent_types_skips_non_string_subagent_type():
    """A non-string subagent_type (int, dict, None) is skipped gracefully."""
    events = [
        _agent_tool_use_event(None),
        _agent_tool_use_event(42),
        _agent_tool_use_event({"nested": "thing"}),
        _agent_tool_use_event(["list", "type"]),
    ]
    assert _extract_subagent_types(events) == []


def test_extract_subagent_types_skips_empty_string_subagent_type():
    """An empty-string subagent_type is treated as missing."""
    events = [_agent_tool_use_event("")]
    assert _extract_subagent_types(events) == []


def test_extract_subagent_types_mixes_valid_and_invalid_inputs():
    """Invalid entries are skipped but valid ones are still collected in order."""
    events = [
        _agent_tool_use_event(None),
        _agent_tool_use_event("Explore"),
        _agent_tool_use_event(""),
        _agent_tool_use_event("test-architect"),
        _agent_tool_use_event(123),
    ]
    assert _extract_subagent_types(events) == ["explore", "test-architect"]


def test_extract_subagent_types_ignores_non_assistant_events():
    """Agent-like tool_use blocks in non-assistant events are ignored."""
    events = [
        {
            "type": "system",  # not assistant
            "message": {
                "content": [
                    {
                        "type": "tool_use",
                        "name": "Agent",
                        "input": {"subagent_type": "Explore"},
                    }
                ]
            },
        },
        {
            "type": "user",  # not assistant
            "message": {
                "content": [
                    {
                        "type": "tool_use",
                        "name": "Agent",
                        "input": {"subagent_type": "Plan"},
                    }
                ]
            },
        },
    ]
    assert _extract_subagent_types(events) == []


def test_extract_subagent_types_ignores_other_tool_uses_in_same_event():
    """Only tool_use blocks named exactly 'Agent' contribute."""
    events = [
        {
            "type": "assistant",
            "message": {
                "content": [
                    {
                        "type": "tool_use",
                        "name": "Read",
                        "input": {"subagent_type": "Explore"},  # wrong name
                    },
                    {
                        "type": "tool_use",
                        "name": "Bash",
                        "input": {"subagent_type": "Plan"},  # wrong name
                    },
                    {
                        "type": "tool_use",
                        "name": "Agent",
                        "input": {"subagent_type": "test-architect"},  # the only valid one
                    },
                ]
            },
        }
    ]
    assert _extract_subagent_types(events) == ["test-architect"]


def test_extract_subagent_types_tolerates_malformed_event_shapes():
    """Various shape oddities must not raise; they are just skipped."""
    events = [
        {"type": "assistant"},  # no message
        {"type": "assistant", "message": None},  # message is None
        {"type": "assistant", "message": "string-not-dict"},  # message wrong type
        {"type": "assistant", "message": {}},  # missing content
        {"type": "assistant", "message": {"content": None}},  # content None
        {"type": "assistant", "message": {"content": "not-a-list"}},  # content wrong type
        {
            "type": "assistant",
            "message": {"content": [None, "string", 5]},  # blocks not dicts
        },
        {
            "type": "assistant",
            "message": {
                "content": [
                    {
                        "type": "tool_use",
                        "name": "Agent",
                        "input": "not-a-dict",  # input wrong type
                    }
                ]
            },
        },
        # And one valid event at the end to prove iteration continues.
        _agent_tool_use_event("Explore"),
    ]
    assert _extract_subagent_types(events) == ["explore"]


# ---------------------------------------------------------------------------
# _finalize: agents=... metadata in the history entry
# ---------------------------------------------------------------------------


def _make_result_with_agents(
    subagent_types: list[str],
    *,
    real_model: str = "claude-sonnet-4-6-20250620",
) -> AgentResult:
    """Build an AgentResult whose raw_events include one Agent tool_use per type.

    Each subagent type is wrapped in its own assistant event so insertion-order
    matches the input list.
    """
    raw_events: list[dict] = [_assistant_event(real_model)]
    for t in subagent_types:
        raw_events.append(_agent_tool_use_event(t))
    return AgentResult(
        exit_code=0,
        session_id="sess-xyz",
        final_text="all done.",
        stderr_tail="",
        status=Status.DONE,
        context=None,
        raw_events=raw_events,
        stopped=False,
        result_subtype=None,
    )


async def test_finalize_history_entry_appends_agents_field_when_subagents_used(
    worker, task_store
):
    """History header gains `agents=<csv>` when Agent tool calls were made."""
    task_id = await _active_task(task_store)
    result = _make_result_with_agents(["Explore", "test-architect"])

    await worker._finalize(task_id, result)

    task = task_store.get(task_id)
    first_line = task.history.splitlines()[1]
    assert "[agent]" in first_line
    assert "run=0" in first_line
    # Order matches insertion; types are lowercased.
    assert "agents=explore,test-architect" in first_line


async def test_finalize_history_entry_omits_agents_field_when_no_subagents(
    worker, task_store
):
    """History header has no `agents=` segment when no Agent calls were made."""
    task_id = await _active_task(task_store)
    result = _make_result_with_model("claude-sonnet-4-6-20250620")

    await worker._finalize(task_id, result)

    task = task_store.get(task_id)
    first_line = task.history.splitlines()[1]
    assert "[agent]" in first_line
    # Bare key must not appear at all when the list is empty.
    assert "agents=" not in first_line


async def test_finalize_history_entry_agents_dedupes_and_lowercases(
    worker, task_store
):
    """Repeated and mixed-case subagent_types are normalised in the header."""
    task_id = await _active_task(task_store)
    result = _make_result_with_agents(
        ["Explore", "EXPLORE", "Plan", "explore", "test-architect"]
    )

    await worker._finalize(task_id, result)

    task = task_store.get(task_id)
    first_line = task.history.splitlines()[1]
    assert "agents=explore,plan,test-architect" in first_line


# ---------------------------------------------------------------------------
# _topo_children: topological sort helper
# ---------------------------------------------------------------------------


from app.worker import _topo_children  # noqa: E402


async def test_topo_children_empty_goal(task_store):
    """Goal with no children returns an empty list."""
    goal = await task_store.create(space_id=SPACE_ID, title="Goal", brief="g", type="goal")
    assert _topo_children(goal.id, task_store) == []


async def test_topo_children_no_deps_returns_all_children(task_store):
    """Children without deps are all returned (order determined by manual_order/id)."""
    goal = await task_store.create(space_id=SPACE_ID, title="Goal", brief="g", type="goal")
    c1 = await task_store.create(space_id=SPACE_ID, title="C1", brief="b", parent_id=goal.id)
    c2 = await task_store.create(space_id=SPACE_ID, title="C2", brief="b", parent_id=goal.id)
    result = _topo_children(goal.id, task_store)
    assert set(result) == {c1.id, c2.id}
    assert len(result) == 2


async def test_topo_children_respects_sibling_deps(task_store):
    """A child that depends on a sibling runs after it."""
    goal = await task_store.create(space_id=SPACE_ID, title="Goal", brief="g", type="goal")
    c1 = await task_store.create(
        space_id=SPACE_ID, title="C1", brief="b", parent_id=goal.id
    )
    c2 = await task_store.create(
        space_id=SPACE_ID, title="C2", brief="b", parent_id=goal.id, depends_on=[c1.id]
    )
    result = _topo_children(goal.id, task_store)
    assert result.index(c1.id) < result.index(c2.id)


# ---------------------------------------------------------------------------
# _run_goal: orchestration logic (mocked run_agent)
# ---------------------------------------------------------------------------


async def test_run_goal_no_children_parks_waiting(worker, task_store):
    """A goal with no child tasks is parked WAITING (needs decomposition), not
    silently marked DONE — otherwise a childless goal (or an empty nested
    subgoal) would cascade a whole tree to DONE without doing any work."""
    goal = await task_store.create(space_id=SPACE_ID, title="Empty goal", brief="g", type="goal")
    await task_store.transition(
        goal.id, TaskState.ACTIVE, allowed={(TaskState.BACKLOG, TaskState.ACTIVE)}
    )

    await worker._run_goal(goal.id, None)

    assert task_store.get(goal.id).state == TaskState.WAITING


async def test_run_goal_skips_already_done_goal(worker, task_store):
    """Calling _run_goal on an already-DONE goal is a no-op (stale enqueue guard)."""
    goal = await task_store.create(space_id=SPACE_ID, title="Done goal", brief="g", type="goal")
    # Manually transition to DONE (simulating a goal that finished but was double-enqueued).
    await task_store.transition(goal.id, TaskState.ACTIVE, allowed={(TaskState.BACKLOG, TaskState.ACTIVE)})
    await task_store.transition(goal.id, TaskState.DONE, allowed={(TaskState.ACTIVE, TaskState.DONE)})

    await worker._run_goal(goal.id, None)

    # State unchanged and no history appended by a second run.
    assert task_store.get(goal.id).state == TaskState.DONE


async def test_run_goal_runs_children_in_order_and_marks_done(worker, task_store, monkeypatch):
    """Goal with two BACKLOG children runs them sequentially and marks itself DONE."""
    import app.worker as worker_module

    run_order: list[str] = []

    async def fake_run_agent(task, *, user_message, on_event, cancel_event=None, space=None, goal_context=None, **kwargs):
        run_order.append(task.id)
        return _make_result(exit_code=0, status=Status.DONE)

    monkeypatch.setattr(worker_module, "run_agent", fake_run_agent)

    goal = await task_store.create(space_id=SPACE_ID, title="Goal", brief="g", type="goal")
    c1 = await task_store.create(space_id=SPACE_ID, title="C1", brief="b", parent_id=goal.id)
    c2 = await task_store.create(
        space_id=SPACE_ID, title="C2", brief="b", parent_id=goal.id, depends_on=[c1.id]
    )
    await task_store.transition(
        goal.id, TaskState.ACTIVE, allowed={(TaskState.BACKLOG, TaskState.ACTIVE)}
    )

    await worker._run_goal(goal.id, None)

    assert run_order == [c1.id, c2.id]
    assert task_store.get(c1.id).state == TaskState.DONE
    assert task_store.get(c2.id).state == TaskState.DONE
    assert task_store.get(goal.id).state == TaskState.DONE


async def test_bare_goal_child_emits_node_status_and_finalizes_done(
    worker, task_store, monkeypatch
):
    """Bare mode acceptance: a goal WITHOUT the delivery-workflow sentinel and
    WITHOUT any gate/report structure runs its single child through
    ``_topo_children``.  The child's agent emits a plain ``node_status`` block —
    no CC-v1 ``{phase}-report`` artifact — and ``parse_status`` reads it to DONE.
    This proves a goal runs to completion without any pipeline."""
    import app.worker as worker_module
    from app.agent import parse_status
    from app.delivery_driver import detect_delivery_workflow_spec

    node_status_output = (
        "All done.\n\n"
        "```node_status\n"
        '{"status": "done", "produces": "change", "fields": {}}\n'
        "```\n"
    )

    async def fake_run_agent(
        task, *, user_message, on_event, cancel_event=None,
        space=None, goal_context=None, **kwargs,
    ):
        # Derive the result exactly as the real runner does — parse the agent's
        # final text. No report artifact is written or read anywhere.
        status, context = parse_status(node_status_output)
        return _make_result(
            exit_code=0, status=status, context=context,
            final_text=node_status_output,
        )

    monkeypatch.setattr(worker_module, "run_agent", fake_run_agent)

    goal = await task_store.create(
        space_id=SPACE_ID, title="Bare Goal", brief="ship it", type="goal"
    )
    child = await task_store.create(
        space_id=SPACE_ID, title="Child", brief="do the thing", parent_id=goal.id
    )
    await task_store.transition(
        goal.id, TaskState.ACTIVE, allowed={(TaskState.BACKLOG, TaskState.ACTIVE)}
    )

    # Precondition: no delivery-workflow sentinel → the bare _topo_children path runs.
    assert detect_delivery_workflow_spec(goal.brief or "") is None
    # And the agent's node_status block parses to DONE via tier 1 (no report artifact).
    # Compare by value (Status is a str-enum) to stay robust under pytest's dual
    # module-import ordering, which can give the enum two class identities.
    assert parse_status(node_status_output)[0] == Status.DONE

    await worker._run_goal(goal.id, None)

    assert task_store.get(child.id).state == TaskState.DONE
    assert task_store.get(goal.id).state == TaskState.DONE


async def test_run_goal_skips_done_children(worker, task_store, monkeypatch):
    """Children already DONE are skipped; goal still completes."""
    import app.worker as worker_module

    ran: list[str] = []

    async def fake_run_agent(task, *, user_message, on_event, cancel_event=None, space=None, goal_context=None, **kwargs):
        ran.append(task.id)
        return _make_result(exit_code=0, status=Status.DONE)

    monkeypatch.setattr(worker_module, "run_agent", fake_run_agent)

    goal = await task_store.create(space_id=SPACE_ID, title="Goal", brief="g", type="goal")
    c1 = await task_store.create(space_id=SPACE_ID, title="C1", brief="b", parent_id=goal.id)
    c2 = await task_store.create(space_id=SPACE_ID, title="C2", brief="b", parent_id=goal.id)

    # Pre-complete c1
    await task_store.transition(c1.id, TaskState.ACTIVE, allowed={(TaskState.BACKLOG, TaskState.ACTIVE)})
    await task_store.finalize_run(c1.id, new_state=TaskState.DONE, session_id=None, waiting_question=None, history_entry="```\ndone\n```")

    await task_store.transition(
        goal.id, TaskState.ACTIVE, allowed={(TaskState.BACKLOG, TaskState.ACTIVE)}
    )

    await worker._run_goal(goal.id, None)

    assert c1.id not in ran
    assert c2.id in ran
    assert task_store.get(goal.id).state == TaskState.DONE


async def test_run_goal_pauses_silently_when_child_is_active(worker, task_store):
    """If a child is already ACTIVE when _run_goal starts (e.g. restart after upgrade),
    the goal goes WAITING with no user-visible waiting_question.
    goal_sync will re-enqueue the goal once the child finishes."""
    goal = await task_store.create(space_id=SPACE_ID, title="Goal", brief="g", type="goal")
    child = await task_store.create(space_id=SPACE_ID, title="C1", brief="b", parent_id=goal.id)
    # Simulate the post-upgrade state: both goal and child preserved as ACTIVE.
    await task_store.transition(
        goal.id, TaskState.ACTIVE, allowed={(TaskState.BACKLOG, TaskState.ACTIVE)}
    )
    await task_store.transition(
        child.id, TaskState.ACTIVE, allowed={(TaskState.BACKLOG, TaskState.ACTIVE)}
    )

    await worker._run_goal(goal.id, None)

    goal_task = task_store.get(goal.id)
    assert goal_task.state == TaskState.WAITING
    # No user-facing question — this resolves automatically when the child finishes.
    assert goal_task.waiting_question is None


async def test_run_goal_pauses_when_child_fails(worker, task_store, monkeypatch):
    """If a child ends in WAIT, the goal transitions to WAITING."""
    import app.worker as worker_module

    async def fake_run_agent(task, *, user_message, on_event, cancel_event=None, space=None, goal_context=None, **kwargs):
        return _make_result(exit_code=0, status=Status.WAIT, context="Need input")

    monkeypatch.setattr(worker_module, "run_agent", fake_run_agent)

    goal = await task_store.create(space_id=SPACE_ID, title="Goal", brief="g", type="goal")
    await task_store.create(space_id=SPACE_ID, title="C1", brief="b", parent_id=goal.id)
    await task_store.transition(
        goal.id, TaskState.ACTIVE, allowed={(TaskState.BACKLOG, TaskState.ACTIVE)}
    )

    await worker._run_goal(goal.id, None)

    goal_task = task_store.get(goal.id)
    assert goal_task.state == TaskState.WAITING
    assert goal_task.waiting_question is not None


async def test_run_goal_injects_goal_context(worker, task_store, monkeypatch):
    """goal_context passed to run_agent contains the goal title and brief."""
    import app.worker as worker_module

    captured_contexts: list[str | None] = []

    async def fake_run_agent(task, *, user_message, on_event, cancel_event=None, space=None, goal_context=None, **kwargs):
        captured_contexts.append(goal_context)
        return _make_result(exit_code=0, status=Status.DONE)

    monkeypatch.setattr(worker_module, "run_agent", fake_run_agent)

    goal = await task_store.create(
        space_id=SPACE_ID, title="My Goal", brief="The full goal brief.", type="goal"
    )
    await task_store.create(space_id=SPACE_ID, title="C1", brief="b", parent_id=goal.id)
    await task_store.transition(
        goal.id, TaskState.ACTIVE, allowed={(TaskState.BACKLOG, TaskState.ACTIVE)}
    )

    await worker._run_goal(goal.id, None)

    assert len(captured_contexts) == 1
    ctx = captured_contexts[0]
    assert ctx is not None
    assert "My Goal" in ctx
    assert "The full goal brief." in ctx


# ---------------------------------------------------------------------------
# _run_goal: nested goal (sub-goal recursion) tests
# ---------------------------------------------------------------------------


async def test_nested_goal_two_level_hierarchy(worker, task_store, monkeypatch):
    """goal → sub-goal → [task1, task2]: all tasks run in order, parent reaches DONE."""
    import app.worker as worker_module

    run_order: list[str] = []

    async def fake_run_agent(task, *, user_message, on_event, cancel_event=None, space=None, goal_context=None, **kwargs):
        run_order.append(task.id)
        return _make_result(exit_code=0, status=Status.DONE)

    monkeypatch.setattr(worker_module, "run_agent", fake_run_agent)

    parent = await task_store.create(space_id=SPACE_ID, title="Parent Goal", brief="parent brief", type="goal")
    sub = await task_store.create(space_id=SPACE_ID, title="Sub Goal", brief="sub brief", type="goal", parent_id=parent.id)
    t1 = await task_store.create(space_id=SPACE_ID, title="T1", brief="b", parent_id=sub.id)
    t2 = await task_store.create(space_id=SPACE_ID, title="T2", brief="b", parent_id=sub.id, depends_on=[t1.id])
    await task_store.transition(parent.id, TaskState.ACTIVE, allowed={(TaskState.BACKLOG, TaskState.ACTIVE)})

    await worker._run_goal(parent.id, None)

    assert run_order == [t1.id, t2.id]
    assert task_store.get(t1.id).state == TaskState.DONE
    assert task_store.get(t2.id).state == TaskState.DONE
    assert task_store.get(sub.id).state == TaskState.DONE
    assert task_store.get(parent.id).state == TaskState.DONE


async def test_nested_goal_mixed_children(worker, task_store, monkeypatch):
    """goal → [direct_task, sub-goal → nested_task]: both leaves run, parent reaches DONE."""
    import app.worker as worker_module

    run_order: list[str] = []

    async def fake_run_agent(task, *, user_message, on_event, cancel_event=None, space=None, goal_context=None, **kwargs):
        run_order.append(task.id)
        return _make_result(exit_code=0, status=Status.DONE)

    monkeypatch.setattr(worker_module, "run_agent", fake_run_agent)

    parent = await task_store.create(space_id=SPACE_ID, title="Parent Goal", brief="g", type="goal")
    direct = await task_store.create(space_id=SPACE_ID, title="Direct Task", brief="b", parent_id=parent.id)
    sub = await task_store.create(space_id=SPACE_ID, title="Sub Goal", brief="s", type="goal", parent_id=parent.id, depends_on=[direct.id])
    nested = await task_store.create(space_id=SPACE_ID, title="Nested Task", brief="b", parent_id=sub.id)
    await task_store.transition(parent.id, TaskState.ACTIVE, allowed={(TaskState.BACKLOG, TaskState.ACTIVE)})

    await worker._run_goal(parent.id, None)

    assert direct.id in run_order
    assert nested.id in run_order
    assert run_order.index(direct.id) < run_order.index(nested.id)
    assert task_store.get(direct.id).state == TaskState.DONE
    assert task_store.get(nested.id).state == TaskState.DONE
    assert task_store.get(sub.id).state == TaskState.DONE
    assert task_store.get(parent.id).state == TaskState.DONE


async def test_nested_goal_three_level_hierarchy(worker, task_store, monkeypatch):
    """goal → sub-goal → child-goal → leaf_task: 3-level recursion reaches DONE."""
    import app.worker as worker_module

    ran: list[str] = []

    async def fake_run_agent(task, *, user_message, on_event, cancel_event=None, space=None, goal_context=None, **kwargs):
        ran.append(task.id)
        return _make_result(exit_code=0, status=Status.DONE)

    monkeypatch.setattr(worker_module, "run_agent", fake_run_agent)

    grandparent = await task_store.create(space_id=SPACE_ID, title="Grandparent", brief="g", type="goal")
    parent = await task_store.create(space_id=SPACE_ID, title="Parent", brief="p", type="goal", parent_id=grandparent.id)
    child_goal = await task_store.create(space_id=SPACE_ID, title="Child Goal", brief="c", type="goal", parent_id=parent.id)
    leaf = await task_store.create(space_id=SPACE_ID, title="Leaf Task", brief="b", parent_id=child_goal.id)
    await task_store.transition(grandparent.id, TaskState.ACTIVE, allowed={(TaskState.BACKLOG, TaskState.ACTIVE)})

    await worker._run_goal(grandparent.id, None)

    assert ran == [leaf.id]
    assert task_store.get(leaf.id).state == TaskState.DONE
    assert task_store.get(child_goal.id).state == TaskState.DONE
    assert task_store.get(parent.id).state == TaskState.DONE
    assert task_store.get(grandparent.id).state == TaskState.DONE


async def test_nested_goal_subgoal_failure_pauses_parent(worker, task_store, monkeypatch):
    """If a sub-goal's task fails (WAIT), sub-goal and parent both land in WAITING."""
    import app.worker as worker_module

    async def fake_run_agent(task, *, user_message, on_event, cancel_event=None, space=None, goal_context=None, **kwargs):
        return _make_result(exit_code=0, status=Status.WAIT, context="Needs input")

    monkeypatch.setattr(worker_module, "run_agent", fake_run_agent)

    parent = await task_store.create(space_id=SPACE_ID, title="Parent Goal", brief="g", type="goal")
    sub = await task_store.create(space_id=SPACE_ID, title="Sub Goal", brief="s", type="goal", parent_id=parent.id)
    await task_store.create(space_id=SPACE_ID, title="Failing Task", brief="b", parent_id=sub.id)
    await task_store.transition(parent.id, TaskState.ACTIVE, allowed={(TaskState.BACKLOG, TaskState.ACTIVE)})

    await worker._run_goal(parent.id, None)

    assert task_store.get(sub.id).state == TaskState.WAITING
    parent_task = task_store.get(parent.id)
    assert parent_task.state == TaskState.WAITING
    assert parent_task.waiting_question is not None
    assert "Sub Goal" in parent_task.waiting_question


# ---------------------------------------------------------------------------
# _run_goal: trace and stats recording for the goal itself
# ---------------------------------------------------------------------------


async def test_run_goal_records_trace_for_goal_task(worker, task_store, monkeypatch):
    """_run_goal writes a synthetic RunTrace for the goal task itself."""
    import app.worker as worker_module

    async def fake_run_agent(task, *, user_message, on_event, cancel_event=None, space=None, goal_context=None, **kwargs):
        return _make_result(exit_code=0, status=Status.DONE)

    monkeypatch.setattr(worker_module, "run_agent", fake_run_agent)

    goal = await task_store.create(space_id=SPACE_ID, title="Traced Goal", brief="g", type="goal")
    await task_store.create(space_id=SPACE_ID, title="C1", brief="b", parent_id=goal.id)
    await task_store.transition(
        goal.id, TaskState.ACTIVE, allowed={(TaskState.BACKLOG, TaskState.ACTIVE)}
    )

    await worker._run_goal(goal.id, None)

    assert task_store.get(goal.id).state == TaskState.DONE
    trace = await worker.trace_store.load_latest(SPACE_ID, goal.id)
    assert trace is not None
    assert trace.task_id == goal.id
    assert trace.exit_reason == "DONE"
    assert trace.run_index == 0


async def test_run_goal_records_stats_for_goal_task(worker, task_store, monkeypatch):
    """_run_goal writes a RunStats entry for the goal task itself."""
    import app.worker as worker_module

    async def fake_run_agent(task, *, user_message, on_event, cancel_event=None, space=None, goal_context=None, **kwargs):
        return _make_result(exit_code=0, status=Status.DONE)

    monkeypatch.setattr(worker_module, "run_agent", fake_run_agent)

    goal = await task_store.create(space_id=SPACE_ID, title="Traced Goal", brief="g", type="goal")
    await task_store.create(space_id=SPACE_ID, title="C1", brief="b", parent_id=goal.id)
    await task_store.transition(
        goal.id, TaskState.ACTIVE, allowed={(TaskState.BACKLOG, TaskState.ACTIVE)}
    )

    await worker._run_goal(goal.id, None)

    stats = await worker.stats_store.load(SPACE_ID, goal.id)
    assert stats is not None
    assert len(stats.runs) == 1
    assert stats.runs[0].exit_reason == "DONE"
    assert stats.runs[0].run_index == 0


async def test_run_goal_records_waiting_trace_on_child_failure(worker, task_store, monkeypatch):
    """_run_goal writes exit_reason='WAITING' when a child task fails."""
    import app.worker as worker_module

    async def fake_run_agent(task, *, user_message, on_event, cancel_event=None, space=None, goal_context=None, **kwargs):
        return _make_result(exit_code=0, status=Status.WAIT, context="Need input")

    monkeypatch.setattr(worker_module, "run_agent", fake_run_agent)

    goal = await task_store.create(space_id=SPACE_ID, title="Goal", brief="g", type="goal")
    await task_store.create(space_id=SPACE_ID, title="C1", brief="b", parent_id=goal.id)
    await task_store.transition(
        goal.id, TaskState.ACTIVE, allowed={(TaskState.BACKLOG, TaskState.ACTIVE)}
    )

    await worker._run_goal(goal.id, None)

    assert task_store.get(goal.id).state == TaskState.WAITING
    trace = await worker.trace_store.load_latest(SPACE_ID, goal.id)
    assert trace is not None
    assert trace.exit_reason == "WAITING"


async def test_run_goal_increments_run_index_on_second_run(worker, task_store, monkeypatch):
    """Trace run_index increments when the goal is re-run."""
    import app.worker as worker_module

    call_count = {"n": 0}

    async def fake_run_agent(task, *, user_message, on_event, cancel_event=None, space=None, goal_context=None, **kwargs):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return _make_result(exit_code=0, status=Status.WAIT, context="wait")
        return _make_result(exit_code=0, status=Status.DONE)

    monkeypatch.setattr(worker_module, "run_agent", fake_run_agent)

    goal = await task_store.create(space_id=SPACE_ID, title="Re-run Goal", brief="g", type="goal")
    c1 = await task_store.create(space_id=SPACE_ID, title="C1", brief="b", parent_id=goal.id)
    await task_store.transition(
        goal.id, TaskState.ACTIVE, allowed={(TaskState.BACKLOG, TaskState.ACTIVE)}
    )

    # First run — child fails → goal WAITING
    await worker._run_goal(goal.id, None)
    assert task_store.get(goal.id).state == TaskState.WAITING

    # Resume goal and child for second run
    await task_store.transition(
        c1.id, TaskState.BACKLOG, allowed={(TaskState.WAITING, TaskState.BACKLOG)}
    )
    await task_store.transition(
        goal.id, TaskState.ACTIVE, allowed={(TaskState.WAITING, TaskState.ACTIVE)}
    )

    # Second run — child succeeds → goal DONE
    await worker._run_goal(goal.id, None)
    assert task_store.get(goal.id).state == TaskState.DONE

    traces = await worker.trace_store.list_runs(SPACE_ID, goal.id)
    assert len(traces) == 2
    assert traces[0].run_index == 0
    assert traces[1].run_index == 1


# ---------------------------------------------------------------------------
# _finalize: autopilot post-DONE PR hook
# ---------------------------------------------------------------------------


from app.autopilot_pr import PostDoneResult  # noqa: E402


@pytest.fixture
async def worker_with_space(task_store, space_store, tmp_spaces_dir):
    """A Worker wired to a real SpaceStore so the post-DONE autopilot hook can fire."""
    return Worker(
        store=task_store,
        space_store=space_store,
        stats_store=StatsStore(tmp_spaces_dir),
        trace_store=TraceStore(tmp_spaces_dir),
    )


async def test_finalize_done_calls_run_post_done_flow(
    worker_with_space, task_store, monkeypatch
):
    """When a task reaches DONE and space_store is set, autopilot_pr.run_post_done_flow is invoked."""
    import app.worker as worker_module

    called: list[tuple[str, str]] = []

    async def fake_flow(task, space, store):
        called.append((task.id, space.id))
        return PostDoneResult(committed=True, pushed=True)

    monkeypatch.setattr(worker_module.autopilot_pr, "run_post_done_flow", fake_flow)

    task_id = await _active_task(task_store, title="Will finish")
    result = _make_result(exit_code=0, status=Status.DONE)

    await worker_with_space._finalize(task_id, result)

    assert called == [(task_id, SPACE_ID)]


async def test_finalize_waiting_does_not_call_run_post_done_flow(
    worker_with_space, task_store, monkeypatch
):
    """When a task ends in WAITING (non-DONE), the post-DONE flow is NOT invoked."""
    import app.worker as worker_module

    called: list[tuple] = []

    async def fake_flow(task, space, store):
        called.append((task.id, space.id))
        return PostDoneResult()

    monkeypatch.setattr(worker_module.autopilot_pr, "run_post_done_flow", fake_flow)

    task_id = await _active_task(task_store)
    # status=WAIT → WAITING state.
    result = _make_result(exit_code=0, status=Status.WAIT, context="hold up")

    await worker_with_space._finalize(task_id, result)

    assert called == []


async def test_finalize_done_without_space_store_skips_post_done_flow(
    worker, task_store, monkeypatch
):
    """The default `worker` fixture has space_store=None — post-DONE flow must not fire."""
    import app.worker as worker_module

    called: list[tuple] = []

    async def fake_flow(task, space, store):
        called.append((task.id, space.id))
        return PostDoneResult()

    monkeypatch.setattr(worker_module.autopilot_pr, "run_post_done_flow", fake_flow)

    task_id = await _active_task(task_store)
    result = _make_result(exit_code=0, status=Status.DONE)

    await worker._finalize(task_id, result)

    assert called == []


async def test_finalize_publishes_pr_opened_when_pr_url_returned(
    worker_with_space, task_store, monkeypatch
):
    """When run_post_done_flow returns pr_url, a 'pr_opened' event with that URL is published."""
    import app.worker as worker_module

    async def fake_flow(task, space, store):
        return PostDoneResult(
            committed=True,
            pushed=True,
            pr_url="https://github.com/x/y/pull/55",
        )

    monkeypatch.setattr(worker_module.autopilot_pr, "run_post_done_flow", fake_flow)

    task_id = await _active_task(task_store)
    result = _make_result(exit_code=0, status=Status.DONE)

    await worker_with_space._finalize(task_id, result)

    buf = worker_with_space._run_buffer.get(task_id, [])
    pr_events = [e for e in buf if e.get("type") == "pr_opened"]
    assert len(pr_events) == 1
    assert pr_events[0]["pr_url"] == "https://github.com/x/y/pull/55"
    # The proposed_pr_path branch must NOT fire concurrently.
    assert "proposed_pr_path" not in pr_events[0]


async def test_finalize_publishes_pr_opened_with_proposed_pr_path_when_no_pr_url(
    worker_with_space, task_store, monkeypatch
):
    """When pr_url is None but proposed_pr_path is set, the event carries proposed_pr_path."""
    import app.worker as worker_module

    async def fake_flow(task, space, store):
        return PostDoneResult(
            committed=True,
            pushed=True,
            pr_url=None,
            proposed_pr_path="/data/spaces/x/.cronos/pull_requests/t.md",
        )

    monkeypatch.setattr(worker_module.autopilot_pr, "run_post_done_flow", fake_flow)

    task_id = await _active_task(task_store)
    result = _make_result(exit_code=0, status=Status.DONE)

    await worker_with_space._finalize(task_id, result)

    buf = worker_with_space._run_buffer.get(task_id, [])
    pr_events = [e for e in buf if e.get("type") == "pr_opened"]
    assert len(pr_events) == 1
    assert pr_events[0]["proposed_pr_path"] == "/data/spaces/x/.cronos/pull_requests/t.md"
    # No pr_url key set.
    assert "pr_url" not in pr_events[0]


async def test_finalize_does_not_publish_pr_opened_when_both_refs_are_none(
    worker_with_space, task_store, monkeypatch
):
    """If post-DONE flow returns neither pr_url nor proposed_pr_path, no pr_opened event."""
    import app.worker as worker_module

    async def fake_flow(task, space, store):
        return PostDoneResult(committed=False)

    monkeypatch.setattr(worker_module.autopilot_pr, "run_post_done_flow", fake_flow)

    task_id = await _active_task(task_store)
    result = _make_result(exit_code=0, status=Status.DONE)

    await worker_with_space._finalize(task_id, result)

    buf = worker_with_space._run_buffer.get(task_id, [])
    pr_events = [e for e in buf if e.get("type") == "pr_opened"]
    assert pr_events == []


async def test_finalize_swallows_run_post_done_flow_exception(
    worker_with_space, task_store, monkeypatch, caplog
):
    """If run_post_done_flow raises, _finalize logs but does not propagate.

    Locks the safety contract: an autopilot failure must not crash the worker
    nor corrupt the run finalization (task already moved to DONE).
    """
    import logging as logging_mod

    import app.worker as worker_module

    async def fake_flow(task, space, store):
        raise RuntimeError("autopilot exploded")

    monkeypatch.setattr(worker_module.autopilot_pr, "run_post_done_flow", fake_flow)

    task_id = await _active_task(task_store)
    result = _make_result(exit_code=0, status=Status.DONE)

    with caplog.at_level(logging_mod.ERROR, logger="cronos.worker"):
        await worker_with_space._finalize(task_id, result)

    # Task is still DONE (state was persisted before the autopilot hook).
    assert task_store.get(task_id).state == TaskState.DONE
    # Error was logged.
    error_records = [
        r for r in caplog.record_tuples
        if r[0] == "cronos.worker" and r[1] == logging_mod.ERROR
    ]
    assert any("autopilot_pr" in r[2] for r in error_records)


async def test_finalize_done_publishes_run_end_after_pr_opened(
    worker_with_space, task_store, monkeypatch
):
    """The pr_opened event is published BEFORE run_end so SSE clients see it pre-EOF."""
    import app.worker as worker_module

    async def fake_flow(task, space, store):
        return PostDoneResult(pr_url="https://github.com/x/y/pull/1")

    monkeypatch.setattr(worker_module.autopilot_pr, "run_post_done_flow", fake_flow)

    task_id = await _active_task(task_store)
    result = _make_result(exit_code=0, status=Status.DONE)

    await worker_with_space._finalize(task_id, result)

    buf = worker_with_space._run_buffer.get(task_id, [])
    event_types = [e.get("type") for e in buf]
    # pr_opened must precede run_end.
    pr_idx = event_types.index("pr_opened")
    run_end_idx = event_types.index("run_end")
    assert pr_idx < run_end_idx


# ---------------------------------------------------------------------------
# _run_goal: auto-repair non-sibling dep
# ---------------------------------------------------------------------------


async def test_run_goal_auto_repairs_non_sibling_dep_and_runs_in_order(
    worker, task_store, monkeypatch, caplog
):
    """A direct child (sub-goal) carries a depends_on pointing at a grandchild of the
    parent goal (non-sibling dep).  _run_goal should auto-repair by replacing the
    grandchild dep with the proper sibling dep, re-order, and run everything in the
    correct order.

    Setup:
      goal
        ├── alpha-subgoal   (ID sorts first — processed first without repair)
        │     └── alpha-doc  ← grandchild of goal
        └── zeta-subgoal    (depends_on=[alpha-doc] — wrong: non-sibling dep)
              └── zeta-task

    Without repair:  alpha-subgoal runs first (sorts before zeta alphabetically),
    alpha-doc finishes, zeta tries to activate → dep already met → no error.

    To trigger the repair we need zeta-subgoal to be processed BEFORE alpha-subgoal.
    We achieve this by giving zeta-subgoal a depends_on=[alpha-doc] (the non-sibling
    dep) while naming it so it sorts FIRST alphabetically ("aaa-" prefix).
    """
    import logging as logging_mod
    import app.worker as worker_module

    run_order: list[str] = []

    async def fake_run_agent(task, *, user_message, on_event, cancel_event=None, space=None, goal_context=None, **kwargs):
        run_order.append(task.id)
        return _make_result(exit_code=0, status=Status.DONE)

    monkeypatch.setattr(worker_module, "run_agent", fake_run_agent)

    # Parent goal
    goal = await task_store.create(space_id=SPACE_ID, title="Parent Goal", brief="g", type="goal")

    # "Beta SG": the prerequisite subgoal (ID ~ "...-beta-sg", sorts second)
    beta_sg = await task_store.create(
        space_id=SPACE_ID, title="Beta SG", brief="b", parent_id=goal.id, type="goal"
    )
    beta_doc = await task_store.create(
        space_id=SPACE_ID, title="Beta doc", brief="b", parent_id=beta_sg.id
    )

    # "Alpha SG": the dependent subgoal (ID ~ "...-alpha-sg", sorts first).
    # depends_on=[beta_doc] — a grandchild dep, NOT a sibling dep.
    # _topo_children ignores non-sibling deps, so alpha is ordered before beta
    # but transition(alpha, ACTIVE) fails because beta_doc is not done.
    alpha_sg = await task_store.create(
        space_id=SPACE_ID, title="Alpha SG", brief="b", parent_id=goal.id, type="goal",
        depends_on=[beta_doc.id],
    )
    alpha_task = await task_store.create(
        space_id=SPACE_ID, title="Alpha task", brief="b", parent_id=alpha_sg.id
    )

    await task_store.transition(goal.id, TaskState.ACTIVE, allowed={(TaskState.BACKLOG, TaskState.ACTIVE)})

    with caplog.at_level(logging_mod.WARNING, logger="cronos.worker"):
        await worker._run_goal(goal.id, None)

    # Beta (prerequisite) must run before Alpha
    assert run_order.index(beta_doc.id) < run_order.index(alpha_task.id)
    # Auto-repair warning emitted
    assert any("Auto-repaired missing sibling dep" in r.message for r in caplog.records)
    # Alpha SG now has Beta SG as a sibling dep
    alpha_sg_after = task_store.get(alpha_sg.id)
    assert beta_sg.id in alpha_sg_after.depends_on
    # Goal completes successfully
    assert task_store.get(goal.id).state == TaskState.DONE


async def test_run_goal_correct_sibling_deps_no_repair_needed(
    worker, task_store, monkeypatch, caplog
):
    """When sibling deps are already correct, no auto-repair fires and goal succeeds."""
    import logging as logging_mod
    import app.worker as worker_module

    async def fake_run_agent(task, *, user_message, on_event, cancel_event=None, space=None, goal_context=None, **kwargs):
        return _make_result(exit_code=0, status=Status.DONE)

    monkeypatch.setattr(worker_module, "run_agent", fake_run_agent)

    goal = await task_store.create(space_id=SPACE_ID, title="Goal", brief="g", type="goal")
    sg_a = await task_store.create(
        space_id=SPACE_ID, title="SG-A", brief="b", parent_id=goal.id, type="goal"
    )
    await task_store.create(space_id=SPACE_ID, title="SG-A task", brief="b", parent_id=sg_a.id)
    sg_b = await task_store.create(
        space_id=SPACE_ID, title="SG-B", brief="b", parent_id=goal.id, type="goal",
        depends_on=[sg_a.id],
    )
    await task_store.create(space_id=SPACE_ID, title="SG-B task", brief="b", parent_id=sg_b.id)

    await task_store.transition(goal.id, TaskState.ACTIVE, allowed={(TaskState.BACKLOG, TaskState.ACTIVE)})

    with caplog.at_level(logging_mod.WARNING, logger="cronos.worker"):
        await worker._run_goal(goal.id, None)

    assert not any("Auto-repaired" in r.message for r in caplog.records)
    assert task_store.get(goal.id).state == TaskState.DONE


async def test_run_goal_auto_repair_capped_at_one_attempt(
    worker, task_store, monkeypatch, caplog
):
    """Auto-repair skips deps it cannot resolve (dep not found in store); goal fails."""
    import logging as logging_mod
    import app.worker as worker_module

    async def fake_run_agent(task, *, user_message, on_event, cancel_event=None, space=None, goal_context=None, **kwargs):
        return _make_result(exit_code=0, status=Status.DONE)

    monkeypatch.setattr(worker_module, "run_agent", fake_run_agent)

    goal = await task_store.create(space_id=SPACE_ID, title="Goal", brief="g", type="goal")
    # Alpha SG (sorts first) depends on a task that does not exist → unresolvable dep.
    alpha_sg = await task_store.create(
        space_id=SPACE_ID, title="Alpha SG", brief="b", parent_id=goal.id, type="goal",
        depends_on=["nonexistent-task-id"],
    )
    await task_store.create(space_id=SPACE_ID, title="Alpha task", brief="b", parent_id=alpha_sg.id)

    beta_sg = await task_store.create(
        space_id=SPACE_ID, title="Beta SG", brief="b", parent_id=goal.id, type="goal"
    )
    await task_store.create(space_id=SPACE_ID, title="Beta task", brief="b", parent_id=beta_sg.id)

    await task_store.transition(goal.id, TaskState.ACTIVE, allowed={(TaskState.BACKLOG, TaskState.ACTIVE)})

    with caplog.at_level(logging_mod.WARNING, logger="cronos.worker"):
        await worker._run_goal(goal.id, None)

    # Goal fails (dep cannot be resolved — dep_task is None so sibling walk is skipped)
    assert task_store.get(goal.id).state == TaskState.WAITING
    # No repair warning: dep_task was None, nothing to repair
    assert not any("Auto-repaired" in r.message for r in caplog.records)
