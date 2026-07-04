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

from pathlib import Path


from delivery_workflow.ir import IREdge, IRGraph, IRNode, LoopPolicy
from delivery_workflow.results import AgentResult, GateResult, TelemetryData
from delivery_workflow.runner import run


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
        self.scope_log: list[tuple[str, int, dict]] = []  # (node_id, attempt, scope)
        self.gate_log: list[str] = []  # gate node ids
        self.escalated: list[tuple[str, str]] = []
        self.conditions: list[tuple[str, dict]] = []

    def dispatchAgent(self, agent_ref: str, inputs: dict) -> AgentResult:
        node_id = inputs.get("node_id", agent_ref)
        attempt = inputs.get("attempt", 1)
        self.dispatch_log.append((node_id, attempt))
        self.scope_log.append((node_id, attempt, dict(inputs.get("scope") or {})))

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
        from delivery_workflow.lib.conditions import eval_condition
        return eval_condition(expr, scope)

    # HostPort (R10b): typed events replace the escalate() hook.
    def on_event(self, event) -> None:
        from delivery_workflow.events import RunBlocked, RunEscalated

        if isinstance(event, RunBlocked):
            self.escalated.append((event.node_id, event.question))
        elif isinstance(event, RunEscalated):
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

        state = run(graph, rt, host=rt, eval_condition=rt.evalCondition)

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

        state = run(graph, rt, host=rt, eval_condition=rt.evalCondition)
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

        run(graph, rt, host=rt, eval_condition=rt.evalCondition)

        # Verify that a condition referencing review.fields.verdict was evaluated.
        exprs = [expr for expr, _ in rt.conditions]
        assert any("review.fields.verdict" in expr for expr in exprs), (
            f"review.fields.verdict never evaluated in: {exprs}"
        )


def _make_gate_fix_loop_graph(max_iter: int = 3) -> IRGraph:
    """producer(agent) → gate(loop, max=max_iter) → sink(agent).

    Edges:
      producer → gate  (unconditional)
      gate     → sink  (when gate.decision == 'proceed')
      gate     → producer (when gate.decision != 'proceed')  # bounded fix-loop

    Mirrors the six "simple" delivery gates (g-scout etc.): a gate carrying a
    loop block whose non-proceed decision routes back to its producing agent,
    bounded by loop.max via the runner's gate-loop handling.
    """
    nodes = [
        IRNode(id="producer", kind="agent", data={"agent": "scout"}),
        IRNode(
            id="gate",
            kind="gate",
            loop=LoopPolicy(until="gate.decision == 'proceed'", max=max_iter),
        ),
        IRNode(id="sink", kind="agent", data={"agent": "analyst"}),
    ]
    edges = [
        IREdge(source="producer", target="gate"),
        IREdge(source="gate", target="sink", when="gate.decision == 'proceed'"),
        IREdge(source="gate", target="producer", when="gate.decision != 'proceed'"),
    ]
    return IRGraph(nodes=nodes, edges=edges)


class TestGateFixLoop:
    """§P4: a gate's loop bounds a fix back-edge to its producer (does NOT self-retry)."""

    def test_non_proceed_routes_to_producer_then_proceeds(self):
        graph = _make_gate_fix_loop_graph(max_iter=3)
        rt = _SequencedRuntime(
            agent_sequence=[],  # all agents default to done
            gate_sequence=[
                GateResult(decision="needs_fix", errors=["fix me"]),  # attempt 1
                GateResult(decision="proceed", errors=[]),            # attempt 2
            ],
        )
        state = run(graph, rt, host=rt, eval_condition=rt.evalCondition)

        assert state.status == "done"
        producer_calls = [nid for nid, _ in rt.dispatch_log if nid == "producer"]
        assert len(producer_calls) == 2, f"producer dispatched {len(producer_calls)}×"
        assert any(nid == "sink" for nid, _ in rt.dispatch_log), "sink never ran"
        # The gate must NOT escalate — the fix edge does the work.
        assert rt.escalated == []

    def test_fail_decision_also_routes_to_producer(self):
        """The '!= proceed' guard catches a hard 'fail' (the schema-gate case),
        not just 'needs_fix'."""
        graph = _make_gate_fix_loop_graph(max_iter=3)
        rt = _SequencedRuntime(
            agent_sequence=[],
            gate_sequence=[
                GateResult(decision="fail", errors=["schema violation"]),  # attempt 1
                GateResult(decision="proceed", errors=[]),                 # attempt 2
            ],
        )
        state = run(graph, rt, host=rt, eval_condition=rt.evalCondition)

        assert state.status == "done"
        producer_calls = [nid for nid, _ in rt.dispatch_log if nid == "producer"]
        assert len(producer_calls) == 2
        assert any(nid == "sink" for nid, _ in rt.dispatch_log)
        assert rt.escalated == []

    def test_fix_loop_carries_gate_errors_into_producer_rerun(self):
        """No blind retries: a gate's errors reach the looped-back producer's
        re-dispatch scope as ``{gate}.fields.errors`` so it sees WHY it failed.

        Reproduces the live g-build stall: the producer's SECOND (fix-loop)
        dispatch previously saw only the gate decision — never the actionable
        error string — and reproduced the same rejected artifact."""
        graph = _make_gate_fix_loop_graph(max_iter=3)
        rt = _SequencedRuntime(
            agent_sequence=[],
            gate_sequence=[
                GateResult(
                    decision="fail",
                    errors=[
                        "impl-report has no validation_command",
                        "cannot re-execute",
                    ],
                ),
                GateResult(decision="proceed", errors=[]),
            ],
        )
        state = run(graph, rt, host=rt, eval_condition=rt.evalCondition)

        assert state.status == "done"
        producer_scopes = [s for nid, _att, s in rt.scope_log if nid == "producer"]
        assert len(producer_scopes) == 2, "producer must re-run once via the fix edge"
        # First pass: the gate has not run yet — nothing in scope from it.
        assert "gate.fields.errors" not in producer_scopes[0]
        # Fix-loop re-run: the joined, truncated error text is in scope.
        assert producer_scopes[1].get("gate.fields.errors") == (
            "impl-report has no validation_command; cannot re-execute"
        )

    def test_fix_loop_no_errors_adds_no_scope_key(self):
        """A non-proceed gate with an empty errors list adds NO errors key —
        the producer re-run scope never carries an empty ``gate.fields.errors``
        (the decision alone still routes the fix edge)."""
        graph = _make_gate_fix_loop_graph(max_iter=3)
        rt = _SequencedRuntime(
            agent_sequence=[],
            gate_sequence=[
                GateResult(decision="needs_fix", errors=[]),
                GateResult(decision="proceed", errors=[]),
            ],
        )
        state = run(graph, rt, host=rt, eval_condition=rt.evalCondition)

        assert state.status == "done"
        producer_scopes = [s for nid, _att, s in rt.scope_log if nid == "producer"]
        assert len(producer_scopes) == 2
        assert producer_scopes[1].get("gate.decision") == "needs_fix"
        assert "gate.fields.errors" not in producer_scopes[1]

    def test_bounded_exhaustion_stalls_with_gate_detail(self):
        """A gate that never proceeds is capped at loop.max evaluations, then the
        run terminates 'stalled' with kind=gate_exhausted at RUN level (R6/OD-3
        — reversing the pre-R6 engineered dead-end-to-'done' the driver had to
        unpick from node internals) — and the gate does NOT escalate."""
        graph = _make_gate_fix_loop_graph(max_iter=3)
        rt = _SequencedRuntime(
            agent_sequence=[],
            gate_sequence=[GateResult(decision="needs_fix", errors=["still bad"]) for _ in range(10)],
        )
        state = run(graph, rt, host=rt, eval_condition=rt.evalCondition)

        assert state.status == "stalled"
        # Run-level machine-readable detail — hosts never dig through nodes.
        assert state.stall is not None
        assert state.stall["kind"] == "gate_exhausted"
        assert state.stall["nodes"] == ["gate"]
        assert "needs_fix" in state.stall["reason"]
        assert "still bad" in state.stall["reason"]
        gate_evals = [g for g in rt.gate_log if g == "gate"]
        assert len(gate_evals) == 3, f"gate evaluated {len(gate_evals)}× (expected max=3)"
        producer_calls = [nid for nid, _ in rt.dispatch_log if nid == "producer"]
        assert len(producer_calls) == 3, f"producer dispatched {len(producer_calls)}×"
        # sink is never reached (gate never proceeds).
        assert not any(nid == "sink" for nid, _ in rt.dispatch_log)
        # The gate's non-proceed decision is still persisted as gate detail.
        assert state.nodes["gate"].gate["decision"] == "needs_fix"
        # No generic escalate — the actionable park message renders from state.stall.
        assert rt.escalated == []


class TestImportBoundary:
    """Grep-based import boundary test (R9).

    Ensures no runner/*.py file contains a direct 'from app' or 'import app'
    or 'from backend' / 'import backend' import statement.
    """

    def test_no_app_imports_in_runner_modules(self):
        runner_dir = (
            Path(__file__).parent.parent / "src" / "delivery_workflow" / "runner"
        )
        assert runner_dir.is_dir(), f"runner dir moved? {runner_dir}"
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
        lib_dir = Path(__file__).parent.parent / "src" / "delivery_workflow" / "lib"
        assert lib_dir.is_dir(), f"lib dir moved? {lib_dir}"
        forbidden_patterns = ["from app", "import app", "from backend", "import backend"]
        # Only *module-level* (unindented) imports break import-time portability
        # — those are what load app.* when ``import delivery_workflow.lib.x``
        # runs.  (The last function-local residual — lib/verify.py's CLI-only
        # normalize import — was deleted in R11.)  Match the raw line, not the
        # stripped one; test_import_boundary.py covers indented imports via AST.
        violations: list[str] = []
        for py_file in lib_dir.rglob("*.py"):
            text = py_file.read_text(encoding="utf-8")
            for line_num, line in enumerate(text.splitlines(), 1):
                for pat in forbidden_patterns:
                    if line.startswith(pat):
                        violations.append(f"{py_file.relative_to(lib_dir)}:{line_num}: {line.strip()}")
        assert violations == [], "Import boundary violation in lib/:\n" + "\n".join(violations)
