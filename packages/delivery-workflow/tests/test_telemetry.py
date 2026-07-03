"""Tests for lib/telemetry (TelemetrySink + BudgetExceededSignal) — R12/R13."""
from __future__ import annotations

from pathlib import Path

import pytest

from delivery_workflow.interface import TelemetryOps
from delivery_workflow.lib.state.store import StateStore
from delivery_workflow.lib.telemetry import BudgetExceededSignal, TelemetrySink
from delivery_workflow.state_types import BudgetState, NodeState, WorkflowState


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_state(run_dir: Path, *, nodes: dict[str, NodeState] | None = None) -> None:
    state = WorkflowState(
        spec="delivery/v1",
        run_id="run-tel-001",
        status="running",
        budget=BudgetState(usd_ceiling=10.0, usd_spent=0.0),
        nodes=nodes or {},
    )
    StateStore(run_dir).write(state)


# ---------------------------------------------------------------------------
# R12 — emit accumulates usd_spent
# ---------------------------------------------------------------------------


def test_emit_single_node_accumulates_usd() -> None:
    sink = TelemetrySink()
    sink.emit("scout", {"tokens": 1000.0, "usd": 0.50, "seconds": 30.0})
    assert sink.usd_spent == pytest.approx(0.50)


def test_emit_multiple_nodes_cumulates() -> None:
    sink = TelemetrySink()
    sink.emit("scout", {"tokens": 1000.0, "usd": 0.50, "seconds": 30.0})
    sink.emit("analyst", {"tokens": 2000.0, "usd": 1.20, "seconds": 60.0})
    sink.emit("designer", {"tokens": 3000.0, "usd": 2.10, "seconds": 90.0})
    assert sink.usd_spent == pytest.approx(3.80)


def test_emit_zero_usd_does_not_increment() -> None:
    sink = TelemetrySink()
    sink.emit("scout", {"tokens": 500.0, "usd": 0.0, "seconds": 10.0})
    assert sink.usd_spent == pytest.approx(0.0)


def test_emit_missing_usd_key_treated_as_zero() -> None:
    sink = TelemetrySink()
    sink.emit("scout", {"tokens": 500.0, "seconds": 10.0})
    assert sink.usd_spent == pytest.approx(0.0)


def test_usd_spent_starts_at_zero() -> None:
    sink = TelemetrySink()
    assert sink.usd_spent == 0.0


# ---------------------------------------------------------------------------
# R12 — node_data() retrieval
# ---------------------------------------------------------------------------


def test_node_data_returns_last_emit() -> None:
    sink = TelemetrySink()
    payload = {"tokens": 1234.0, "usd": 0.87, "seconds": 45.0}
    sink.emit("reviewer", payload)
    result = sink.node_data("reviewer")
    assert result == payload


def test_node_data_unknown_node_returns_none() -> None:
    sink = TelemetrySink()
    assert sink.node_data("nonexistent") is None


def test_node_data_is_a_copy() -> None:
    """Mutating the returned dict does not affect internal state."""
    sink = TelemetrySink()
    sink.emit("scout", {"tokens": 100.0, "usd": 0.10, "seconds": 5.0})
    nd = sink.node_data("scout")
    assert nd is not None
    nd["usd"] = 999.0
    assert sink.node_data("scout") == {"tokens": 100.0, "usd": 0.10, "seconds": 5.0}


def test_emit_overwrites_node_data_on_retry() -> None:
    sink = TelemetrySink()
    sink.emit("reviewer", {"tokens": 500.0, "usd": 0.30, "seconds": 20.0})
    sink.emit("reviewer", {"tokens": 700.0, "usd": 0.40, "seconds": 25.0})
    nd = sink.node_data("reviewer")
    assert nd is not None
    assert nd["tokens"] == 700.0


# ---------------------------------------------------------------------------
# R13 — BudgetExceededSignal
# ---------------------------------------------------------------------------


def test_budget_exceeded_signal_raised_when_ceiling_breached() -> None:
    sink = TelemetrySink(usd_ceiling=1.00)
    sink.emit("scout", {"tokens": 100.0, "usd": 0.50, "seconds": 10.0})
    with pytest.raises(BudgetExceededSignal):
        sink.emit("analyst", {"tokens": 200.0, "usd": 0.60, "seconds": 20.0})


def test_budget_exceeded_signal_carries_amounts() -> None:
    sink = TelemetrySink(usd_ceiling=1.00)
    sink.emit("scout", {"tokens": 100.0, "usd": 0.80, "seconds": 10.0})
    with pytest.raises(BudgetExceededSignal) as exc_info:
        sink.emit("analyst", {"tokens": 200.0, "usd": 0.30, "seconds": 20.0})
    err = exc_info.value
    assert err.usd_spent == pytest.approx(1.10)
    assert err.usd_ceiling == pytest.approx(1.00)


def test_budget_signal_raised_after_accumulation() -> None:
    """usd_spent is updated before the signal fires."""
    sink = TelemetrySink(usd_ceiling=0.50)
    with pytest.raises(BudgetExceededSignal):
        sink.emit("scout", {"tokens": 1000.0, "usd": 0.75, "seconds": 30.0})
    assert sink.usd_spent == pytest.approx(0.75)


def test_no_signal_when_ceiling_zero(tmp_path: Path) -> None:
    """usd_ceiling=0.0 (default) means no enforcement."""
    sink = TelemetrySink(usd_ceiling=0.0)
    for _ in range(10):
        sink.emit("node", {"usd": 100.0})
    assert sink.usd_spent == pytest.approx(1000.0)


def test_no_signal_when_exactly_at_ceiling() -> None:
    """Exactly at ceiling (not over) should not raise."""
    sink = TelemetrySink(usd_ceiling=1.00)
    sink.emit("scout", {"tokens": 100.0, "usd": 1.00, "seconds": 30.0})
    assert sink.usd_spent == pytest.approx(1.00)


def test_signal_message_is_human_readable() -> None:
    with pytest.raises(BudgetExceededSignal) as exc_info:
        sink = TelemetrySink(usd_ceiling=0.50)
        sink.emit("x", {"usd": 0.75})
    msg = str(exc_info.value)
    assert "Budget exceeded" in msg
    assert "0.75" in msg or "0.7500" in msg


# ---------------------------------------------------------------------------
# Protocol conformance — TelemetrySink satisfies TelemetryOps (R12 AC)
# ---------------------------------------------------------------------------


def test_telemetry_sink_satisfies_telemetry_ops_protocol() -> None:
    sink = TelemetrySink()
    assert isinstance(sink, TelemetryOps)


# ---------------------------------------------------------------------------
# StateStore integration — persist telemetry to state.json
# ---------------------------------------------------------------------------


def test_emit_persists_node_telemetry_to_state(tmp_path: Path) -> None:
    _make_state(tmp_path, nodes={"scout": NodeState(status="done")})
    store = StateStore(tmp_path)
    sink = TelemetrySink(usd_ceiling=10.0, state_store=store)
    sink.emit("scout", {"tokens": 1500.0, "usd": 0.75, "seconds": 45.0})
    state = store.read()
    assert state.nodes["scout"].telemetry is not None
    assert state.nodes["scout"].telemetry["tokens"] == 1500.0


def test_emit_persists_usd_spent_to_budget(tmp_path: Path) -> None:
    _make_state(tmp_path, nodes={"scout": NodeState(status="done")})
    store = StateStore(tmp_path)
    sink = TelemetrySink(usd_ceiling=10.0, state_store=store)
    sink.emit("scout", {"tokens": 1000.0, "usd": 0.50, "seconds": 20.0})
    sink.emit("analyst", {"tokens": 2000.0, "usd": 1.20, "seconds": 60.0})
    state = store.read()
    assert state.budget.usd_spent == pytest.approx(1.70)


def test_emit_unknown_node_still_updates_budget(tmp_path: Path) -> None:
    """Nodes not in state.json should still update budget.usd_spent."""
    _make_state(tmp_path, nodes={})
    store = StateStore(tmp_path)
    sink = TelemetrySink(usd_ceiling=10.0, state_store=store)
    sink.emit("mystery-node", {"tokens": 500.0, "usd": 0.25, "seconds": 10.0})
    state = store.read()
    assert state.budget.usd_spent == pytest.approx(0.25)


def test_emit_without_state_store_does_not_raise(tmp_path: Path) -> None:
    """No store = no persistence, but no errors either."""
    sink = TelemetrySink(usd_ceiling=5.0)
    sink.emit("scout", {"tokens": 100.0, "usd": 0.10, "seconds": 5.0})
    assert sink.usd_spent == pytest.approx(0.10)
