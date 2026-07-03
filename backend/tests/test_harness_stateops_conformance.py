"""R2 — StateOps conformance suite run against the harness ``_StateOps``.

The delivery-workflow package ships a StateOps conformance suite
(``lib/state/conformance.py``) encoding the persistence round-trip law
(01-state-model.md §5.4): everything the runner writes through
``StateOps.write()`` must read back identically through ``StateOps.read()``.

Two implementations of the same Protocol exist today with historically
divergent semantics (D2: ``CronosStateOps`` dropped ``fields``; the harness
``_StateOps`` persisted them). Running the *same* package-provided checks
against both implementations — here for the harness one, and in
``packages/delivery-workflow/tests/regression/test_stateops_conformance.py``
for the StateStore-backed one — makes that class of divergence impossible to
reintroduce silently.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Path bootstrap so delivery-workflow modules are importable in test context.
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parents[2]
_DW_PKG = _REPO_ROOT / "packages" / "delivery-workflow"
if str(_DW_PKG) not in sys.path:
    sys.path.insert(0, str(_DW_PKG))

from lib.state.conformance import (  # noqa: E402
    STATEOPS_CONFORMANCE_CHECKS,
    run_stateops_conformance,
)
from state_types import WorkflowState  # noqa: E402

from app.harnesses.executor_adapter import _StateOps  # noqa: E402


def _make_ops(initial: WorkflowState) -> _StateOps:
    return _StateOps(initial)


@pytest.mark.parametrize(
    "check", STATEOPS_CONFORMANCE_CHECKS, ids=lambda c: c.__name__
)
def test_harness_stateops_conformance(check) -> None:
    check(_make_ops)


def test_harness_stateops_conformance_entry_point() -> None:
    run_stateops_conformance(_make_ops)
