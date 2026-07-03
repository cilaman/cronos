"""R7 regression — resume as a first-class package API (kills D7 + D10).

Covers ``runner/resume.py`` against synthetic graphs with REAL StateStore
persistence (the conformance harness ``make_state_ops``):

* every event type × every legal starting run status,
* illegal event/state combinations → ``ResumeError`` with NO write,
* the sealed bare-``run()`` re-entry (top-of-run guard in runner/core.py),
* the OD-2 answer chain (``fields.answer`` → typed scope → dispatch inputs),
* OD-1 reject routing + the R8 reset path (target re-armed, human node kept),
* the in-state RetryFailed ceiling (``resume_retries``) round-trip,
* multi-resume idempotency (replaying a consumed event errors, re-deriving a
  stall is stable).

The persistence round-trip law for the new keys (``resume_retries``,
``budget``) lives in ``lib/state/conformance.py`` and runs against BOTH
StateOps implementations — ``StateStoreOps`` here
(tests/regression/test_stateops_conformance.py) and the backend harness
``_StateOps`` (backend/tests/test_harness_stateops_conformance.py).
"""
from __future__ import annotations

from pathlib import Path

import pytest

from delivery_workflow import runner as workflow_runner
from delivery_workflow.ir import IREdge, IRGraph, IRNode
from delivery_workflow.runner import (
    DEFAULT_MAX_RESUME_RETRIES,
    HumanAnswer,
    Nothing,
    RaiseBudget,
    ResumeError,
    RetryFailed,
    resume,
)

from tests.conformance.harness import (
    ScriptedExecutor,
    agent_done,
    agent_failed,
    make_state_ops,
)


# ---------------------------------------------------------------------------
# Synthetic graph helpers
# ---------------------------------------------------------------------------


def _node(nid: str, kind: str = "agent", data: dict | None = None) -> IRNode:
    return IRNode(id=nid, kind=kind, data=data or {})


def _edge(src: str, tgt: str, when: str = "") -> IREdge:
    return IREdge(source=src, target=tgt, when=when)


def _signoff_graph(on_reject: str | None = "a") -> IRGraph:
    """a → signoff(human) → b, with an optional on_reject route back to a."""
    data: dict = {"prompt": "ok?"}
    if on_reject is not None:
        data["on_reject"] = on_reject
    return IRGraph(
        nodes=[_node("a"), _node("signoff", kind="human", data=data), _node("b")],
        edges=[_edge("a", "signoff"), _edge("signoff", "b")],
        metadata={"budget": {"usd_ceiling": 5.0}},
    )


def _timed_wait_graph() -> IRGraph:
    """a → w(wait timed) → b."""
    return IRGraph(
        nodes=[
            _node("a"),
            _node("w", kind="wait", data={"mode": "timed", "max_wait_seconds": 60}),
            _node("b"),
        ],
        edges=[_edge("a", "w"), _edge("w", "b")],
    )


def _linear_graph() -> IRGraph:
    """a → b (agents)."""
    return IRGraph(
        nodes=[_node("a"), _node("b")],
        edges=[_edge("a", "b")],
        metadata={"budget": {"usd_ceiling": 5.0}},
    )


def _run(tmp_path: Path, graph: IRGraph, script: dict | None = None):
    state_ops = make_state_ops(tmp_path / "run", graph)
    executor = ScriptedExecutor(script=script, state_ops=state_ops)
    return executor, state_ops


# ===========================================================================
# HumanAnswer — approve
# ===========================================================================


def test_human_answer_approve_completes_and_stores_answer(tmp_path: Path) -> None:
    graph = _signoff_graph()
    executor, ops = _run(tmp_path, graph)

    parked = workflow_runner.run(graph=graph, executor=executor, state_ops=ops)
    assert parked.status == "blocked"
    assert parked.nodes["signoff"].status == "blocked"

    final = resume(graph, executor, ops, HumanAnswer("signoff", "ship it", "approve"))

    assert final.status == "done"
    node = final.nodes["signoff"]
    assert node.status == "done"
    assert node.fields["answer"] == "ship it"        # OD-2
    assert node.fields["verdict"] == "approve"
    assert node.fields["prompt"] == "ok?"            # prior fields kept
    # The answer reached the downstream node's dispatch inputs via scope.
    b_scope = executor.agent_inputs["b"][0]["scope"]
    assert b_scope["signoff.fields.answer"] == "ship it"
    # Persisted identically.
    assert ops.read().nodes["signoff"].fields["answer"] == "ship it"


def test_human_answer_requires_blocked_run(tmp_path: Path) -> None:
    graph = _signoff_graph()
    executor, ops = _run(tmp_path, graph)
    # Fresh 'running' state — no park.
    with pytest.raises(ResumeError, match="requires a 'blocked' run"):
        resume(graph, executor, ops, HumanAnswer("signoff", "hi", "approve"))
    # Nothing was written.
    assert ops.read().status == "running"
    assert ops.read().nodes == {}


@pytest.mark.parametrize("status", ["failed", "escalated", "stalled", "done"])
def test_human_answer_illegal_on_other_statuses(tmp_path: Path, status: str) -> None:
    graph = _signoff_graph()
    executor, ops = _run(tmp_path, graph)
    ops.write({"status": status})
    with pytest.raises(ResumeError, match="requires a 'blocked' run"):
        resume(graph, executor, ops, HumanAnswer("signoff", "hi", "approve"))


def test_human_answer_validates_node(tmp_path: Path) -> None:
    graph = _signoff_graph()
    executor, ops = _run(tmp_path, graph)
    workflow_runner.run(graph=graph, executor=executor, state_ops=ops)  # park

    with pytest.raises(ResumeError, match="not in the graph"):
        resume(graph, executor, ops, HumanAnswer("nope", "hi", "approve"))
    with pytest.raises(ResumeError, match="only 'human' nodes"):
        resume(graph, executor, ops, HumanAnswer("a", "hi", "approve"))
    with pytest.raises(ResumeError, match="verdict"):
        resume(graph, executor, ops, HumanAnswer("signoff", "hi", "maybe"))  # type: ignore[arg-type]

    # A human node that is NOT the park point (already done) is rejected too.
    ops.write({"nodes": {"signoff": {"status": "done"}}})
    with pytest.raises(ResumeError, match="not 'blocked'"):
        resume(graph, executor, ops, HumanAnswer("signoff", "hi", "approve"))


def test_human_answer_wait_human_node(tmp_path: Path) -> None:
    """wait(mode=human) nodes take HumanAnswer exactly like kind=human."""
    graph = IRGraph(
        nodes=[
            _node("a"),
            _node("w", kind="wait", data={"mode": "human", "prompt": "go?"}),
            _node("b"),
        ],
        edges=[_edge("a", "w"), _edge("w", "b")],
    )
    executor, ops = _run(tmp_path, graph)
    parked = workflow_runner.run(graph=graph, executor=executor, state_ops=ops)
    assert parked.status == "blocked"
    final = resume(graph, executor, ops, HumanAnswer("w", "go", "approve"))
    assert final.status == "done"
    assert final.nodes["w"].fields["answer"] == "go"


# ===========================================================================
# HumanAnswer — reject
# ===========================================================================


def test_reject_with_route_rearms_target_and_answer_reaches_rerun(tmp_path: Path) -> None:
    graph = _signoff_graph(on_reject="a")
    executor, ops = _run(tmp_path, graph, {
        "a": [agent_done(flavor="v1"), agent_done(flavor="v2")],
    })
    workflow_runner.run(graph=graph, executor=executor, state_ops=ops)  # park

    rejected = resume(
        graph, executor, ops, HumanAnswer("signoff", "no — do X instead", "reject")
    )

    # The target re-ran; the run re-parked at the (re-armed) sign-off.
    assert executor.calls["a"] == 2
    assert rejected.status == "blocked"
    assert rejected.nodes["signoff"].status == "blocked"
    # OD-2: the re-run's inputs carried the reject answer via scope.
    rerun_scope = executor.agent_inputs["a"][1]["scope"]
    assert rerun_scope["signoff.fields.answer"] == "no — do X instead"
    assert rerun_scope["signoff.fields.verdict"] == "reject"
    assert rerun_scope["signoff.status"] == "needs_fix"
    # b must NOT have run off the rejected sign-off.
    assert "b" not in executor.calls

    # Approve the re-armed sign-off: the corrected output flows to b.
    final = resume(graph, executor, ops, HumanAnswer("signoff", "yes", "approve"))
    assert final.status == "done"
    assert executor.calls["b"] == 1
    assert executor.agent_inputs["b"][0]["scope"]["a.fields.flavor"] == "v2"


def test_reject_without_route_stalls_never_approves(tmp_path: Path) -> None:
    graph = _signoff_graph(on_reject=None)
    executor, ops = _run(tmp_path, graph)
    workflow_runner.run(graph=graph, executor=executor, state_ops=ops)  # park

    final = resume(graph, executor, ops, HumanAnswer("signoff", "no", "reject"))

    assert final.status == "stalled"
    assert final.stall is not None
    assert final.stall["kind"] == "rejected"
    assert final.stall["nodes"] == ["signoff"]
    node = final.nodes["signoff"]
    assert node.status == "needs_fix", "a rejected sign-off must never read as done"
    assert node.fields["answer"] == "no"
    assert "b" not in executor.calls, "reject must not route the approve edge"
    # Bare run() on the reject-stalled state is SEALED — the rejected node is
    # needs_fix (routable, so the answer stays in scope) and an unsealed
    # re-entry would replay its unconditional out-edges, converting the
    # recorded "no" into a routed "yes" (D10 through the back door).
    again = workflow_runner.run(graph=graph, executor=executor, state_ops=ops)
    assert again.status == "stalled"
    assert "b" not in executor.calls


def test_reject_route_to_undeclared_node_errors(tmp_path: Path) -> None:
    graph = _signoff_graph(on_reject="ghost")
    executor, ops = _run(tmp_path, graph)
    workflow_runner.run(graph=graph, executor=executor, state_ops=ops)  # park
    with pytest.raises(ResumeError, match="on_reject='ghost'"):
        resume(graph, executor, ops, HumanAnswer("signoff", "no", "reject"))


# ===========================================================================
# RetryFailed
# ===========================================================================


def test_retry_failed_rearms_and_succeeds(tmp_path: Path) -> None:
    graph = _linear_graph()
    executor, ops = _run(tmp_path, graph, {
        "a": [agent_failed("boom"), agent_done(flavor="fixed")],
    })
    failed = workflow_runner.run(graph=graph, executor=executor, state_ops=ops)
    assert failed.status == "failed"
    assert failed.nodes["a"].status == "failed"

    final = resume(graph, executor, ops, RetryFailed(["a"]))

    assert final.status == "done"
    assert executor.calls == {"a": 2, "b": 1}
    assert final.nodes["a"].status == "done"
    # attempt preserved across the re-arm: two executions → attempt 2.
    assert final.nodes["a"].attempt == 2
    # The counter is persisted in state (not a sidecar file).
    assert ops.read().resume_retries == {"a": 1}


def test_retry_failed_all_selects_failed_nodes(tmp_path: Path) -> None:
    graph = _linear_graph()
    executor, ops = _run(tmp_path, graph, {
        "a": [agent_failed(), agent_done()],
    })
    workflow_runner.run(graph=graph, executor=executor, state_ops=ops)
    final = resume(graph, executor, ops, RetryFailed("all"))
    assert final.status == "done"
    assert executor.calls["a"] == 2


def test_retry_failed_ceiling_persists_and_stalls(tmp_path: Path) -> None:
    graph = _linear_graph()
    executor, ops = _run(tmp_path, graph, {"a": agent_failed()})
    workflow_runner.run(graph=graph, executor=executor, state_ops=ops)

    for expected in range(1, DEFAULT_MAX_RESUME_RETRIES + 1):
        final = resume(graph, executor, ops, RetryFailed("all"))
        assert final.status == "failed"
        # Round-trip through the REAL StateStore: fresh read equals the count.
        assert ops.read().resume_retries == {"a": expected}

    calls_before = executor.calls["a"]
    final = resume(graph, executor, ops, RetryFailed("all"))
    assert executor.calls["a"] == calls_before, "exhausted retry must not dispatch"
    assert final.status == "stalled"
    assert final.stall["kind"] == "retry_exhausted"
    assert final.stall["nodes"] == ["a"]
    # Re-deriving the stall is stable (multi-resume idempotency).
    final = resume(graph, executor, ops, RetryFailed(["a"]))
    assert final.status == "stalled"
    assert final.stall["kind"] == "retry_exhausted"


def test_retry_failed_custom_ceiling(tmp_path: Path) -> None:
    graph = _linear_graph()
    executor, ops = _run(tmp_path, graph, {"a": agent_failed()})
    workflow_runner.run(graph=graph, executor=executor, state_ops=ops)
    resume(graph, executor, ops, RetryFailed("all"), max_retries=1)
    final = resume(graph, executor, ops, RetryFailed("all"), max_retries=1)
    assert final.status == "stalled"
    assert executor.calls["a"] == 2


def test_retry_failed_validation_errors(tmp_path: Path) -> None:
    graph = _linear_graph()
    executor, ops = _run(tmp_path, graph, {"a": agent_failed()})
    workflow_runner.run(graph=graph, executor=executor, state_ops=ops)

    with pytest.raises(ResumeError, match="not in the graph"):
        resume(graph, executor, ops, RetryFailed(["ghost"]))
    with pytest.raises(ResumeError, match="can be re-armed"):
        resume(graph, executor, ops, RetryFailed(["b"]))  # b never ran
    with pytest.raises(ResumeError, match="at least one node id"):
        resume(graph, executor, ops, RetryFailed([]))

    # Illegal starting statuses.
    for status in ("running", "blocked", "done"):
        ops.write({"status": status})
        with pytest.raises(ResumeError, match="RetryFailed requires"):
            resume(graph, executor, ops, RetryFailed("all"))


def test_retry_failed_after_success_errors(tmp_path: Path) -> None:
    """Replaying RetryFailed after the run completed is a clear error."""
    graph = _linear_graph()
    executor, ops = _run(tmp_path, graph, {"a": [agent_failed(), agent_done()]})
    workflow_runner.run(graph=graph, executor=executor, state_ops=ops)
    final = resume(graph, executor, ops, RetryFailed("all"))
    assert final.status == "done"
    with pytest.raises(ResumeError, match="RetryFailed requires"):
        resume(graph, executor, ops, RetryFailed("all"))


def test_retry_failed_prunes_stale_counters(tmp_path: Path) -> None:
    """Counters for nodes that progressed since are pruned on the next event."""
    graph = _linear_graph()
    executor, ops = _run(tmp_path, graph, {
        "a": [agent_failed(), agent_done()],
        "b": [agent_failed(), agent_done()],
    })
    workflow_runner.run(graph=graph, executor=executor, state_ops=ops)   # a fails
    final = resume(graph, executor, ops, RetryFailed("all"))             # a ok, b fails
    assert final.status == "failed"
    assert ops.read().resume_retries == {"a": 1}
    final = resume(graph, executor, ops, RetryFailed("all"))             # b retried
    assert final.status == "done"
    # a's stale counter was pruned when the b-retry snapshot was written.
    assert ops.read().resume_retries == {"b": 1}


def test_retry_failed_on_escalated_run(tmp_path: Path) -> None:
    """escalated + RetryFailed: the escalated trap is resumable (D7)."""
    graph = _linear_graph()
    executor, ops = _run(tmp_path, graph, {"a": [agent_failed(), agent_done()]})
    workflow_runner.run(graph=graph, executor=executor, state_ops=ops)
    # A policy writer sealed the run as escalated (e.g. global cap).
    ops.write({"status": "escalated"})
    final = resume(graph, executor, ops, RetryFailed(["a"]))
    assert final.status == "done"
    assert executor.calls == {"a": 2, "b": 1}


# ===========================================================================
# RaiseBudget
# ===========================================================================


@pytest.mark.parametrize("start_status", ["escalated", "blocked"])
def test_raise_budget_lifts_ceiling_and_resumes(tmp_path: Path, start_status: str) -> None:
    graph = _linear_graph()  # ceiling 5.0
    executor, ops = _run(tmp_path, graph)
    ops.write({"status": start_status})

    final = resume(graph, executor, ops, RaiseBudget(50.0))

    assert final.status == "done"          # the tiny graph just completes
    persisted = ops.read()
    assert persisted.budget.usd_ceiling == 50.0, (
        "the lifted ceiling must be persisted in state"
    )
    assert executor.calls == {"a": 1, "b": 1}


def test_raise_budget_must_raise(tmp_path: Path) -> None:
    graph = _linear_graph()  # ceiling 5.0
    executor, ops = _run(tmp_path, graph)
    ops.write({"status": "escalated"})
    with pytest.raises(ResumeError, match="does not raise"):
        resume(graph, executor, ops, RaiseBudget(5.0))
    with pytest.raises(ResumeError, match="does not raise"):
        resume(graph, executor, ops, RaiseBudget(1.0))
    assert ops.read().budget.usd_ceiling == 5.0  # nothing written


@pytest.mark.parametrize("status", ["running", "failed", "stalled", "done"])
def test_raise_budget_illegal_statuses(tmp_path: Path, status: str) -> None:
    graph = _linear_graph()
    executor, ops = _run(tmp_path, graph)
    ops.write({"status": status})
    with pytest.raises(ResumeError, match="RaiseBudget requires"):
        resume(graph, executor, ops, RaiseBudget(50.0))


# ===========================================================================
# Nothing
# ===========================================================================


def test_nothing_completes_served_timed_wait(tmp_path: Path) -> None:
    """The D7 kill: wait(timed) escalates (MVP: no real sleep); Nothing() is
    the post-wait re-entry — the wait completes and the run proceeds instead
    of re-escalating forever."""
    graph = _timed_wait_graph()
    executor, ops = _run(tmp_path, graph)

    parked = workflow_runner.run(graph=graph, executor=executor, state_ops=ops)
    assert parked.status == "escalated"
    assert parked.nodes["w"].status == "escalated"

    # Bare run() must halt (sealed) — the pre-R7 livelock shape, now correct.
    sealed = workflow_runner.run(graph=graph, executor=executor, state_ops=ops)
    assert sealed.status == "escalated"
    assert "b" not in executor.calls

    final = resume(graph, executor, ops, Nothing())

    assert final.status == "done"
    assert final.nodes["w"].status == "done"
    assert final.nodes["w"].fields.get("wait_elapsed") is True
    assert executor.calls == {"a": 1, "b": 1}


def test_nothing_plain_escalated_rearms_status_only(tmp_path: Path) -> None:
    """No timed wait involved (e.g. global cap): Nothing() flips status →
    running and re-enters; only the status changes."""
    graph = _linear_graph()
    executor, ops = _run(tmp_path, graph, {"a": [agent_failed(), agent_done()]})
    workflow_runner.run(graph=graph, executor=executor, state_ops=ops)
    ops.write({"status": "escalated"})
    final = resume(graph, executor, ops, Nothing())
    # The failed node is re-dispatched by ordinary seeding (documented:
    # Nothing() does not touch nodes; use RetryFailed for counted retries).
    assert final.status == "done"
    assert ops.read().resume_retries == {}


@pytest.mark.parametrize("status", ["running", "blocked", "failed", "stalled", "done"])
def test_nothing_illegal_statuses(tmp_path: Path, status: str) -> None:
    graph = _linear_graph()
    executor, ops = _run(tmp_path, graph)
    ops.write({"status": status})
    with pytest.raises(ResumeError, match="only legal on an 'escalated' run"):
        resume(graph, executor, ops, Nothing())


# ===========================================================================
# Sealed bare run() + misc
# ===========================================================================


@pytest.mark.parametrize("status", ["blocked", "escalated", "cancelled", "stalled"])
def test_bare_run_halts_on_sealed_statuses(tmp_path: Path, status: str) -> None:
    graph = _linear_graph()
    executor, ops = _run(tmp_path, graph)
    ops.write({"status": status})
    final = workflow_runner.run(graph=graph, executor=executor, state_ops=ops)
    assert final.status == status
    assert dict(executor.calls) == {}, (
        "bare run() must not dispatch on a sealed persisted status — "
        "runner.resume() is the only legal re-entry (R7)"
    )


def test_resume_requires_state_ops(tmp_path: Path) -> None:
    graph = _linear_graph()
    executor = ScriptedExecutor()
    with pytest.raises(ResumeError, match="requires a StateOps"):
        resume(graph, executor, None, Nothing())  # type: ignore[arg-type]


def test_unknown_event_type_errors(tmp_path: Path) -> None:
    graph = _linear_graph()
    executor, ops = _run(tmp_path, graph)
    with pytest.raises(ResumeError, match="unknown resume event"):
        resume(graph, executor, ops, object())  # type: ignore[arg-type]


# ===========================================================================
# on_reject route SHAPE (D10 through the resume path) — the target must be a
# forward-ancestor of the sign-off; ResumeError is raised BEFORE any write.
# ===========================================================================


def _parallel_fixer_graph() -> IRGraph:
    """a → signoff(on_reject=fixer) → b, with a PARALLEL a → fixer branch —
    fixer has no path back into the sign-off (the D10-through-resume shape)."""
    return IRGraph(
        nodes=[
            _node("a"),
            _node("signoff", kind="human", data={"prompt": "ok?", "on_reject": "fixer"}),
            _node("fixer"),
            _node("b"),
        ],
        edges=[
            _edge("a", "signoff"),
            _edge("a", "fixer"),
            _edge("signoff", "b"),
        ],
        metadata={"budget": {"usd_ceiling": 5.0}},
    )


def test_reject_route_not_forward_ancestor_errors_without_write(tmp_path: Path) -> None:
    """A non-dominating on_reject target (parallel branch) must NOT convert
    the rejection into a routed approval: the event is refused, the persisted
    state stays byte-identical (still answerable), and downstream never runs."""
    graph = _parallel_fixer_graph()
    executor, ops = _run(tmp_path, graph)
    parked = workflow_runner.run(graph=graph, executor=executor, state_ops=ops)
    assert parked.status == "blocked"

    with pytest.raises(ResumeError, match="forward-ancestor"):
        resume(graph, executor, ops, HumanAnswer("signoff", "NO — do not ship", "reject"))

    # No write happened: the run is still parked and answerable.
    persisted = ops.read()
    assert persisted.status == "blocked"
    assert persisted.nodes["signoff"].status == "blocked"
    assert workflow_runner.blocked_human_nodes(graph, persisted) == ["signoff"]
    assert "b" not in executor.calls, "the rejected sign-off must never route b"

    # The park is recoverable — an approve still applies.
    final = resume(graph, executor, ops, HumanAnswer("signoff", "ok then", "approve"))
    assert final.status == "done"


def test_reject_route_self_target_errors(tmp_path: Path) -> None:
    graph = _signoff_graph(on_reject="signoff")
    executor, ops = _run(tmp_path, graph)
    workflow_runner.run(graph=graph, executor=executor, state_ops=ops)  # park
    with pytest.raises(ResumeError, match="forward-ancestor"):
        resume(graph, executor, ops, HumanAnswer("signoff", "NO", "reject"))
    assert ops.read().nodes["signoff"].status == "blocked"
    assert "b" not in executor.calls


def test_reject_route_undeclared_node_errors_before_any_write(tmp_path: Path) -> None:
    """The ghost-target guard fires BEFORE the needs_fix write (module
    contract: a rejected event leaves the persisted state byte-identical) —
    the run stays blocked and a retried HumanAnswer still applies."""
    graph = _signoff_graph(on_reject="ghost")
    executor, ops = _run(tmp_path, graph)
    workflow_runner.run(graph=graph, executor=executor, state_ops=ops)  # park

    with pytest.raises(ResumeError, match="on_reject='ghost'"):
        resume(graph, executor, ops, HumanAnswer("signoff", "no", "reject"))

    persisted = ops.read()
    assert persisted.status == "blocked"
    assert persisted.nodes["signoff"].status == "blocked", (
        "the needs_fix patch must not land before the on_reject validation"
    )
    assert workflow_runner.blocked_human_nodes(graph, persisted) == ["signoff"]
    final = resume(graph, executor, ops, HumanAnswer("signoff", "fine", "approve"))
    assert final.status == "done"


def test_rejected_signoff_never_routes_forward_edges_at_seeding(tmp_path: Path) -> None:
    """Resume seeding must not replay a needs_fix HUMAN node's forward
    out-edges (only gates legitimately route from needs_fix): a hand-damaged
    state with a rejected sign-off and status 'running' terminates
    stalled/starved — never a silent 'done' with downstream executed."""
    graph = _signoff_graph(on_reject=None)
    executor, ops = _run(tmp_path, graph)
    ops.write({
        "status": "running",
        "nodes": {
            "a": {"status": "done", "attempt": 1},
            "signoff": {
                "status": "needs_fix", "attempt": 1,
                "fields": {"answer": "NO", "verdict": "reject"},
            },
        },
    })

    final = workflow_runner.run(graph=graph, executor=executor, state_ops=ops)

    assert "b" not in executor.calls, (
        "the rejected sign-off's approve edge fired at resume seeding — "
        "the recorded 'no' became a routed 'yes' (D10)"
    )
    assert final.status == "stalled"
    assert final.stall is not None and final.stall["kind"] == "starved_nodes"


# ===========================================================================
# Loop exhaustion (on_exhaust=escalate) — persisted node 'escalated', run
# 'escalated'; the documented event grammar (Nothing / RetryFailed) applies.
# ===========================================================================


def _loop_graph(max_iter: int = 2) -> IRGraph:
    from delivery_workflow.ir import LoopPolicy

    return IRGraph(
        nodes=[
            IRNode(
                id="a", kind="agent", data={},
                loop=LoopPolicy(
                    until="a.fields.verdict == 'pass'", max=max_iter,
                    on_exhaust="escalate", stall=[],
                ),
            ),
            _node("b"),
        ],
        edges=[_edge("a", "b")],
        metadata={"budget": {"usd_ceiling": 5.0}},
    )


def test_loop_exhaust_persists_escalated_node_and_run(tmp_path: Path) -> None:
    """The exhausted node is persisted 'escalated' (not 'done') and the run
    terminates 'escalated' (not the adapter's 'blocked') — the state the R7
    event grammar assumes exists."""
    graph = _loop_graph(max_iter=2)
    executor, ops = _run(tmp_path, graph, {"a": agent_done(verdict="fail")})

    final = workflow_runner.run(graph=graph, executor=executor, state_ops=ops)

    assert final.status == "escalated"
    assert executor.calls["a"] == 2
    assert "b" not in executor.calls
    persisted = ops.read()
    assert persisted.status == "escalated", (
        "the adapter's blocked write must be overridden by the runner"
    )
    assert persisted.nodes["a"].status == "escalated", (
        "a loop-exhausted node persisted 'done' is a routable terminal — "
        "resume seeding would dispatch b past the failed quality loop"
    )


def test_loop_exhaust_retry_failed_rearms_and_completes(tmp_path: Path) -> None:
    graph = _loop_graph(max_iter=2)
    executor, ops = _run(tmp_path, graph, {
        "a": [agent_done(verdict="fail"), agent_done(verdict="fail"),
              agent_done(verdict="pass")],
    })
    workflow_runner.run(graph=graph, executor=executor, state_ops=ops)

    final = resume(graph, executor, ops, RetryFailed(["a"]))

    assert final.status == "done"
    assert executor.calls == {"a": 3, "b": 1}
    assert ops.read().resume_retries == {"a": 1}


def test_loop_exhaust_nothing_rederives_never_routes_past(tmp_path: Path) -> None:
    """Nothing() on a loop-exhausted run re-derives the escalated halt (one
    seeding re-dispatch, until still unmet) — it never routes b."""
    graph = _loop_graph(max_iter=2)
    executor, ops = _run(tmp_path, graph, {"a": agent_done(verdict="fail")})
    workflow_runner.run(graph=graph, executor=executor, state_ops=ops)

    final = resume(graph, executor, ops, Nothing())

    assert final.status == "escalated"
    assert "b" not in executor.calls


def test_loop_exhaust_raise_budget_does_not_route_past(tmp_path: Path) -> None:
    """RaiseBudget on a loop-exhausted run must not treat the exhausted node
    as a routable 'done': the run re-derives 'escalated', b never runs."""
    graph = _loop_graph(max_iter=2)
    executor, ops = _run(tmp_path, graph, {"a": agent_done(verdict="fail")})
    workflow_runner.run(graph=graph, executor=executor, state_ops=ops)

    final = resume(graph, executor, ops, RaiseBudget(50.0))

    assert final.status == "escalated"
    assert "b" not in executor.calls, (
        "RaiseBudget silently routed past the failed quality loop"
    )


# ===========================================================================
# RaiseBudget input validation
# ===========================================================================


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf"), -1.0, 0.0])
def test_raise_budget_rejects_non_finite_or_non_positive(tmp_path: Path, bad: float) -> None:
    graph = _linear_graph()  # ceiling 5.0
    executor, ops = _run(tmp_path, graph)
    ops.write({"status": "escalated"})
    with pytest.raises(ResumeError):
        resume(graph, executor, ops, RaiseBudget(bad))
    persisted = ops.read()
    assert persisted.budget.usd_ceiling == 5.0
    assert persisted.status == "escalated"
