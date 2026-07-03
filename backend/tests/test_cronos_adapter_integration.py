"""I5b — CronosAdapter all-six-ops integration test (R9).

Tests one CronosAdapter instance exercising all six ops together:
1. state.read + state.write
2. telemetry.emit
3. dispatchAgent (mocked store+trace_store)
4. runGate (mocked lib.gate.runGate)
5. evalCondition
6. escalate
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


from app.delivery_adapter import CronosAdapter
from delivery_workflow.interface import ExecutorInterface, StateOps, TelemetryOps
from delivery_workflow.lib.state.events import EventLog
from delivery_workflow.lib.state.store import StateStore
from delivery_workflow.results import AgentResult, GateResult
from delivery_workflow.state_types import BudgetState, NodeState, WorkflowState


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_DS_ENVELOPE = {
    "status": "done",
    "artifact_paths": ["scout-report.md"],
    "produces": "research",
    "fields": {"has_ui": "false"},
    "open_questions": [],
    "telemetry": {"tokens": 500, "usd": 0.005, "seconds": 10},
}

_DS_FENCE = json.dumps(_DS_ENVELOPE)


def _make_task(state_name: str) -> SimpleNamespace:
    from app.storage import TaskState

    return SimpleNamespace(
        id="child-001",
        state=TaskState[state_name.upper()],
        waiting_question=None,
    )


def _make_cronos_gate_result(decision: str) -> MagicMock:
    r = MagicMock()
    r.decision = decision
    r.errors = []
    r.evidence = {}
    r.to_dict = lambda: {"decision": decision, "errors": [], "evidence": {}}
    return r


# ---------------------------------------------------------------------------
# Integration test
# ---------------------------------------------------------------------------


class TestAllSixOps:
    def test_all_ops_on_single_adapter(self, tmp_path: Path) -> None:
        run_dir = tmp_path / "run"
        run_dir.mkdir(parents=True)

        # Initialise state.json.
        ws = WorkflowState(
            spec="delivery-ping",
            run_id="test-integration",
            status="running",
            budget=BudgetState(usd_ceiling=5.0),
        )
        StateStore(run_dir).write(ws)

        # Mocks.
        store = MagicMock()
        trace_store = MagicMock()
        store.create = AsyncMock(return_value=_make_task("DONE"))
        store.get = MagicMock(return_value=_make_task("DONE"))
        store.transition = AsyncMock()
        store.finalize_run = AsyncMock()

        trace = SimpleNamespace(
            turns=[SimpleNamespace(input_tokens=200, output_tokens=100)],
            duration_seconds=8.0,
            final_text_snippet=f"```delivery_status\n{_DS_FENCE}\n```",
            # R1: dispatchAgent reads the structured envelope, not the snippet.
            node_status=_DS_ENVELOPE,
        )
        trace_store.load_latest = AsyncMock(return_value=trace)

        adapter = CronosAdapter(
            store=store,
            trace_store=trace_store,
            space_id="s1",
            run_dir=run_dir,
            tracking_task_id="tracking-001",
            usd_ceiling=5.0,
            token_cost_usd=0.001,
            run_child=lambda ref, inp: trace,
        )

        # --- R9: Protocol conformance ---
        assert isinstance(adapter, ExecutorInterface)
        assert isinstance(adapter.state, StateOps)
        assert isinstance(adapter.telemetry, TelemetryOps)

        # --- R6: state.read/write ---
        adapter.state.write({"nodes": {"scout": {"status": "running"}}})
        ws = adapter.state.read()
        assert ws.nodes["scout"].status == "running"

        # --- R7: telemetry.emit ---
        # Pre-create node for telemetry persistence.
        adapter.state.write({"nodes": {"scout": {"status": "done"}}})
        adapter.telemetry.emit("scout", {"tokens": 300, "usd": 0.003, "seconds": 8.0})
        ws = adapter.state.read()
        assert ws.budget.usd_spent == pytest.approx(0.003)

        # --- R1/R2/R3: dispatchAgent ---
        result = adapter.dispatchAgent("pipeline-scout", {"artifact_paths": ["spec.md"]})
        assert isinstance(result, AgentResult)
        assert result.status == "done"
        assert result.telemetry.tokens > 0

        # --- R4: runGate ---
        with patch(
            "delivery_workflow.lib.gate.runGate",
            return_value=_make_cronos_gate_result("proceed"),
        ):
            gate_result = adapter.runGate({"id": "g-scout", "checks": []}, ["scout-report.md"])
        assert isinstance(gate_result, GateResult)
        assert gate_result.decision == "proceed"

        # --- R5 (re-anchored by R10b): the condition path is runner-internal;
        # the adapter carries no evalCondition method anymore.
        from delivery_workflow.lib.conditions import eval_condition

        scope = {"analyze.fields.has_ui": "false"}
        assert eval_condition("analyze.fields.has_ui == 'false'", scope) is True
        assert eval_condition("analyze.fields.has_ui == 'true'", scope) is False
        assert not hasattr(adapter, "evalCondition")

        # --- R8: escalate ---
        store.get = MagicMock(return_value=_make_task("ACTIVE"))
        asyncio.run(adapter._escalate_async("review", "Architecture review needed"))
        ws = adapter.state.read()
        assert ws.status == "blocked"

        # --- Events.jsonl has entries ---
        events = EventLog(run_dir).read_all()
        assert any(e["node_id"] == "scout" for e in events)
        assert all("ts" in e for e in events)
