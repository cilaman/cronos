"""
runner/dispatch.py — Per-node dispatch logic for the cyclic work-list runner.

Harvests all 8 node-kind dispatch patterns from HarnessExecutor:
  agent      → executor.dispatchAgent (async in real adapter; sync call here
               using asyncio.run when called from synchronous runner)
  gate       → executor.runGate → GateResult
  exec       → executor.runExec → ExecResult (shell command to completion, no LLM)
  human      → executor.escalate + park (blocked)
  decision   → edge-routing only; no external dispatch; always "done"
  wait(human)→ executor.escalate + park (blocked)
  wait(timed)→ executor.escalate (timed sleep deferred; escalate for safety)
  aggregator → inspect predecessor NodeState; all/any verdict
  trigger    → immediate done (fires once)

NodeOutcome is the return type; the runner persists it into WorkflowState.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from ir import IRNode
from state_types import WorkflowState

if TYPE_CHECKING:
    from interface import ExecutorInterface

log = logging.getLogger(__name__)


@dataclass
class NodeOutcome:
    """Result of dispatching a single node.

    The runner writes this into WorkflowState.nodes[node_id] after each dispatch.
    """

    status: str  # "done" | "blocked" | "failed" | "escalated"
    attempt: int = 0
    artifact_paths: list[str] = field(default_factory=list)
    gate: dict[str, Any] | None = None
    fields: dict[str, Any] = field(default_factory=dict)


def dispatch_node(
    node: IRNode,
    scope: dict[str, Any],
    executor: "ExecutorInterface",
    state: WorkflowState,
    incoming: dict[str, list[str]] | None = None,
) -> NodeOutcome:
    """Dispatch *node* against *executor*; return a NodeOutcome.

    Reads current attempt count from *state* (for loop tracking) and
    delegates to the appropriate per-kind handler.

    *incoming* maps node_id → predecessor node ids (from the graph's edges).
    Only the gate handler needs it (to read its upstream producer's
    artifact_paths); the other kinds ignore it.
    """
    current_ns = state.nodes.get(node.id)
    attempt = (current_ns.attempt if current_ns else 0) + 1

    kind = node.kind

    # Gate is the only kind that needs predecessor context (a gate produces no
    # artifacts of its own — it verifies the upstream node's).  Dispatch it
    # explicitly so the other handlers keep their uniform signature.
    if kind == "gate":
        return _dispatch_gate(
            node=node,
            scope=scope,
            executor=executor,
            state=state,
            attempt=attempt,
            incoming=incoming,
        )

    handlers = {
        "agent": _dispatch_agent,
        "exec": _dispatch_exec,
        "human": _dispatch_human,
        "decision": _dispatch_decision,
        "wait": _dispatch_wait,
        "aggregator": _dispatch_aggregator,
        "trigger": _dispatch_trigger,
    }
    handler = handlers.get(kind)
    if handler is None:
        log.error("dispatch_node: unknown kind %r for node %r", kind, node.id)
        return NodeOutcome(status="failed", attempt=attempt)

    return handler(node=node, scope=scope, executor=executor, state=state, attempt=attempt)


# ---------------------------------------------------------------------------
# Per-kind handlers
# ---------------------------------------------------------------------------


def _dispatch_agent(
    node: IRNode,
    scope: dict[str, Any],
    executor: "ExecutorInterface",
    state: WorkflowState,
    attempt: int,
) -> NodeOutcome:
    """Dispatch an agent node via executor.dispatchAgent.

    The executor.dispatchAgent may be async (CronosAdapter) or sync (NullRuntime
    subclasses).  We detect and handle both cases.
    """
    agent_ref: str = node.data.get("agent", node.id)
    inputs: dict[str, Any] = {
        "scope": scope,
        "node_id": node.id,
        "attempt": attempt,
        "model": node.data.get("model"),
        "produces": node.data.get("produces"),
        "tools": node.data.get("tools"),
        "recon": node.data.get("recon"),
        "inputs": node.data.get("inputs"),
    }

    try:
        result = executor.dispatchAgent(agent_ref, inputs)
        # Handle coroutine (async adapter).
        if asyncio.iscoroutine(result):
            result = asyncio.get_event_loop().run_until_complete(result)
    except Exception as exc:
        log.error("dispatch_agent: node %r raised %s", node.id, exc)
        return NodeOutcome(status="failed", attempt=attempt)

    from results import AgentResult

    if not isinstance(result, AgentResult):
        log.error("dispatch_agent: expected AgentResult, got %r", type(result))
        return NodeOutcome(status="failed", attempt=attempt)

    if result.status in ("blocked",):
        return NodeOutcome(status="blocked", attempt=attempt, fields=result.fields)

    if result.status == "failed":
        return NodeOutcome(status="failed", attempt=attempt, fields=result.fields)

    return NodeOutcome(
        status="done",
        attempt=attempt,
        artifact_paths=result.artifact_paths,
        fields=result.fields,
    )


def _dispatch_gate(
    node: IRNode,
    scope: dict[str, Any],
    executor: "ExecutorInterface",
    state: WorkflowState,
    attempt: int,
    incoming: dict[str, list[str]] | None = None,
) -> NodeOutcome:
    """Dispatch a gate node via executor.runGate."""
    gate_config: dict[str, Any] = dict(node.data)
    gate_config["id"] = node.id

    # A gate produces no artifacts of its own — it verifies its upstream
    # producer's.  Collect artifact_paths from the (done) predecessor nodes so
    # the executor can derive the artifact class/slug and locate the report.
    # (Reading the gate node's own paths — as this used to — always yielded []
    # and left schema checks unable to route: "requires 'agent' and 'slug'".)
    artifact_paths: list[str] = []
    for src in (incoming or {}).get(node.id, []):
        pred = state.nodes.get(src)
        if pred is not None and pred.status == "done":
            artifact_paths.extend(pred.artifact_paths)
    if not artifact_paths:
        # Backward-compat fallback: a gate node that carries its own paths
        # (e.g. hand-seeded in tests).
        current_ns = state.nodes.get(node.id)
        if current_ns:
            artifact_paths = list(current_ns.artifact_paths)

    try:
        result = executor.runGate(gate_config, artifact_paths)
    except Exception as exc:
        log.error("dispatch_gate: node %r raised %s", node.id, exc)
        return NodeOutcome(status="failed", attempt=attempt)

    from results import GateResult

    if not isinstance(result, GateResult):
        log.error("dispatch_gate: expected GateResult, got %r", type(result))
        return NodeOutcome(status="failed", attempt=attempt)

    gate_dict: dict[str, Any] = {
        "decision": result.decision,
        "errors": result.errors,
        "evidence": result.evidence,
    }

    return NodeOutcome(
        status="done",
        attempt=attempt,
        gate=gate_dict,
        fields={"decision": result.decision},
    )


def _dispatch_exec(
    node: IRNode,
    scope: dict[str, Any],
    executor: "ExecutorInterface",
    state: WorkflowState,
    attempt: int,
) -> NodeOutcome:
    """Dispatch an exec node — run a shell command to completion via executor.runExec.

    Unlike an agent node this spawns no LLM: the runner blocks synchronously on the
    command, so there is nothing to background and no scheduled-wakeup dead-end (P1).
    Exit 0 → done; any other exit → failed. The captured output is written as the
    node's artifact so a downstream gate can read a real result.
    """
    command = node.data.get("command")
    if not command:
        log.error("dispatch_exec: node %r has no 'command'", node.id)
        return NodeOutcome(status="failed", attempt=attempt)

    inputs: dict[str, Any] = {
        "scope": scope,
        "node_id": node.id,
        "attempt": attempt,
        "produces": node.data.get("produces"),
        "timeout": node.data.get("timeout"),
        "fail_on_nonzero": node.data.get("fail_on_nonzero", True),
    }

    try:
        result = executor.runExec(node.id, command, inputs)
        if asyncio.iscoroutine(result):
            result = asyncio.get_event_loop().run_until_complete(result)
    except Exception as exc:
        log.error("dispatch_exec: node %r raised %s", node.id, exc)
        return NodeOutcome(status="failed", attempt=attempt)

    from results import ExecResult

    if not isinstance(result, ExecResult):
        log.error("dispatch_exec: expected ExecResult, got %r", type(result))
        return NodeOutcome(status="failed", attempt=attempt)

    artifact_paths = [result.artifact_path] if result.artifact_path else []
    return NodeOutcome(
        status="done" if result.status == "done" else "failed",
        attempt=attempt,
        artifact_paths=artifact_paths,
        fields={"exit_code": result.exit_code},
    )


def _dispatch_human(
    node: IRNode,
    scope: dict[str, Any],
    executor: "ExecutorInterface",
    state: WorkflowState,
    attempt: int,
) -> NodeOutcome:
    """Dispatch a human node — escalate (park the run, wait for human input)."""
    prompt: str = node.data.get("prompt", "Human input required.")
    reason = f"[human] {node.id}: {prompt}"
    try:
        executor.escalate(node.id, reason)
    except Exception as exc:
        log.error("dispatch_human: escalate raised %s", exc)
    return NodeOutcome(status="blocked", attempt=attempt, fields={"prompt": prompt})


def _dispatch_decision(
    node: IRNode,
    scope: dict[str, Any],
    executor: "ExecutorInterface",
    state: WorkflowState,
    attempt: int,
) -> NodeOutcome:
    """Dispatch a decision node — edge-routing only, no external call."""
    return NodeOutcome(status="done", attempt=attempt)


def _dispatch_wait(
    node: IRNode,
    scope: dict[str, Any],
    executor: "ExecutorInterface",
    state: WorkflowState,
    attempt: int,
) -> NodeOutcome:
    """Dispatch a wait node.

    human mode  → escalate + block (mirrors HarnessExecutor enter_wait).
    timed mode  → escalate with reason (sleep semantics deferred; safe default).
    """
    mode: str = node.data.get("mode", "human")
    if mode == "human":
        prompt: str = node.data.get("prompt", "Waiting for human input.")
        reason = f"[wait/human] {node.id}: {prompt}"
        try:
            executor.escalate(node.id, reason)
        except Exception as exc:
            log.error("dispatch_wait: escalate raised %s", exc)
        return NodeOutcome(status="blocked", attempt=attempt, fields={"mode": "human"})

    # timed mode — escalate conservatively (actual sleep would need async context).
    max_wait: int = node.data.get("max_wait_seconds", 60)
    reason = f"[wait/timed] {node.id}: max_wait_seconds={max_wait}"
    try:
        executor.escalate(node.id, reason)
    except Exception as exc:
        log.error("dispatch_wait(timed): escalate raised %s", exc)
    return NodeOutcome(status="escalated", attempt=attempt, fields={"mode": "timed"})


def _dispatch_aggregator(
    node: IRNode,
    scope: dict[str, Any],
    executor: "ExecutorInterface",
    state: WorkflowState,
    attempt: int,
) -> NodeOutcome:
    """Dispatch an aggregator node.

    mode='all'  → done only if ALL predecessors done; any failure → failed.
    mode='any'  → done if ANY predecessor done; failed only if ALL fail.
    """
    mode: str = node.data.get("mode", "all")

    # Find predecessor statuses from the node's data or from state.
    # The aggregator's predecessor list is encoded in node.data['inputs']['from']
    # or derived from edges in the graph (passed via state).  We read from
    # the state directly (predecessor ids must already be in state.nodes).
    pred_ids: list[str] = node.data.get("inputs", {}).get("from", [])

    if not pred_ids:
        # No predecessors listed — treat as done immediately.
        return NodeOutcome(status="done", attempt=attempt)

    pred_statuses: list[str] = []
    for pid in pred_ids:
        ns = state.nodes.get(pid)
        pred_statuses.append(ns.status if ns else "pending")

    if mode == "all":
        if all(s == "done" for s in pred_statuses):
            return NodeOutcome(status="done", attempt=attempt)
        if any(s == "failed" for s in pred_statuses):
            return NodeOutcome(status="failed", attempt=attempt)
        # Not all done yet — pending (caller should not have dispatched yet,
        # but return a safe value).
        return NodeOutcome(status="blocked", attempt=attempt)

    if mode == "any":
        if any(s == "done" for s in pred_statuses):
            return NodeOutcome(status="done", attempt=attempt)
        if all(s == "failed" for s in pred_statuses):
            return NodeOutcome(status="failed", attempt=attempt)
        return NodeOutcome(status="blocked", attempt=attempt)

    # Unknown mode — fail safely.
    log.error("dispatch_aggregator: unknown mode %r for node %r", mode, node.id)
    return NodeOutcome(status="failed", attempt=attempt)


def _dispatch_trigger(
    node: IRNode,
    scope: dict[str, Any],
    executor: "ExecutorInterface",
    state: WorkflowState,
    attempt: int,
) -> NodeOutcome:
    """Dispatch a trigger node — immediate done (fires once)."""
    return NodeOutcome(status="done", attempt=attempt)
