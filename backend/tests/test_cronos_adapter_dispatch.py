"""CronosAdapter.dispatchAgent tests (post inline-execution refactor).

dispatchAgent is now a *synchronous* thin shim: it calls the injected
``run_child(agent_ref, inputs)`` callback (which creates + executes the child on
the Cronos main loop and returns the child's RunTrace), then parses the
delivery_status fence + telemetry into an AgentResult. Child creation, brief
tagging, and BACKLOG→ACTIVE transition now live in
``RunExecutor.run_delivery_child`` (see test_run_delivery_child.py).

Tests:
- Happy path: run_child returns a trace with a delivery_status fence → done
- Telemetry summed per-turn
- No run_child wired → failed
- run_child returns None (no trace) → failed
- >500-char delivery_status clipped → artifact fallback (DD-05)
- run_child invoked with (agent_ref, inputs)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

_BUNDLE = Path(__file__).parent.parent.parent / "packages" / "delivery-workflow"
if str(_BUNDLE) not in sys.path:
    sys.path.insert(0, str(_BUNDLE))

from adapters.cronos.adapter import CronosAdapter
from results import AgentResult
from state_types import BudgetState, WorkflowState


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_DS_SNIPPET = json.dumps(
    {
        "status": "done",
        "artifact_paths": ["reports/scout.md"],
        "produces": "research",
        "fields": {"has_ui": False},
        "open_questions": [],
        "telemetry": {"tokens": 1200, "usd": 0.012, "seconds": 30},
    }
)

_DS_FENCE = f"```delivery_status\n{_DS_SNIPPET}\n```"


def _make_trace(
    final_text: str = _DS_FENCE,
    input_tokens: int = 800,
    output_tokens: int = 400,
    duration_seconds: float = 15.0,
) -> SimpleNamespace:
    turn = SimpleNamespace(input_tokens=input_tokens, output_tokens=output_tokens)
    return SimpleNamespace(
        turns=[turn],
        duration_seconds=duration_seconds,
        final_text_snippet=final_text,
    )


def _adapter(tmp_path: Path, run_child) -> CronosAdapter:
    run_dir = tmp_path / "run"
    run_dir.mkdir(parents=True, exist_ok=True)
    ws = WorkflowState(
        spec="ping",
        run_id="r1",
        status="running",
        budget=BudgetState(usd_ceiling=25.0),
    )
    from lib.state.store import StateStore

    StateStore(run_dir).write(ws)
    return CronosAdapter(
        store=MagicMock(),
        trace_store=MagicMock(),
        space_id="s1",
        run_dir=run_dir,
        tracking_task_id="tracking-001",
        token_cost_usd=0.001,
        run_child=run_child,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestDispatchAgentHappyPath:
    def test_returns_done_result(self, tmp_path: Path) -> None:
        adapter = _adapter(tmp_path, run_child=lambda ref, inp: _make_trace())

        result = adapter.dispatchAgent(
            "pipeline-scout", {"artifact_paths": ["docs/spec.md"]}
        )

        assert isinstance(result, AgentResult)
        assert result.status == "done"
        assert result.artifact_paths == ["reports/scout.md"]
        assert result.produces == "research"
        assert result.fields == {"has_ui": False}

    def test_telemetry_sums_per_turn(self, tmp_path: Path) -> None:
        trace = _make_trace(input_tokens=1000, output_tokens=500)
        adapter = _adapter(tmp_path, run_child=lambda ref, inp: trace)

        result = adapter.dispatchAgent("pipeline-scout", {})
        assert result.telemetry.tokens == 1500
        assert result.telemetry.usd == pytest.approx(1500 * 0.001)

    def test_run_child_invoked_with_ref_and_inputs(self, tmp_path: Path) -> None:
        captured = {}

        def _rc(ref, inp):
            captured["ref"] = ref
            captured["inputs"] = inp
            return _make_trace()

        adapter = _adapter(tmp_path, run_child=_rc)
        adapter.dispatchAgent("reviewer", {"node_id": "g-review"})

        assert captured["ref"] == "reviewer"
        assert captured["inputs"] == {"node_id": "g-review"}


class TestDispatchAgentFailurePaths:
    def test_no_run_child_returns_failed(self, tmp_path: Path) -> None:
        adapter = _adapter(tmp_path, run_child=None)
        result = adapter.dispatchAgent("pipeline-scout", {})
        assert result.status == "failed"
        assert result.open_questions

    def test_no_trace_returns_failed(self, tmp_path: Path) -> None:
        adapter = _adapter(tmp_path, run_child=lambda ref, inp: None)
        result = adapter.dispatchAgent("pipeline-scout", {})
        assert result.status == "failed"
        assert result.open_questions


class TestDispatchAgentDeliveryStatusFallback:
    def test_long_ds_block_uses_artifact_fallback(self, tmp_path: Path) -> None:
        """Regression: >500-char delivery_status block clipped by final_text_snippet.

        The adapter must fall back to scanning *.md artifacts in run_dir (DD-05).
        """
        long_fields = {f"field_{i}": f"value_{i}" for i in range(30)}
        long_ds_json = json.dumps(
            {
                "status": "done",
                "artifact_paths": ["reports/artifact.md"],
                "produces": "research",
                "fields": long_fields,
                "open_questions": [],
                "telemetry": {"tokens": 500, "usd": 0.001, "seconds": 5},
            }
        )
        assert len(long_ds_json) > 500, "test assumption: JSON >500 chars"
        clipped_snippet = long_ds_json[:500]  # no complete fence

        adapter = _adapter(
            tmp_path, run_child=lambda ref, inp: _make_trace(clipped_snippet)
        )
        run_dir = tmp_path / "run"
        report = run_dir / "scout-report.md"
        report.write_text(f"# Scout Report\n\n```delivery_status\n{long_ds_json}\n```\n")

        result = adapter.dispatchAgent("pipeline-scout", {})
        assert result.status == "done"
        assert result.artifact_paths == ["reports/artifact.md"]
