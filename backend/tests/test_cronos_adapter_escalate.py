"""I5a — CronosAdapter.escalate tests (R8).

Tests:
- escalate sets state.status="blocked"
- escalate calls finalize_run with WAITING + waiting_question
- escalate is idempotent when task already WAITING
- escalate with no tracking_task_id only marks state blocked
- escalate with unknown tracking task only marks state blocked
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

_BUNDLE = Path(__file__).parent.parent.parent / "packages" / "delivery-workflow"
if str(_BUNDLE) not in sys.path:
    sys.path.insert(0, str(_BUNDLE))

from adapters.cronos.adapter import CronosAdapter
from lib.state.store import StateStore
from state_types import BudgetState, WorkflowState


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_task(state_name: str, waiting_question: str | None = None) -> SimpleNamespace:
    from app.storage import TaskState

    return SimpleNamespace(
        id="task-001",
        state=TaskState[state_name.upper()],
        waiting_question=waiting_question,
    )


def _adapter(
    tmp_path: Path,
    store: MagicMock | None = None,
    tracking_task_id: str | None = "task-001",
) -> CronosAdapter:
    run_dir = tmp_path / "run"
    run_dir.mkdir(parents=True)
    ws = WorkflowState(
        spec="ping", run_id="r1", status="running", budget=BudgetState(usd_ceiling=10.0)
    )
    StateStore(run_dir).write(ws)
    if store is None:
        store = MagicMock()
    return CronosAdapter(
        store=store,
        trace_store=MagicMock(),
        space_id="s1",
        run_dir=run_dir,
        tracking_task_id=tracking_task_id,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestEscalate:
    def test_marks_state_blocked(self, tmp_path: Path) -> None:
        store = MagicMock()
        store.get = MagicMock(return_value=_make_task("ACTIVE"))
        store.finalize_run = AsyncMock()

        adapter = _adapter(tmp_path, store)
        adapter.escalate("some-node", "Tests failed")

        ws = StateStore(tmp_path / "run").read()
        assert ws.status == "blocked"

    def test_calls_finalize_run_with_waiting(self, tmp_path: Path) -> None:
        store = MagicMock()
        store.get = MagicMock(return_value=_make_task("ACTIVE"))
        store.finalize_run = AsyncMock()

        adapter = _adapter(tmp_path, store)
        asyncio.run(adapter._escalate_async("some-node", "Needs human review"))

        store.finalize_run.assert_awaited_once()
        call_kwargs = store.finalize_run.call_args.kwargs
        from app.storage import TaskState

        assert call_kwargs["new_state"] == TaskState.WAITING
        assert "Needs human review" in call_kwargs["waiting_question"]

    def test_idempotent_when_already_waiting(self, tmp_path: Path) -> None:
        store = MagicMock()
        store.get = MagicMock(
            return_value=_make_task("WAITING", "Already blocked")
        )
        store.finalize_run = AsyncMock()

        adapter = _adapter(tmp_path, store)
        asyncio.run(adapter._escalate_async("some-node", "New reason"))

        # finalize_run should NOT be called since task is already WAITING.
        store.finalize_run.assert_not_awaited()

    def test_no_tracking_task_id_only_marks_state(self, tmp_path: Path) -> None:
        store = MagicMock()
        store.finalize_run = AsyncMock()

        adapter = _adapter(tmp_path, store, tracking_task_id=None)
        asyncio.run(adapter._escalate_async("some-node", "No tracking task"))

        ws = StateStore(tmp_path / "run").read()
        assert ws.status == "blocked"
        store.finalize_run.assert_not_awaited()

    def test_unknown_tracking_task_only_marks_state(self, tmp_path: Path) -> None:
        store = MagicMock()
        store.get = MagicMock(return_value=None)
        store.finalize_run = AsyncMock()

        adapter = _adapter(tmp_path, store)
        asyncio.run(adapter._escalate_async("some-node", "Unknown task"))

        ws = StateStore(tmp_path / "run").read()
        assert ws.status == "blocked"
        store.finalize_run.assert_not_awaited()
