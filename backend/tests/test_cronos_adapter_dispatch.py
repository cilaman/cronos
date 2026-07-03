"""CronosAdapter.dispatchAgent tests (post inline-execution refactor).

dispatchAgent is now a *synchronous* thin shim: it calls the injected
``run_child(agent_ref, inputs)`` callback (which creates + executes the child on
the Cronos main loop and returns the child's RunTrace), then reads the
structured ``trace.node_status`` envelope (R1 — parsed backend-side from the
FULL final text, never from ``final_text_snippet``) + telemetry into an
AgentResult. Child creation, brief tagging, and BACKLOG→ACTIVE transition now
live in ``RunExecutor.run_delivery_child``.

Tests:
- Happy path: run_child returns a trace with a node_status envelope → done
- Telemetry summed per-turn
- No run_child wired → failed
- run_child returns None (no trace) → failed
- No envelope → failed; mtime artifact scan is log-only (R1 demotion of DD-05)
- run_child invoked with (agent_ref, inputs)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest


from app.delivery_adapter import CronosAdapter
from delivery_workflow.results import AgentResult
from delivery_workflow.state_types import BudgetState, WorkflowState


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_DS_ENVELOPE = {
    "status": "done",
    "artifact_paths": ["reports/scout.md"],
    "produces": "research",
    "fields": {"has_ui": False},
    "open_questions": [],
    "telemetry": {"tokens": 1200, "usd": 0.012, "seconds": 30},
}

_DS_FENCE = f"```delivery_status\n{json.dumps(_DS_ENVELOPE)}\n```"


def _make_trace(
    node_status: dict | None = None,
    final_text: str = _DS_FENCE,
    input_tokens: int = 800,
    output_tokens: int = 400,
    duration_seconds: float = 15.0,
) -> SimpleNamespace:
    """Stub RunTrace — post-R1 the structured ``node_status`` field carries the
    envelope; ``final_text_snippet`` is a UI nicety and never load-bearing."""
    turn = SimpleNamespace(input_tokens=input_tokens, output_tokens=output_tokens)
    return SimpleNamespace(
        turns=[turn],
        duration_seconds=duration_seconds,
        final_text_snippet=final_text,
        node_status=node_status,
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
    from delivery_workflow.lib.state.store import StateStore

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
        adapter = _adapter(
            tmp_path, run_child=lambda ref, inp: _make_trace(_DS_ENVELOPE)
        )

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


class TestDispatchAgentNoEnvelope:
    def test_missing_envelope_never_credits_artifact_scan(self, tmp_path: Path) -> None:
        """R1 (D6): the mtime artifact scan (old DD-05 fallback) is demoted to a
        log-only diagnostic.  A trace without ``node_status`` returns failed even
        when a matching report with a valid fence sits in run_dir — the scan is
        logged as "would have credited", never credited.
        """
        long_ds_json = json.dumps(
            {
                "status": "done",
                "artifact_paths": ["reports/artifact.md"],
                "produces": "research",
                "fields": {},
                "open_questions": [],
                "telemetry": {"tokens": 500, "usd": 0.001, "seconds": 5},
            }
        )

        adapter = _adapter(
            tmp_path, run_child=lambda ref, inp: _make_trace(node_status=None)
        )
        run_dir = tmp_path / "run"
        report = run_dir / "scout-report.md"
        report.write_text(f"# Scout Report\n\n```delivery_status\n{long_ds_json}\n```\n")

        result = adapter.dispatchAgent("pipeline-scout", {"node_id": "scout"})
        assert result.status == "failed"
        assert "No node_status fence found" in result.open_questions[0]

    def test_snippet_fence_is_not_load_bearing(self, tmp_path: Path) -> None:
        """A fence visible only in final_text_snippet is ignored post-R1."""
        adapter = _adapter(
            tmp_path,
            run_child=lambda ref, inp: _make_trace(
                node_status=None, final_text=_DS_FENCE
            ),
        )
        result = adapter.dispatchAgent("pipeline-scout", {"node_id": "scout"})
        assert result.status == "failed"
