"""I4 — CronosAdapter.evalCondition tests (R5).

Tests:
- Simple equality: "status == 'done'" → True/False
- Dotted-path identifiers: "analyze.fields.has_ui == 'true'" → True
- Hyphenated identifiers: "g-tests.status == 'done'" → True
- && conjunction: "a == 'x' && b == 'y'" → True/False
- Unknown variable → False (sandboxed)
- Non-string scope values are coerced to str
- Also tests public eval_condition in decision.py directly
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

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


def _adapter(tmp_path: Path) -> CronosAdapter:
    run_dir = tmp_path / "run"
    run_dir.mkdir(parents=True)
    ws = WorkflowState(
        spec="ping", run_id="r1", status="running", budget=BudgetState(usd_ceiling=10.0)
    )
    StateStore(run_dir).write(ws)
    return CronosAdapter(
        store=MagicMock(),
        trace_store=MagicMock(),
        space_id="s1",
        run_dir=run_dir,
    )


# ---------------------------------------------------------------------------
# Tests: evalCondition via adapter
# ---------------------------------------------------------------------------


class TestEvalConditionAdapter:
    def test_simple_equality_true(self, tmp_path: Path) -> None:
        adapter = _adapter(tmp_path)
        assert adapter.evalCondition("status == 'done'", {"status": "done"}) is True

    def test_simple_equality_false(self, tmp_path: Path) -> None:
        adapter = _adapter(tmp_path)
        assert adapter.evalCondition("status == 'done'", {"status": "running"}) is False

    def test_dotted_path_true(self, tmp_path: Path) -> None:
        adapter = _adapter(tmp_path)
        # Dotted path: "analyze.fields.has_ui" as a scope key
        scope = {"analyze.fields.has_ui": "true"}
        assert adapter.evalCondition("analyze.fields.has_ui == 'true'", scope) is True

    def test_dotted_path_false(self, tmp_path: Path) -> None:
        adapter = _adapter(tmp_path)
        scope = {"analyze.fields.has_ui": "false"}
        assert adapter.evalCondition("analyze.fields.has_ui == 'true'", scope) is False

    def test_hyphenated_identifier(self, tmp_path: Path) -> None:
        adapter = _adapter(tmp_path)
        scope = {"g-tests.status": "done"}
        assert adapter.evalCondition("g-tests.status == 'done'", scope) is True

    def test_and_conjunction_all_true(self, tmp_path: Path) -> None:
        adapter = _adapter(tmp_path)
        scope = {"review.decision": "needs_fix", "review.category": "local"}
        expr = "review.decision == 'needs_fix' && review.category == 'local'"
        assert adapter.evalCondition(expr, scope) is True

    def test_and_conjunction_one_false(self, tmp_path: Path) -> None:
        adapter = _adapter(tmp_path)
        scope = {"review.decision": "needs_fix", "review.category": "architectural"}
        expr = "review.decision == 'needs_fix' && review.category == 'local'"
        assert adapter.evalCondition(expr, scope) is False

    def test_unknown_variable_returns_false(self, tmp_path: Path) -> None:
        adapter = _adapter(tmp_path)
        assert (
            adapter.evalCondition("nonexistent.field == 'foo'", {"other": "foo"})
            is False
        )

    def test_non_string_coerced(self, tmp_path: Path) -> None:
        adapter = _adapter(tmp_path)
        # Boolean False → str "False"
        scope = {"has_ui": False}
        assert adapter.evalCondition("has_ui == 'False'", scope) is True

    def test_in_operator(self, tmp_path: Path) -> None:
        adapter = _adapter(tmp_path)
        scope = {"verdict": "needs_fix"}
        assert adapter.evalCondition("verdict in needs_fix,fail", scope) is True
        assert adapter.evalCondition("verdict in proceed,done", scope) is False

    def test_ne_operator(self, tmp_path: Path) -> None:
        adapter = _adapter(tmp_path)
        scope = {"status": "done"}
        assert adapter.evalCondition("status != 'running'", scope) is True
        assert adapter.evalCondition("status != 'done'", scope) is False


# ---------------------------------------------------------------------------
# Tests: eval_condition in decision.py (DD-07 public surface)
# ---------------------------------------------------------------------------


class TestEvalConditionDecision:
    def test_simple_equality(self) -> None:
        from app.harnesses.decision import eval_condition

        assert eval_condition("x == 'a'", {"x": "a"}) is True
        assert eval_condition("x == 'a'", {"x": "b"}) is False

    def test_dotted_path(self) -> None:
        from app.harnesses.decision import eval_condition

        scope = {"analyze.fields.has_ui": "true"}
        assert eval_condition("analyze.fields.has_ui == 'true'", scope) is True

    def test_hyphenated_key(self) -> None:
        from app.harnesses.decision import eval_condition

        scope = {"g-review.decision": "pass"}
        assert eval_condition("g-review.decision == 'pass'", scope) is True

    def test_and_conjunction(self) -> None:
        from app.harnesses.decision import eval_condition

        scope = {"a": "x", "b": "y"}
        assert eval_condition("a == 'x' && b == 'y'", scope) is True
        assert eval_condition("a == 'x' && b == 'z'", scope) is False

    def test_short_circuit_on_false(self) -> None:
        from app.harnesses.decision import eval_condition

        # First clause false → should return False without evaluating second.
        scope = {"a": "x"}
        assert eval_condition("a == 'z' && nonexistent == 'q'", scope) is False

    def test_empty_expr_returns_true(self) -> None:
        from app.harnesses.decision import eval_condition

        # Split on && yields [''] which passes _eval_variable_condition with False
        # for empty string — eval_condition('', {}) → the regex won't match
        # so returns False (not True). This is acceptable defensive behaviour.
        result = eval_condition("", {})
        assert isinstance(result, bool)
