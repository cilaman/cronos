"""
backend/app/harnesses/executor_adapter — HarnessExecutorAdapter.

Bridges the Cronos BFS runtime (WorkerProtocol / RunState) to the portable
delivery-workflow ``ExecutorInterface`` so that ``runner.core.run()`` can
drive a Cronos harness without touching any BFS executor logic.

Import boundary
---------------
This file is in ``backend/app/harnesses/`` and MAY import from ``backend/app/``
(unlike compiler.py which has a tighter R13 boundary).  It MUST NOT import from
``packages/delivery-workflow/runner/*`` or ``packages/delivery-workflow/lib/*``
other than what is needed to satisfy the ExecutorInterface protocol.

WorkerAdapter Protocol
----------------------
The adapter accepts any object that satisfies the ``WorkerAdapter`` Protocol
below.  The real Worker satisfies it; tests inject lightweight stubs.

escalate() discriminator
------------------------
``escalate(node_id, reason)`` is called in two semantically different situations
by the runner:

1. **Human-wait park** — reason starts with ``"[wait/human]"`` or ``"[human]"``.
   The adapter sets ``waiting_node_id`` on the in-memory WorkflowState AND
   updates the RunState so the BFS executor's resume path picks it up.

2. **Loop exhaust / global cap** — any other reason.
   The adapter marks the WorkflowState status as ``"escalated"`` (which causes
   runner.core.run() to halt).  ``waiting_node_id`` is NOT set.
"""

from __future__ import annotations

import asyncio
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Protocol, runtime_checkable

# ---------------------------------------------------------------------------
# sys.path bootstrap — make packages/delivery-workflow importable.
# ---------------------------------------------------------------------------
_THIS_FILE = Path(__file__).resolve()
# backend/app/harnesses/executor_adapter.py → 4 parents up = space root
_SPACE_ROOT = _THIS_FILE.parent.parent.parent.parent.parent
_DW_PKG = _SPACE_ROOT / "packages" / "delivery-workflow"
_DW_PKG_STR = str(_DW_PKG)
if _DW_PKG_STR not in sys.path:
    sys.path.insert(0, _DW_PKG_STR)

from results import AgentResult, GateResult  # noqa: E402
from state_types import NodeState as WfNodeState  # noqa: E402
from state_types import WorkflowState  # noqa: E402

from ..models import TaskState  # noqa: E402
from ..trace_parser import RunTrace  # noqa: E402
from .decision import eval_condition as _eval_condition  # noqa: E402
from .run_state import RunState  # noqa: E402
from .state_mapping import runstate_to_workflowstate, workflowstate_to_runstate  # noqa: E402

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# WorkerAdapter Protocol (injected dependency)
# ---------------------------------------------------------------------------


@runtime_checkable
class WorkerAdapter(Protocol):
    """Minimal interface from the BFS worker required by HarnessExecutorAdapter.

    Both the real ``Worker`` and test stubs satisfy this protocol.
    """

    async def run_agent(self, task_id: str) -> RunTrace:
        """Run the agent for *task_id* and return a RunTrace."""
        ...

    async def finalize_child(self, task_id: str) -> TaskState:
        """Finalise a completed child task and return its new TaskState."""
        ...


# ---------------------------------------------------------------------------
# _StateOps — in-memory StateOps implementation
# ---------------------------------------------------------------------------


class _StateOps:
    """In-memory StateOps backed by a ``WorkflowState`` snapshot.

    ``read()`` returns a deep-copy-equivalent of the current WorkflowState
    (realised by round-tripping through ``runstate_to_workflowstate`` at
    construction time; thereafter mutated in-place by runner writes).

    ``write(patch)`` applies a shallow merge from the patch dict into the
    in-memory WorkflowState:
      - ``"status"`` → ``state.status``
      - ``"nodes"`` → merges each node sub-dict into ``state.nodes``
    """

    def __init__(self, initial: WorkflowState) -> None:
        self._state = initial

    def read(self) -> WorkflowState:
        return self._state

    def write(self, patch: dict[str, Any]) -> None:
        if "status" in patch:
            self._state.status = patch["status"]  # type: ignore[assignment]
        if "nodes" in patch:
            for node_id, node_dict in patch["nodes"].items():
                existing = self._state.nodes.get(node_id)
                if existing is None:
                    existing = WfNodeState(status="blocked")
                    self._state.nodes[node_id] = existing
                if "status" in node_dict:
                    existing.status = node_dict["status"]
                if "attempt" in node_dict:
                    existing.attempt = node_dict["attempt"]
                if "artifact_paths" in node_dict:
                    existing.artifact_paths = node_dict["artifact_paths"]
                if "gate" in node_dict:
                    existing.gate = node_dict["gate"]
                if "fields" in node_dict:
                    existing.fields = {**(existing.fields or {}), **node_dict["fields"]}


# ---------------------------------------------------------------------------
# _TelemetryOps — forwards events to a callback
# ---------------------------------------------------------------------------


class _TelemetryOps:
    """TelemetryOps that synthesises events matching the existing _publish schema.

    Each ``emit()`` call converts the telemetry payload into one or more
    ``_publish``-compatible events and forwards them to the publish callback.

    Supported event types derived from the ``data`` keys (matching R7):
      - ``node_id`` present → ``"node_transition"`` event with ``node_id`` and
        ``status`` if present.
      - ``edge_id`` present → ``"edge_chosen"`` event.
      - ``run_status`` present → ``"run_status"`` event.

    When none of these special keys are present, the payload is forwarded as a
    generic telemetry event.

    Parameters
    ----------
    goal_task_id:
        The run/goal task id used as the SSE subscription key for ``_publish``.
    publish_cb:
        Callable ``(task_id: str, event: dict) -> None``.  Typically
        ``worker._publish`` bound to the current harness run context.
    """

    def __init__(
        self,
        goal_task_id: str,
        publish_cb: Callable[[str, dict], None],
    ) -> None:
        self._goal_task_id = goal_task_id
        self._publish = publish_cb

    def emit(self, node_id: str, data: dict[str, float]) -> None:
        """Emit a telemetry payload as an SSE event.

        Synthesises events matching the existing ``_publish`` schema (R7):
        - ``"node_transition"`` with keys: ``type``, ``node_id``, ``status``,
          ``from_status``, ``timestamp``.
        - ``"edge_chosen"`` with keys: ``type``, ``edge_id``, ``timestamp``.
        - ``"run_status"`` with keys: ``type``, ``status``, ``timestamp``.
        """
        ts = _utcnow_iso()
        # Discriminate on keys in data to decide event type.
        if "status" in data and node_id:
            event: dict = {
                "type": "node_transition",
                "node_id": node_id,
                "status": data.get("status"),
                "from_status": data.get("from_status", "pending"),
                "timestamp": ts,
            }
            self._publish(self._goal_task_id, event)
        if "edge_id" in data:
            event = {
                "type": "edge_chosen",
                "edge_id": data["edge_id"],
                "timestamp": ts,
            }
            self._publish(self._goal_task_id, event)
        if "run_status" in data:
            event = {
                "type": "run_status",
                "status": data["run_status"],
                "timestamp": ts,
            }
            self._publish(self._goal_task_id, event)


# ---------------------------------------------------------------------------
# Human-wait discriminator
# ---------------------------------------------------------------------------

_HUMAN_WAIT_PREFIXES = ("[wait/human]", "[human]", "wait:")


def _is_human_wait(reason: str) -> bool:
    """Return True if *reason* indicates a human-wait park (not loop exhaust)."""
    return any(reason.startswith(p) for p in _HUMAN_WAIT_PREFIXES)


# ---------------------------------------------------------------------------
# HarnessExecutorAdapter
# ---------------------------------------------------------------------------


class HarnessExecutorAdapter:
    """Cronos-side implementation of the delivery-workflow ``ExecutorInterface``.

    Wraps a ``WorkerAdapter`` instance for agent dispatch; delegates condition
    evaluation to ``harnesses.decision.eval_condition``; bridges
    ``escalate()`` to either human-wait parking or loop-exhaust signalling
    depending on the ``reason`` string prefix.

    Parameters
    ----------
    worker_adapter:
        Object satisfying ``WorkerAdapter`` Protocol.
    run_state:
        Initial ``RunState`` loaded from disk (or freshly initialised).
        The adapter converts this to a ``WorkflowState`` at construction time
        and keeps it in-memory for the duration of the run.
    harness_id:
        The harness identifier; passed to ``runstate_to_workflowstate`` as the
        ``spec`` field.
    goal_task_id:
        The task id of the harness run goal; used as SSE subscription key.
    publish_cb:
        Callable ``(task_id: str, event: dict) -> None`` for SSE event
        forwarding.  Pass a no-op lambda in tests.
    task_id_factory:
        Optional callable ``(agent_ref: str, inputs: dict) -> str`` that
        returns a pre-created child task id for ``dispatchAgent``.  When None,
        the adapter raises ``NotImplementedError`` for agent dispatch (suitable
        for unit tests that stub ``dispatchAgent`` entirely).
    """

    def __init__(
        self,
        worker_adapter: WorkerAdapter,
        run_state: RunState,
        harness_id: str,
        goal_task_id: str,
        publish_cb: Callable[[str, dict], None] | None = None,
        task_id_factory: Callable[[str, dict], str] | None = None,
    ) -> None:
        self._worker = worker_adapter
        self._base_run_state = run_state
        self._harness_id = harness_id
        self._goal_task_id = goal_task_id
        self._task_id_factory = task_id_factory

        # Convert RunState to WorkflowState for the runner.
        initial_ws = runstate_to_workflowstate(run_state, harness_id)
        self.state = _StateOps(initial_ws)

        # Telemetry bridge.
        effective_publish = publish_cb if publish_cb is not None else _noop_publish
        self.telemetry = _TelemetryOps(goal_task_id, effective_publish)

    # ------------------------------------------------------------------
    # ExecutorInterface methods
    # ------------------------------------------------------------------

    def dispatchAgent(self, agent_ref: str, inputs: dict[str, Any]) -> AgentResult:
        """Dispatch an agent via the WorkerAdapter.

        Resolves the child task id from ``inputs["node_id"]`` (injected by
        the runner's dispatch layer) and calls ``worker_adapter.run_agent`` +
        ``worker_adapter.finalize_child``.

        Returns
        -------
        AgentResult
            ``status="done"`` if the child task reached DONE; ``"failed"``
            otherwise.
        """
        node_id: str = inputs.get("node_id", agent_ref)

        # If the caller injected a pre-created task_id via task_id_factory,
        # use it.  Otherwise, look it up from the existing WorkflowState
        # fields or raise if no factory is available.
        if self._task_id_factory is not None:
            task_id = self._task_id_factory(agent_ref, inputs)
        else:
            # Derive task_id from the current WorkflowState (child_task_id stored
            # in node fields by a prior BFS reconciliation step, or node_id itself
            # if no prior state exists).
            ws = self.state.read()
            ns = ws.nodes.get(node_id)
            task_id = (ns.fields.get("child_task_id") if ns else None) or node_id

        log.info(
            "HarnessExecutorAdapter.dispatchAgent: node=%r agent_ref=%r task_id=%r",
            node_id, agent_ref, task_id,
        )

        # Emit node_transition: pending → in_progress.
        self.telemetry.emit(node_id, {"status": "in_progress", "from_status": "pending"})

        try:
            trace: RunTrace = _run_sync(self._worker.run_agent(task_id))
        except Exception as exc:
            log.exception(
                "dispatchAgent: run_agent failed for node=%r task_id=%r: %s",
                node_id, task_id, exc,
            )
            self.telemetry.emit(node_id, {"status": "failed", "from_status": "in_progress"})
            return AgentResult(
                status="failed",
                artifact_paths=[],
                produces="",
                fields={"error": str(exc), "child_task_id": task_id},
                open_questions=[],
                telemetry=_zero_telemetry(),
            )

        try:
            final_state: TaskState = _run_sync(self._worker.finalize_child(task_id))
        except Exception as exc:
            log.exception(
                "dispatchAgent: finalize_child failed for node=%r task_id=%r: %s",
                node_id, task_id, exc,
            )
            self.telemetry.emit(node_id, {"status": "failed", "from_status": "in_progress"})
            return AgentResult(
                status="failed",
                artifact_paths=[],
                produces="",
                fields={"error": str(exc), "child_task_id": task_id},
                open_questions=[],
                telemetry=_zero_telemetry(),
            )

        if final_state == TaskState.DONE:
            output = trace.final_text_snippet if trace else ""
            self.telemetry.emit(node_id, {"status": "done", "from_status": "in_progress"})
            # P0-1: parse the agent's node_status/delivery_status envelope and
            # surface its structured fields (verdict, finding_class, ...) so
            # downstream edges keyed on ``{node}.fields.{k}`` can route.  Without
            # this the verdict stays trapped as raw text in ``fields.output`` and
            # every verdict-routed edge dead-ends.  Mirrors the BFS executor's
            # _enrich_scope_from_delivery_status.  Node status stays "done" so
            # runner/scope exposes the fields (it gates on status == "done").
            fields: dict[str, Any] = {
                "child_task_id": task_id,
                "output": output,
                "exit_reason": trace.exit_reason if trace else "",
            }
            from .executor import _parse_status_envelope  # noqa: PLC0415
            envelope = _parse_status_envelope(output)
            if envelope is not None:
                env_status = envelope.get("status")
                if isinstance(env_status, str) and env_status:
                    fields["verdict"] = env_status
                env_fields = envelope.get("fields")
                if isinstance(env_fields, dict):
                    for k, v in env_fields.items():
                        fields[str(k)] = str(v)
            return AgentResult(
                status="done",
                artifact_paths=[],
                produces=output,
                fields=fields,
                open_questions=[],
                telemetry=_zero_telemetry(),
            )
        else:
            self.telemetry.emit(node_id, {"status": "failed", "from_status": "in_progress"})
            return AgentResult(
                status="failed",
                artifact_paths=[],
                produces="",
                fields={
                    "child_task_id": task_id,
                    "final_state": final_state.value if hasattr(final_state, "value") else str(final_state),
                },
                open_questions=[],
                telemetry=_zero_telemetry(),
            )

    def runGate(self, gate: dict[str, Any], artifact_paths: list[str]) -> GateResult:
        """Gate nodes are not used in Cronos harnesses (no 'gate' kind in NodeType).

        Raises NotImplementedError — gate nodes should not appear in compiled
        Cronos harnesses.  If one is encountered, it is a compiler or schema bug.
        """
        raise NotImplementedError(
            f"Cronos harnesses do not support gate nodes; gate={gate!r}"
        )

    def evalCondition(self, expr: str, scope: dict[str, Any]) -> bool:
        """Evaluate a condition expression using the harness decision evaluator.

        Delegates to ``harnesses.decision.eval_condition`` (whitelisted
        grammar: ``==``, ``!=``, ``in``, ``&&``, ``||``).  No eval().
        """
        if not expr:
            return True
        try:
            return _eval_condition(expr, scope)
        except Exception as exc:
            log.warning(
                "evalCondition: failed to evaluate %r: %s — returning False.", expr, exc
            )
            return False

    def escalate(self, node_id: str, reason: str) -> None:
        """Handle escalation from the runner.

        Discriminates between two call shapes (R-high-risk from design report):

        Human-wait park (reason starts with '[wait/human]', '[human]', or 'wait:')
        --------------------------------------------------------------------------
        Sets ``state.nodes[node_id].status = 'blocked'`` (human-wait) and
        marks the WorkflowState status as ``'blocked'`` so the runner halts.
        The caller (run_executor.py) is responsible for setting
        ``RunState.waiting_node_id`` by converting back via
        ``workflowstate_to_runstate``.

        Loop exhaust / global cap (all other reasons)
        -----------------------------------------------
        Sets ``state.status = 'escalated'``.  ``waiting_node_id`` is NOT set.
        """
        log.info(
            "HarnessExecutorAdapter.escalate: node=%r reason=%r", node_id, reason
        )

        ws = self.state.read()

        if _is_human_wait(reason):
            # Human-wait park: set node to blocked + run to blocked.
            if node_id not in ws.nodes:
                ws.nodes[node_id] = WfNodeState(status="blocked")
            else:
                ws.nodes[node_id].status = "blocked"
            # Persist via state_ops.write so runner.core sees the blocked status.
            self.state.write({"status": "blocked", "nodes": {node_id: {"status": "blocked"}}})
            log.info(
                "escalate: human-wait park — node=%r blocked; run status=blocked.", node_id
            )
        else:
            # Loop exhaust or global cap: escalate the run.
            self.state.write({"status": "escalated"})
            log.info(
                "escalate: loop-exhaust or global cap — node=%r; run status=escalated.",
                node_id,
            )

    # ------------------------------------------------------------------
    # RunState conversion helper
    # ------------------------------------------------------------------

    def to_run_state(self) -> RunState:
        """Convert the current in-memory WorkflowState back to a RunState.

        Uses ``workflowstate_to_runstate`` with the original ``_base_run_state``
        as the identity/routing base.
        """
        return workflowstate_to_runstate(self.state.read(), self._base_run_state)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _utcnow_iso() -> str:
    """Return current UTC time as ISO-8601 string with trailing 'Z'."""
    return datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f") + "Z"


def _noop_publish(task_id: str, event: dict) -> None:  # noqa: ARG001
    """No-op publish callback used when no real SSE publisher is available."""
    pass


def _run_sync(coro: Any) -> Any:
    """Run *coro* synchronously.

    Uses ``asyncio.get_event_loop().run_until_complete`` if there is no
    running event loop, or ``asyncio.run`` in otherwise-sync contexts.
    In an already-running loop context (e.g. tests using pytest-asyncio),
    the coroutine MUST be awaited by the test itself — this helper is for
    the synchronous ExecutorInterface methods called from runner.core.run().
    """
    if asyncio.iscoroutine(coro):
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Called from within an already-running event loop (e.g. pytest-asyncio):
                # we cannot call loop.run_until_complete here. Use a new loop in a
                # separate thread via asyncio.run_coroutine_threadsafe.
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                    future = pool.submit(asyncio.run, coro)
                    return future.result()
            return loop.run_until_complete(coro)
        except RuntimeError:
            return asyncio.run(coro)
    return coro


def _zero_telemetry():
    """Return a zeroed TelemetryData for AgentResult."""
    from results import TelemetryData  # noqa: PLC0415
    return TelemetryData(tokens=0, usd=0.0, seconds=0.0)
