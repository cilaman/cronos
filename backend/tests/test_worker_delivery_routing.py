"""Tests for delivery-workflow sentinel routing in run_executor.py (I7).

Asserts:
  (a) Sentinel-present goals call delivery_driver.run_delivery_goal.
  (b) Non-sentinel goals call _topo_children_local (regression guard).

The test isolates run_goal by mocking the store, space_store, and the
delivery_driver module to avoid any real I/O or agent execution.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


from app.delivery_driver import detect_delivery_workflow_spec


# ---------------------------------------------------------------------------
# Test _detect_delivery_workflow_spec (pure function — unit test)
# ---------------------------------------------------------------------------

class TestDetectDeliveryWorkflowSpec:
    """Regression guard: the pure sentinel detector must not false-match."""

    SENTINEL = "<!-- delivery-workflow: packages/delivery-workflow/src/delivery_workflow/delivery.workflow.yaml -->"

    def test_detects_sentinel(self):
        brief = f"# My Goal\n\n{self.SENTINEL}"
        path = detect_delivery_workflow_spec(brief)
        assert path == "packages/delivery-workflow/src/delivery_workflow/delivery.workflow.yaml"

    def test_returns_none_for_ordinary_brief(self):
        brief = "# Regular goal\n\nThis is an HTML <!-- comment --> inline."
        path = detect_delivery_workflow_spec(brief)
        assert path is None

    def test_returns_none_for_empty(self):
        assert detect_delivery_workflow_spec("") is None

    def test_returns_none_for_none(self):
        assert detect_delivery_workflow_spec(None) is None  # type: ignore[arg-type]

    def test_path_extracted_correctly(self):
        brief = "<!-- delivery-workflow: some/path/workflow.yaml -->"
        assert detect_delivery_workflow_spec(brief) == "some/path/workflow.yaml"

    def test_html_comment_in_prose_does_not_match(self):
        """A comment not at the start of a line must not match."""
        brief = "This goal uses <!-- delivery-workflow: sneaky --> in prose."
        # "This goal uses ..." starts the line — ^ won't match.
        path = detect_delivery_workflow_spec(brief)
        assert path is None


# ---------------------------------------------------------------------------
# Integration: run_goal sentinel routing
# ---------------------------------------------------------------------------

def _make_run_executor(goal_brief: str, goal_state_value: str = "backlog"):
    """Build a minimal RunExecutor stub for run_goal routing tests."""
    from app.models import TaskState
    from app.run_executor import RunExecutor

    # Minimal goal task.
    goal_task = SimpleNamespace(
        id="goal-1",
        title="Test Goal",
        brief=goal_brief,
        state=TaskState.BACKLOG,
        space_id="test-space",
        waiting_question=None,
    )
    if goal_state_value == "done":
        goal_task.state = TaskState.DONE

    store = MagicMock()
    store.get = MagicMock(return_value=goal_task)
    store.drain_pending = AsyncMock(return_value=[])
    store.transition = AsyncMock()
    store.all = MagicMock(return_value=[])

    space_store = MagicMock()
    space_store.spaces_dir = Path("/fake/spaces")
    space_store.get = MagicMock(return_value=SimpleNamespace(id="test-space", dir="/fake/spaces/test-space"))

    worker = MagicMock()
    worker._current_id = None
    worker._current_cancel = None
    worker.trace_store = None
    worker._owner_id = "owner"
    worker._publish = AsyncMock()

    bus = MagicMock()
    bus.clear_buffer = MagicMock()
    bus.drain_subscribers = MagicMock()
    bus.publish = AsyncMock()

    executor = RunExecutor.__new__(RunExecutor)
    executor.store = store
    executor.space_store = space_store
    executor._worker = worker
    executor._bus = bus
    executor.harness_store = None
    executor.memory_store = None
    executor._done_sentinel = object()

    finalizer = MagicMock()
    finalizer.space_store = space_store
    finalizer.finalize_goal = AsyncMock(return_value=None)
    executor._finalizer = finalizer

    return executor


@pytest.mark.asyncio
async def test_sentinel_goal_delegates_to_delivery_driver():
    """A goal with the delivery-workflow sentinel must call run_delivery_goal."""
    sentinel_brief = (
        "# Delivery Goal\n\n"
        "<!-- delivery-workflow: packages/delivery-workflow/src/delivery_workflow/delivery.workflow.yaml -->"
    )
    executor = _make_run_executor(sentinel_brief)

    called_with = {}

    async def fake_delivery_run(**kwargs):
        called_with.update(kwargs)

    with patch("app.delivery_driver.run_delivery_goal", fake_delivery_run):
        # Also patch the import inside run_goal.
        with patch("app.run_executor.run_delivery_goal", fake_delivery_run):
            await executor.run_goal("goal-1", user_message=None)

    assert "spec_path" in called_with
    assert called_with["spec_path"] == "packages/delivery-workflow/src/delivery_workflow/delivery.workflow.yaml"
    assert called_with["goal_id"] == "goal-1"


@pytest.mark.asyncio
async def test_non_sentinel_goal_uses_topo_children():
    """A goal WITHOUT the sentinel must follow the normal _topo_children_local path."""
    ordinary_brief = "# Regular Goal\n\nDo some tasks."
    executor = _make_run_executor(ordinary_brief)

    delivery_called = []

    async def fake_delivery_run(**kwargs):
        delivery_called.append(kwargs)

    with patch("app.run_executor.run_delivery_goal", fake_delivery_run):
        # run_goal will call _topo_children_local → store.all() returns []
        # which means ordered_child_ids = [] and the while loop exits early.
        await executor.run_goal("goal-1", user_message=None)

    # delivery_driver must NOT have been called.
    assert delivery_called == [], "delivery_driver.run_delivery_goal must not be called for ordinary goals"


@pytest.mark.asyncio
async def test_sentinel_goal_does_not_call_topo_children():
    """After delegating to delivery_driver, run_goal must return immediately."""
    sentinel_brief = "<!-- delivery-workflow: path/workflow.yaml -->"
    executor = _make_run_executor(sentinel_brief)

    topo_called = []

    original_topo = None
    async def fake_delivery_run(**kwargs):
        pass

    with patch("app.run_executor.run_delivery_goal", AsyncMock()):
        with patch("app.run_executor._topo_children_local", side_effect=lambda *a, **k: topo_called.append(True) or []):
            await executor.run_goal("goal-1", user_message=None)

    assert topo_called == [], "_topo_children_local must not be called when sentinel present"
