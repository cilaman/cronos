"""
backend/app/harnesses/executor — HarnessExecutor: DAG-based harness node runner.

The HarnessExecutor walks the harness graph in topological order (Kahn's
algorithm over Harness.edges), executes each node sequentially via ``await``,
and persists execution state atomically after each node completes.

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

* Control-flow nodes — any non-agent NodeType is treated as a pass-through
  stub for now: recorded as ``status='skipped'`` with
  ``reason='control_flow_stub'`` and all outgoing edges are followed.

* Variable scope — root vars are merged first; upstream node outputs override
  on key collision (per interpolate.py precedence rule).

* Resume — before re-executing a node found in an existing RunState with
  ``status='in_progress'``, the executor queries the TaskStore for the
  recorded ``child_task_id``; if that task exists and is DONE, the node is
  accepted as done without re-execution.
"""

from __future__ import annotations

import logging
from collections import deque
from pathlib import Path
from typing import Any, Callable, Protocol, runtime_checkable

import os

from ..models import Space, TaskState
from ..storage import TaskStore
from ..trace_parser import RunTrace
from .brief_composer import compose_brief
from .interpolate import interpolate
from .model import Harness, HarnessNode, NodeType
from .run_state import NodeState, RunState, load, save_atomic

_DATA_DIR = Path(os.environ.get("CRONOS_DATA_DIR", "/data"))

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


# ---------------------------------------------------------------------------
# Topo-sort helpers
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
# HarnessExecutor
# ---------------------------------------------------------------------------


class HarnessExecutor:
    """Execute a Harness graph node by node in topological order.

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
    """

    def __init__(
        self,
        store: TaskStore,
        worker_protocol: WorkerProtocol,
        tools_resolver: Callable,
    ) -> None:
        self.store = store
        self.worker = worker_protocol
        self.tools_resolver = tools_resolver

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    async def execute(
        self,
        run_goal_id: str,
        harness: Harness,
        space: Space,
    ) -> RunState:
        """Execute *harness* sequentially, persisting state after each node.

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
        # Compute run-state file path.  Space.id maps to the directory
        # {DATA_DIR}/spaces/{space.id}/.cronos/harness-runs/{run_goal_id}.json
        run_state_path: Path | None = (
            _DATA_DIR / "spaces" / space.id / ".cronos" / "harness-runs" / f"{run_goal_id}.json"
        )

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

        # ------------------------------------------------------------------
        # Reconcile in_progress nodes before execution begins
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

        # ------------------------------------------------------------------
        # Topological execution
        # ------------------------------------------------------------------
        ordered_nodes = _topo_sort(harness)
        upstream_failed = False

        for node in ordered_nodes:
            node_id = node.id

            # Skip nodes already completed from a prior run.
            existing_ns = state.nodes_executed.get(node_id)
            if existing_ns is not None and existing_ns.status in ("done", "skipped", "failed"):
                # Restore output to scope so downstream nodes can use it.
                if existing_ns.output and existing_ns.status == "done":
                    scope[node_id] = existing_ns.output
                continue

            # Fail-fast: upstream failure marks remaining nodes as skipped.
            if upstream_failed:
                state.nodes_executed[node_id] = NodeState(
                    status="skipped",
                    reason="upstream_failed",
                )
                _maybe_save(state, run_state_path)
                continue

            # ------------------------------------------------------------------
            # Control-flow nodes — stub pass-through
            # ------------------------------------------------------------------
            if node.type != NodeType.agent:
                log.debug("Node %s is control-flow (%s) — stub pass-through.", node_id, node.type)
                state.nodes_executed[node_id] = NodeState(
                    status="skipped",
                    reason="control_flow_stub",
                )
                _maybe_save(state, run_state_path)
                continue

            # ------------------------------------------------------------------
            # Agent node execution
            # ------------------------------------------------------------------
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
                state.nodes_executed[node_id] = NodeState(
                    status="failed",
                    reason=f"child_task_create_error: {exc}",
                )
                _maybe_save(state, run_state_path)
                upstream_failed = True
                continue

            child_task_id = child_task.id

            # 5. Mark node in_progress and persist before running agent
            state.nodes_executed[node_id] = NodeState(
                status="in_progress",
                child_task_id=child_task_id,
            )
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
                # Attempt to finalize the child with a failed trace if possible.
                state.nodes_executed[node_id] = NodeState(
                    status="failed",
                    child_task_id=child_task_id,
                    reason=f"run_agent_error: {exc}",
                )
                _maybe_save(state, run_state_path)
                upstream_failed = True
                continue

            # 7. Finalize child via WorkerProtocol
            try:
                new_state = await self.worker.finalize_child(child_task_id, trace)
            except Exception as exc:
                log.exception("finalize_child failed for node %s", node_id)
                state.nodes_executed[node_id] = NodeState(
                    status="failed",
                    child_task_id=child_task_id,
                    reason=f"finalize_child_error: {exc}",
                )
                _maybe_save(state, run_state_path)
                upstream_failed = True
                continue

            # 8. Determine node outcome
            if new_state == TaskState.DONE:
                output_value = trace.final_text_snippet if trace else ""
                scope[node_id] = output_value
                state.nodes_executed[node_id] = NodeState(
                    status="done",
                    child_task_id=child_task_id,
                    output=output_value,
                )
                _maybe_save(state, run_state_path)
                log.info("Node %s completed successfully.", node_id)
            else:
                # Node did not reach DONE — fail-fast.
                state.nodes_executed[node_id] = NodeState(
                    status="failed",
                    child_task_id=child_task_id,
                    reason=f"child_task_ended_in_{new_state.value}",
                )
                _maybe_save(state, run_state_path)
                upstream_failed = True
                log.warning(
                    "Node %s failed (child %s ended in %s); activating fail-fast.",
                    node_id, child_task_id, new_state.value,
                )

        return state


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
