"""StateOps conformance suite — the persistence round-trip law (R2, kills D2).

The law (01-state-model.md §5.4): **everything the runner writes through
``StateOps.write()`` must read back identically through ``StateOps.read()``**.
Concretely, for node patches that means ``status``, ``attempt``,
``artifact_paths``, ``gate`` and ``fields``; for top-level patches it means
``status``. Values already persisted by other writers (e.g. ``telemetry``
written by ``TelemetrySink``) must survive unrelated writes untouched.

Every ``StateOps`` implementation — the package's ``CronosStateOps``, the
backend harness ``_StateOps``, any future embedder — must pass every check in
``STATEOPS_CONFORMANCE_CHECKS``. Host test suites parametrize over the list:

    from lib.state.conformance import STATEOPS_CONFORMANCE_CHECKS

    @pytest.mark.parametrize(
        "check", STATEOPS_CONFORMANCE_CHECKS, ids=lambda c: c.__name__
    )
    def test_stateops_conformance(check):
        check(make_ops)

where ``make_ops(initial: WorkflowState) -> StateOps`` returns a fresh,
isolated implementation seeded with ``initial`` (each invocation must yield an
independent instance/storage).

Scope notes
-----------
* ``fields`` patches are asserted as *snapshot-superset* writes (each patch
  carries every key it wants present, possibly overwriting existing values) —
  this is exactly what the runner emits (``runner/core.py`` writes the full
  ``outcome.fields`` with every node outcome). Whether an implementation
  merges or replaces keys *dropped* by a later patch is implementation-defined
  today and deliberately not asserted here.
* ``telemetry`` is not written by the runner through node patches (it flows
  through ``TelemetryOps``/``TelemetrySink``), so the suite asserts
  *preservation* — telemetry present in state must survive StateOps writes —
  rather than patch-write support.

This module is part of the portable core: it must never import ``app.*`` or
``backend.*`` (see ``.importlinter``).
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable

from state_types import BudgetState, NodeState, WorkflowState

if TYPE_CHECKING:  # pragma: no cover — typing only
    from interface import StateOps

    MakeOps = Callable[[WorkflowState], StateOps]
else:
    MakeOps = Callable[[WorkflowState], Any]


def _fresh_state(**nodes: NodeState) -> WorkflowState:
    return WorkflowState(
        spec="conformance",
        run_id="run-conformance",
        status="running",
        budget=BudgetState(usd_ceiling=0.0),
        nodes=dict(nodes),
    )


_GATE = {"decision": "proceed", "errors": []}
_FIELDS = {"has_ui": "no", "verdict": "pass"}
_TELEMETRY = {"tokens": 1200.0, "usd": 0.12, "seconds": 34.0}


# ---------------------------------------------------------------------------
# Checks — each takes a make_ops factory and raises AssertionError on failure.
# ---------------------------------------------------------------------------


def check_top_level_status_roundtrip(make_ops: MakeOps) -> None:
    """Every run status the runner writes reads back identically."""
    ops = make_ops(_fresh_state())
    for status in ("blocked", "failed", "escalated", "running", "done"):
        ops.write({"status": status})
        got = ops.read().status
        assert got == status, (
            f"top-level status round-trip broken: wrote {status!r}, read {got!r}"
        )


def check_new_node_full_patch_roundtrip(make_ops: MakeOps) -> None:
    """A full runner node patch for a previously-unknown node reads back
    identically — this is the exact write shape of ``runner/core.py`` after a
    dispatch, and the D2 defect site (``fields`` used to be dropped)."""
    ops = make_ops(_fresh_state())
    ops.write({"nodes": {"analyze": {
        "status": "done",
        "attempt": 1,
        "artifact_paths": ["docs/analysis.md"],
        "gate": _GATE,
        "fields": dict(_FIELDS),
    }}})
    node = ops.read().nodes["analyze"]
    assert node.status == "done", f"status: wrote 'done', read {node.status!r}"
    assert node.attempt == 1, f"attempt: wrote 1, read {node.attempt!r}"
    assert node.artifact_paths == ["docs/analysis.md"], (
        f"artifact_paths: read back {node.artifact_paths!r}"
    )
    assert node.gate == _GATE, f"gate: read back {node.gate!r}"
    assert node.fields == _FIELDS, (
        f"fields: wrote {_FIELDS!r}, read back {node.fields!r} — "
        "field-based routing (has_ui/verdict/finding_class) is dead (D2)"
    )


def check_existing_node_update_roundtrip(make_ops: MakeOps) -> None:
    """A superset update of an existing node reads back identically —
    overwritten keys take the new value, added keys appear."""
    initial = _fresh_state(
        review=NodeState(status="running", attempt=1, fields={"verdict": "fail"}),
    )
    ops = make_ops(initial)
    new_fields = {"verdict": "pass", "finding_class": "none"}
    ops.write({"nodes": {"review": {
        "status": "done",
        "attempt": 2,
        "artifact_paths": ["docs/review.md"],
        "gate": {"decision": "needs_fix", "errors": ["e1"]},
        "fields": dict(new_fields),
    }}})
    node = ops.read().nodes["review"]
    assert node.status == "done", f"status: read back {node.status!r}"
    assert node.attempt == 2, f"attempt: read back {node.attempt!r}"
    assert node.artifact_paths == ["docs/review.md"], (
        f"artifact_paths: read back {node.artifact_paths!r}"
    )
    assert node.gate == {"decision": "needs_fix", "errors": ["e1"]}, (
        f"gate: read back {node.gate!r}"
    )
    assert node.fields == new_fields, (
        f"fields: wrote {new_fields!r}, read back {node.fields!r}"
    )


def check_partial_patch_preserves_unpatched_keys(make_ops: MakeOps) -> None:
    """A status-only patch must not destroy the node's other persisted values
    (attempt, artifact_paths, fields, telemetry)."""
    initial = _fresh_state(
        analyze=NodeState(
            status="running",
            attempt=1,
            artifact_paths=["docs/analysis.md"],
            fields=dict(_FIELDS),
            telemetry=dict(_TELEMETRY),
        ),
    )
    ops = make_ops(initial)
    ops.write({"nodes": {"analyze": {"status": "done"}}})
    node = ops.read().nodes["analyze"]
    assert node.status == "done"
    assert node.attempt == 1, f"attempt clobbered: {node.attempt!r}"
    assert node.artifact_paths == ["docs/analysis.md"], (
        f"artifact_paths clobbered: {node.artifact_paths!r}"
    )
    assert node.fields == _FIELDS, f"fields clobbered: {node.fields!r}"
    assert node.telemetry == _TELEMETRY, (
        f"telemetry clobbered: {node.telemetry!r}"
    )


def check_unrelated_write_preserves_other_nodes(make_ops: MakeOps) -> None:
    """Writing node B (and the run status) must leave node A byte-identical."""
    initial = _fresh_state(
        analyze=NodeState(
            status="done",
            attempt=1,
            artifact_paths=["docs/analysis.md"],
            gate=_GATE,
            fields=dict(_FIELDS),
            telemetry=dict(_TELEMETRY),
        ),
    )
    ops = make_ops(initial)
    ops.write({
        "status": "running",
        "nodes": {"design": {
            "status": "done",
            "attempt": 1,
            "artifact_paths": [],
            "gate": None,
            "fields": {},
        }},
    })
    node = ops.read().nodes["analyze"]
    assert node.status == "done"
    assert node.attempt == 1
    assert node.artifact_paths == ["docs/analysis.md"]
    assert node.gate == _GATE, f"gate clobbered: {node.gate!r}"
    assert node.fields == _FIELDS, f"fields clobbered: {node.fields!r}"
    assert node.telemetry == _TELEMETRY, f"telemetry clobbered: {node.telemetry!r}"


def check_fields_survive_park_resume_cycle(make_ops: MakeOps) -> None:
    """The D2 production scenario: an agent node completes with routing fields,
    the run parks on a human node (blocked), the host approves the sign-off and
    re-arms the run — the routing fields written before the park must still be
    readable for resume-time condition evaluation."""
    ops = make_ops(_fresh_state())
    # Agent node done, carrying routing fields (runner write shape).
    ops.write({"nodes": {"analyze": {
        "status": "done", "attempt": 1, "artifact_paths": [],
        "gate": None, "fields": {"has_ui": "no"},
    }}})
    # Human node parks the run.
    ops.write({"nodes": {"signoff": {"status": "blocked"}}})
    ops.write({"status": "blocked"})
    # Host resume: sign-off approved, run re-armed.
    ops.write({"status": "running", "nodes": {"signoff": {"status": "done"}}})
    state = ops.read()
    assert state.status == "running"
    assert state.nodes["signoff"].status == "done"
    assert state.nodes["analyze"].fields == {"has_ui": "no"}, (
        "routing fields lost across park/resume: "
        f"{state.nodes['analyze'].fields!r} — conditional edges cannot be "
        "evaluated on resume (D2)"
    )


STATEOPS_CONFORMANCE_CHECKS: tuple[Callable[[MakeOps], None], ...] = (
    check_top_level_status_roundtrip,
    check_new_node_full_patch_roundtrip,
    check_existing_node_update_roundtrip,
    check_partial_patch_preserves_unpatched_keys,
    check_unrelated_write_preserves_other_nodes,
    check_fields_survive_park_resume_cycle,
)


def run_stateops_conformance(make_ops: MakeOps) -> None:
    """Run every conformance check against *make_ops*; raise on first failure.

    Convenience entry point for hosts that prefer a single assertion over
    pytest parametrization.
    """
    for check in STATEOPS_CONFORMANCE_CHECKS:
        check(make_ops)
