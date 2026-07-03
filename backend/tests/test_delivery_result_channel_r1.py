"""R1 regression — the result channel (kills D6, D4, D13's package half).

Defects (00-assessment.md §2):

* D6 — node classification travelled through ``final_text_snippet``, a
  head-truncation to 2,000 chars of the agent's final message; a fence after
  long prose was amputated, the adapter fell back to an mtime-newest
  filesystem scan, and a successful child was classified ``failed``.
* D4 — the fence vocabulary was open and ``runner/dispatch.py`` maps only
  ``blocked``/``failed`` specially, so any unknown status (``wait``,
  ``error``, ``partial``) silently became node ``done``.

R1 (03-remediation-plan.md, 01-state-model.md §5.1/§5.7 option 1):

* The backend trace parser extracts the envelope from the FULL final text
  into the structured ``RunTrace.node_status`` field;
  ``CronosAdapter.dispatchAgent`` reads ONLY that field —
  ``final_text_snippet`` is no longer load-bearing.
* The vocabulary is CLOSED at the adapter boundary: a fence status outside
  {done, blocked, needs_fix, failed} maps to ``failed`` with
  ``open_questions=["unknown_status:<raw>"]`` — never silently to done.
* The mtime fallback scan is demoted to a log-only diagnostic (two-release
  deprecation): it logs what it WOULD have credited but the result is the
  honest ``failed``.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.delivery_adapter import CronosAdapter
from delivery_workflow.lib.state.store import StateStore
from delivery_workflow.results import AgentResult
from delivery_workflow.state_types import BudgetState, WorkflowState


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _envelope(status: str = "done", **overrides) -> dict:
    env = {
        "status": status,
        "artifact_paths": ["reports/scout.md"],
        "produces": "research",
        "fields": {"has_ui": False},
        "open_questions": [],
    }
    env.update(overrides)
    return env


def _trace(node_status: dict | None = None, **attrs) -> SimpleNamespace:
    """Stub RunTrace: mirrors the post-R1 backend RunTrace surface."""
    ns = SimpleNamespace(
        turns=[SimpleNamespace(input_tokens=800, output_tokens=400)],
        duration_seconds=15.0,
        final_text_snippet="",
        node_status=node_status,
    )
    for k, v in attrs.items():
        setattr(ns, k, v)
    return ns


def _adapter(tmp_path: Path, run_child) -> CronosAdapter:
    run_dir = tmp_path / "run"
    run_dir.mkdir(parents=True, exist_ok=True)
    StateStore(run_dir).write(
        WorkflowState(
            spec="t", run_id="r1", status="running",
            budget=BudgetState(usd_ceiling=5.0),
        )
    )
    return CronosAdapter(
        store=object(),
        trace_store=object(),
        space_id="s1",
        run_dir=run_dir,
        tracking_task_id="tracking-001",
        token_cost_usd=0.001,
        run_child=run_child,
        goal_slug="my-goal",
    )


# ---------------------------------------------------------------------------
# Closed vocabulary at the adapter boundary (D4)
# ---------------------------------------------------------------------------


class TestClosedVocabulary:
    @pytest.mark.parametrize("status", ["done", "blocked", "needs_fix", "failed"])
    def test_known_statuses_pass_through(self, tmp_path: Path, status: str) -> None:
        adapter = _adapter(
            tmp_path, run_child=lambda ref, inp: _trace(_envelope(status))
        )
        result = adapter.dispatchAgent("scout", {"node_id": "scout"})
        assert isinstance(result, AgentResult)
        assert result.status == status

    @pytest.mark.parametrize("raw", ["WAIT", "wait", "error", "partial", "ok"])
    def test_unknown_status_maps_to_failed_with_marker(
        self, tmp_path: Path, raw: str
    ) -> None:
        """D4: an out-of-vocabulary status must NEVER silently become done."""
        adapter = _adapter(
            tmp_path, run_child=lambda ref, inp: _trace(_envelope(raw))
        )
        result = adapter.dispatchAgent("scout", {"node_id": "scout"})
        assert result.status == "failed"
        assert result.open_questions[0] == f"unknown_status:{raw}"

    def test_missing_status_key_maps_to_failed(self, tmp_path: Path) -> None:
        env = _envelope()
        del env["status"]
        adapter = _adapter(tmp_path, run_child=lambda ref, inp: _trace(env))
        result = adapter.dispatchAgent("scout", {"node_id": "scout"})
        assert result.status == "failed"
        assert result.open_questions[0] == "unknown_status:None"

    def test_vocabulary_check_is_case_insensitive(self, tmp_path: Path) -> None:
        """The transport keeps the raw fence dict; the boundary normalizes."""
        adapter = _adapter(
            tmp_path, run_child=lambda ref, inp: _trace(_envelope("DONE"))
        )
        result = adapter.dispatchAgent("scout", {"node_id": "scout"})
        assert result.status == "done"

    def test_unknown_status_keeps_artifacts_and_fields_for_diagnosis(
        self, tmp_path: Path
    ) -> None:
        adapter = _adapter(
            tmp_path,
            run_child=lambda ref, inp: _trace(
                _envelope("wait", open_questions=["still waiting on X"])
            ),
        )
        result = adapter.dispatchAgent("scout", {"node_id": "scout"})
        assert result.status == "failed"
        assert result.open_questions == ["unknown_status:wait", "still waiting on X"]
        assert result.artifact_paths == ["reports/scout.md"]
        assert result.fields == {"has_ui": False}


# ---------------------------------------------------------------------------
# trace.node_status is the ONLY classification channel (D6)
# ---------------------------------------------------------------------------


class TestStructuredChannel:
    def test_envelope_fields_flow_into_agent_result(self, tmp_path: Path) -> None:
        env = _envelope(
            "done",
            artifact_paths=["a.md", "b.md"],
            produces="design",
            fields={"verdict": "pass"},
            open_questions=["q1"],
        )
        adapter = _adapter(tmp_path, run_child=lambda ref, inp: _trace(env))
        result = adapter.dispatchAgent("architect", {"node_id": "architect"})
        assert result.status == "done"
        assert result.artifact_paths == ["a.md", "b.md"]
        assert result.produces == "design"
        assert result.fields == {"verdict": "pass"}
        assert result.open_questions == ["q1"]

    def test_snippet_fence_is_no_longer_load_bearing(self, tmp_path: Path) -> None:
        """A fence that only survives in final_text_snippet is IGNORED: the
        snippet is a UI nicety after R1.  Classification uses node_status."""
        fence = f"```node_status\n{json.dumps(_envelope('done'))}\n```"
        trace = _trace(node_status=None, final_text_snippet=fence)
        adapter = _adapter(tmp_path, run_child=lambda ref, inp: trace)
        result = adapter.dispatchAgent("scout", {"node_id": "scout"})
        assert result.status == "failed"
        assert "No node_status fence found" in result.open_questions[0]

    def test_legacy_trace_without_field_fails_honestly(self, tmp_path: Path) -> None:
        """Traces saved before the field existed (no attribute at all)."""
        trace = SimpleNamespace(
            turns=[], duration_seconds=1.0, final_text_snippet=""
        )
        adapter = _adapter(tmp_path, run_child=lambda ref, inp: trace)
        result = adapter.dispatchAgent("scout", {"node_id": "scout"})
        assert result.status == "failed"
        assert "No node_status fence found" in result.open_questions[0]

    def test_non_dict_node_status_fails_honestly(self, tmp_path: Path) -> None:
        adapter = _adapter(
            tmp_path, run_child=lambda ref, inp: _trace(node_status=None)
        )
        result = adapter.dispatchAgent("scout", {"node_id": "scout"})
        assert result.status == "failed"


# ---------------------------------------------------------------------------
# mtime fallback scan demoted to log-only (D6 deprecation path)
# ---------------------------------------------------------------------------


class TestFallbackScanDemoted:
    def test_scan_hit_is_logged_but_never_credited(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Pre-R1 this exact setup credited the node 'done' from the newest
        artifact on disk.  Now: log what WOULD have been credited, return
        failed."""
        adapter = _adapter(tmp_path, run_child=lambda ref, inp: _trace(None))
        report = tmp_path / "run" / "scout-report.md"
        report.write_text(
            f"# Report\n\n```node_status\n{json.dumps(_envelope('done'))}\n```\n",
            encoding="utf-8",
        )

        with caplog.at_level(logging.WARNING, logger="app.delivery_adapter"):
            result = adapter.dispatchAgent(
                "scout", {"node_id": "scout", "produces": {"class": "research"}}
            )

        assert result.status == "failed"
        assert "No node_status fence found" in result.open_questions[0]
        messages = [rec.getMessage() for rec in caplog.records]
        assert any(
            "would have credited" in msg and "scout" in msg for msg in messages
        )

    def test_scan_miss_is_also_logged(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        adapter = _adapter(tmp_path, run_child=lambda ref, inp: _trace(None))
        with caplog.at_level(logging.WARNING, logger="app.delivery_adapter"):
            result = adapter.dispatchAgent("scout", {"node_id": "scout"})
        assert result.status == "failed"
        assert any(
            "found nothing" in rec.getMessage() for rec in caplog.records
        )


# ---------------------------------------------------------------------------
# Telemetry unaffected by the channel change
# ---------------------------------------------------------------------------


def test_telemetry_still_summed_per_turn(tmp_path: Path) -> None:
    adapter = _adapter(
        tmp_path, run_child=lambda ref, inp: _trace(_envelope("done"))
    )
    result = adapter.dispatchAgent("scout", {"node_id": "scout"})
    assert result.telemetry.tokens == 1200
    assert result.telemetry.usd == pytest.approx(1200 * 0.001)
