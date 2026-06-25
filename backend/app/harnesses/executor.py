"""
backend/app/harnesses/executor — HarnessExecutor: DAG-based harness node runner.

The HarnessExecutor walks the harness graph using a **runtime-gated BFS**
(replacing the earlier static Kahn's algorithm + linear loop).  Nodes whose
in-degree has reached zero (i.e. all predecessors are ``done``) are enqueued
in sorted-node-id order for determinism, matching the tie-break used by the
now-internal ``_topo_sort`` helper.

Key design decisions
--------------------
* WorkerProtocol (typing.Protocol) — the executor accepts *any* object that
  exposes ``run_agent`` and ``finalize_child``.  The real Worker satisfies the
  protocol; tests use stubs.  This prevents circular imports and enables
  isolated unit testing.

* Fail-fast — when an Agent node fails (finalize_child returns a non-DONE
  state), all remaining un-executed nodes are marked ``skipped`` with
  ``reason='upstream_failed'`` and execution halts.  This mirrors
  worker._run_goal semantics.

* No new worker lane — nodes are awaited sequentially inside execute(); no
  asyncio.create_task() is used.

* Control-flow dispatch table — non-agent node types are dispatched to their
  dedicated evaluators:
  - ``type='decision'`` → ``decision.evaluate_decision()``
  - ``type='wait'`` (human mode) → ``wait.enter_wait()`` → returns
    ``WaitOutcome``; executor parks harness goal in WAITING state and returns.
  - ``type='wait'`` (timed mode) → ``await wait.await_timed_wait()``; then
    continue BFS traversal.
  - ``type='aggregator'`` → ``aggregator.aggregator_ready()``; verdict drives
    whether to proceed or remain pending.

* Variable scope — root vars are merged first; upstream node outputs override
  on key collision (per interpolate.py precedence rule).

* Resume — before re-executing a node found in an existing RunState with
  ``status='in_progress'``, the executor queries the TaskStore for the
  recorded ``child_task_id``; if that task exists and is DONE, the node is
  accepted as done without re-execution.

* Wait-human resume — when ``RunState.waiting_node_id`` is set on entry,
  the executor resumes traversal from that node's outgoing edges.  Already-
  completed nodes (in ``run_state.nodes_executed``) are not re-executed.
  ``waiting_node_id`` is cleared on resume.
"""

from __future__ import annotations

import logging
from collections import deque
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Protocol, runtime_checkable

import os

from ..logging_config import bind_run_context

from ..memory_parser import parse_delivery_status_block
from ..models import Space, TaskState
from ..storage import TaskStore
from ..trace_parser import RunTrace
from .aggregator import AggregatorVerdict, aggregator_ready, compose_output
from .brief_composer import compose_brief
from .decision import eval_condition, evaluate_decision
from .interpolate import interpolate
from .model import Harness, HarnessEdge, HarnessNode, NodeType
from . import run_index as _run_index
from .run_state import NodeState, RunState, load, save_atomic
from .wait import WaitAction, enter_wait, await_timed_wait

_DATA_DIR = Path(os.environ.get("CRONOS_DATA_DIR", "/data"))


def _utcnow_iso() -> str:
    """Return the current UTC time as an ISO-8601 string with trailing 'Z'."""
    return datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f") + "Z"

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# WorkerProtocol
# ---------------------------------------------------------------------------


@runtime_checkable
class WorkerProtocol(Protocol):
    """Minimal subset of Worker callable interface required by HarnessExecutor.

    The real ``Worker`` class satisfies this protocol.  Tests inject a stub.
    """

    async def run_agent(self, task_id: str, **kwargs: Any) -> RunTrace:
        """Run the agent for *task_id* and return a RunTrace.

        The executor does not interpret ``kwargs`` — they are forwarded as-is.
        The real Worker's ``run_agent`` signature accepts additional kwargs
        (space, goal_context, memory_items, …); the protocol captures only the
        minimum required by the executor.
        """
        ...

    async def finalize_child(self, task_id: str, trace: RunTrace) -> TaskState:
        """Finalize a completed child task and return its new TaskState.

        The executor uses the returned state to decide whether to continue
        (DONE) or halt with fail-fast (any other state).
        """
        ...

    def _publish(self, task_id: str, event: dict) -> None:
        """Publish an event dict to all SSE subscribers for *task_id*.

        Event types used by the executor:
        - ``{"type": "node_transition", "node_id": ..., "from_status": ...,
                "to_status": ..., "timestamp": ...}``
        - ``{"type": "edge_chosen", "from_node": ..., "to_node": ...,
                "timestamp": ...}``
        - ``{"type": "run_status", "run_id": ..., "status": ...,
                "timestamp": ...}``

        If the worker is None (unit-test mode), the executor skips the call.
        """
        ...


# ---------------------------------------------------------------------------
# Topo-sort helpers (kept for internal use and backward-compat imports)
# ---------------------------------------------------------------------------


def _topo_sort(harness: Harness) -> list[HarnessNode]:
    """Return harness nodes in topological order using Kahn's algorithm.

    Operates on ``harness.edges`` (not TaskStore children).  Each edge
    represents a directed dependency: source node must complete before the
    target node executes.

    Raises ``ValueError`` if the graph contains a cycle (should not happen
    if the harness passed model-layer cycle detection, but we guard anyway).
    """
    # Build adjacency: source_node_id -> list[target_node_id]
    # and in-degree map.
    node_by_id: dict[str, HarnessNode] = {n.id: n for n in harness.nodes}
    in_degree: dict[str, int] = {n.id: 0 for n in harness.nodes}
    successors: dict[str, list[str]] = {n.id: [] for n in harness.nodes}

    for edge in harness.edges:
        src = edge.source.node_id
        tgt = edge.target.node_id
        successors[src].append(tgt)
        in_degree[tgt] += 1

    # Initialize queue with all zero-in-degree nodes, sorted by node id for
    # determinism when multiple nodes are ready simultaneously.
    queue: deque[str] = deque(
        sorted(nid for nid, deg in in_degree.items() if deg == 0)
    )
    order: list[HarnessNode] = []

    while queue:
        nid = queue.popleft()
        order.append(node_by_id[nid])
        # Reduce in-degree of all successors; enqueue when they reach 0.
        for succ_id in sorted(successors[nid]):  # sorted for determinism
            in_degree[succ_id] -= 1
            if in_degree[succ_id] == 0:
                queue.append(succ_id)

    if len(order) != len(harness.nodes):
        raise ValueError("Harness graph contains a cycle; cannot execute.")

    return order


# ---------------------------------------------------------------------------
# BFS graph helpers
# ---------------------------------------------------------------------------


def _build_graph(harness: Harness) -> tuple[
    dict[str, HarnessNode],
    dict[str, int],
    dict[str, list[str]],
    dict[str, list[HarnessEdge]],
]:
    """Build adjacency structures for BFS traversal.

    Returns
    -------
    node_by_id:
        Mapping node_id → HarnessNode.
    in_degree:
        Mapping node_id → number of incoming edges (predecessor count).
    successors:
        Mapping node_id → list of successor node_ids.
    outgoing_edges:
        Mapping node_id → list of outgoing HarnessEdge objects (preserves order
        from harness.edges; used by the decision evaluator).
    """
    node_by_id: dict[str, HarnessNode] = {n.id: n for n in harness.nodes}
    in_degree: dict[str, int] = {n.id: 0 for n in harness.nodes}
    successors: dict[str, list[str]] = {n.id: [] for n in harness.nodes}
    outgoing_edges: dict[str, list[HarnessEdge]] = {n.id: [] for n in harness.nodes}

    for edge in harness.edges:
        src = edge.source.node_id
        tgt = edge.target.node_id
        successors[src].append(tgt)
        outgoing_edges[src].append(edge)
        in_degree[tgt] += 1

    return node_by_id, in_degree, successors, outgoing_edges


def _get_predecessors_state(
    node_id: str,
    harness: Harness,
    state: RunState,
) -> dict[str, NodeState]:
    """Return predecessor NodeState mapping for *node_id*.

    Uses reverse edge traversal to find predecessors.  Predecessors not yet
    in ``state.nodes_executed`` are represented as ``NodeState(status='pending')``.
    """
    pred_state: dict[str, NodeState] = {}
    for edge in harness.edges:
        if edge.target.node_id == node_id:
            pred_id = edge.source.node_id
            pred_state[pred_id] = state.nodes_executed.get(
                pred_id, NodeState(status="pending")
            )
    return pred_state


# ---------------------------------------------------------------------------
# HarnessExecutor
# ---------------------------------------------------------------------------


class HarnessExecutor:
    """Execute a Harness graph node by node using a runtime-gated BFS.

    Parameters
    ----------
    store:
        TaskStore used to create child tasks and look up existing ones
        during resume reconciliation.
    worker_protocol:
        Object satisfying WorkerProtocol — provides ``run_agent`` and
        ``finalize_child`` without coupling executor.py to worker.py.
    tools_resolver:
        Callable ``(space_id: str, agent_ref: str) -> AiToolEntry | None``
        used to resolve agent/skill references to their AiToolEntry.
    event_worker:
        Optional object that provides ``_publish(task_id, event)`` for
        broadcasting SSE events.  Defaults to None (silent mode for tests
        and legacy callers that have not been wired to the Worker yet).
        When None, all ``_publish`` calls are silently skipped.
    """

    def __init__(
        self,
        store: TaskStore,
        worker_protocol: WorkerProtocol,
        tools_resolver: Callable,
        event_worker: "WorkerProtocol | None" = None,
    ) -> None:
        self.store = store
        self.worker = worker_protocol
        self.tools_resolver = tools_resolver
        self._worker = event_worker  # may be None; used only for _publish()

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    async def execute(
        self,
        run_goal_id: str,
        harness: Harness,
        space: Space,
    ) -> RunState:
        """Execute *harness* via runtime-gated BFS, persisting state after each node.

        Parameters
        ----------
        run_goal_id:
            Identifier for this harness run (typically a Task id).  Used as
            the key for the run-state JSON file path and as ``parent_run_id``
            when extracting child RunTraces.
        harness:
            The Harness graph to execute.
        space:
            The Space in which child tasks are created.

        Returns
        -------
        RunState
            The final run state after all nodes have been processed.
        """
        async with bind_run_context(run_id=run_goal_id):
            return await self._execute_body(run_goal_id, harness, space)

    async def _execute_body(
        self,
        run_goal_id: str,
        harness: Harness,
        space: Space,
    ) -> RunState:
        # Compute run-state file path.  Space.id maps to the directory
        # {DATA_DIR}/spaces/{space.id}/.cronos/harness-runs/{run_goal_id}.json
        run_state_path: Path | None = (
            _DATA_DIR / "spaces" / space.id / ".cronos" / "harness-runs" / f"{run_goal_id}.json"
        )
        space_dir = _DATA_DIR / "spaces" / space.id

        # ------------------------------------------------------------------
        # Load or initialise run state (resume support)
        # ------------------------------------------------------------------
        harness_id = getattr(harness, "id", harness.name)
        existing = None
        try:
            existing = load(run_state_path)
        except (ValueError, OSError) as exc:
            log.warning(
                "Could not load run state for %s (%s); starting fresh.",
                run_goal_id, exc,
            )
        state: RunState = existing or RunState(
            run_id=run_goal_id,
            harness_id=harness_id,
            goal_task_id=run_goal_id,
        )

        # Publish run_status=running event to signal execution start.
        self._publish_event(run_goal_id, {
            "type": "run_status",
            "run_id": run_goal_id,
            "status": "running",
            "timestamp": _utcnow_iso(),
        })

        # ------------------------------------------------------------------
        # Reconcile in_progress Agent nodes before execution begins.
        # Control-flow in_progress nodes (decision/wait/aggregator) that
        # survived a restart are left as-is; the BFS will skip them since
        # they appear in nodes_executed.
        # ------------------------------------------------------------------
        for node_id, ns in list(state.nodes_executed.items()):
            if ns.status == "in_progress" and ns.child_task_id:
                child = self.store.get(ns.child_task_id)
                if child is not None and child.state == TaskState.DONE:
                    log.info(
                        "Resume: node %s child %s already DONE — accepting.",
                        node_id, ns.child_task_id,
                    )
                    state.nodes_executed[node_id] = NodeState(
                        status="done",
                        child_task_id=ns.child_task_id,
                        output=ns.output,
                    )
                else:
                    # Child did not finish — treat node as pending (re-execute).
                    log.info(
                        "Resume: node %s child %s not DONE — will re-execute.",
                        node_id, ns.child_task_id,
                    )
                    del state.nodes_executed[node_id]

        # ------------------------------------------------------------------
        # Build variable scope from harness root variables
        # ------------------------------------------------------------------
        # scope accumulates variable values; upstream node outputs override.
        scope: dict[str, str] = dict(harness.variables)

        # Restore scope from already-completed nodes (resume path).
        for node_id, ns in state.nodes_executed.items():
            if ns.status == "done" and ns.output is not None:
                scope[node_id] = ns.output

        # ------------------------------------------------------------------
        # Build BFS graph structures
        # ------------------------------------------------------------------
        node_by_id, in_degree, successors, outgoing_edges_map = _build_graph(harness)

        # ------------------------------------------------------------------
        # Adjust in_degree for already-completed nodes (resume path).
        # For every node already in state.nodes_executed with a terminal status
        # (done, failed, skipped), decrement the in_degree of its successors.
        # This lets the BFS correctly compute which nodes are "ready" when we
        # resume from a partially-completed run.
        # ------------------------------------------------------------------
        for completed_node_id, ns in state.nodes_executed.items():
            if ns.status in ("done", "failed", "skipped"):
                for succ_id in successors.get(completed_node_id, []):
                    in_degree[succ_id] = max(0, in_degree[succ_id] - 1)

        # ------------------------------------------------------------------
        # Determine BFS starting point
        # ------------------------------------------------------------------
        # Case 1: Wait-human resume — start from the waiting node's successors.
        if state.waiting_node_id is not None:
            waiting_id = state.waiting_node_id
            log.info(
                "Resume: detected waiting_node_id=%r — resuming from its outgoing edges.",
                waiting_id,
            )
            # Clear the waiting_node_id (resume in progress).
            state.waiting_node_id = None
            # Mark the wait node as done (it was in_progress during the wait).
            if state.nodes_executed.get(waiting_id, NodeState(status="pending")).status == "in_progress":
                state.nodes_executed[waiting_id] = NodeState(status="done")
                # Also decrement successors' in_degree for the now-done wait node.
                for succ_id in successors.get(waiting_id, []):
                    in_degree[succ_id] = max(0, in_degree[succ_id] - 1)
            # Seed the BFS ready queue with the wait node's successors
            # whose in-degree has reached 0 after the adjustment above.
            ready_queue: deque[str] = deque(
                sorted(
                    succ_id
                    for succ_id in successors.get(waiting_id, [])
                    if in_degree.get(succ_id, 0) == 0
                    and succ_id not in state.nodes_executed
                )
            )
        else:
            # Case 2: Normal start (or timed-Wait resume).
            # Include in_degree-0 nodes that are either:
            #   (a) not yet in nodes_executed (fresh execution), OR
            #   (b) an in-progress timed Wait with a persisted wake_at — these were
            #       interrupted mid-sleep and should resume with the remaining interval.
            ready_queue = deque(
                sorted(
                    nid
                    for nid, deg in in_degree.items()
                    if deg == 0
                    and (
                        nid not in state.nodes_executed
                        or (
                            state.nodes_executed[nid].status == "in_progress"
                            and not state.nodes_executed[nid].child_task_id
                            and node_by_id[nid].type == NodeType.wait
                            and node_by_id[nid].data.get("mode") != "human"
                        )
                    )
                )
            )

        # Track which nodes are currently in the ready queue (avoid duplicate enqueues).
        in_queue: set[str] = set(ready_queue)

        # ------------------------------------------------------------------
        # Runtime-gated BFS execution loop
        # ------------------------------------------------------------------
        upstream_failed = False

        while ready_queue:
            node_id = ready_queue.popleft()
            in_queue.discard(node_id)

            # ------------------------------------------------------------------
            # Cancel-race guard: reload RunState from disk and check for
            # cancellation before processing each node.  This prevents the
            # executor from overwriting a 'cancelled' status set by the cancel
            # handler (I6) between two node executions.
            # ------------------------------------------------------------------
            if run_state_path is not None:
                try:
                    reloaded = load(run_state_path)
                    if reloaded is not None and reloaded.status == "cancelled":
                        log.info(
                            "Run %r is cancelled (detected at BFS boundary); stopping.",
                            run_goal_id,
                        )
                        self._publish_event(run_goal_id, {
                            "type": "run_status",
                            "run_id": run_goal_id,
                            "status": "cancelled",
                            "timestamp": _utcnow_iso(),
                        })
                        return reloaded
                except (ValueError, OSError) as exc:
                    log.warning(
                        "Could not reload run state for cancel check (%s); continuing.",
                        exc,
                    )

            # Skip nodes already completed from a prior run.
            existing_ns = state.nodes_executed.get(node_id)
            if existing_ns is not None and existing_ns.status in ("done", "skipped", "failed"):
                # Restore output to scope so downstream nodes can use it.
                if existing_ns.output is not None and existing_ns.status == "done":
                    scope[node_id] = existing_ns.output
                # Decrement successors' effective in-degree and enqueue ready ones.
                self._enqueue_successors(
                    node_id, successors, state, in_degree, in_queue, ready_queue
                )
                continue

            # Fail-fast: upstream failure marks remaining nodes as skipped.
            if upstream_failed:
                now = _utcnow_iso()
                state.nodes_executed[node_id] = NodeState(
                    status="skipped",
                    reason="upstream_failed",
                    ended_at=now,
                )
                self._publish_event(run_goal_id, {
                    "type": "node_transition",
                    "node_id": node_id,
                    "from_status": "pending",
                    "to_status": "skipped",
                    "timestamp": now,
                })
                _maybe_save(state, run_state_path)
                # Enqueue successors so they can also be skipped.
                self._enqueue_successors(
                    node_id, successors, state, in_degree, in_queue, ready_queue
                )
                continue

            node = node_by_id[node_id]

            # ------------------------------------------------------------------
            # Dispatch by node type
            # ------------------------------------------------------------------
            if node.type == NodeType.agent:
                done, output, child_task_id, park = await self._execute_agent_node(
                    node, node_id, run_goal_id, harness, space, scope, state, run_state_path
                )
                if park:
                    # Loop escalation: run is parked, waiting_node_id already set.
                    _maybe_save(state, run_state_path)
                    return state
                if done:
                    if output is not None:
                        scope[node_id] = output
                    self._enqueue_successors(
                        node_id, successors, state, in_degree, in_queue, ready_queue
                    )
                else:
                    upstream_failed = True
                    # Enqueue successors so they can be skipped.
                    self._enqueue_successors(
                        node_id, successors, state, in_degree, in_queue, ready_queue
                    )

            elif node.type == NodeType.decision:
                chosen_edge_id = await self._execute_decision_node(
                    node, node_id, harness, scope, state, run_state_path,
                    outgoing_edges_map[node_id]
                )
                if chosen_edge_id is not None:
                    # Only enqueue the chosen edge's target.
                    chosen_edge = next(
                        (e for e in outgoing_edges_map[node_id] if e.id == chosen_edge_id),
                        None
                    )
                    if chosen_edge is not None:
                        tgt = chosen_edge.target.node_id
                        # Publish edge_chosen event.
                        self._publish_event(run_goal_id, {
                            "type": "edge_chosen",
                            "from_node": node_id,
                            "to_node": tgt,
                            "timestamp": _utcnow_iso(),
                        })
                        if tgt not in state.nodes_executed and tgt not in in_queue:
                            ready_queue.append(tgt)
                            in_queue.add(tgt)
                else:
                    # Decision evaluation failed.
                    upstream_failed = True
                    self._enqueue_successors(
                        node_id, successors, state, in_degree, in_queue, ready_queue
                    )

            elif node.type == NodeType.wait:
                park = await self._execute_wait_node(
                    node, node_id, state, run_state_path, space
                )
                if park:
                    # Human wait: executor parks and returns immediately.
                    _maybe_save(state, run_state_path)
                    return state
                else:
                    # Timed wait completed: continue BFS.
                    self._enqueue_successors(
                        node_id, successors, state, in_degree, in_queue, ready_queue
                    )

            elif node.type == NodeType.aggregator:
                ready, failed = await self._execute_aggregator_node(
                    node, node_id, harness, state, run_state_path
                )
                if ready:
                    self._enqueue_successors(
                        node_id, successors, state, in_degree, in_queue, ready_queue
                    )
                elif failed:
                    upstream_failed = True
                    self._enqueue_successors(
                        node_id, successors, state, in_degree, in_queue, ready_queue
                    )
                # else: pending — do not enqueue successors; aggregator stays out of queue

            elif node.type == NodeType.trigger:
                # Trigger nodes are entry points only — treat as immediate pass-through.
                now = _utcnow_iso()
                state.nodes_executed[node_id] = NodeState(
                    status="done",
                    ended_at=now,
                )
                self._publish_event(run_goal_id, {
                    "type": "node_transition",
                    "node_id": node_id,
                    "from_status": "pending",
                    "to_status": "done",
                    "timestamp": now,
                })
                _maybe_save(state, run_state_path)
                self._enqueue_successors(
                    node_id, successors, state, in_degree, in_queue, ready_queue
                )

            else:
                # Unknown node type — log and skip.
                log.warning("Node %s has unknown type %r; skipping.", node_id, node.type)
                now = _utcnow_iso()
                state.nodes_executed[node_id] = NodeState(
                    status="skipped",
                    reason=f"unknown_node_type:{node.type}",
                    ended_at=now,
                )
                self._publish_event(run_goal_id, {
                    "type": "node_transition",
                    "node_id": node_id,
                    "from_status": "pending",
                    "to_status": "skipped",
                    "timestamp": now,
                })
                _maybe_save(state, run_state_path)
                self._enqueue_successors(
                    node_id, successors, state, in_degree, in_queue, ready_queue
                )

        # ------------------------------------------------------------------
        # Terminal run state: determine done vs failed and update index.
        # ------------------------------------------------------------------
        final_status = "failed" if upstream_failed else "done"
        now = _utcnow_iso()

        # Load-merge-save: reload from disk to avoid overwriting a concurrent
        # 'cancelled' write before setting the terminal run-level status.
        if run_state_path is not None:
            try:
                reloaded_final = load(run_state_path)
                if reloaded_final is not None:
                    if reloaded_final.status == "cancelled":
                        log.info(
                            "Run %r was cancelled during final BFS drain; not overwriting.",
                            run_goal_id,
                        )
                        self._publish_event(run_goal_id, {
                            "type": "run_status",
                            "run_id": run_goal_id,
                            "status": "cancelled",
                            "timestamp": now,
                        })
                        return reloaded_final
                    # Merge node results into the reloaded state.
                    for nid, ns in state.nodes_executed.items():
                        reloaded_final.nodes_executed[nid] = ns
                    reloaded_final.status = final_status
                    reloaded_final.waiting_node_id = state.waiting_node_id
                    state = reloaded_final
            except (ValueError, OSError) as exc:
                log.warning(
                    "Could not reload run state for terminal merge (%s); using in-memory state.",
                    exc,
                )

        state.status = final_status
        _maybe_save(state, run_state_path)

        # Update the run index with the terminal status.
        try:
            await _run_index.update_run_status(
                space_dir, harness_id, run_goal_id,
                status=final_status, finished_at=now,
            )
        except Exception:
            log.exception(
                "Failed to update run index for %s (status=%s); continuing.",
                run_goal_id, final_status,
            )

        # Publish terminal run_status event.
        self._publish_event(run_goal_id, {
            "type": "run_status",
            "run_id": run_goal_id,
            "status": final_status,
            "timestamp": now,
        })

        return state

    # ------------------------------------------------------------------
    # Event publishing helper
    # ------------------------------------------------------------------

    def _publish_event(self, run_id: str, event: dict) -> None:
        """Publish *event* via the event worker's _publish(), if one is set."""
        if self._worker is not None:
            self._worker._publish(run_id, event)

    # ------------------------------------------------------------------
    # BFS helper — enqueue successors whose runtime in-degree reaches 0
    # ------------------------------------------------------------------

    def _enqueue_successors(
        self,
        node_id: str,
        successors: dict[str, list[str]],
        state: RunState,
        in_degree: dict[str, int],
        in_queue: set[str],
        ready_queue: deque[str],
    ) -> None:
        """Decrement runtime in-degree for each successor of *node_id*.

        When a successor's effective in-degree reaches 0 (all predecessors
        have reached a terminal state) and it is not already in the queue or
        completed, it is appended to the ready queue.

        Sorted insertion is used to preserve deterministic tie-breaking
        (matching ``_topo_sort``'s sorted-by-node-id order).
        """
        newly_ready: list[str] = []
        for succ_id in successors.get(node_id, []):
            if succ_id in state.nodes_executed or succ_id in in_queue:
                continue
            # Decrement runtime in-degree counter.
            in_degree[succ_id] = max(0, in_degree[succ_id] - 1)
            if in_degree[succ_id] == 0:
                newly_ready.append(succ_id)

        # Append in sorted order for determinism.
        for succ_id in sorted(newly_ready):
            if succ_id not in in_queue:
                ready_queue.append(succ_id)
                in_queue.add(succ_id)

    # ------------------------------------------------------------------
    # Agent node execution
    # ------------------------------------------------------------------

    async def _execute_agent_node(
        self,
        node: HarnessNode,
        node_id: str,
        run_goal_id: str,
        harness: Harness,
        space: Space,
        scope: dict[str, str],
        state: RunState,
        run_state_path: "Path | None",
    ) -> tuple[bool, "str | None", "str | None", bool]:
        """Execute an Agent node — loop-aware dispatcher.

        Returns
        -------
        (done, output, child_task_id, park)
            done:  True if the node completed successfully.
            output: the node's output string (or None on failure / park).
            child_task_id: the id of the last child task created.
            park:  True if the run should be parked in WAITING (loop escalation).
        """
        loop_config = node.data.get("loop") if node.data else None
        if not loop_config or not isinstance(loop_config, dict):
            # No loop — single execution (I5 path, backward compat).
            return await self._run_agent_once(
                node, node_id, run_goal_id, harness, space, scope, state, run_state_path,
            )

        # I6: Loop-convergence policy.
        until_cond: str | None = loop_config.get("until")
        stall_checks: list = list(loop_config.get("stall") or [])
        max_attempts: int = int(loop_config.get("max", 10))
        on_exhaust: str = str(loop_config.get("on_exhaust", "escalate"))

        # Reconcile attempt counter from persisted NodeState (resume support).
        existing_ns = state.nodes_executed.get(node_id)
        attempt: int = existing_ns.attempt if existing_ns else 0
        prior_finding_ids: list[str] = list(existing_ns.prior_finding_ids if existing_ns else [])
        prior_diff_bytes: int | None = None

        last_output: str | None = None
        last_child_task_id: str | None = None

        while True:
            attempt += 1
            log.info(
                "Node %r loop attempt %d / max=%d.", node_id, attempt, max_attempts,
            )

            done, output, child_task_id, park = await self._run_agent_once(
                node, node_id, run_goal_id, harness, space, scope, state, run_state_path,
            )
            last_output = output
            last_child_task_id = child_task_id

            if park or not done:
                # Attempt failed or was cancelled — propagate immediately.
                return done, output, child_task_id, park

            # Parse delivery_status from this attempt's output.
            ds = parse_delivery_status_block(output or "")
            current_finding_ids = _extract_finding_ids(ds)

            # Check until condition.
            if until_cond and eval_condition(until_cond, scope):
                log.info(
                    "Node %r loop: until condition met after %d attempt(s).",
                    node_id, attempt,
                )
                break

            # Check stall: recurring_findings.
            if "recurring_findings" in stall_checks:
                if current_finding_ids and set(current_finding_ids) == set(prior_finding_ids):
                    log.warning(
                        "Node %r stall: recurring_findings after %d attempt(s).",
                        node_id, attempt,
                    )
                    return self._escalate_loop(
                        node_id, run_goal_id, state, run_state_path,
                        reason=f"recurring_findings after {attempt} attempt(s)",
                    )

            # Check stall: no_diff_progress.
            if "no_diff_progress" in stall_checks and ds is not None:
                fields = ds.get("fields") or {}
                diff_bytes_raw = fields.get("diff_bytes")
                if diff_bytes_raw is not None:
                    try:
                        current_diff_bytes = int(diff_bytes_raw)
                        if prior_diff_bytes is not None and current_diff_bytes >= prior_diff_bytes:
                            log.warning(
                                "Node %r stall: no_diff_progress after %d attempt(s).",
                                node_id, attempt,
                            )
                            return self._escalate_loop(
                                node_id, run_goal_id, state, run_state_path,
                                reason=f"no_diff_progress after {attempt} attempt(s)",
                            )
                        prior_diff_bytes = current_diff_bytes
                    except (ValueError, TypeError):
                        pass  # non-numeric diff_bytes: skip no_diff_progress check

            # Check max backstop.
            if attempt >= max_attempts:
                log.warning(
                    "Node %r loop exhausted (attempt=%d, max=%d).",
                    node_id, attempt, max_attempts,
                )
                return self._escalate_loop(
                    node_id, run_goal_id, state, run_state_path,
                    reason=f"max_attempts={max_attempts} exhausted",
                )

            # Persist loop bookkeeping before next attempt (resume safety).
            prior_finding_ids = current_finding_ids
            existing = state.nodes_executed.get(node_id)
            if existing is not None:
                state.nodes_executed[node_id] = NodeState(
                    status="in_progress",
                    child_task_id=existing.child_task_id,
                    output=existing.output,
                    started_at=existing.started_at,
                    attempt=attempt,
                    prior_finding_ids=prior_finding_ids,
                )
            _maybe_save(state, run_state_path)

        # Loop exited normally (until condition met).
        return True, last_output, last_child_task_id, False

    def _escalate_loop(
        self,
        node_id: str,
        run_goal_id: str,
        state: RunState,
        run_state_path: "Path | None",
        reason: str,
    ) -> tuple[bool, None, None, bool]:
        """Park the run in WAITING when a loop exhausts without convergence.

        Sets ``state.waiting_node_id = node_id`` so the run-executor
        transitions the goal task to ``TaskState.WAITING``.  The node remains
        ``in_progress`` (not failed) per R5.
        """
        waiting_question = (
            f"Loop node '{node_id}' escalated: {reason}. "
            "Human intervention required to unblock."
        )
        log.warning(
            "Node %r loop escalation: %s. Parking run %r in WAITING.",
            node_id, reason, run_goal_id,
        )
        state.waiting_node_id = node_id
        _maybe_save(state, run_state_path)
        self._publish_event(run_goal_id, {
            "type": "node_transition",
            "node_id": node_id,
            "from_status": "in_progress",
            "to_status": "waiting",
            "timestamp": _utcnow_iso(),
            "waiting_question": waiting_question,
        })
        return False, None, None, True

    async def _run_agent_once(
        self,
        node: HarnessNode,
        node_id: str,
        run_goal_id: str,
        harness: Harness,
        space: Space,
        scope: dict[str, str],
        state: RunState,
        run_state_path: "Path | None",
    ) -> tuple[bool, "str | None", "str | None", bool]:
        """Single-attempt agent node execution (extracted from _execute_agent_node).

        Returns
        -------
        (done, output, child_task_id, park)
            park is always False from this function (park is only raised by
            the loop controller _execute_agent_node).
        """
        # 1. Interpolate prompt
        prompt_template: str = node.data.get("prompt_template", "")
        interpolated_prompt, unresolved = interpolate(
            prompt_template,
            root_vars=dict(harness.variables),
            upstream_outputs={k: v for k, v in scope.items() if k not in harness.variables},
        )
        if unresolved:
            log.warning(
                "Node %s has unresolved placeholders: %s",
                node_id, unresolved,
            )

        # 2. Resolve agent entry via tools_resolver
        agent_ref: str = node.data.get("agent_ref", "") or ""
        agent_entry = None
        if agent_ref:
            try:
                agent_entry = self.tools_resolver(space.id, agent_ref)
            except Exception:
                log.exception("tools_resolver failed for agent_ref=%r", agent_ref)

        # 3. Compose brief
        brief = compose_brief(node, interpolated_prompt, agent_entry)

        # 4. Create child Task
        try:
            child_task = await self.store.create(
                space_id=space.id,
                title=node.label or node.id,
                brief=brief,
                parent_id=run_goal_id,
            )
        except Exception as exc:
            log.exception("Failed to create child task for node %s", node_id)
            now = _utcnow_iso()
            state.nodes_executed[node_id] = NodeState(
                status="failed",
                reason=f"child_task_create_error: {exc}",
                ended_at=now,
            )
            self._publish_event(run_goal_id, {
                "type": "node_transition",
                "node_id": node_id,
                "from_status": "pending",
                "to_status": "failed",
                "timestamp": now,
            })
            _maybe_save(state, run_state_path)
            return False, None, None, False

        child_task_id = child_task.id

        # 5. Mark node in_progress and persist before running agent
        started_at = _utcnow_iso()
        state.nodes_executed[node_id] = NodeState(
            status="in_progress",
            child_task_id=child_task_id,
            started_at=started_at,
        )
        self._publish_event(run_goal_id, {
            "type": "node_transition",
            "node_id": node_id,
            "from_status": "pending",
            "to_status": "in_progress",
            "timestamp": started_at,
        })
        _maybe_save(state, run_state_path)

        # 6. Run agent via WorkerProtocol
        trace: RunTrace | None = None
        try:
            trace = await self.worker.run_agent(
                child_task_id,
                parent_run_id=run_goal_id,
            )
        except Exception as exc:
            log.exception("run_agent failed for node %s (child %s)", node_id, child_task_id)
            ended_at = _utcnow_iso()
            # Load-merge-save to avoid overwriting a concurrent cancel.
            if run_state_path is not None:
                try:
                    reloaded = load(run_state_path)
                    if reloaded is not None and reloaded.status == "cancelled":
                        return False, None, child_task_id, False
                    if reloaded is not None:
                        state.nodes_executed = reloaded.nodes_executed
                        if reloaded.status not in ("done", "failed", "cancelled"):
                            state.status = reloaded.status
                except (ValueError, OSError):
                    pass
            state.nodes_executed[node_id] = NodeState(
                status="failed",
                child_task_id=child_task_id,
                reason=f"run_agent_error: {exc}",
                started_at=started_at,
                ended_at=ended_at,
            )
            self._publish_event(run_goal_id, {
                "type": "node_transition",
                "node_id": node_id,
                "from_status": "in_progress",
                "to_status": "failed",
                "timestamp": ended_at,
            })
            _maybe_save(state, run_state_path)
            return False, None, child_task_id, False

        # 7. Finalize child via WorkerProtocol
        try:
            new_state = await self.worker.finalize_child(child_task_id, trace)
        except Exception as exc:
            log.exception("finalize_child failed for node %s", node_id)
            ended_at = _utcnow_iso()
            if run_state_path is not None:
                try:
                    reloaded = load(run_state_path)
                    if reloaded is not None and reloaded.status == "cancelled":
                        return False, None, child_task_id, False
                    if reloaded is not None:
                        state.nodes_executed = reloaded.nodes_executed
                        if reloaded.status not in ("done", "failed", "cancelled"):
                            state.status = reloaded.status
                except (ValueError, OSError):
                    pass
            state.nodes_executed[node_id] = NodeState(
                status="failed",
                child_task_id=child_task_id,
                reason=f"finalize_child_error: {exc}",
                started_at=started_at,
                ended_at=ended_at,
            )
            self._publish_event(run_goal_id, {
                "type": "node_transition",
                "node_id": node_id,
                "from_status": "in_progress",
                "to_status": "failed",
                "timestamp": ended_at,
            })
            _maybe_save(state, run_state_path)
            return False, None, child_task_id, False

        # 8. Determine node outcome
        ended_at = _utcnow_iso()
        # Load-merge-save discipline: reload before writing terminal node state.
        if run_state_path is not None:
            try:
                reloaded = load(run_state_path)
                if reloaded is not None and reloaded.status == "cancelled":
                    log.info(
                        "Run %r cancelled after node %r completed; not persisting result.",
                        run_goal_id, node_id,
                    )
                    return False, None, child_task_id, False
                if reloaded is not None:
                    # Preserve any concurrent writes to other nodes.
                    state.nodes_executed = reloaded.nodes_executed
                    if reloaded.status not in ("done", "failed", "cancelled"):
                        state.status = reloaded.status
            except (ValueError, OSError) as exc:
                log.warning(
                    "Could not reload run state post-node (%s); continuing with in-memory state.",
                    exc,
                )

        if new_state == TaskState.DONE:
            output_value = trace.final_text_snippet if trace else ""
            # Flat key — preserves existing scope convention.
            scope[node_id] = output_value
            # R12: enrich scope with structured delivery_status fields so that
            # conditional edges can branch on agent output (G3.3 routing unblock).
            _enrich_scope_from_delivery_status(node_id, output_value, scope)
            state.nodes_executed[node_id] = NodeState(
                status="done",
                child_task_id=child_task_id,
                output=output_value,
                started_at=started_at,
                ended_at=ended_at,
            )
            self._publish_event(run_goal_id, {
                "type": "node_transition",
                "node_id": node_id,
                "from_status": "in_progress",
                "to_status": "done",
                "timestamp": ended_at,
            })
            _maybe_save(state, run_state_path)
            log.info("Node %s completed successfully.", node_id)
            return True, output_value, child_task_id, False
        else:
            # Node did not reach DONE — fail-fast.
            state.nodes_executed[node_id] = NodeState(
                status="failed",
                child_task_id=child_task_id,
                reason=f"child_task_ended_in_{new_state.value}",
                started_at=started_at,
                ended_at=ended_at,
            )
            self._publish_event(run_goal_id, {
                "type": "node_transition",
                "node_id": node_id,
                "from_status": "in_progress",
                "to_status": "failed",
                "timestamp": ended_at,
            })
            _maybe_save(state, run_state_path)
            log.warning(
                "Node %s failed (child %s ended in %s); activating fail-fast.",
                node_id, child_task_id, new_state.value,
            )
            return False, None, child_task_id, False

    # ------------------------------------------------------------------
    # Decision node execution
    # ------------------------------------------------------------------

    async def _execute_decision_node(
        self,
        node: HarnessNode,
        node_id: str,
        harness: Harness,
        scope: dict[str, str],
        state: RunState,
        run_state_path: "Path | None",
        edges: list[HarnessEdge],
    ) -> "str | None":
        """Evaluate a Decision node and return the chosen edge id, or None on failure."""
        state.nodes_executed[node_id] = NodeState(status="in_progress")
        _maybe_save(state, run_state_path)

        predecessors_state = _get_predecessors_state(node_id, harness, state)

        # Find the most-recent predecessor's run trace from scope (not available
        # directly — pass None and let decision layer use exit_reason/text layers).
        # The executor does not cache RunTrace objects; the decision evaluator will
        # fall through to the regex / variable layers.
        run_trace: RunTrace | None = None

        try:
            chosen_edge_id = evaluate_decision(
                node=node,
                predecessors_state=predecessors_state,
                scope=scope,
                run_trace=run_trace,
                outgoing_edges=edges,
            )
        except ValueError as exc:
            log.warning(
                "Decision node %r evaluation failed: %s; marking failed.",
                node_id, exc,
            )
            state.nodes_executed[node_id] = NodeState(
                status="failed",
                reason=f"decision_error: {exc}",
            )
            _maybe_save(state, run_state_path)
            return None

        log.info("Decision node %r chose edge %r.", node_id, chosen_edge_id)
        state.nodes_executed[node_id] = NodeState(
            status="done",
            output=chosen_edge_id,
        )
        _maybe_save(state, run_state_path)
        return chosen_edge_id

    # ------------------------------------------------------------------
    # Wait node execution
    # ------------------------------------------------------------------

    async def _execute_wait_node(
        self,
        node: HarnessNode,
        node_id: str,
        state: RunState,
        run_state_path: "Path | None",
        space: Space,
    ) -> bool:
        """Evaluate a Wait node.

        Returns
        -------
        bool
            True if the executor should park (human mode); False if traversal
            should continue (timed mode completed).
        """
        mode = node.data.get("mode", "human")

        if mode == "human":
            state.nodes_executed[node_id] = NodeState(status="in_progress")
            _maybe_save(state, run_state_path)
            outcome = enter_wait(node, state)
            # waiting_node_id is now set on state by enter_wait().
            log.info(
                "Wait node %r (human): parking run %r. waiting_question=%r",
                node_id, state.run_id, outcome.waiting_question,
            )
            # Persist the updated state (with waiting_node_id set) before returning.
            _maybe_save(state, run_state_path)
            # Return True to signal the executor to stop and return.
            return True
        else:
            # Timed mode.
            # Read prior wake_at BEFORE overwriting node state so resume preserves it.
            prior_node_state = state.nodes_executed.get(node_id)
            wake_at: str | None = prior_node_state.wake_at if prior_node_state else None

            if wake_at is None:
                # First entry: compute absolute wake time and persist before sleeping.
                raw: float | int | None = node.data.get("duration_seconds")
                duration: float = float(raw) if raw is not None else 0.0
                wake_at = (datetime.now(timezone.utc) + timedelta(seconds=duration)).isoformat()

            state.nodes_executed[node_id] = NodeState(status="in_progress", wake_at=wake_at)
            _maybe_save(state, run_state_path)

            log.info("Wait node %r (timed): sleeping until %s.", node_id, wake_at)
            await await_timed_wait(node, wake_at=wake_at)
            state.nodes_executed[node_id] = NodeState(status="done")
            _maybe_save(state, run_state_path)
            log.info("Wait node %r (timed): sleep complete.", node_id)
            return False

    # ------------------------------------------------------------------
    # Aggregator node execution
    # ------------------------------------------------------------------

    async def _execute_aggregator_node(
        self,
        node: HarnessNode,
        node_id: str,
        harness: Harness,
        state: RunState,
        run_state_path: "Path | None",
    ) -> tuple[bool, bool]:
        """Evaluate an Aggregator node.

        Returns
        -------
        (ready, failed)
            ready: True if the aggregator has fired (done verdict).
            failed: True if the aggregator has failed verdict.
            (False, False) means verdict is still pending.
        """
        mode = node.data.get("mode", "all")
        predecessors_state = _get_predecessors_state(node_id, harness, state)

        if not predecessors_state:
            # No predecessors — vacuously done for mode='all', pending for mode='any'.
            if mode == "any":
                log.warning(
                    "Aggregator node %r (any) has no predecessors; marking done.", node_id
                )
            state.nodes_executed[node_id] = NodeState(
                status="in_progress",
            )

        verdict = aggregator_ready(node, predecessors_state)
        log.debug("Aggregator node %r: verdict=%r mode=%r", node_id, verdict, mode)

        if verdict == AggregatorVerdict.done:
            output = compose_output(verdict, predecessors_state, mode)
            state.nodes_executed[node_id] = NodeState(
                status="done",
                output=str(output),
            )
            _maybe_save(state, run_state_path)
            log.info("Aggregator node %r fired (done).", node_id)
            return True, False

        elif verdict == AggregatorVerdict.failed:
            output = compose_output(verdict, predecessors_state, mode)
            state.nodes_executed[node_id] = NodeState(
                status="failed",
                reason=f"aggregator_failed: {output}",
            )
            _maybe_save(state, run_state_path)
            log.warning("Aggregator node %r failed.", node_id)
            return False, True

        else:
            # pending — do not persist a state change; aggregator is not ready.
            log.debug("Aggregator node %r is pending; not enqueuing successors.", node_id)
            return False, False


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _maybe_save(state: RunState, path: "Path | None") -> None:
    """Persist *state* atomically if *path* is set; silently skip otherwise."""
    if path is None:
        return
    try:
        save_atomic(path, state)
    except Exception:
        log.exception("Failed to persist run state to %s", path)


def _enrich_scope_from_delivery_status(
    node_id: str,
    output: str,
    scope: dict[str, str],
) -> None:
    """Populate dotted-path scope keys from a ```delivery_status block.

    After a node reaches DONE, parses the agent's final_text_snippet for a
    ```delivery_status JSON fence and adds the following keys to *scope*:
      - ``"<node_id>.status"``        — normalised-lowercase status string
      - ``"<node_id>.fields.<name>"`` — one key per entry in ``fields`` dict

    The existing flat key ``scope[node_id]`` is NOT touched — this function
    only adds new dotted-path keys (R12, G3.3 routing unblock).

    Fields values are coerced to ``str`` so the scope stays ``dict[str, str]``.
    """
    if not output:
        return
    ds = parse_delivery_status_block(output)
    if ds is None:
        return
    status_val = ds.get("status")
    if isinstance(status_val, str):
        scope[f"{node_id}.status"] = status_val  # already lowercase from parser
    fields = ds.get("fields")
    if isinstance(fields, dict):
        for k, v in fields.items():
            scope[f"{node_id}.fields.{k}"] = str(v)
    log.debug(
        "_enrich_scope_from_delivery_status: node=%r status=%r fields=%r",
        node_id, status_val, list(fields.keys()) if isinstance(fields, dict) else None,
    )


def _extract_finding_ids(ds: "dict | None") -> list[str]:
    """Extract finding IDs from a parsed delivery_status dict.

    Precedence: ``fields.finding_ids`` (list[str]) over ``fields.findings[].id``.
    Returns an empty list when the dict is None or contains no recognisable IDs.
    """
    if ds is None:
        return []
    fields = ds.get("fields")
    if not isinstance(fields, dict):
        return []
    fids = fields.get("finding_ids")
    if isinstance(fids, list) and fids:
        return [str(f) for f in fids]
    findings = fields.get("findings")
    if isinstance(findings, list):
        return [str(f.get("id", "")) for f in findings if isinstance(f, dict) and f.get("id")]
    return []
