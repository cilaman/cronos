"""Tests for app.event_bus.EventBus — pub/sub event bus extracted from Worker."""
from __future__ import annotations

import asyncio
import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.event_bus import DONE_SENTINEL, RUN_BUFFER_CAP, EventBus


# ── helpers ──────────────────────────────────────────────────────────────────

def _make_bus() -> EventBus:
    return EventBus()


# ── constants ─────────────────────────────────────────────────────────────────

def test_done_sentinel_is_dict():
    assert isinstance(DONE_SENTINEL, dict)
    assert DONE_SENTINEL.get("type") == "stream_end"


def test_run_buffer_cap_is_positive():
    assert RUN_BUFFER_CAP > 0


# ── publish ───────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_publish_adds_to_buffer():
    bus = _make_bus()
    event = {"type": "run_start", "task_id": "t1"}
    bus.publish("t1", event)
    buf = bus._run_buffer.get("t1", [])
    assert event in buf


@pytest.mark.asyncio
async def test_publish_trims_buffer_to_cap():
    bus = _make_bus()
    for i in range(RUN_BUFFER_CAP + 10):
        bus.publish("t1", {"type": "event", "i": i})
    assert len(bus._run_buffer["t1"]) == RUN_BUFFER_CAP


@pytest.mark.asyncio
async def test_publish_delivers_to_subscriber():
    bus = _make_bus()
    replay, q = bus.subscribe("t1")
    event = {"type": "assistant", "data": "hello"}
    bus.publish("t1", event)
    received = q.get_nowait()
    assert received == event


@pytest.mark.asyncio
async def test_publish_handles_slow_subscriber_queue_full():
    """When a subscriber queue is full, publish drops oldest then pushes."""
    bus = _make_bus()
    # Create a queue with maxsize=1 to force QueueFull immediately.
    q: asyncio.Queue[dict] = asyncio.Queue(maxsize=1)
    bus._subscribers["t2"] = [q]
    # First event fills the queue.
    bus.publish("t2", {"type": "e1"})
    # Second event must trigger the QueueFull path (drop oldest then put).
    bus.publish("t2", {"type": "e2"})
    # Queue should contain the newer event.
    result = q.get_nowait()
    assert result["type"] == "e2"


@pytest.mark.asyncio
async def test_publish_forwards_lifecycle_to_space_subscribers():
    bus = _make_bus()
    sq = bus.subscribe_space()
    bus.publish("t1", {"type": "run_start", "task_id": "t1"})
    event = sq.get_nowait()
    assert event["type"] == "run_start"


@pytest.mark.asyncio
async def test_publish_does_not_forward_non_lifecycle_to_space_subscribers():
    bus = _make_bus()
    sq = bus.subscribe_space()
    bus.publish("t1", {"type": "assistant", "data": "x"})
    assert sq.empty()


@pytest.mark.asyncio
async def test_publish_space_subscriber_queue_full_drops_oldest():
    """Space subscriber QueueFull path: drop oldest, retry put."""
    bus = _make_bus()
    sq: asyncio.Queue[dict] = asyncio.Queue(maxsize=1)
    bus._space_subscribers = [sq]
    bus.publish("t1", {"type": "run_start", "task_id": "t1"})
    bus.publish("t2", {"type": "run_end", "task_id": "t2"})
    result = sq.get_nowait()
    assert result["type"] == "run_end"


# ── clear_buffer ──────────────────────────────────────────────────────────────

def test_clear_buffer_empties_buffer():
    bus = _make_bus()
    bus.publish("t1", {"type": "e"})
    assert bus._run_buffer["t1"]
    bus.clear_buffer("t1")
    assert bus._run_buffer["t1"] == []


# ── drain_subscribers ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_drain_subscribers_sends_sentinel():
    bus = _make_bus()
    replay, q = bus.subscribe("t1")
    sentinel = {"type": "stream_end"}
    bus.drain_subscribers("t1", sentinel)
    received = q.get_nowait()
    assert received == sentinel


@pytest.mark.asyncio
async def test_drain_subscribers_no_op_when_queue_full():
    """QueueFull during drain is silently ignored."""
    bus = _make_bus()
    q: asyncio.Queue[dict] = asyncio.Queue(maxsize=1)
    q.put_nowait({"type": "existing"})
    bus._subscribers["t3"] = [q]
    # Should not raise even though the queue is full.
    bus.drain_subscribers("t3", {"type": "stream_end"})


# ── subscribe / unsubscribe ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_subscribe_returns_empty_replay_for_new_task():
    bus = _make_bus()
    replay, q = bus.subscribe("brand-new")
    assert replay == []
    assert isinstance(q, asyncio.Queue)


@pytest.mark.asyncio
async def test_subscribe_returns_existing_replay():
    bus = _make_bus()
    bus.publish("t1", {"type": "run_start"})
    replay, q = bus.subscribe("t1")
    assert any(e["type"] == "run_start" for e in replay)


def test_unsubscribe_removes_queue():
    bus = _make_bus()
    _, q = bus.subscribe("t1")
    bus.unsubscribe("t1", q)
    assert q not in bus._subscribers.get("t1", [])


def test_unsubscribe_unknown_queue_is_noop():
    """Unsubscribing a queue that was never registered must not raise."""
    bus = _make_bus()
    q: asyncio.Queue[dict] = asyncio.Queue()
    bus.unsubscribe("nonexistent", q)  # should not raise


def test_unsubscribe_cleans_up_empty_subscriber_list():
    bus = _make_bus()
    _, q = bus.subscribe("t1")
    bus.unsubscribe("t1", q)
    assert "t1" not in bus._subscribers


# ── subscribe_space / unsubscribe_space ───────────────────────────────────────

def test_subscribe_space_returns_queue():
    bus = _make_bus()
    q = bus.subscribe_space()
    assert isinstance(q, asyncio.Queue)
    assert q in bus._space_subscribers


def test_unsubscribe_space_removes_queue():
    bus = _make_bus()
    q = bus.subscribe_space()
    bus.unsubscribe_space(q)
    assert q not in bus._space_subscribers


def test_unsubscribe_space_unknown_queue_is_noop():
    bus = _make_bus()
    q: asyncio.Queue[dict] = asyncio.Queue()
    bus.unsubscribe_space(q)  # should not raise


# ── register_run / lookup_space_id ────────────────────────────────────────────

def test_register_and_lookup_run():
    bus = _make_bus()
    bus.register_run("run-1", "space-A")
    assert bus.lookup_space_id("run-1") == "space-A"


def test_lookup_unknown_run_returns_none():
    bus = _make_bus()
    assert bus.lookup_space_id("not-registered") is None


# ── rebuild_run_id_cache ──────────────────────────────────────────────────────

def test_rebuild_run_id_cache_scans_index_files():
    bus = _make_bus()
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        space_dir = tmp_path / "my-space"
        index_dir = space_dir / ".cronos" / "harness-runs"
        index_dir.mkdir(parents=True)
        index_file = index_dir / "my-harness-index.json"
        index_file.write_text(json.dumps([
            {"run_id": "run-abc", "harness_id": "my-harness"},
        ]))

        bus.rebuild_run_id_cache(tmp_path, tmp_path)
        assert bus.lookup_space_id("run-abc") == "my-space"


def test_rebuild_run_id_cache_skips_nonexistent_dir():
    bus = _make_bus()
    bus.rebuild_run_id_cache(Path("/nonexistent/path"), Path("/nonexistent"))
    # No error, no entries.
    assert len(bus._run_id_to_space_id) == 0


def test_rebuild_run_id_cache_skips_malformed_file():
    bus = _make_bus()
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        space_dir = tmp_path / "sp1"
        index_dir = space_dir / ".cronos" / "harness-runs"
        index_dir.mkdir(parents=True)
        bad_file = index_dir / "broken-index.json"
        bad_file.write_text("{ not valid json")

        bus.rebuild_run_id_cache(tmp_path, tmp_path)
        # Should not raise; no valid entries added.
        assert bus.lookup_space_id("anything") is None


def test_rebuild_run_id_cache_skips_non_dir_space():
    """Files (not dirs) in the spaces root are skipped."""
    bus = _make_bus()
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        # Create a file (not a directory) in spaces root.
        (tmp_path / "not-a-dir.txt").write_text("data")
        bus.rebuild_run_id_cache(tmp_path, tmp_path)
        assert len(bus._run_id_to_space_id) == 0
