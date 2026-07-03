"""I1 — CronosAdapter foundation: StateOps, TelemetryOps, Protocol conformance.

Tests:
- CronosStateOps.read/write round-trip
- EventLog receives one ISO-8601-stamped line per node status transition
- CronosTelemetryOps.emit accumulates usd_spent
- isinstance(adapter, ExecutorInterface) passes (R9 — async dispatchAgent is ok)
- isinstance(adapter.state, StateOps) passes
- isinstance(adapter.telemetry, TelemetryOps) passes
- TelemetrySink raises BudgetExceededSignal when ceiling exceeded
- _telemetry_from_trace sums per-turn tokens correctly (R7/DD-04)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

# Make sure the delivery-workflow package is importable.

from app.delivery_adapter import (
    CronosAdapter,
    CronosStateOps,
    CronosTelemetryOps,
    _telemetry_from_trace,
)
from delivery_workflow.interface import ExecutorInterface, StateOps, TelemetryOps
from delivery_workflow.lib.state.events import EventLog
from delivery_workflow.lib.state.store import StateStore
from delivery_workflow.lib.telemetry.sink import BudgetExceededSignal, TelemetrySink
from delivery_workflow.state_types import BudgetState, WorkflowState


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def run_dir(tmp_path: Path) -> Path:
    return tmp_path / "run"


@pytest.fixture()
def state_store(run_dir: Path) -> StateStore:
    run_dir.mkdir(parents=True)
    store = StateStore(run_dir)
    initial = WorkflowState(
        spec="delivery-ping",
        run_id="test-run-1",
        status="running",
        budget=BudgetState(usd_ceiling=10.0),
    )
    store.write(initial)
    return store


@pytest.fixture()
def event_log(run_dir: Path) -> EventLog:
    run_dir.mkdir(parents=True, exist_ok=True)
    return EventLog(run_dir)


@pytest.fixture()
def state_ops(state_store: StateStore, event_log: EventLog) -> CronosStateOps:
    return CronosStateOps(state_store, event_log)


@pytest.fixture()
def adapter(run_dir: Path, state_store: StateStore) -> CronosAdapter:
    """CronosAdapter with stub store/trace_store; state.json pre-initialised."""
    store = MagicMock()
    trace_store = MagicMock()
    return CronosAdapter(
        store=store,
        trace_store=trace_store,
        space_id="test-space",
        run_dir=run_dir,
        tracking_task_id="task-001",
        token_cost_usd=0.001,
    )


# ---------------------------------------------------------------------------
# StateOps tests
# ---------------------------------------------------------------------------


class TestCronosStateOps:
    def test_read_returns_workflow_state(self, state_ops: CronosStateOps) -> None:
        ws = state_ops.read()
        assert isinstance(ws, WorkflowState)
        assert ws.spec == "delivery-ping"
        assert ws.status == "running"

    def test_write_top_level_status(self, state_ops: CronosStateOps) -> None:
        state_ops.write({"status": "blocked"})
        ws = state_ops.read()
        assert ws.status == "blocked"

    def test_write_new_node_creates_entry_and_appends_event(
        self, state_ops: CronosStateOps, event_log: EventLog
    ) -> None:
        state_ops.write({"nodes": {"scout": {"status": "running"}}})
        ws = state_ops.read()
        assert "scout" in ws.nodes
        assert ws.nodes["scout"].status == "running"

        events = event_log.read_all()
        assert len(events) == 1
        assert events[0]["node_id"] == "scout"
        assert events[0]["status"] == "running"
        assert events[0]["type"] == "node_transition"
        assert "ts" in events[0]

    def test_write_status_change_appends_event(
        self, state_ops: CronosStateOps, event_log: EventLog
    ) -> None:
        state_ops.write({"nodes": {"scout": {"status": "running"}}})
        state_ops.write({"nodes": {"scout": {"status": "done"}}})

        events = event_log.read_all()
        statuses = [e["status"] for e in events if e["node_id"] == "scout"]
        assert statuses == ["running", "done"]

    def test_write_same_status_no_duplicate_event(
        self, state_ops: CronosStateOps, event_log: EventLog
    ) -> None:
        state_ops.write({"nodes": {"scout": {"status": "done"}}})
        state_ops.write({"nodes": {"scout": {"status": "done"}}})

        events = [e for e in event_log.read_all() if e["node_id"] == "scout"]
        assert len(events) == 1

    def test_write_artifact_paths(self, state_ops: CronosStateOps) -> None:
        state_ops.write(
            {
                "nodes": {
                    "scout": {
                        "status": "done",
                        "artifact_paths": ["path/to/report.md"],
                    }
                }
            }
        )
        ws = state_ops.read()
        assert ws.nodes["scout"].artifact_paths == ["path/to/report.md"]

    def test_write_multiple_nodes(
        self, state_ops: CronosStateOps, event_log: EventLog
    ) -> None:
        state_ops.write(
            {
                "nodes": {
                    "scout": {"status": "done"},
                    "analyze": {"status": "running"},
                }
            }
        )
        ws = state_ops.read()
        assert ws.nodes["scout"].status == "done"
        assert ws.nodes["analyze"].status == "running"

        node_ids = {e["node_id"] for e in event_log.read_all()}
        assert node_ids == {"scout", "analyze"}

    def test_event_lines_are_iso8601(
        self, state_ops: CronosStateOps, event_log: EventLog
    ) -> None:
        state_ops.write({"nodes": {"n1": {"status": "done"}}})
        events = event_log.read_all()
        ts = events[0]["ts"]
        # ISO-8601: contains 'T' and ends with timezone info
        assert "T" in ts


# ---------------------------------------------------------------------------
# TelemetryOps tests
# ---------------------------------------------------------------------------


class TestCronosTelemetryOps:
    def test_emit_accumulates_usd(self, state_store: StateStore) -> None:
        sink = TelemetrySink(usd_ceiling=0.0, state_store=state_store)
        ops = CronosTelemetryOps(sink)
        ops.emit("scout", {"tokens": 1000, "usd": 0.01, "seconds": 10.0})
        ops.emit("analyze", {"tokens": 500, "usd": 0.005, "seconds": 5.0})
        assert ops.usd_spent == pytest.approx(0.015)

    def test_emit_persists_to_state_json(
        self, state_store: StateStore, run_dir: Path
    ) -> None:
        sink = TelemetrySink(usd_ceiling=0.0, state_store=state_store)
        ops = CronosTelemetryOps(sink)
        # Pre-create the node so telemetry persistence finds it.
        ws = state_store.read()
        from delivery_workflow.state_types import NodeState

        ws.nodes["scout"] = NodeState(status="done")
        state_store.write(ws)

        ops.emit("scout", {"tokens": 1000, "usd": 0.01, "seconds": 10.0})
        ws2 = state_store.read()
        assert ws2.budget.usd_spent == pytest.approx(0.01)
        assert ws2.nodes["scout"].telemetry is not None
        assert ws2.nodes["scout"].telemetry["usd"] == pytest.approx(0.01)

    def test_emit_raises_budget_exceeded(self, state_store: StateStore) -> None:
        sink = TelemetrySink(usd_ceiling=0.005, state_store=state_store)
        ops = CronosTelemetryOps(sink)
        with pytest.raises(BudgetExceededSignal):
            ops.emit("scout", {"tokens": 10000, "usd": 0.01, "seconds": 5.0})


# ---------------------------------------------------------------------------
# _telemetry_from_trace helper (DD-04)
# ---------------------------------------------------------------------------


class TestTelemetryFromTrace:
    def _make_turn(self, input_tokens: int, output_tokens: int) -> SimpleNamespace:
        return SimpleNamespace(input_tokens=input_tokens, output_tokens=output_tokens)

    def test_sums_per_turn_tokens(self) -> None:
        trace = SimpleNamespace(
            turns=[
                self._make_turn(100, 50),
                self._make_turn(200, 80),
            ],
            duration_seconds=15.0,
        )
        telem = _telemetry_from_trace(trace, token_cost_usd=0.001)
        assert telem.tokens == 430
        assert telem.usd == pytest.approx(0.43)
        assert telem.seconds == 15.0

    def test_no_turns_returns_zero(self) -> None:
        trace = SimpleNamespace(turns=[], duration_seconds=0.0)
        telem = _telemetry_from_trace(trace, token_cost_usd=0.001)
        assert telem.tokens == 0
        assert telem.usd == 0.0

    def test_zero_cost_rate(self) -> None:
        trace = SimpleNamespace(
            turns=[self._make_turn(1000, 500)],
            duration_seconds=5.0,
        )
        telem = _telemetry_from_trace(trace, token_cost_usd=0.0)
        assert telem.tokens == 1500
        assert telem.usd == 0.0


# ---------------------------------------------------------------------------
# Protocol conformance (R9)
# ---------------------------------------------------------------------------


class TestProtocolConformance:
    def test_adapter_is_executor_interface(self, adapter: CronosAdapter) -> None:
        assert isinstance(adapter, ExecutorInterface)

    def test_state_is_state_ops(self, adapter: CronosAdapter) -> None:
        assert isinstance(adapter.state, StateOps)

    def test_telemetry_is_telemetry_ops(self, adapter: CronosAdapter) -> None:
        assert isinstance(adapter.telemetry, TelemetryOps)

    def test_required_methods_present(self, adapter: CronosAdapter) -> None:
        # NodeExecutor port + HostPort (R10b).  evalCondition left the
        # surface entirely (condition evaluation is runner-internal);
        # escalate survives as the internal parking bridge behind on_event.
        for method in ("dispatchAgent", "runGate", "runExec", "on_event"):
            assert hasattr(adapter, method), f"Missing method: {method}"
        assert not hasattr(adapter, "evalCondition")

    def test_state_methods_present(self, adapter: CronosAdapter) -> None:
        assert hasattr(adapter.state, "read")
        assert hasattr(adapter.state, "write")

    def test_telemetry_emit_present(self, adapter: CronosAdapter) -> None:
        assert hasattr(adapter.telemetry, "emit")


# ---------------------------------------------------------------------------
# B1 — state.json bootstrap + write guard (resume enablement)
# ---------------------------------------------------------------------------


class TestBootstrapAndWriteGuard:
    def test_bootstrap_seeds_state_when_absent(self, tmp_path: Path) -> None:
        run_dir = tmp_path / "run"
        run_dir.mkdir(parents=True)
        store = StateStore(run_dir)
        ops = CronosStateOps(store, EventLog(run_dir))
        assert not store.exists()

        ops.bootstrap_if_absent(spec="delivery-ping", run_id="goal-1", usd_ceiling=5.0)

        assert store.exists()
        ws = store.read()
        assert ws.spec == "delivery-ping"
        assert ws.run_id == "goal-1"
        assert ws.status == "running"
        assert ws.budget.usd_ceiling == 5.0

    def test_bootstrap_is_idempotent_preserves_existing_state(
        self, tmp_path: Path
    ) -> None:
        run_dir = tmp_path / "run"
        run_dir.mkdir(parents=True)
        store = StateStore(run_dir)
        ops = CronosStateOps(store, EventLog(run_dir))
        # Simulate a prior run that completed the scout node.
        ops.bootstrap_if_absent(spec="s", run_id="goal-1", usd_ceiling=1.0)
        ops.write({"nodes": {"scout": {"status": "done"}}})

        # A resumed run must NOT clobber the existing state.
        ops.bootstrap_if_absent(spec="s", run_id="goal-1", usd_ceiling=1.0)

        ws = store.read()
        assert "scout" in ws.nodes
        assert ws.nodes["scout"].status == "done"

    def test_write_does_not_crash_when_state_missing(self, tmp_path: Path) -> None:
        """Defensive: a gate outcome write before bootstrap must not raise."""
        run_dir = tmp_path / "run"
        run_dir.mkdir(parents=True)
        ops = CronosStateOps(StateStore(run_dir), EventLog(run_dir))
        assert not (run_dir / "state.json").exists()

        # Should not raise FileNotFoundError.
        ops.write({"nodes": {"g-scout": {"status": "done"}}})

        ws = ops.read()
        assert ws.nodes["g-scout"].status == "done"
