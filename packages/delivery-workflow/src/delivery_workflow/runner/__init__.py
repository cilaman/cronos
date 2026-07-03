"""runner — cyclic work-list workflow executor (app-free portable core)."""
from __future__ import annotations

from typing import TYPE_CHECKING

from delivery_workflow.state_types import WorkflowState

# R7 resume API — the only legal re-entry for a persisted halted run
# (01-state-model.md §5.3).  Re-exported here so hosts import one surface:
#   from runner import resume, HumanAnswer, RetryFailed, RaiseBudget, Nothing
from delivery_workflow.runner.resume import (  # noqa: F401
    DEFAULT_MAX_RESUME_RETRIES,
    HumanAnswer,
    Nothing,
    RaiseBudget,
    ResumeError,
    ResumeEvent,
    RetryFailed,
    blocked_human_nodes,
    resume,
)

if TYPE_CHECKING:
    from typing import Any, Callable

    from delivery_workflow.interface import HostPort, NodeExecutor, StateOps
    from delivery_workflow.ir import IRGraph


def run(
    graph: "IRGraph",
    executor: "NodeExecutor",
    state_ops: "StateOps | None" = None,
    host: "HostPort | None" = None,
    *,
    eval_condition: "Callable[[str, dict[str, Any]], bool] | None" = None,
) -> WorkflowState:
    """Execute *graph* against *executor*; return the final WorkflowState.

    See runner.core.run for full documentation.  Hosts should prefer the
    ``DeliveryRun`` facade (``delivery_workflow.delivery_run``), which wraps
    this entry point and returns the closed ``Outcome`` taxonomy.
    """
    from delivery_workflow.runner.core import run as _run

    return _run(
        graph=graph,
        executor=executor,
        state_ops=state_ops,
        host=host,
        eval_condition=eval_condition,
    )
