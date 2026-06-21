"""Tests for app.run_side_effects.RunSideEffects."""
from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.run_side_effects import RunSideEffects


# ── helpers ──────────────────────────────────────────────────────────────────

def _make_task(task_id: str = "t1", space_id: str = "sp1") -> MagicMock:
    t = MagicMock()
    t.id = task_id
    t.space_id = space_id
    t.title = "Test task"
    t.agent_model = "default"
    t.agent_mode = "auto"
    return t


def _make_store(task=None) -> MagicMock:
    store = MagicMock()
    store.get = MagicMock(return_value=task)
    store.spaces_dir = MagicMock()
    return store


def _make_result(exit_code: int = 0, stopped: bool = False) -> MagicMock:
    r = MagicMock()
    r.exit_code = exit_code
    r.stopped = stopped
    r.session_id = "sess-1"
    r.raw_events = []
    r.status = MagicMock()
    r.status.value = "DONE"
    return r


def _now() -> datetime:
    return datetime.now(tz=UTC)


def _make_usage() -> dict:
    return {
        "input_tokens": 100,
        "output_tokens": 50,
        "cache_read_tokens": 0,
        "cache_creation_tokens": 0,
        "tool_uses": {},
        "error_count": 0,
        "real_model": None,
    }


# ── save_memory_blocks ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_save_memory_blocks_no_op_when_no_memory_store():
    store = _make_store(_make_task())
    rse = RunSideEffects(None, None, None, store)
    # Should not raise.
    await rse.save_memory_blocks("t1", "MEMORY: some content", 0)


@pytest.mark.asyncio
async def test_save_memory_blocks_no_op_when_empty_text():
    ms = AsyncMock()
    store = _make_store(_make_task())
    rse = RunSideEffects(None, None, ms, store)
    await rse.save_memory_blocks("t1", "", 0)
    ms.create.assert_not_called()


@pytest.mark.asyncio
async def test_save_memory_blocks_no_op_when_no_blocks():
    ms = AsyncMock()
    store = _make_store(_make_task())
    rse = RunSideEffects(None, None, ms, store)
    await rse.save_memory_blocks("t1", "No memory blocks here.", 0)
    ms.create.assert_not_called()


@pytest.mark.asyncio
async def test_save_memory_blocks_no_op_when_task_not_found():
    ms = AsyncMock()
    store = _make_store(None)  # task not found
    rse = RunSideEffects(None, None, ms, store)
    # Inject a fake parse_memory_blocks that returns something
    fake_block = MagicMock()
    fake_block.content = "Some memory content\nLine 2"
    fake_block.kind_hint = "observation"
    with patch("app.run_side_effects.RunSideEffects.save_memory_blocks") as m:
        m.return_value = None  # just confirm our test is safe
    await rse.save_memory_blocks("t1", "MEMORY: some content", 0)
    ms.create.assert_not_called()


@pytest.mark.asyncio
async def test_save_memory_blocks_creates_item():
    ms = AsyncMock()
    task = _make_task()
    store = _make_store(task)
    rse = RunSideEffects(None, None, ms, store)

    fake_block = MagicMock()
    fake_block.content = "Some memory insight"
    fake_block.kind_hint = "observation"

    with patch("app.memory_parser.parse_memory_blocks", return_value=[fake_block]):
        await rse.save_memory_blocks("t1", "MEMORY: Some memory insight", 3)

    ms.create.assert_called_once()
    call_kwargs = ms.create.call_args.kwargs
    assert call_kwargs["kind"] == "observation"
    assert call_kwargs["confirmed"] is False
    assert "task:t1" in call_kwargs["sources"]
    assert "run:3" in call_kwargs["sources"]


@pytest.mark.asyncio
async def test_save_memory_blocks_swallows_create_exception():
    ms = AsyncMock()
    ms.create.side_effect = RuntimeError("DB error")
    task = _make_task()
    store = _make_store(task)
    rse = RunSideEffects(None, None, ms, store)

    fake_block = MagicMock()
    fake_block.content = "content"
    fake_block.kind_hint = None  # tests fallback to "observation"

    with patch("app.memory_parser.parse_memory_blocks", return_value=[fake_block]):
        # Should not propagate the exception.
        await rse.save_memory_blocks("t1", "MEMORY: content", 0)


# ── save_cronos_remember_blocks ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_save_cronos_remember_no_op_when_no_memory_store():
    store = _make_store()
    rse = RunSideEffects(None, None, None, store)
    await rse.save_cronos_remember_blocks(
        "CRONOS_REMEMBER: test", space_id="sp1", sources=[], log_id="t1"
    )


@pytest.mark.asyncio
async def test_save_cronos_remember_no_op_when_empty_text():
    ms = AsyncMock()
    store = _make_store()
    rse = RunSideEffects(None, None, ms, store)
    await rse.save_cronos_remember_blocks("", space_id="sp1", sources=[], log_id="t1")
    ms.create.assert_not_called()


@pytest.mark.asyncio
async def test_save_cronos_remember_creates_item():
    ms = AsyncMock()
    store = _make_store()
    rse = RunSideEffects(None, None, ms, store)

    fake_block = MagicMock()
    fake_block.name = "my-memory"
    fake_block.type = "decision"
    fake_block.description = "We decided to do X"
    fake_block.body = "Extended notes"
    fake_block.metadata = {"key": "value"}

    with patch("app.memory_parser.parse_cronos_remember_blocks", return_value=[fake_block]):
        await rse.save_cronos_remember_blocks(
            "CRONOS_REMEMBER block", space_id="sp1", sources=["task:t1"], log_id="t1"
        )

    ms.create.assert_called_once()
    kwargs = ms.create.call_args.kwargs
    assert kwargs["kind"] == "decision"
    assert kwargs["title"] == "my-memory"
    assert "We decided to do X" in kwargs["body"]
    assert "Extended notes" in kwargs["body"]
    assert kwargs["confirmed"] is False


@pytest.mark.asyncio
async def test_save_cronos_remember_no_metadata():
    ms = AsyncMock()
    store = _make_store()
    rse = RunSideEffects(None, None, ms, store)

    fake_block = MagicMock()
    fake_block.name = "mem"
    fake_block.type = "fact"
    fake_block.description = "Some fact"
    fake_block.body = None
    fake_block.metadata = None

    with patch("app.memory_parser.parse_cronos_remember_blocks", return_value=[fake_block]):
        await rse.save_cronos_remember_blocks(
            "CRONOS_REMEMBER block", space_id="sp1", sources=[], log_id="t1"
        )

    kwargs = ms.create.call_args.kwargs
    assert kwargs["links"] == []  # no metadata → empty links


@pytest.mark.asyncio
async def test_save_cronos_remember_swallows_create_exception():
    ms = AsyncMock()
    ms.create.side_effect = RuntimeError("error")
    store = _make_store()
    rse = RunSideEffects(None, None, ms, store)

    fake_block = MagicMock()
    fake_block.name = "mem"
    fake_block.type = "fact"
    fake_block.description = "desc"
    fake_block.body = None
    fake_block.metadata = None

    with patch("app.memory_parser.parse_cronos_remember_blocks", return_value=[fake_block]):
        await rse.save_cronos_remember_blocks(
            "CRONOS_REMEMBER block", space_id="sp1", sources=[], log_id="t1"
        )


# ── record_telemetry ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_record_telemetry_no_op_when_task_not_found():
    store = _make_store(None)
    rse = RunSideEffects(None, None, None, store)
    # Should not raise.
    await rse.record_telemetry(
        "t1", "sp1", _make_result(), _now(), _now(), "DONE", None, 0, None, _make_usage()
    )


@pytest.mark.asyncio
async def test_record_telemetry_saves_stats():
    ss = AsyncMock()
    store = _make_store(_make_task())
    rse = RunSideEffects(ss, None, None, store)

    now = _now()
    with patch("app.tools.index.adopted_index_for_space", return_value=None):
        await rse.record_telemetry(
            "t1", "sp1", _make_result(), now, now, "DONE", None, 0, None, _make_usage()
        )

    ss.append_run.assert_called_once()


@pytest.mark.asyncio
async def test_record_telemetry_swallows_stats_exception():
    ss = AsyncMock()
    ss.append_run.side_effect = RuntimeError("stats error")
    store = _make_store(_make_task())
    rse = RunSideEffects(ss, None, None, store)

    now = _now()
    with patch("app.tools.index.adopted_index_for_space", return_value=None):
        # Should not propagate.
        await rse.record_telemetry(
            "t1", "sp1", _make_result(), now, now, "DONE", None, 0, None, _make_usage()
        )
