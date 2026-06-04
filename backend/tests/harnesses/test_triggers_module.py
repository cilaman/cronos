"""
Tests for backend/app/harnesses/triggers.py

Covers:
  - EventBusEvent creation and field validation
  - EventDebouncer.should_fire() dedup logic:
      - same event_id within debounce window fires only once
      - different event_ids fire independently
      - after the debounce window expires, the same event_id fires again
  - fan_out_to_harnesses() with mocked harness_store, task_store, worker_pool:
      - no harnesses → empty run_ids
      - harness with no trigger node → not matched
      - harness with trigger node of wrong kind → not matched
      - harness with matching trigger node → enqueues a run
      - multiple harnesses, only matching one gets a run
      - debounce suppresses duplicate fan-out calls
      - harness_store.list() exception is caught, empty list returned
      - enqueue_harness_run() exception is caught, other harnesses still processed
"""

from __future__ import annotations

import asyncio
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.harnesses.triggers import EventBusEvent, EventDebouncer, fan_out_to_harnesses
from app.harnesses.model import Harness, HarnessNode, NodeType, Position
from app.harnesses.run_index import RunSummary


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _utc_now_str() -> str:
    from datetime import datetime, timezone
    return datetime.now(tz=timezone.utc).isoformat()


def _make_trigger_node(kind: str, debounce_seconds: float = 0.5) -> HarnessNode:
    """Create a trigger HarnessNode with the given kind."""
    return HarnessNode(
        id="trigger-1",
        type=NodeType.trigger,
        position=Position(x=0.0, y=0.0),
        ports={},
        data={"kind": kind, "debounce_seconds": debounce_seconds},
        label="Trigger",
    )


def _make_agent_node(node_id: str = "agent-1") -> HarnessNode:
    return HarnessNode(
        id=node_id,
        type=NodeType.agent,
        position=Position(x=100.0, y=0.0),
        ports={},
        data={},
        label="Agent",
    )


def _make_harness(name: str, nodes: list[HarnessNode] | None = None) -> Harness:
    return Harness(
        name=name,
        nodes=nodes or [],
        edges=[],
    )


def _make_run_summary(harness_name: str, run_id: str = "run-001") -> RunSummary:
    return RunSummary(
        run_id=run_id,
        harness_id=harness_name,
        status="running",
        triggered_at=_utc_now_str(),
    )


# ---------------------------------------------------------------------------
# EventBusEvent tests
# ---------------------------------------------------------------------------


class TestEventBusEvent:
    def test_task_state_change_event(self):
        event = EventBusEvent(
            event_id="task-state-change:my-space:task-123",
            kind="task-state-change",
            space_id="my-space",
            payload={"task_id": "task-123", "old_state": "active", "new_state": "done"},
            timestamp="2026-01-01T00:00:00Z",
        )
        assert event.event_id == "task-state-change:my-space:task-123"
        assert event.kind == "task-state-change"
        assert event.space_id == "my-space"
        assert event.payload["task_id"] == "task-123"
        assert event.timestamp == "2026-01-01T00:00:00Z"

    def test_webhook_event(self):
        event = EventBusEvent(
            event_id="webhook:my-space:/hooks/ci:abc123",
            kind="webhook",
            space_id="my-space",
            payload={"body": {"action": "push"}},
            timestamp="2026-01-01T12:00:00Z",
        )
        assert event.kind == "webhook"
        assert "body" in event.payload

    def test_file_change_event(self):
        event = EventBusEvent(
            event_id="file-change:my-space:.cronos/tasks/*.md:/path/to/file.md",
            kind="file-change",
            space_id="my-space",
            payload={"path": "/path/to/file.md", "watch_pattern": ".cronos/tasks/*.md"},
            timestamp="2026-01-01T08:00:00Z",
        )
        assert event.kind == "file-change"
        assert event.payload["path"] == "/path/to/file.md"

    def test_default_empty_payload(self):
        event = EventBusEvent(
            event_id="webhook:s:k",
            kind="webhook",
            space_id="s",
            timestamp="2026-01-01T00:00:00Z",
        )
        assert event.payload == {}

    def test_invalid_kind_raises(self):
        with pytest.raises(Exception):
            EventBusEvent(
                event_id="bad",
                kind="task_state_change",  # underscore variant — must reject
                space_id="s",
                timestamp="2026-01-01T00:00:00Z",
            )

    def test_invalid_kind_camel_raises(self):
        with pytest.raises(Exception):
            EventBusEvent(
                event_id="bad",
                kind="TaskStateChange",  # camelCase — must reject
                space_id="s",
                timestamp="2026-01-01T00:00:00Z",
            )

    def test_missing_required_field_raises(self):
        with pytest.raises(Exception):
            EventBusEvent(
                kind="webhook",
                space_id="s",
                timestamp="2026-01-01T00:00:00Z",
                # event_id missing
            )

    def test_immutable_fields_present(self):
        """All three literal kind values are accepted."""
        for kind in ("task-state-change", "webhook", "file-change"):
            event = EventBusEvent(
                event_id=f"{kind}:s:k",
                kind=kind,
                space_id="s",
                timestamp="2026-01-01T00:00:00Z",
            )
            assert event.kind == kind


# ---------------------------------------------------------------------------
# EventDebouncer tests
# ---------------------------------------------------------------------------


class TestEventDebouncer:
    def test_first_call_always_fires(self):
        d = EventDebouncer()
        assert d.should_fire("evt-1", 1.0) is True

    def test_second_call_within_window_suppressed(self):
        d = EventDebouncer()
        assert d.should_fire("evt-1", 1.0) is True
        assert d.should_fire("evt-1", 1.0) is False

    def test_different_event_ids_fire_independently(self):
        d = EventDebouncer()
        assert d.should_fire("evt-a", 1.0) is True
        assert d.should_fire("evt-b", 1.0) is True  # separate id
        assert d.should_fire("evt-a", 1.0) is False  # suppressed
        assert d.should_fire("evt-b", 1.0) is False  # suppressed

    def test_fires_again_after_window_expires(self):
        d = EventDebouncer()
        # Use a very small debounce window (0.01s) so we can test expiry without
        # sleeping for a long time.
        assert d.should_fire("evt-1", 0.01) is True
        # Manually move the clock by patching the last_fired entry.
        d._last_fired["evt-1"] = time.monotonic() - 0.02  # pretend 20ms have elapsed
        assert d.should_fire("evt-1", 0.01) is True  # window has passed

    def test_suppressed_before_window_expires(self):
        d = EventDebouncer()
        assert d.should_fire("evt-1", 10.0) is True
        # Window is 10s; immediately check again.
        assert d.should_fire("evt-1", 10.0) is False

    def test_reset_clears_entry(self):
        d = EventDebouncer()
        d.should_fire("evt-1", 1.0)
        d.reset("evt-1")
        # After reset, should fire again immediately.
        assert d.should_fire("evt-1", 1.0) is True

    def test_reset_nonexistent_key_is_noop(self):
        d = EventDebouncer()
        d.reset("nonexistent")  # Must not raise

    def test_lazy_sweep_removes_expired_entries(self):
        d = EventDebouncer()
        d.should_fire("old-evt", 0.01)
        # Manually expire by backdating.
        d._last_fired["old-evt"] = time.monotonic() - 0.1  # 100ms ago, well past 2×0.01
        # Trigger a sweep by calling should_fire for a different event.
        d.should_fire("new-evt", 0.01)
        # Sweep should have removed "old-evt" (2× window = 0.02s < 0.1s elapsed).
        assert "old-evt" not in d._last_fired

    def test_many_different_events_all_fire_once(self):
        d = EventDebouncer()
        for i in range(20):
            assert d.should_fire(f"evt-{i}", 5.0) is True
        for i in range(20):
            assert d.should_fire(f"evt-{i}", 5.0) is False

    def test_zero_debounce_always_fires(self):
        """With debounce_seconds=0, every call should fire (0-length window)."""
        d = EventDebouncer()
        # The check is: now - last >= debounce_seconds; with 0, any elapsed time passes.
        assert d.should_fire("evt-1", 0.0) is True
        # next call: elapsed since last is > 0, so it fires again
        assert d.should_fire("evt-1", 0.0) is True


# ---------------------------------------------------------------------------
# fan_out_to_harnesses() tests
# ---------------------------------------------------------------------------


class TestFanOutToHarnesses:
    """
    fan_out_to_harnesses() is an async coroutine. Tests use pytest-anyio /
    pytest asyncio; conftest.py in the backend test root sets asyncio_mode=auto
    for async test functions.
    """

    def _make_mock_harness_store(self, harnesses: list[Harness]) -> MagicMock:
        store = MagicMock()
        store.list = AsyncMock(return_value=harnesses)
        return store

    def _make_mock_task_store(self) -> MagicMock:
        return MagicMock()

    def _make_mock_worker_pool(self) -> MagicMock:
        return MagicMock()

    def _make_event(
        self,
        kind: str = "task-state-change",
        event_id: str | None = None,
        space_id: str = "test-space",
    ) -> EventBusEvent:
        if event_id is None:
            event_id = f"{kind}:{space_id}:key-001"
        return EventBusEvent(
            event_id=event_id,
            kind=kind,
            space_id=space_id,
            payload={},
            timestamp="2026-01-01T00:00:00Z",
        )

    async def test_no_harnesses_returns_empty(self, tmp_path):
        store = self._make_mock_harness_store([])
        event = self._make_event()
        result = await fan_out_to_harnesses(
            event,
            harness_store=store,
            task_store=self._make_mock_task_store(),
            worker_pool=self._make_mock_worker_pool(),
            space_dir=tmp_path,
        )
        assert result == []
        store.list.assert_awaited_once_with(tmp_path)

    async def test_harness_with_no_trigger_node_not_matched(self, tmp_path):
        harness = _make_harness("my-harness", nodes=[_make_agent_node()])
        store = self._make_mock_harness_store([harness])
        event = self._make_event(kind="task-state-change")

        with patch(
            "app.harnesses.triggers.enqueue_harness_run", new_callable=AsyncMock
        ) as mock_enqueue:
            result = await fan_out_to_harnesses(
                event,
                harness_store=store,
                task_store=self._make_mock_task_store(),
                worker_pool=self._make_mock_worker_pool(),
                space_dir=tmp_path,
            )
        assert result == []
        mock_enqueue.assert_not_awaited()

    async def test_harness_with_wrong_kind_trigger_not_matched(self, tmp_path):
        trigger_node = _make_trigger_node("webhook")  # event is task-state-change
        harness = _make_harness("my-harness", nodes=[trigger_node])
        store = self._make_mock_harness_store([harness])
        event = self._make_event(kind="task-state-change", event_id="task-state-change:test-space:unique-key-1")

        with patch(
            "app.harnesses.triggers.enqueue_harness_run", new_callable=AsyncMock
        ) as mock_enqueue:
            result = await fan_out_to_harnesses(
                event,
                harness_store=store,
                task_store=self._make_mock_task_store(),
                worker_pool=self._make_mock_worker_pool(),
                space_dir=tmp_path,
            )
        assert result == []
        mock_enqueue.assert_not_awaited()

    async def test_matching_trigger_node_enqueues_run(self, tmp_path):
        trigger_node = _make_trigger_node("task-state-change")
        harness = _make_harness("my-harness", nodes=[trigger_node])
        store = self._make_mock_harness_store([harness])
        event = self._make_event(kind="task-state-change", event_id="task-state-change:test-space:unique-key-2")

        summary = _make_run_summary("my-harness", "run-001")
        with patch(
            "app.harnesses.triggers.enqueue_harness_run", new_callable=AsyncMock, return_value=summary
        ) as mock_enqueue:
            result = await fan_out_to_harnesses(
                event,
                harness_store=store,
                task_store=self._make_mock_task_store(),
                worker_pool=self._make_mock_worker_pool(),
                space_dir=tmp_path,
            )
        assert result == ["run-001"]
        mock_enqueue.assert_awaited_once()

    async def test_only_matching_harness_gets_run(self, tmp_path):
        trigger_match = _make_trigger_node("webhook")
        trigger_no_match = _make_trigger_node("file-change")
        harness_a = _make_harness("harness-a", nodes=[trigger_match])
        harness_b = _make_harness("harness-b", nodes=[trigger_no_match])
        store = self._make_mock_harness_store([harness_a, harness_b])
        event = self._make_event(kind="webhook", event_id="webhook:test-space:unique-key-3")

        summary = _make_run_summary("harness-a", "run-002")
        with patch(
            "app.harnesses.triggers.enqueue_harness_run", new_callable=AsyncMock, return_value=summary
        ) as mock_enqueue:
            result = await fan_out_to_harnesses(
                event,
                harness_store=store,
                task_store=self._make_mock_task_store(),
                worker_pool=self._make_mock_worker_pool(),
                space_dir=tmp_path,
            )
        assert result == ["run-002"]
        mock_enqueue.assert_awaited_once()

    async def test_multiple_matching_harnesses_all_get_runs(self, tmp_path):
        trigger = _make_trigger_node("file-change")
        harness_a = _make_harness("harness-a", nodes=[_make_trigger_node("file-change")])
        harness_b = _make_harness("harness-b", nodes=[_make_trigger_node("file-change")])
        store = self._make_mock_harness_store([harness_a, harness_b])
        event = self._make_event(kind="file-change", event_id="file-change:test-space:unique-key-4")

        summary_a = _make_run_summary("harness-a", "run-003")
        summary_b = _make_run_summary("harness-b", "run-004")
        side_effects = [summary_a, summary_b]

        with patch(
            "app.harnesses.triggers.enqueue_harness_run",
            new_callable=AsyncMock,
            side_effect=side_effects,
        ) as mock_enqueue:
            result = await fan_out_to_harnesses(
                event,
                harness_store=store,
                task_store=self._make_mock_task_store(),
                worker_pool=self._make_mock_worker_pool(),
                space_dir=tmp_path,
            )
        assert set(result) == {"run-003", "run-004"}
        assert mock_enqueue.await_count == 2

    async def test_duplicate_event_id_debounced_on_second_call(self, tmp_path):
        """Same event fired twice in quick succession: second call is suppressed."""
        from app.harnesses import triggers as triggers_mod

        trigger_node = _make_trigger_node("webhook", debounce_seconds=10.0)
        harness = _make_harness("my-harness", nodes=[trigger_node])
        store = self._make_mock_harness_store([harness])
        event = self._make_event(kind="webhook", event_id="webhook:test-space:dedup-key-99")

        # Reset the module-level debouncer entry for this test key.
        triggers_mod._debouncer.reset(f"my-harness:{event.event_id}")

        summary = _make_run_summary("my-harness", "run-dedup")
        with patch(
            "app.harnesses.triggers.enqueue_harness_run",
            new_callable=AsyncMock,
            return_value=summary,
        ) as mock_enqueue:
            # First call — should enqueue.
            result1 = await fan_out_to_harnesses(
                event,
                harness_store=store,
                task_store=self._make_mock_task_store(),
                worker_pool=self._make_mock_worker_pool(),
                space_dir=tmp_path,
            )
            # Second call immediately — should be suppressed.
            result2 = await fan_out_to_harnesses(
                event,
                harness_store=store,
                task_store=self._make_mock_task_store(),
                worker_pool=self._make_mock_worker_pool(),
                space_dir=tmp_path,
            )

        assert result1 == ["run-dedup"]
        assert result2 == []  # deduplicated
        assert mock_enqueue.await_count == 1

    async def test_harness_store_list_exception_returns_empty(self, tmp_path):
        store = MagicMock()
        store.list = AsyncMock(side_effect=RuntimeError("store unavailable"))
        event = self._make_event()

        result = await fan_out_to_harnesses(
            event,
            harness_store=store,
            task_store=self._make_mock_task_store(),
            worker_pool=self._make_mock_worker_pool(),
            space_dir=tmp_path,
        )
        assert result == []

    async def test_enqueue_exception_caught_continues_other_harnesses(self, tmp_path):
        """If enqueue fails for one harness, processing continues for the next."""
        from app.harnesses import triggers as triggers_mod

        # Two harnesses both match; first enqueue raises, second succeeds.
        harness_a = _make_harness("harness-x", nodes=[_make_trigger_node("webhook")])
        harness_b = _make_harness("harness-y", nodes=[_make_trigger_node("webhook")])
        store = self._make_mock_harness_store([harness_a, harness_b])
        event = self._make_event(kind="webhook", event_id="webhook:test-space:exception-key-77")

        # Reset debouncer state for these harness+event combos.
        triggers_mod._debouncer.reset(f"harness-x:{event.event_id}")
        triggers_mod._debouncer.reset(f"harness-y:{event.event_id}")

        summary_b = _make_run_summary("harness-y", "run-ok")
        with patch(
            "app.harnesses.triggers.enqueue_harness_run",
            new_callable=AsyncMock,
            side_effect=[RuntimeError("boom"), summary_b],
        ) as mock_enqueue:
            result = await fan_out_to_harnesses(
                event,
                harness_store=store,
                task_store=self._make_mock_task_store(),
                worker_pool=self._make_mock_worker_pool(),
                space_dir=tmp_path,
            )

        # Only harness-y run should be in the result (harness-x failed).
        assert result == ["run-ok"]
        assert mock_enqueue.await_count == 2

    async def test_file_change_kind_matched(self, tmp_path):
        trigger_node = _make_trigger_node("file-change")
        harness = _make_harness("file-harness", nodes=[trigger_node])
        store = self._make_mock_harness_store([harness])
        event = self._make_event(kind="file-change", event_id="file-change:test-space:unique-fc-55")

        summary = _make_run_summary("file-harness", "run-fc")
        with patch(
            "app.harnesses.triggers.enqueue_harness_run",
            new_callable=AsyncMock,
            return_value=summary,
        ):
            result = await fan_out_to_harnesses(
                event,
                harness_store=store,
                task_store=self._make_mock_task_store(),
                worker_pool=self._make_mock_worker_pool(),
                space_dir=tmp_path,
            )
        assert result == ["run-fc"]

    async def test_enqueue_called_with_correct_args(self, tmp_path):
        """Verify enqueue_harness_run receives the expected keyword arguments."""
        from app.harnesses import triggers as triggers_mod

        trigger_node = _make_trigger_node("task-state-change")
        harness = _make_harness("check-args-harness", nodes=[trigger_node])
        store = self._make_mock_harness_store([harness])
        event = EventBusEvent(
            event_id="task-state-change:test-space:arg-check-key",
            kind="task-state-change",
            space_id="test-space",
            payload={"task_id": "t-1"},
            timestamp="2026-06-01T00:00:00Z",
        )

        # Reset debouncer state for this test.
        triggers_mod._debouncer.reset(f"check-args-harness:{event.event_id}")

        task_store = self._make_mock_task_store()
        worker_pool = self._make_mock_worker_pool()
        summary = _make_run_summary("check-args-harness", "run-args")

        with patch(
            "app.harnesses.triggers.enqueue_harness_run",
            new_callable=AsyncMock,
            return_value=summary,
        ) as mock_enqueue:
            await fan_out_to_harnesses(
                event,
                harness_store=store,
                task_store=task_store,
                worker_pool=worker_pool,
                space_dir=tmp_path,
            )

        mock_enqueue.assert_awaited_once()
        call_kwargs = mock_enqueue.call_args
        assert call_kwargs.kwargs["space_id"] == "test-space"
        assert call_kwargs.kwargs["harness_name"] == "check-args-harness"
        assert call_kwargs.kwargs["triggered_at"] == "2026-06-01T00:00:00Z"
        assert call_kwargs.kwargs["task_store"] is task_store
        assert call_kwargs.kwargs["worker_pool"] is worker_pool
        assert call_kwargs.kwargs["space_dir"] == tmp_path
