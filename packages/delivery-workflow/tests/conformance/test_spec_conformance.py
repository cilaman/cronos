"""R4 spec-conformance suite — the remediation progress meter.

Each scenario drives the SHIPPED ``delivery.workflow.yaml`` end-to-end through
the real ``spec_loader`` + ``compiler_a`` + ``runner.run`` against real
``StateStore`` persistence, simulating host park→resume cycles the way
``delivery_driver`` performs them today (see ``harness.host_resume_from_blocked``).

Per scenario we assert:
  (a) the EXACT executed-node set and per-node dispatch counts,
  (b) the terminal ``WorkflowState.status``,
  (c) state round-trip equality (disk == in-memory result).

Expectations today's code cannot meet are marked ``xfail(strict=True)`` with a
reason naming the remediation item that will flip them (R5–R8,
docs/pipeline-review/03-remediation-plan.md).  ``strict=True`` means a fix that
lands unnoticed turns XPASS → hard failure, forcing the marker to be removed —
the suite therefore doubles as the remediation progress meter:

    grep -rn "test_conformance_" packages/delivery-workflow/tests/conformance/

Scenario names are stable and greppable; do not rename them.

Since R5 (condition-aware resume seeding), ``test_conformance_signoff_branch``
is GREEN and live-evaluates the shipped spec's typed-boolean edges
(signoff-scope→frontend/architect on ``analyze.fields.has_ui``) across the
park→resume cycle — it is the composition-level typed-condition guard (an R3
revert fails it, in addition to tests/regression/test_typed_conditions_r3.py).
"""
from __future__ import annotations

from pathlib import Path

import pytest

import runner as workflow_runner

from tests.conformance.harness import (
    ALL_NODES,
    EXEC_NODES,
    GATE_NODES,
    HUMAN_NODES,
    AGENT_NODES,
    ScriptedExecutor,
    agent_done,
    assert_state_roundtrip,
    drive_with_host_resumes,
    host_resume_from_blocked,
    load_shipped_graph,
    make_state_ops,
)


@pytest.fixture()
def graph():
    return load_shipped_graph()


def _make_run(tmp_path: Path, graph, script: dict) -> tuple[ScriptedExecutor, object]:
    """One production-shaped run: real persistence + scripted executor."""
    state_ops = make_state_ops(tmp_path / "run", graph)
    executor = ScriptedExecutor(script=script, state_ops=state_ops)
    return executor, state_ops


# ===========================================================================
# Spec universe guard — pins the node ids the scenario expectations below are
# derived from.  A spec edit fails here first, forcing a conscious update of
# the executed-set constants instead of a silent drift.
# ===========================================================================


def test_conformance_spec_universe(graph) -> None:
    by_kind: dict[str, set[str]] = {}
    for node in graph.nodes:
        by_kind.setdefault(node.kind, set()).add(node.id)

    assert by_kind.get("agent") == set(AGENT_NODES)
    assert by_kind.get("gate") == set(GATE_NODES)
    assert by_kind.get("exec") == set(EXEC_NODES)
    assert by_kind.get("human") == set(HUMAN_NODES)
    assert {n.id for n in graph.nodes} == set(ALL_NODES)

    # The three human sign-offs are what force the park→resume cycles every
    # scenario below exercises.
    assert HUMAN_NODES == {"signoff-scope", "signoff-design", "release"}


# ===========================================================================
# (a) FULL HAPPY PATH — all agents succeed, gates proceed, has_ui=true,
#     three human sign-offs approved via park→resume.
#
# Empirical post-R1–R3 status: GREEN.  The D1 blanket seeding decrement is
# masked when has_ui=true because the frontend branch is *supposed* to fire,
# and the erroneous unconditional decrement of `architect` (via the
# signoff-scope→architect false branch) is absorbed by the frontend→architect
# join.  The executed set, counts, terminal and round-trip are all already
# correct, so this scenario is asserted un-xfailed.
# ===========================================================================


def test_conformance_happy_path(tmp_path: Path, graph) -> None:
    executor, state_ops = _make_run(tmp_path, graph, {
        "analyze": agent_done(has_ui=True),  # JSON bool, per agents/analyst.md
        "review": agent_done(verdict="pass", finding_class="none"),
        "security": agent_done(verdict="pass", finding_class="none"),
    })

    outcome = drive_with_host_resumes(graph, executor, state_ops)

    # (a) exact executed-node set: every node of the shipped spec, once each.
    assert executor.executed_nodes() == set(ALL_NODES)
    assert dict(executor.calls) == {
        nid: 1 for nid in ALL_NODES - HUMAN_NODES
    }, "every agent/gate/exec node must dispatch exactly once on the happy path"
    assert executor.human_park_sequence() == [
        "signoff-scope", "signoff-design", "release",
    ], "human sign-offs must park in pipeline order"
    assert outcome.resumes == [
        ["signoff-scope"], ["signoff-design"], ["release"],
    ], "each host resume must approve exactly the one parked sign-off"

    # (b) terminal status.
    assert outcome.final.status == "done"

    # (c) round-trip law: disk state == in-memory result.
    assert_state_roundtrip(state_ops, outcome.final)


# ===========================================================================
# (b) SIGN-OFF BRANCH (D1) — has_ui=false: after the resume past
#     signoff-scope, `frontend` must NOT execute and `architect` must.
#
# GREEN since R5: resume seeding replays each done node's outgoing `when`
# conditions against the rebuilt typed scope, records fired vs excluded edges
# (the `edges_evaluated` map), and propagates exclusion transitively — the
# excluded frontend branch drops out of the frontend→architect join instead
# of firing unconditionally (D1) or starving architect.
# ===========================================================================


def test_conformance_signoff_branch(tmp_path: Path, graph) -> None:
    executor, state_ops = _make_run(tmp_path, graph, {
        "analyze": agent_done(has_ui=False),  # JSON bool — no UI in this build
        "review": agent_done(verdict="pass", finding_class="none"),
        "security": agent_done(verdict="pass", finding_class="none"),
    })

    outcome = drive_with_host_resumes(graph, executor, state_ops)

    # (a) exact executed-node set: everything except frontend.  The
    # signoff-scope→architect edge (has_ui == false) carries the flow directly
    # to architect; the frontend→architect join input is excluded with it.
    assert "frontend" not in executor.executed_nodes(), (
        "has_ui=false, yet frontend executed after the sign-off resume (D1)"
    )
    assert executor.executed_nodes() == set(ALL_NODES) - {"frontend"}
    assert dict(executor.calls) == {
        nid: 1 for nid in ALL_NODES - HUMAN_NODES - {"frontend"}
    }
    assert outcome.resumes == [
        ["signoff-scope"], ["signoff-design"], ["release"],
    ]

    # (b) terminal status.
    assert outcome.final.status == "done"

    # (c) round-trip law.
    assert_state_roundtrip(state_ops, outcome.final)


# ===========================================================================
# (c) STARVED TAIL (D5) — a mid-pipeline routing field is missing post-resume:
#     `analyze` emits no `has_ui` at all, so BOTH signoff-scope branch
#     conditions are False after the resume.  The run must NOT report `done`
#     with the tail unexecuted; the expected terminal is the future `stalled`
#     (01-state-model.md §5.2) carrying the starved nodes.
#
# Today the run reports success anyway: the D1 blanket seeding fires both
# branches regardless, and even once R5 stops that, the runner has no
# completeness invariant — a drained work-list is unconditionally `done`
# (runner/core.py work-list exit), silently swallowing the unexecuted tail.
# ===========================================================================


@pytest.mark.xfail(
    strict=True,
    reason="R6 completeness invariant + stalled outcome (D5; needs R5 first): "
    "work-list drain reports done even when the pipeline tail was starved by "
    "unmet edge conditions — 'stalled' does not exist yet",
)
def test_conformance_starved_tail(tmp_path: Path, graph) -> None:
    executor, state_ops = _make_run(tmp_path, graph, {
        "analyze": agent_done(),  # contract violation: has_ui missing entirely
        "review": agent_done(verdict="pass", finding_class="none"),
        "security": agent_done(verdict="pass", finding_class="none"),
    })

    outcome = drive_with_host_resumes(graph, executor, state_ops)

    # (a) exact executed-node set: the pre-park prefix only.  frontend is
    # legitimately excluded (its one in-edge evaluated false), but architect
    # has an in-edge that was never evaluated (frontend→architect), so the
    # tail from architect onward is starved, not excluded.
    assert executor.executed_nodes() == {
        "scout", "g-scout", "analyze", "g-analysis", "signoff-scope",
    }, "the tail past signoff-scope must not execute when has_ui is missing"

    # (b) terminal status: the future R6 outcome — not a false `done`.
    assert outcome.final.status == "stalled", (
        f"run reported {outcome.final.status!r} with the pipeline tail "
        "unexecuted — silent partial success (D5)"
    )

    # (c) round-trip law.
    assert_state_roundtrip(state_ops, outcome.final)


# ===========================================================================
# (d) TIMED-WAIT / ESCALATED (D7) — a run that persisted status="escalated"
#     must be resumable.
#
# Writers of persisted `escalated` today: wait(timed) dispatch
# (runner/dispatch.py), the global iteration cap and loop-exhaust paths
# (runner/core.py).  The shipped spec cannot reach a *persisted* escalated
# cheaply (the adapter's escalate parks runs as `blocked`), so this scenario
# parks the run at signoff-scope and then applies the status="escalated"
# patch those writers produce.  The runner's cancel-race guard then halts on
# `escalated` before dispatching anything, and today's only host resume
# mechanism (_resume_from_blocked) does not match it: answer → instant halt →
# re-park, forever (repro D9).
#
# When R7 lands, rewrite the resume step to the package API
# (DeliveryRun.resume(RetryFailed|RaiseBudget)) and drop the host simulation.
# ===========================================================================


@pytest.mark.xfail(
    strict=True,
    reason="R7 resume API (D7): persisted 'escalated' is a terminal trap — the "
    "runner guard halts on it and no host resume path matches it",
)
def test_conformance_escalated_resume(tmp_path: Path, graph) -> None:
    executor, state_ops = _make_run(tmp_path, graph, {
        "analyze": agent_done(has_ui=True),
    })

    # Reach the first human park through the real pipeline prefix.
    first = workflow_runner.run(graph=graph, executor=executor, state_ops=state_ops)
    assert first.status == "blocked", "precondition: run parks at signoff-scope"

    # The policy-limit writers persist status="escalated" (wait(timed) /
    # global cap / loop exhaust).
    state_ops.write({"status": "escalated"})

    # One full host resume cycle, exactly as re-entry works today.
    calls_before = sum(executor.calls.values())
    host_resume_from_blocked(state_ops, graph)  # no-op: status != "blocked"
    final = workflow_runner.run(graph=graph, executor=executor, state_ops=state_ops)

    # (a)+(b) the resume must make progress: either new work was dispatched or
    # the run left the escalated state.  Today neither happens.
    progressed = sum(executor.calls.values()) > calls_before
    assert progressed or final.status != "escalated", (
        "persisted 'escalated' run made no progress on resume — every re-entry "
        "halts instantly and the goal re-parks WAITING forever (D7)"
    )

    # (c) round-trip law.
    assert_state_roundtrip(state_ops, final)


# ===========================================================================
# (e) FIX-LOOP — review keeps finding problems until its loop budget is spent.
#
# On the shipped spec the review fix-loop is the `review` node's own
# LoopPolicy (until: "review.fields.verdict == 'pass'", max: 5): a non-pass
# verdict re-enqueues review itself.  (The g-review needs_fix edges to
# implement/architect can only fire once review exits its loop, which requires
# verdict == 'pass' — so they are unreachable on the shipped spec; noted in
# the review docs, not this suite's defect to fix.)
#
# Budget law (R8 acceptance): loop.max=N must yield exactly N executions, with
# the attempt counter owned by a single writer (attempt == executions).
# GREEN since R8: dispatch is the sole attempt owner (the loop-back second
# increment — D8, which made max=5 yield only 3 executions with the counter
# overshooting to 5 — is deleted from runner/loop.py).
# ===========================================================================


def test_conformance_fix_loop(tmp_path: Path, graph) -> None:
    executor, state_ops = _make_run(tmp_path, graph, {
        "analyze": agent_done(has_ui=True),
        # review never passes — the loop budget is the only bound.
        "review": agent_done(verdict="needs_fix", finding_class="local"),
        "security": agent_done(verdict="pass", finding_class="none"),
    })

    outcome = drive_with_host_resumes(graph, executor, state_ops)

    # (a) loop budget honored: loop.max=5 ⇒ exactly 5 review executions, and
    # the attempt counter equals the execution count (single owner).
    review_loop = next(n.loop for n in graph.nodes if n.id == "review")
    assert review_loop is not None and review_loop.max == 5, (
        "spec drift: review loop.max changed — update this scenario"
    )
    assert executor.calls["review"] == review_loop.max, (
        f"loop.max={review_loop.max} must yield exactly {review_loop.max} "
        f"review executions, got {executor.calls['review']} (D8 double-increment)"
    )
    assert outcome.final.nodes["review"].attempt == executor.calls["review"], (
        "attempt counter must equal the number of executions (single owner)"
    )
    # The tail past review must NOT run — the loop exhausted without a pass —
    # and the prefix must have dispatched exactly once each (a regression that
    # double-dispatches prefix nodes only in exhaust runs must fail here).
    prefix = {
        "scout", "g-scout", "analyze", "g-analysis", "frontend", "architect",
        "g-design", "testarch", "implement", "g-build",
    }
    assert dict(executor.calls) == {**{nid: 1 for nid in prefix}, "review": 5}
    assert executor.executed_nodes() == (
        prefix | {"signoff-scope", "signoff-design", "review"}
    )

    # (c) round-trip law.
    assert_state_roundtrip(state_ops, outcome.final)


# ===========================================================================
# (e') FIX-LOOP, PASSING — review fails twice then passes on attempt 3
#      (within max=5); the pipeline completes end-to-end.
#
# GREEN since R1–R3 (execution count was already correct when the loop exits
# early via its until-condition); the attempt bookkeeping is now also correct
# post-R8 (single owner, asserted in test_conformance_fix_loop above).
# ===========================================================================


def test_conformance_fix_loop_pass(tmp_path: Path, graph) -> None:
    executor, state_ops = _make_run(tmp_path, graph, {
        "analyze": agent_done(has_ui=True),
        "review": [
            agent_done(verdict="needs_fix", finding_class="local"),
            agent_done(verdict="needs_fix", finding_class="local"),
            agent_done(verdict="pass", finding_class="none"),
        ],
        "security": agent_done(verdict="pass", finding_class="none"),
    })

    outcome = drive_with_host_resumes(graph, executor, state_ops)

    # (a) exact executed-node set and counts: full pipeline, review 3×.
    assert executor.executed_nodes() == set(ALL_NODES)
    expected_counts = {nid: 1 for nid in ALL_NODES - HUMAN_NODES}
    expected_counts["review"] = 3
    assert dict(executor.calls) == expected_counts
    assert outcome.resumes == [
        ["signoff-scope"], ["signoff-design"], ["release"],
    ]

    # (b) terminal status.
    assert outcome.final.status == "done"

    # (c) round-trip law.
    assert_state_roundtrip(state_ops, outcome.final)
