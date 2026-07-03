"""R3 regression tests — typed scope and conditions (kills D3).

Defect D3 (00-assessment.md §2): JSON booleans in agent fences stringified
via ``str(True)`` → ``"True"``, which matched neither ``== true`` nor
``== false`` — both branches of the shipped spec's has_ui routing
(delivery.workflow.yaml:212-213) evaluated False.

Covered here:
  1. Typed comparisons — bool / int / float / str through eval_condition.
  2. String scopes behave exactly as v1 for present keys (backend harness
     compatibility — decision.py / executor.py / executor_adapter.py all
     consume this evaluator with all-string scopes).
  3. exists(path) / !exists(path) presence guards.
  4. Missing key → False for every operator (incl. ``!=``) + WARNING log
     (deliberate R3 breaking change replacing the None != rhs → True footgun).
  5. Canonical serialization: booleans render true/false, numbers unquoted —
     canonical_scalar/canonicalize_scope, and state.json (JSON-native).
  6. The full D3 chain: typed fields → StateStore round-trip → build_scope →
     eval_condition, and the runner routing has_ui=false to architect
     (not frontend) pre-resume.
"""
from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

_PKG = Path(__file__).parent.parent.parent
if str(_PKG) not in sys.path:
    sys.path.insert(0, str(_PKG))

import runner as workflow_runner  # noqa: E402
from ir import IREdge, IRGraph, IRNode  # noqa: E402
from lib.conditions import (  # noqa: E402
    canonical_scalar,
    canonicalize_scope,
    eval_condition,
)
from lib.state.store import StateStore  # noqa: E402
from results import AgentResult, TelemetryData  # noqa: E402
from runner.scope import build_scope  # noqa: E402
from state_types import BudgetState, NodeState, WorkflowState  # noqa: E402


def _state(**nodes: NodeState) -> WorkflowState:
    return WorkflowState(
        spec="t", run_id="r", status="running",
        budget=BudgetState(usd_ceiling=0.0), nodes=dict(nodes),
    )


# ---------------------------------------------------------------------------
# 1. Typed comparisons
# ---------------------------------------------------------------------------


class TestTypedComparisons:
    def test_bool_true_matches_canonical_token(self):
        assert eval_condition("n.fields.has_ui == true", {"n.fields.has_ui": True}) is True
        assert eval_condition("n.fields.has_ui == false", {"n.fields.has_ui": True}) is False

    def test_bool_false_matches_canonical_token(self):
        assert eval_condition("n.fields.has_ui == false", {"n.fields.has_ui": False}) is True
        assert eval_condition("n.fields.has_ui == true", {"n.fields.has_ui": False}) is False

    def test_bool_python_repr_never_matches(self):
        """str(True) → 'True' is exactly the D3 defect spelling — must not match."""
        assert eval_condition("flag == 'True'", {"flag": True}) is False
        assert eval_condition("flag == True", {"flag": True}) is False

    def test_bool_not_equals(self):
        assert eval_condition("flag != false", {"flag": True}) is True
        assert eval_condition("flag != true", {"flag": True}) is False

    def test_bool_quoted_canonical_matches(self):
        """Quoted canonical form is equivalent to the bare token."""
        assert eval_condition("flag == 'true'", {"flag": True}) is True

    def test_int_equality(self):
        assert eval_condition("n.fields.count == 3", {"n.fields.count": 3}) is True
        assert eval_condition("n.fields.count == 4", {"n.fields.count": 3}) is False
        assert eval_condition("n.fields.count != 4", {"n.fields.count": 3}) is True

    def test_int_vs_float_literal_numeric_equality(self):
        assert eval_condition("count == 3.0", {"count": 3}) is True
        assert eval_condition("count == 3", {"count": 3.0}) is True

    def test_float_equality(self):
        assert eval_condition("score == 0.5", {"score": 0.5}) is True
        assert eval_condition("score == 0.6", {"score": 0.5}) is False

    def test_number_never_matches_bool_token(self):
        """int 1 is not bool True; canonical forms differ ('1' vs 'true')."""
        assert eval_condition("x == true", {"x": 1}) is False
        assert eval_condition("x == 1", {"x": True}) is False

    def test_in_operator_typed(self):
        assert eval_condition("flag in true,false", {"flag": True}) is True
        assert eval_condition("count in 1,2,3", {"count": 2}) is True
        assert eval_condition("count in 1,2,3", {"count": 4}) is False

    def test_none_value_canonical_null(self):
        assert eval_condition("x == null", {"x": None}) is True
        assert eval_condition("x == none", {"x": None}) is False


class TestStringScopesUnchangedV1:
    """Backend harness path compatibility: all-string scopes, present keys —
    byte-for-byte v1 semantics."""

    def test_string_equality(self):
        assert eval_condition("verdict == pass", {"verdict": "pass"}) is True
        assert eval_condition("verdict == 'pass'", {"verdict": "pass"}) is True
        assert eval_condition("verdict == fail", {"verdict": "pass"}) is False

    def test_string_not_equals_present_key(self):
        assert eval_condition("status != error", {"status": "done"}) is True
        assert eval_condition("status != done", {"status": "done"}) is False

    def test_string_in(self):
        assert eval_condition("cls in code,dependency", {"cls": "code"}) is True
        assert eval_condition("cls in code,dependency", {"cls": "design"}) is False

    def test_string_true_matches_bare_true_token(self):
        """A string 'true' (harness scopes stringify) still matches `== true`."""
        assert eval_condition("has_ui == true", {"has_ui": "true"}) is True

    def test_string_numeric_text_still_string_compared(self):
        assert eval_condition("count == 3", {"count": "3"}) is True
        # v1 compared raw text; '3.0' text != '3' literal stays False for strings.
        assert eval_condition("count == 3", {"count": "3.0"}) is False

    def test_string_python_repr_true_unchanged(self):
        """A scope that (wrongly) carries 'True' text keeps v1 behavior."""
        assert eval_condition("flag == 'True'", {"flag": "True"}) is True
        assert eval_condition("flag == true", {"flag": "True"}) is False


# ---------------------------------------------------------------------------
# 3. exists() guard
# ---------------------------------------------------------------------------


class TestExistsGuard:
    def test_exists_present(self):
        assert eval_condition("exists(review.fields.verdict)", {"review.fields.verdict": "pass"}) is True

    def test_exists_missing(self):
        assert eval_condition("exists(review.fields.verdict)", {}) is False

    def test_exists_present_none_value(self):
        """exists() is about key presence, not truthiness."""
        assert eval_condition("exists(x)", {"x": None}) is True
        assert eval_condition("exists(x)", {"x": False}) is True

    def test_not_exists(self):
        assert eval_condition("!exists(x)", {}) is True
        assert eval_condition("!exists(x)", {"x": "v"}) is False

    def test_exists_in_conjunction(self):
        scope = {"review.fields.verdict": "needs_fix"}
        assert eval_condition(
            "exists(review.fields.verdict) && review.fields.verdict == needs_fix", scope
        ) is True
        assert eval_condition(
            "exists(review.fields.cls) && review.fields.verdict == needs_fix", scope
        ) is False

    def test_exists_in_disjunction(self):
        assert eval_condition("exists(a) || b == 1", {"b": 1}) is True
        assert eval_condition("exists(a) || b == 2", {"b": 1}) is False

    def test_exists_whitespace_tolerant(self):
        assert eval_condition("exists( x )", {"x": "v"}) is True


# ---------------------------------------------------------------------------
# 4. Missing key → False + WARNING (R3 breaking change)
# ---------------------------------------------------------------------------


class TestMissingKeySemantics:
    def test_missing_key_eq_false(self):
        assert eval_condition("x == 1", {}) is False

    def test_missing_key_ne_false(self):
        """v1 evaluated None != rhs → True; R3 makes every missing-key clause False."""
        assert eval_condition("x != 1", {}) is False

    def test_missing_key_in_false(self):
        assert eval_condition("x in a,b", {}) is False

    def test_missing_key_logs_warning(self, caplog):
        with caplog.at_level(logging.WARNING, logger="lib.conditions"):
            assert eval_condition("ghost.fields.x != 1", {"other": 1}) is False
        assert any(
            "not in scope" in rec.getMessage() for rec in caplog.records
        ), f"expected a missing-key warning, got: {[r.getMessage() for r in caplog.records]}"

    def test_present_key_no_warning(self, caplog):
        with caplog.at_level(logging.WARNING, logger="lib.conditions"):
            assert eval_condition("x != 1", {"x": 2}) is True
        assert not caplog.records


# ---------------------------------------------------------------------------
# 5. Canonical serialization
# ---------------------------------------------------------------------------


class TestCanonicalSerialization:
    def test_canonical_scalar_booleans(self):
        assert canonical_scalar(True) == "true"
        assert canonical_scalar(False) == "false"

    def test_canonical_scalar_numbers_unquoted(self):
        assert canonical_scalar(3) == "3"
        assert canonical_scalar(-7) == "-7"
        assert canonical_scalar(3.5) == "3.5"

    def test_canonical_scalar_string_passthrough(self):
        assert canonical_scalar("pass") == "pass"

    def test_canonical_scalar_none(self):
        assert canonical_scalar(None) == "null"

    def test_canonicalize_scope(self):
        scope = {"a": True, "b": 3, "c": "s", "d": None, "e": 0.5}
        assert canonicalize_scope(scope) == {
            "a": "true", "b": "3", "c": "s", "d": "null", "e": "0.5",
        }

    def test_state_json_keeps_json_native_types(self, tmp_path):
        """state.json canonicalizes: booleans true/false, numbers unquoted —
        never the Python reprs 'True'/'3'-as-string."""
        store = StateStore(tmp_path)
        ws = _state(analyze=NodeState(
            status="done",
            fields={"has_ui": True, "count": 3, "score": 0.5, "verdict": "pass"},
        ))
        store.write(ws)
        raw = (tmp_path / "state.json").read_text()
        data = json.loads(raw)
        fields = data["nodes"]["analyze"]["fields"]
        assert fields == {"has_ui": True, "count": 3, "score": 0.5, "verdict": "pass"}
        assert '"has_ui": true' in raw
        assert '"count": 3' in raw
        assert "True" not in raw


# ---------------------------------------------------------------------------
# 6. The D3 chain end-to-end
# ---------------------------------------------------------------------------


class TestD3Chain:
    def test_build_scope_carries_typed_fields(self):
        ws = _state(analyze=NodeState(status="done", fields={"has_ui": True, "count": 3}))
        scope = build_scope(ws)
        assert scope["analyze.fields.has_ui"] is True
        assert scope["analyze.fields.count"] == 3

    def test_persisted_bool_routes_after_reload(self, tmp_path):
        """Typed fields survive StateStore round-trip and route == true/false."""
        store = StateStore(tmp_path)
        store.write(_state(analyze=NodeState(status="done", fields={"has_ui": False})))
        scope = build_scope(store.read())
        assert scope["analyze.fields.has_ui"] is False
        assert eval_condition("analyze.fields.has_ui == false", scope) is True
        assert eval_condition("analyze.fields.has_ui == true", scope) is False

    def test_adapter_evalcondition_passes_typed_scope_through(self, tmp_path):
        """CronosAdapter.evalCondition no longer str()-coerces the scope (D3)."""
        from adapters.cronos.adapter import CronosAdapter

        run_dir = tmp_path / "run"
        run_dir.mkdir()
        StateStore(run_dir).write(_state())
        adapter = CronosAdapter(
            store=object(), trace_store=object(), space_id="s", run_dir=run_dir,
        )
        scope = {"analyze.fields.has_ui": True}
        assert adapter.evalCondition("analyze.fields.has_ui == true", scope) is True
        assert adapter.evalCondition("analyze.fields.has_ui == false", scope) is False
        assert adapter.evalCondition("exists(analyze.fields.has_ui)", scope) is True

    def test_runner_routes_has_ui_false_to_architect(self):
        """Pre-resume acceptance: JSON bool has_ui=false skips frontend and
        runs architect on the shipped-spec-shaped branch (D3 kill shot)."""

        class _Exec:
            def __init__(self):
                self.dispatched: list[str] = []
                self.state = None
                self.telemetry = self

            def emit(self, node_id, data):
                pass

            def dispatchAgent(self, agent_ref, inputs):
                nid = inputs["node_id"]
                self.dispatched.append(nid)
                fields = {"has_ui": False} if nid == "analyze" else {}
                return AgentResult(
                    status="done", artifact_paths=[], produces="x",
                    fields=fields, open_questions=[],
                    telemetry=TelemetryData(tokens=0, usd=0.0, seconds=0.0),
                )

            def runGate(self, gate, artifact_paths):
                raise NotImplementedError

            def runExec(self, node_id, command, inputs):
                raise NotImplementedError

            def evalCondition(self, expr, scope):
                return eval_condition(expr, scope)

            def escalate(self, node_id, reason):
                pass

        def _node(nid):
            return IRNode(id=nid, kind="agent", data={}, loop=None)

        graph = IRGraph(
            nodes=[_node("analyze"), _node("frontend"), _node("architect")],
            edges=[
                IREdge(source="analyze", target="frontend",
                       when="analyze.fields.has_ui == true", port=None),
                IREdge(source="analyze", target="architect",
                       when="analyze.fields.has_ui == false", port=None),
            ],
            metadata={}, variables={},
        )
        ex = _Exec()
        final = workflow_runner.run(graph=graph, executor=ex, state_ops=None)
        assert "architect" in ex.dispatched
        assert "frontend" not in ex.dispatched
        assert final.nodes["architect"].status == "done"
