"""R2 regression — persistence round-trip law (kills D2).

D2 (00-assessment.md §2): ``NodeState.fields`` were never persisted —
``_serialize``/``_deserialize`` omitted them and ``CronosStateOps.write``
dropped them — so all field-based routing (``has_ui``, ``verdict``,
``finding_class``) and ``loop.until`` conditions referencing pre-resume nodes
were dead after any resume.

This file runs the package-provided StateOps conformance suite
(``lib/state/conformance.py``) against the StateStore-backed
``CronosStateOps`` — the implementation that failed the law at HEAD — plus
direct ``StateStore`` round-trip regressions for the ``_serialize`` /
``_deserialize`` half of the defect.

The backend suite runs the same conformance checks against the harness
``_StateOps`` (backend/tests/test_harness_stateops_conformance.py), so the two
implementations of the same Protocol can never silently diverge again.
"""
from __future__ import annotations

import itertools
from pathlib import Path

import pytest

from adapters.cronos.adapter import CronosStateOps
from lib.state.conformance import (
    STATEOPS_CONFORMANCE_CHECKS,
    run_stateops_conformance,
)
from lib.state.events import EventLog
from lib.state.store import StateStore
from runner.scope import build_scope
from state_types import BudgetState, NodeState, WorkflowState


# ---------------------------------------------------------------------------
# Factory: fresh StateStore-backed CronosStateOps per invocation.
# ---------------------------------------------------------------------------


@pytest.fixture()
def make_cronos_ops(tmp_path: Path):
    counter = itertools.count()

    def _make(initial: WorkflowState) -> CronosStateOps:
        run_dir = tmp_path / f"run-{next(counter)}"
        run_dir.mkdir()
        store = StateStore(run_dir)
        store.write(initial)
        return CronosStateOps(store, EventLog(run_dir))

    return _make


# ---------------------------------------------------------------------------
# Conformance suite against CronosStateOps (the D2 offender).
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "check", STATEOPS_CONFORMANCE_CHECKS, ids=lambda c: c.__name__
)
def test_cronos_stateops_conformance(check, make_cronos_ops) -> None:
    check(make_cronos_ops)


def test_run_stateops_conformance_entry_point(make_cronos_ops) -> None:
    """The single-call convenience entry point runs green end-to-end."""
    run_stateops_conformance(make_cronos_ops)


# ---------------------------------------------------------------------------
# Direct StateStore round-trip regressions (_serialize/_deserialize half).
# ---------------------------------------------------------------------------


def _state_with(nodes: dict[str, NodeState]) -> WorkflowState:
    return WorkflowState(
        spec="delivery/v2",
        run_id="run-d2",
        status="running",
        budget=BudgetState(usd_ceiling=0.0),
        nodes=nodes,
    )


def test_statestore_roundtrips_fields(tmp_path: Path) -> None:
    """D2 regression: fields written to state.json read back identically."""
    fields = {"has_ui": "no", "verdict": "pass", "count": 3}
    StateStore(tmp_path).write(
        _state_with({"analyze": NodeState(status="done", fields=dict(fields))})
    )
    recovered = StateStore(tmp_path).read()
    assert recovered.nodes["analyze"].fields == fields


def test_statestore_roundtrips_fields_and_telemetry_together(
    tmp_path: Path,
) -> None:
    node = NodeState(
        status="done",
        attempt=2,
        gate={"decision": "proceed", "errors": []},
        artifact_paths=["a.md"],
        telemetry={"tokens": 10.0, "usd": 0.01, "seconds": 1.0},
        fields={"finding_class": "none"},
    )
    StateStore(tmp_path).write(_state_with({"review": node}))
    recovered = StateStore(tmp_path).read().nodes["review"]
    assert recovered.fields == {"finding_class": "none"}
    assert recovered.telemetry == {"tokens": 10.0, "usd": 0.01, "seconds": 1.0}
    assert recovered.gate == {"decision": "proceed", "errors": []}
    assert recovered.artifact_paths == ["a.md"]
    assert recovered.attempt == 2


def test_statestore_empty_fields_read_back_empty(tmp_path: Path) -> None:
    """No-fields nodes stay `{}` on read (and legacy state.json without a
    `fields` key deserializes cleanly)."""
    StateStore(tmp_path).write(_state_with({"scout": NodeState(status="done")}))
    recovered = StateStore(tmp_path).read()
    assert recovered.nodes["scout"].fields == {}


def test_scope_rebuilt_from_persisted_state_contains_fields(
    tmp_path: Path,
) -> None:
    """The repro D2 scenario end-to-end: a runner-shaped write through
    CronosStateOps, read back, and the condition-evaluation scope rebuilt from
    the persisted state must expose the routing fields."""
    store = StateStore(tmp_path)
    store.write(_state_with({}))
    ops = CronosStateOps(store, EventLog(tmp_path))
    ops.write({"nodes": {"analyze": {
        "status": "done", "attempt": 1, "artifact_paths": ["a.md"],
        "gate": None, "fields": {"has_ui": "no", "verdict": "pass"},
    }}})

    back = ops.read()
    assert back.nodes["analyze"].fields == {"has_ui": "no", "verdict": "pass"}

    scope = build_scope(back)
    assert scope.get("analyze.fields.has_ui") == "no"
    assert scope.get("analyze.fields.verdict") == "pass"
