"""
E2E test: needs_fix → loop-back via scope enrichment + cyclic edges (I8).

Reproduces bug #3: the review node returns needs_fix, and the runner should
route back to implement via the cyclic edge ``g-review.decision == 'needs_fix'``.

The test uses NullRuntime subclasses (RecordingRuntime) and synthetic IRGraphs
to avoid any real agent execution.  Importlinter compliance is tested separately.

Key assertions:
  - implement runs twice (once initial, once after needs_fix loop-back)
  - review runs twice (first returns needs_fix, second returns pass)
  - g-review gate's decision drives edge routing correctly
  - Final workflow state is 'done'
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from ir import IREdge, IRGraph, IRNode, LoopPolicy
from results import AgentResult, GateResult, TelemetryData
from runner import run
from state_types import BudgetState, NodeState, WorkflowState


# ---------------------------------------------------------------------------
# Recording runtime that returns pre-configured results per (node_id, attempt)
# ---------------------------------------------------------------------------

class _SequencedRuntime:
    """Returns pre-configured AgentResult values per (node_id, attempt).

    On each dispatchAgent call: pops the first matching entry from _sequence.
    Gate calls always return a pre-configured GateResult.
    """

    def __init__(
        self,
        agent_sequence: list[tuple[str, AgentResult]],
        gate_sequence: list[GateResult] | None = None,
    ) -> None:
        # list of (expected_node_id, AgentResult) in dispatch order.
        self._agent_seq = list(agent_sequence)
        self._gate_seq = list(gate_sequence or [])
        self.dispatch_log: list[tuple[str, int]] = []  # (node_id, attempt)
        self.gate_log: list[str] = []  # gate node ids
        self.escalated: list[tuple[str, str]] = []
        self.conditions: list[tuple[str, dict]] = []

    def dispatchAgent(self, agent_ref: str, inputs: dict) -> AgentResult:
        node_id = inputs.get("node_id", agent_ref)
        attempt = inputs.get("attempt", 1)
        self.dispatch_log.append((node_id, attempt))

        # Pop the first matching entry.
        for i, (expected_nid, result) in enumerate(self._agent_seq):
            if expected_nid == node_id:
                self._agent_seq.pop(i)
                return result

        # Default: done with empty fields.
        return AgentResult(
            status="done",
            artifact_paths=[],
            produces="",
            fields={},
            open_questions=[],
            telemetry=TelemetryData(tokens=0, usd=0.0, seconds=0.0),
        )

    def runGate(self, gate: dict, artifact_paths: list) -> GateResult:
        gate_id = gate.get("id", "")
        self.gate_log.append(gate_id)
        if self._gate_seq:
            return self._gate_seq.pop(0)
        return GateResult(decision="proceed", errors=[])

    def evalCondition(self, expr: str, scope: dict) -> bool:
        self.conditions.append((expr, scope))
        from lib.conditions import eval_condition
        return eval_condition(expr, scope)

    def escalate(self, node_id: str, reason: str) -> None:
        self.escalated.append((node_id, reason))

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


def _make_review_loop_graph() -> IRGraph:
    """Build a minimal implement → g-build → review → g-review graph.

    Edges:
      implement → g-build (unconditional)
      g-build   → review  (when g-build.decision == 'proceed')
      review    → g-review (unconditional)
      g-review  → doc     (when review.fields.verdict == 'pass')
      g-review  → implement (when review.fields.verdict == 'needs_fix')
    """
    nodes = [
        IRNode(id="implement", kind="agent", data={"agent": "implementor"}),
        IRNode(id="g-build", kind="gate"),
        IRNode(id="review", kind="agent", data={"agent": "reviewer"}),
        IRNode(id="g-review", kind="gate"),
        IRNode(id="doc", kind="agent", data={"agent": "doc-sync"}),
    ]
    edges = [
        IREdge(source="implement", target="g-build"),
        IREdge(source="g-build", target="review", when="g-build.decision == 'proceed'"),
        IREdge(source="review", target="g-review"),
        IREdge(source="g-review", target="doc", when="review.fields.verdict == 'pass'"),
        IREdge(
            source="g-review",
            target="implement",
            when="review.fields.verdict == 'needs_fix'",
        ),
    ]
    return IRGraph(nodes=nodes, edges=edges)


def _done_agent(fields: dict | None = None) -> AgentResult:
    return AgentResult(
        status="done",
        artifact_paths=[],
        produces="",
        fields=fields or {},
        open_questions=[],
        telemetry=TelemetryData(tokens=0, usd=0.0, seconds=0.0),
    )


class TestNeedsFixLoopBack:
    def test_needs_fix_loops_back_to_implement(self):
        """review returns needs_fix on first pass → implement re-runs → review passes."""
        graph = _make_review_loop_graph()

        rt = _SequencedRuntime(
            agent_sequence=[
                # First implement pass.
                ("implement", _done_agent()),
                # First review pass: needs_fix.
                ("review", _done_agent({"verdict": "needs_fix", "finding_class": "local"})),
                # Second implement pass (loopback).
                ("implement", _done_agent()),
                # Second review pass: pass.
                ("review", _done_agent({"verdict": "pass"})),
                # doc phase.
                ("doc", _done_agent()),
            ],
            # g-build always proceeds; g-review reflects review's verdict.
            gate_sequence=[
                GateResult(decision="proceed", errors=[]),  # g-build first time
                GateResult(decision="needs_fix", errors=[]),  # g-review: needs_fix
                GateResult(decision="proceed", errors=[]),  # g-build second time
                GateResult(decision="proceed", errors=[]),  # g-review: proceed
            ],
        )

        state = run(graph, rt)

        # Final state must be done.
        assert state.status == "done", f"Expected done, got {state.status}"

        # implement must have been dispatched twice.
        implement_calls = [(nid, att) for nid, att in rt.dispatch_log if nid == "implement"]
        assert len(implement_calls) == 2, f"implement dispatched {len(implement_calls)} times"

        # review must have been dispatched twice.
        review_calls = [(nid, att) for nid, att in rt.dispatch_log if nid == "review"]
        assert len(review_calls) == 2, f"review dispatched {len(review_calls)} times"

        # doc must eventually run.
        assert any(nid == "doc" for nid, _ in rt.dispatch_log), "doc never ran"

    def test_review_passes_on_first_pass_no_loop(self):
        """When review passes immediately, implement runs only once."""
        graph = _make_review_loop_graph()

        rt = _SequencedRuntime(
            agent_sequence=[
                ("implement", _done_agent()),
                ("review", _done_agent({"verdict": "pass"})),
                ("doc", _done_agent()),
            ],
            gate_sequence=[
                GateResult(decision="proceed", errors=[]),  # g-build
                GateResult(decision="proceed", errors=[]),  # g-review
            ],
        )

        state = run(graph, rt)
        assert state.status == "done"
        implement_calls = [nid for nid, _ in rt.dispatch_log if nid == "implement"]
        assert len(implement_calls) == 1

    def test_scope_enriched_before_edge_evaluation(self):
        """The runner's scope must include review.fields.verdict when evaluating g-review edges."""
        graph = _make_review_loop_graph()

        rt = _SequencedRuntime(
            agent_sequence=[
                ("implement", _done_agent()),
                ("review", _done_agent({"verdict": "pass"})),
                ("doc", _done_agent()),
            ],
            gate_sequence=[
                GateResult(decision="proceed", errors=[]),  # g-build
                GateResult(decision="proceed", errors=[]),  # g-review
            ],
        )

        run(graph, rt)

        # Verify that a condition referencing review.fields.verdict was evaluated.
        exprs = [expr for expr, _ in rt.conditions]
        assert any("review.fields.verdict" in expr for expr in exprs), (
            f"review.fields.verdict never evaluated in: {exprs}"
        )


class TestImportBoundary:
    """Grep-based import boundary test (R9).

    Ensures no runner/*.py file contains a direct 'from app' or 'import app'
    or 'from backend' / 'import backend' import statement.
    """

    def test_no_app_imports_in_runner_modules(self):
        runner_dir = Path(__file__).parent.parent / "runner"
        forbidden_patterns = ["from app", "import app", "from backend", "import backend"]
        violations: list[str] = []
        for py_file in runner_dir.glob("*.py"):
            text = py_file.read_text(encoding="utf-8")
            for line_num, line in enumerate(text.splitlines(), 1):
                stripped = line.strip()
                for pat in forbidden_patterns:
                    if stripped.startswith(pat):
                        violations.append(f"{py_file.name}:{line_num}: {stripped}")
        assert violations == [], "Import boundary violation:\n" + "\n".join(violations)

    def test_no_app_imports_in_lib_modules(self):
        lib_dir = Path(__file__).parent.parent / "lib"
        if not lib_dir.exists():
            return
        forbidden_patterns = ["from app", "import app", "from backend", "import backend"]
        violations: list[str] = []
        for py_file in lib_dir.rglob("*.py"):
            text = py_file.read_text(encoding="utf-8")
            for line_num, line in enumerate(text.splitlines(), 1):
                stripped = line.strip()
                for pat in forbidden_patterns:
                    if stripped.startswith(pat):
                        violations.append(f"{py_file.relative_to(lib_dir)}:{line_num}: {stripped}")
        assert violations == [], "Import boundary violation in lib/:\n" + "\n".join(violations)
