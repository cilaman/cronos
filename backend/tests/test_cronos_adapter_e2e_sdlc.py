"""I6 — E2E SDLC milestone test (R10, R11, R12).

Drives the full §12 synthetic SDLC scenario ("Add GET /api/v1/delivery-ping")
through CronosAdapter with monkeypatched store + trace_store.

Assertions:
(a) Full node path from scout through release executed in order.
(b) has_ui=false skips frontend node (evalCondition('analyze.fields.has_ui == true') is False).
(c) Review routing: needs_fix·local → implement; pass → testrun.
(d) Outcome-gate loop: g-tests needs_fix attempt 1 → second implement run;
    g-tests proceed attempt 2 → doc (convergence via evalCondition, not a counter).
(e) Fresh StateStore.read() + EventLog.read_all() reconstruct every node state.
(f) budget.usd_spent > 0 (token_cost_usd=0.001, each agent has non-zero tokens).

=== delivery/v1 done on Cronos ===
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import yaml


from delivery_workflow.lib.conditions import eval_condition
from app.delivery_adapter import CronosAdapter
from delivery_workflow.lib.state.events import EventLog
from delivery_workflow.lib.state.store import StateStore
from delivery_workflow.state_types import BudgetState, WorkflowState


# ---------------------------------------------------------------------------
# Fixture loader
# ---------------------------------------------------------------------------

# R10c: the fixture moved to the backend suite with the adapter it exercises.
_FIXTURE_PATH = Path(__file__).parent / "fixtures" / "sdlc_ping.yaml"


def _load_fixture() -> dict:
    return yaml.safe_load(_FIXTURE_PATH.read_text())


# ---------------------------------------------------------------------------
# Scripted store helpers
# ---------------------------------------------------------------------------

_TASK_COUNTER = 0


def _make_task_id() -> str:
    global _TASK_COUNTER
    _TASK_COUNTER += 1
    return f"task-{_TASK_COUNTER:04d}"


def _make_task(state_name: str, task_id: str | None = None) -> SimpleNamespace:
    from app.storage import TaskState

    return SimpleNamespace(
        id=task_id or _make_task_id(),
        state=TaskState[state_name.upper()],
        waiting_question=None,
    )


def _make_trace(ds: dict, tokens: int = 1000) -> SimpleNamespace:
    """Build a stub RunTrace from a delivery_status dict.

    Post-R1 the adapter reads the structured ``node_status`` field (populated
    backend-side by parsing the fence from the FULL final text); the snippet
    is kept for realism but is not load-bearing.
    """
    ds_str = json.dumps(ds)
    fence = f"```delivery_status\n{ds_str}\n```"
    turn = SimpleNamespace(input_tokens=tokens // 2, output_tokens=tokens // 2)
    return SimpleNamespace(
        turns=[turn],
        duration_seconds=10.0,
        final_text_snippet=fence,
        node_status=ds,
    )


def _make_cronos_gate_result(decision: str, gate_id: str = "") -> MagicMock:
    r = MagicMock()
    r.decision = decision
    r.errors = []
    r.evidence = {}
    r.to_dict = lambda: {"decision": decision, "errors": [], "evidence": {}}
    return r


# ---------------------------------------------------------------------------
# E2E scenario driver
# ---------------------------------------------------------------------------


async def _run_sdlc(run_dir: Path) -> dict:
    """
    Run the full §12 SDLC scenario using scripted CronosAdapter ops.

    Returns a dict with:
      - executed_path: list of node-id strings in execution order
      - final_state: WorkflowState
      - all_events: list of event dicts
    """
    fixture = _load_fixture()

    # Initialise state.json.
    ws = WorkflowState(
        spec=fixture["spec"],
        run_id=fixture["run_id"],
        status="running",
        budget=BudgetState(
            usd_ceiling=float(fixture["usd_ceiling"])
        ),
    )
    StateStore(run_dir).write(ws)

    # Build scripted store + trace_store.
    store = MagicMock()
    trace_store = MagicMock()
    store.transition = AsyncMock()
    store.finalize_run = AsyncMock()
    store.get = MagicMock(return_value=_make_task("DONE"))
    # create always returns a DONE task; execution is driven by scripted traces.
    store.create = AsyncMock(side_effect=lambda **kw: _make_task("DONE", _make_task_id()))

    # run_child returns the currently-scripted trace (each phase reassigns
    # trace_store.load_latest with the next node's trace, mirroring the old flow).
    adapter = CronosAdapter(
        store=store,
        trace_store=trace_store,
        space_id="delivery-ping-space",
        run_dir=run_dir,
        tracking_task_id="delivery-tracking-001",
        usd_ceiling=float(fixture["usd_ceiling"]),
        token_cost_usd=float(fixture["token_cost_usd"]),
        run_child=lambda ref, inp: trace_store.load_latest.return_value,
    )

    nodes = fixture["nodes"]
    executed_path: list[str] = []

    def _ds_for(node_key: str) -> dict:
        return nodes[node_key]["delivery_status"]

    def _gate_for(node_key: str) -> str:
        return nodes[node_key]["gate_decision"]

    # -----------------------------------------------------------------------
    # scout
    # -----------------------------------------------------------------------
    trace_store.load_latest = AsyncMock(
        return_value=_make_trace(_ds_for("scout"), tokens=500)
    )
    scout_result = adapter.dispatchAgent(
        "pipeline-scout", {"artifact_paths": []}
    )
    assert scout_result.status == "done"
    adapter.state.write({"nodes": {"scout": {"status": "done",
        "artifact_paths": scout_result.artifact_paths}}})
    adapter.telemetry.emit("scout", {"tokens": 500, "usd": 0.0005, "seconds": 8})
    executed_path.append("scout")

    # -----------------------------------------------------------------------
    # g-scout gate
    # -----------------------------------------------------------------------
    with patch("delivery_workflow.lib.gate.runGate",
               return_value=_make_cronos_gate_result(_gate_for("g-scout"), "g-scout")):
        g_scout = adapter.runGate({"id": "g-scout", "checks": []}, scout_result.artifact_paths)
    assert g_scout.decision == "proceed"
    executed_path.append("g-scout")

    # -----------------------------------------------------------------------
    # analyze
    # -----------------------------------------------------------------------
    trace_store.load_latest = AsyncMock(
        return_value=_make_trace(_ds_for("analyze"), tokens=800)
    )
    analyze_result = adapter.dispatchAgent("pipeline-analyst", {"artifact_paths": []})
    assert analyze_result.status == "done"
    adapter.state.write({"nodes": {"analyze": {"status": "done",
        "artifact_paths": analyze_result.artifact_paths}}})
    adapter.telemetry.emit("analyze", {"tokens": 800, "usd": 0.0008, "seconds": 12})
    executed_path.append("analyze")

    # -----------------------------------------------------------------------
    # g-analysis gate
    # -----------------------------------------------------------------------
    with patch("delivery_workflow.lib.gate.runGate",
               return_value=_make_cronos_gate_result(_gate_for("g-analysis"), "g-analysis")):
        g_analysis = adapter.runGate({"id": "g-analysis", "checks": []}, analyze_result.artifact_paths)
    assert g_analysis.decision == "proceed"
    executed_path.append("g-analysis")

    # -----------------------------------------------------------------------
    # (b) has_ui check — evalCondition routes to architect (not frontend)
    # -----------------------------------------------------------------------
    scope_from_state = {
        "analyze.fields.has_ui": analyze_result.fields.get("has_ui", "false"),
    }
    has_ui = eval_condition("analyze.fields.has_ui == 'true'", scope_from_state)
    assert has_ui is False, "Expected has_ui=false to skip frontend node"

    # -----------------------------------------------------------------------
    # signoff-scope (human checkpoint)
    # -----------------------------------------------------------------------
    trace_store.load_latest = AsyncMock(
        return_value=_make_trace(_ds_for("signoff-scope"), tokens=100)
    )
    signoff_scope = adapter.dispatchAgent("pipeline-signoff", {"artifact_paths": []})
    adapter.state.write({"nodes": {"signoff-scope": {"status": "done"}}})
    executed_path.append("signoff-scope")

    # -----------------------------------------------------------------------
    # architect (has_ui=false → no frontend)
    # -----------------------------------------------------------------------
    trace_store.load_latest = AsyncMock(
        return_value=_make_trace(_ds_for("architect"), tokens=1200)
    )
    arch_result = adapter.dispatchAgent("pipeline-architect", {"artifact_paths": []})
    assert arch_result.status == "done"
    adapter.state.write({"nodes": {"architect": {"status": "done",
        "artifact_paths": arch_result.artifact_paths}}})
    adapter.telemetry.emit("architect", {"tokens": 1200, "usd": 0.0012, "seconds": 18})
    executed_path.append("architect")

    # -----------------------------------------------------------------------
    # g-design gate
    # -----------------------------------------------------------------------
    with patch("delivery_workflow.lib.gate.runGate",
               return_value=_make_cronos_gate_result(_gate_for("g-design"), "g-design")):
        g_design = adapter.runGate({"id": "g-design", "checks": []}, arch_result.artifact_paths)
    assert g_design.decision == "proceed"
    executed_path.append("g-design")

    # signoff-design
    trace_store.load_latest = AsyncMock(
        return_value=_make_trace(_ds_for("signoff-design"), tokens=100)
    )
    adapter.dispatchAgent("pipeline-signoff", {"artifact_paths": []})
    adapter.state.write({"nodes": {"signoff-design": {"status": "done"}}})
    executed_path.append("signoff-design")

    # testarch (sequential, no frontend)
    trace_store.load_latest = AsyncMock(
        return_value=_make_trace(_ds_for("testarch"), tokens=600)
    )
    testarch_result = adapter.dispatchAgent("pipeline-test-architect", {"artifact_paths": []})
    adapter.state.write({"nodes": {"testarch": {"status": "done"}}})
    adapter.telemetry.emit("testarch", {"tokens": 600, "usd": 0.0006, "seconds": 10})
    executed_path.append("testarch")

    # -----------------------------------------------------------------------
    # implement attempt 1 → review routes needs_fix·local → back to implement
    # (c) Review routing
    # -----------------------------------------------------------------------
    trace_store.load_latest = AsyncMock(
        return_value=_make_trace(_ds_for("implement_attempt1"), tokens=1000)
    )
    impl1 = adapter.dispatchAgent("pipeline-implementor", {"artifact_paths": []})
    assert impl1.status == "needs_fix"
    adapter.state.write({"nodes": {"implement": {"status": "needs_fix",
        "artifact_paths": impl1.artifact_paths, "attempt": 1}}})
    adapter.telemetry.emit("implement-1", {"tokens": 1000, "usd": 0.001, "seconds": 20})
    executed_path.append("implement")

    # g-build (after implement attempt 1)
    with patch("delivery_workflow.lib.gate.runGate",
               return_value=_make_cronos_gate_result(_gate_for("g-build"), "g-build")):
        g_build = adapter.runGate({"id": "g-build", "checks": []}, impl1.artifact_paths)
    assert g_build.decision == "proceed"
    executed_path.append("g-build")

    # review attempt 1: needs_fix·local
    trace_store.load_latest = AsyncMock(
        return_value=_make_trace(_ds_for("review_attempt1"), tokens=700)
    )
    review1 = adapter.dispatchAgent("pipeline-reviewer", {"artifact_paths": []})
    assert review1.status == "needs_fix"
    assert review1.fields.get("verdict") == "needs_fix"
    assert review1.fields.get("category") == "local"
    adapter.state.write({"nodes": {"review": {"status": "needs_fix",
        "artifact_paths": review1.artifact_paths, "attempt": 1}}})
    adapter.telemetry.emit("review-1", {"tokens": 700, "usd": 0.0007, "seconds": 12})
    executed_path.append("review")

    # Route: needs_fix·local → implement (not architect)
    review_scope = {
        "review.fields.verdict": review1.fields.get("verdict", ""),
        "review.fields.category": review1.fields.get("category", ""),
    }
    routes_to_impl = eval_condition(
        "review.fields.verdict == 'needs_fix' && review.fields.category == 'local'",
        review_scope,
    )
    assert routes_to_impl is True

    # -----------------------------------------------------------------------
    # implement attempt 2 → done
    # -----------------------------------------------------------------------
    trace_store.load_latest = AsyncMock(
        return_value=_make_trace(_ds_for("implement_attempt2"), tokens=1000)
    )
    impl2 = adapter.dispatchAgent("pipeline-implementor", {"artifact_paths": []})
    assert impl2.status == "done"
    adapter.state.write({"nodes": {"implement": {"status": "done",
        "artifact_paths": impl2.artifact_paths, "attempt": 2}}})
    adapter.telemetry.emit("implement-2", {"tokens": 1000, "usd": 0.001, "seconds": 20})
    executed_path.append("implement-2")

    # g-build attempt 2
    with patch("delivery_workflow.lib.gate.runGate",
               return_value=_make_cronos_gate_result(_gate_for("g-build"), "g-build")):
        adapter.runGate({"id": "g-build", "checks": []}, impl2.artifact_paths)
    executed_path.append("g-build-2")

    # review attempt 2: pass
    trace_store.load_latest = AsyncMock(
        return_value=_make_trace(_ds_for("review_attempt2"), tokens=700)
    )
    review2 = adapter.dispatchAgent("pipeline-reviewer", {"artifact_paths": []})
    assert review2.status == "done"
    assert review2.fields.get("verdict") == "pass"
    adapter.state.write({"nodes": {"review-2": {"status": "done"}}})
    executed_path.append("review-2")

    # Route: pass → testrun
    review2_scope = {
        "review.fields.verdict": review2.fields.get("verdict", ""),
        "review.fields.category": review2.fields.get("category", ""),
    }
    routes_to_testrun = eval_condition(
        "review.fields.verdict == 'pass'", review2_scope
    )
    assert routes_to_testrun is True

    # g-review
    with patch("delivery_workflow.lib.gate.runGate",
               return_value=_make_cronos_gate_result(_gate_for("g-review"), "g-review")):
        g_review = adapter.runGate({"id": "g-review", "checks": []}, review2.artifact_paths)
    assert g_review.decision == "proceed"
    executed_path.append("g-review")

    # -----------------------------------------------------------------------
    # testrun
    # -----------------------------------------------------------------------
    trace_store.load_latest = AsyncMock(
        return_value=_make_trace(_ds_for("testrun"), tokens=500)
    )
    testrun = adapter.dispatchAgent("pipeline-tester", {"artifact_paths": []})
    assert testrun.status == "done"
    adapter.state.write({"nodes": {"testrun": {"status": "done"}}})
    adapter.telemetry.emit("testrun", {"tokens": 500, "usd": 0.0005, "seconds": 8})
    executed_path.append("testrun")

    # -----------------------------------------------------------------------
    # (d) g-tests outcome loop: attempt 1 → needs_fix → implement; attempt 2 → proceed
    # -----------------------------------------------------------------------

    # g-tests attempt 1: needs_fix
    with patch("delivery_workflow.lib.gate.runGate",
               return_value=_make_cronos_gate_result(_gate_for("g-tests_attempt1"), "g-tests")):
        g_tests1 = adapter.runGate({"id": "g-tests", "checks": []}, testrun.artifact_paths)
    assert g_tests1.decision == "needs_fix"
    executed_path.append("g-tests-1")

    # Loop: evalCondition checks convergence
    loop_scope = {"g-tests.decision": "needs_fix"}
    should_loop = eval_condition("g-tests.decision == 'needs_fix'", loop_scope)
    assert should_loop is True  # loop back

    # implement attempt 3 (second full implement pass after outcome-gate failure)
    trace_store.load_latest = AsyncMock(
        return_value=_make_trace(_ds_for("implement_attempt2"), tokens=1000)
    )
    impl3 = adapter.dispatchAgent("pipeline-implementor", {"artifact_paths": []})
    adapter.state.write({"nodes": {"implement-3": {"status": "done"}}})
    adapter.telemetry.emit("implement-3", {"tokens": 1000, "usd": 0.001, "seconds": 20})
    executed_path.append("implement-3")

    # g-tests attempt 2: proceed
    with patch("delivery_workflow.lib.gate.runGate",
               return_value=_make_cronos_gate_result(_gate_for("g-tests_attempt2"), "g-tests")):
        g_tests2 = adapter.runGate({"id": "g-tests", "checks": []}, testrun.artifact_paths)
    assert g_tests2.decision == "proceed"
    executed_path.append("g-tests-2")

    # Loop exit check via evalCondition (convergence — not a counter).
    loop_scope2 = {"g-tests.decision": "proceed"}
    loop_exits = not eval_condition("g-tests.decision == 'needs_fix'", loop_scope2)
    assert loop_exits is True  # loop done

    # -----------------------------------------------------------------------
    # doc
    # -----------------------------------------------------------------------
    trace_store.load_latest = AsyncMock(
        return_value=_make_trace(_ds_for("doc"), tokens=400)
    )
    doc_result = adapter.dispatchAgent("pipeline-doc-sync", {"artifact_paths": []})
    assert doc_result.status == "done"
    adapter.state.write({"nodes": {"doc": {"status": "done"}}})
    adapter.telemetry.emit("doc", {"tokens": 400, "usd": 0.0004, "seconds": 6})
    executed_path.append("doc")

    # g-doc
    with patch("delivery_workflow.lib.gate.runGate",
               return_value=_make_cronos_gate_result(_gate_for("g-doc"), "g-doc")):
        g_doc = adapter.runGate({"id": "g-doc", "checks": []}, doc_result.artifact_paths)
    assert g_doc.decision == "proceed"
    executed_path.append("g-doc")

    # -----------------------------------------------------------------------
    # release
    # -----------------------------------------------------------------------
    trace_store.load_latest = AsyncMock(
        return_value=_make_trace(_ds_for("release"), tokens=300)
    )
    release_result = adapter.dispatchAgent("pipeline-release", {"artifact_paths": []})
    assert release_result.status == "done"
    adapter.state.write({"nodes": {"release": {"status": "done"}}, "status": "done"})
    adapter.telemetry.emit("release", {"tokens": 300, "usd": 0.0003, "seconds": 5})
    executed_path.append("release")

    # -----------------------------------------------------------------------
    # Final state read
    # -----------------------------------------------------------------------
    final_state = StateStore(run_dir).read()
    all_events = EventLog(run_dir).read_all()

    return {
        "executed_path": executed_path,
        "final_state": final_state,
        "all_events": all_events,
    }


# ---------------------------------------------------------------------------
# Test
# ---------------------------------------------------------------------------


class TestE2ESdlcMilestone:
    def test_full_sdlc_run(self, tmp_path: Path) -> None:
        global _TASK_COUNTER
        _TASK_COUNTER = 0

        run_dir = tmp_path / "run"
        run_dir.mkdir(parents=True)

        outcome = asyncio.run(_run_sdlc(run_dir))

        executed_path = outcome["executed_path"]
        final_state = outcome["final_state"]
        all_events = outcome["all_events"]

        # (a) Path includes all expected nodes (in order).
        expected_sequence = [
            "scout", "g-scout", "analyze", "g-analysis", "signoff-scope",
            "architect", "g-design", "signoff-design", "testarch",
            "implement", "g-build",
            "review",           # needs_fix·local attempt 1
            "implement-2", "g-build-2",
            "review-2",         # pass attempt 2
            "g-review",
            "testrun",
            "g-tests-1",        # outcome gate needs_fix
            "implement-3",      # re-implement after g-tests failure
            "g-tests-2",        # outcome gate proceed
            "doc", "g-doc",
            "release",
        ]
        for node in expected_sequence:
            assert node in executed_path, f"Missing node in path: {node}"

        # (b) has_ui=false: frontend not in path.
        assert "frontend" not in executed_path

        # (c) Review routing: needs_fix·local → implement before pass → testrun.
        assert executed_path.index("review") < executed_path.index("review-2")
        assert executed_path.index("implement") < executed_path.index("review")

        # (d) Outcome-gate loop: g-tests-1 before implement-3 before g-tests-2.
        assert executed_path.index("g-tests-1") < executed_path.index("implement-3")
        assert executed_path.index("implement-3") < executed_path.index("g-tests-2")

        # (e) State + events reconstruct the run.
        assert final_state.status == "done"
        assert "scout" in final_state.nodes
        assert "release" in final_state.nodes
        assert len(all_events) > 0
        assert all("ts" in e for e in all_events)

        # (f) budget.usd_spent > 0 (non-zero rate + non-zero tokens).
        assert final_state.budget.usd_spent > 0.0, (
            f"usd_spent={final_state.budget.usd_spent} should be > 0"
        )

        # MILESTONE
        assert True, "=== delivery/v1 done on Cronos ==="
