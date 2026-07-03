"""Tests for runner/loop.py — LoopPolicy evaluation (I5)."""
from __future__ import annotations



from delivery_workflow.ir import IRNode, LoopPolicy
from delivery_workflow.runner.loop import reset_downstream_nodes, should_loop_back
from delivery_workflow.state_types import BudgetState, NodeState, WorkflowState


# ---------------------------------------------------------------------------
# Minimal mock executor for evalCondition + escalate recording
# ---------------------------------------------------------------------------

class _MockRuntime:
    """Host + scripted condition evaluator for should_loop_back (R10b).

    The runner no longer asks the executor to evaluate conditions —
    ``should_loop_back`` takes a ``host`` (on_event receives the loop-exhaust
    RunEscalated) and an ``eval_condition`` simulation hook.
    """

    def __init__(self, condition_result: bool = False) -> None:
        self._condition_result = condition_result
        self.escalated: list[tuple[str, str]] = []
        self.condition_calls: list[tuple[str, dict]] = []

    def evalCondition(self, expr: str, scope: dict) -> bool:
        self.condition_calls.append((expr, scope))
        return self._condition_result

    def on_event(self, event) -> None:
        from delivery_workflow.events import RunEscalated

        if isinstance(event, RunEscalated):
            self.escalated.append((event.node_id, event.detail))

    @property
    def state(self):
        class _S:
            def read(self): return None
            def write(self, p): pass
        return _S()

    @property
    def telemetry(self):
        class _T:
            def emit(self, nid, d): pass
        return _T()

    def dispatchAgent(self, *a, **k):
        raise NotImplementedError

    def runGate(self, *a, **k):
        raise NotImplementedError


def _state_with_node(node_id: str, attempt: int = 0, **fields) -> WorkflowState:
    state = WorkflowState(
        spec="test", run_id="r1", status="running",
        budget=BudgetState(usd_ceiling=0.0),
    )
    state.nodes[node_id] = NodeState(status="done", attempt=attempt, **fields)
    return state


class TestShouldLoopBack:
    def test_no_loop_policy_returns_false(self):
        node = IRNode(id="n", kind="agent", loop=None)
        state = _state_with_node("n")
        rt = _MockRuntime()
        assert should_loop_back(node, state, {}, host=rt, eval_condition=rt.evalCondition) is False

    def test_condition_met_does_not_loop(self):
        """When until-condition is True, loop exits (no back-edge)."""
        lp = LoopPolicy(until="review.fields.verdict == 'pass'", max=5)
        node = IRNode(id="review", kind="agent", loop=lp)
        state = _state_with_node("review", attempt=1)
        rt = _MockRuntime(condition_result=True)
        assert should_loop_back(node, state, {}, host=rt, eval_condition=rt.evalCondition) is False

    def test_condition_not_met_loops_back(self):
        """When until-condition is False and attempt < max, loop-back."""
        lp = LoopPolicy(until="review.fields.verdict == 'pass'", max=5)
        node = IRNode(id="review", kind="agent", loop=lp)
        state = _state_with_node("review", attempt=1)
        rt = _MockRuntime(condition_result=False)
        assert should_loop_back(node, state, {}, host=rt, eval_condition=rt.evalCondition) is True

    def test_loop_back_does_not_touch_attempt(self):
        """Single attempt owner (R8/D8): dispatch increments once per execution;
        the loop-back path must never add a second increment (which halved loop
        budgets: max=4 yielded 3 executions with the counter overshooting to 5)."""
        lp = LoopPolicy(until="x == 'done'", max=5)
        node = IRNode(id="n", kind="agent", loop=lp)
        state = _state_with_node("n", attempt=2)
        rt = _MockRuntime(condition_result=False)
        assert should_loop_back(node, state, {}, host=rt, eval_condition=rt.evalCondition) is True
        assert state.nodes["n"].attempt == 2  # unchanged — dispatch owns it

    def test_loop_back_zeroes_artifact_paths(self):
        lp = LoopPolicy(until="x == 'done'", max=5)
        node = IRNode(id="n", kind="agent", loop=lp)
        state = _state_with_node("n", attempt=1)
        state.nodes["n"].artifact_paths = ["old/file.md"]
        rt = _MockRuntime(condition_result=False)
        should_loop_back(node, state, {}, host=rt, eval_condition=rt.evalCondition)
        assert state.nodes["n"].artifact_paths == []

    def test_loop_back_zeroes_fields(self):
        lp = LoopPolicy(until="x == 'done'", max=5)
        node = IRNode(id="n", kind="agent", loop=lp)
        state = _state_with_node("n", attempt=1)
        state.nodes["n"].fields = {"verdict": "needs_fix"}
        rt = _MockRuntime(condition_result=False)
        should_loop_back(node, state, {}, host=rt, eval_condition=rt.evalCondition)
        assert state.nodes["n"].fields == {}

    def test_max_reached_escalates(self):
        lp = LoopPolicy(until="x == 'done'", max=3, on_exhaust="escalate")
        node = IRNode(id="review", kind="agent", loop=lp)
        state = _state_with_node("review", attempt=3)
        rt = _MockRuntime(condition_result=False)
        result = should_loop_back(node, state, {}, host=rt, eval_condition=rt.evalCondition)
        # Should NOT loop back when max reached.
        assert result is False
        # Should have escalated.
        assert len(rt.escalated) == 1
        node_id, reason = rt.escalated[0]
        assert node_id == "review"
        assert "max" in reason.lower() or "3" in reason

    def test_max_reached_stop_does_not_escalate(self):
        lp = LoopPolicy(until="x == 'done'", max=3, on_exhaust="stop")
        node = IRNode(id="review", kind="agent", loop=lp)
        state = _state_with_node("review", attempt=3)
        rt = _MockRuntime(condition_result=False)
        result = should_loop_back(node, state, {}, host=rt, eval_condition=rt.evalCondition)
        assert result is False
        assert rt.escalated == []

    def test_condition_evaluated_with_scope(self):
        lp = LoopPolicy(until="review.fields.verdict == 'pass'", max=5)
        node = IRNode(id="review", kind="agent", loop=lp)
        state = _state_with_node("review", attempt=1)
        scope = {"review.fields.verdict": "pass"}
        rt = _MockRuntime(condition_result=True)
        # Override to use actual eval.
        def _eval(expr: str, s: dict) -> bool:
            rt.condition_calls.append((expr, s))
            from delivery_workflow.lib.conditions import eval_condition
            return eval_condition(expr, s)
        rt.evalCondition = _eval
        result = should_loop_back(node, state, scope, host=rt, eval_condition=rt.evalCondition)
        assert result is False  # condition met → no loop-back
        assert rt.condition_calls != []

    def test_node_missing_from_state_loops_without_incrementing(self):
        """Defensive branch: node not yet in state.nodes (the runner normally
        writes the outcome before the loop check).  Loops back; attempt stays 0
        — the next dispatch increments it to 1 (single owner, R8/D8)."""
        lp = LoopPolicy(until="x == 'done'", max=5)
        node = IRNode(id="fresh", kind="agent", loop=lp)
        state = WorkflowState(
            spec="test", run_id="r1", status="running",
            budget=BudgetState(usd_ceiling=0.0),
        )
        rt = _MockRuntime(condition_result=False)
        result = should_loop_back(node, state, {}, host=rt, eval_condition=rt.evalCondition)
        assert result is True
        assert state.nodes["fresh"].attempt == 0


class TestResetDownstreamNodes:
    def test_reset_clears_done_status(self):
        state = WorkflowState(
            spec="t", run_id="r", status="running",
            budget=BudgetState(usd_ceiling=0.0),
            nodes={
                "n": NodeState(status="done", artifact_paths=["f.md"], fields={"v": "x"}, gate={"decision": "proceed"}),
            },
        )
        reset_downstream_nodes("source", state, downstream_ids=["n"])
        ns = state.nodes["n"]
        assert ns.status == "pending"
        assert ns.artifact_paths == []
        assert ns.fields == {}
        assert ns.gate is None

    def test_reset_only_affects_listed_nodes(self):
        state = WorkflowState(
            spec="t", run_id="r", status="running",
            budget=BudgetState(usd_ceiling=0.0),
            nodes={
                "a": NodeState(status="done", fields={"v": "1"}),
                "b": NodeState(status="done", fields={"v": "2"}),
            },
        )
        reset_downstream_nodes("source", state, downstream_ids=["a"])
        assert state.nodes["a"].status == "pending"
        assert state.nodes["b"].status == "done"  # untouched

    def test_reset_skips_missing_nodes(self):
        """No error when a node id is not in state.nodes."""
        state = WorkflowState(
            spec="t", run_id="r", status="running",
            budget=BudgetState(usd_ceiling=0.0),
        )
        # Should not raise.
        reset_downstream_nodes("source", state, downstream_ids=["nonexistent"])
