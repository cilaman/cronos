"""runner — cyclic work-list workflow executor (app-free portable core)."""
from __future__ import annotations

from typing import TYPE_CHECKING

from state_types import WorkflowState

if TYPE_CHECKING:
    from interface import ExecutorInterface, StateOps
    from ir import IRGraph


def run(
    graph: "IRGraph",
    executor: "ExecutorInterface",
    state_ops: "StateOps | None" = None,
) -> WorkflowState:
    """Execute *graph* against *executor*; return the final WorkflowState.

    See runner.core.run for full documentation.
    """
    from runner.core import run as _run

    return _run(graph=graph, executor=executor, state_ops=state_ops)
