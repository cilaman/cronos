"""Tests for I7: delivery-v1 telemetry wiring into the Cronos backend.

Covers:
- lib.telemetry importable from the backend Python environment (R14 AC)
- TelemetrySink.emit() accumulates non-zero tokens and seconds
- BudgetExceededSignal is importable and raised correctly
- _emit_delivery_telemetry helper emits without error given a minimal trace stub
- _emit_delivery_telemetry is a no-op when trace has no turns (zero tokens accepted)
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

# ---------------------------------------------------------------------------
# lib.telemetry import proof (R14 AC1)
# ---------------------------------------------------------------------------


def test_lib_telemetry_importable():
    from lib.telemetry import BudgetExceededSignal, TelemetrySink  # noqa: F401


def test_telemetry_sink_emit_nonzero_tokens():
    from lib.telemetry import TelemetrySink

    sink = TelemetrySink()
    sink.emit("task-1", {"tokens": 1500.0, "usd": 0.0, "seconds": 12.5})

    data = sink.node_data("task-1")
    assert data is not None
    assert data["tokens"] == 1500.0
    assert data["seconds"] == 12.5
    assert data["usd"] == 0.0


def test_telemetry_sink_cumulative_usd():
    from lib.telemetry import TelemetrySink

    sink = TelemetrySink()
    sink.emit("t1", {"tokens": 100.0, "usd": 0.01, "seconds": 1.0})
    sink.emit("t2", {"tokens": 200.0, "usd": 0.02, "seconds": 2.0})
    assert abs(sink.usd_spent - 0.03) < 1e-9


def test_budget_exceeded_signal_raised():
    from lib.telemetry import BudgetExceededSignal, TelemetrySink

    sink = TelemetrySink(usd_ceiling=0.005)
    with pytest.raises(BudgetExceededSignal) as exc_info:
        sink.emit("t", {"tokens": 0.0, "usd": 0.01, "seconds": 1.0})
    assert exc_info.value.usd_spent > exc_info.value.usd_ceiling


def test_telemetry_sink_node_data_unknown_returns_none():
    from lib.telemetry import TelemetrySink

    sink = TelemetrySink()
    assert sink.node_data("no-such-node") is None


# ---------------------------------------------------------------------------
# _emit_delivery_telemetry helper integration
# ---------------------------------------------------------------------------


def _make_trace_stub(
    *,
    input_tokens: int = 400,
    output_tokens: int = 200,
    cache_read_tokens: int = 100,
    cache_creation_tokens: int = 50,
    duration_seconds: float = 8.0,
) -> SimpleNamespace:
    """Minimal trace-like object for unit-testing the helper."""
    turn = SimpleNamespace(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cache_read_tokens=cache_read_tokens,
        cache_creation_tokens=cache_creation_tokens,
    )
    return SimpleNamespace(turns=[turn], duration_seconds=duration_seconds)


def test_emit_delivery_telemetry_no_error():
    from app.run_side_effects import _emit_delivery_telemetry

    trace = _make_trace_stub()
    # must not raise
    _emit_delivery_telemetry("task-xyz", trace)


def test_emit_delivery_telemetry_nonzero_tokens():
    """Verify TelemetrySink receives non-zero tokens from trace turns."""
    from lib.telemetry import TelemetrySink

    from app.run_side_effects import _emit_delivery_telemetry

    # Monkey-patch TelemetrySink to capture what was emitted.
    emitted: list[dict] = []
    original_emit = TelemetrySink.emit

    def _capture(self, node_id, data):
        emitted.append({"node_id": node_id, "data": dict(data)})
        return original_emit(self, node_id, data)

    TelemetrySink.emit = _capture
    try:
        trace = _make_trace_stub(
            input_tokens=300, output_tokens=150,
            cache_read_tokens=0, cache_creation_tokens=0,
        )
        _emit_delivery_telemetry("captured-task", trace)
    finally:
        TelemetrySink.emit = original_emit

    assert len(emitted) == 1
    assert emitted[0]["node_id"] == "captured-task"
    assert emitted[0]["data"]["tokens"] == 450.0  # 300+150+0+0
    assert emitted[0]["data"]["usd"] == 0.0
    assert emitted[0]["data"]["seconds"] == 8.0


def test_emit_delivery_telemetry_zero_turns():
    """Zero-turn trace emits zero tokens — no error."""
    from app.run_side_effects import _emit_delivery_telemetry

    trace = SimpleNamespace(turns=[], duration_seconds=0.0)
    _emit_delivery_telemetry("empty-task", trace)
