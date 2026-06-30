"""
runner/scope.py — Scope dict builder for the cyclic work-list runner.

The scope dict is rebuilt from scratch on every work-list iteration to avoid
stale-scope bugs after back-edge resets (design risk mitigation).

Convention (load-bearing — must match dispatch.py and loop.py):
  {node_id}.fields.{key}   — agent output field value (str)
  {node_id}.status         — node status string
  {node_id}.decision       — gate/decision node outcome string
"""
from __future__ import annotations

from state_types import NodeState, WorkflowState


def build_scope(state: WorkflowState, scope_base: dict[str, str] | None = None) -> dict[str, str]:
    """Build a flat scope dict from completed nodes in *state*.

    Only nodes whose status == 'done' contribute to the scope.  Nodes with
    other statuses (pending, running, failed, etc.) are ignored.

    Parameters
    ----------
    state:
        The current WorkflowState.  ``state.nodes`` is the authoritative
        source; it maps node_id → NodeState.
    scope_base:
        Optional dict of root-level variables (from IRGraph.variables) that
        serve as the base layer.  Node outputs override on key collision.

    Returns
    -------
    dict[str, str]
        Flat scope where all values are strings (condition evaluator requires
        ``dict[str, str]``).
    """
    scope: dict[str, str] = dict(scope_base or {})

    for node_id, ns in state.nodes.items():
        if ns.status != "done":
            continue
        _emit_node_scope(node_id, ns, scope)

    return scope


def _emit_node_scope(node_id: str, ns: NodeState, scope: dict[str, str]) -> None:
    """Write a single done node's state into *scope* in-place."""
    scope[f"{node_id}.status"] = ns.status

    # Gate outcome (stored in ns.gate dict under "decision" key).
    if ns.gate is not None:
        decision = str(ns.gate.get("decision", ""))
        if decision:
            scope[f"{node_id}.decision"] = decision

    # Agent/arbitrary output fields.
    if ns.fields:
        for key, val in ns.fields.items():
            scope[f"{node_id}.fields.{key}"] = str(val)
