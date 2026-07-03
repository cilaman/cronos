"""
runner/scope.py — Scope dict builder for the cyclic work-list runner.

The scope dict is rebuilt from scratch on every work-list iteration to avoid
stale-scope bugs after back-edge resets (design risk mitigation).

Convention (load-bearing — must match dispatch.py and loop.py):
  {node_id}.fields.{key}   — agent output field value (typed scalar)
  {node_id}.status         — node status string
  {node_id}.decision       — gate/decision node outcome string

Typed scope (R3 — kills D3): field values keep their native scalar type
(bool/int/float/str, plus None) instead of being ``str()``-coerced, so a
JSON boolean emitted by an agent (``fields: {"has_ui": true}``) routes
``analyze.fields.has_ui == true`` edges correctly.  ``lib.conditions``
compares typed values; hosts that need a purely textual view must render
via ``lib.conditions.canonicalize_scope`` (booleans → ``true``/``false``,
numbers unquoted), never ``str()``.
"""
from __future__ import annotations

from typing import Any

from delivery_workflow.state_types import NodeState, WorkflowState

#: Scalar types carried through the scope untouched.
_SCALAR_TYPES = (bool, int, float, str)


#: Node statuses that contribute to the scope.  ``done`` is the normal
#: terminal; ``needs_fix`` is a gate's non-proceed terminal (R9/D11 — the
#: runner writes it as the REAL node status) whose ``{gate}.decision`` must
#: stay routable, or the spec's fix edges (``g-x.decision != 'proceed'``)
#: could never fire.
_SCOPED_STATUSES = ("done", "needs_fix")


def build_scope(state: WorkflowState, scope_base: dict[str, Any] | None = None) -> dict[str, Any]:
    """Build a flat scope dict from completed nodes in *state*.

    Only nodes with a terminal, routable status ('done', or 'needs_fix' for a
    gate's non-proceed decision — R9) contribute to the scope.  Nodes with
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
    dict[str, Any]
        Flat scope whose values are typed scalars (bool/int/float/str/None).
        Non-scalar field values (lists, dicts) fall back to ``str()``.
    """
    scope: dict[str, Any] = dict(scope_base or {})

    for node_id, ns in state.nodes.items():
        if ns.status not in _SCOPED_STATUSES:
            continue
        _emit_node_scope(node_id, ns, scope)

    return scope


def _emit_node_scope(node_id: str, ns: NodeState, scope: dict[str, Any]) -> None:
    """Write a single terminal (done/needs_fix) node's state into *scope* in-place."""
    scope[f"{node_id}.status"] = ns.status

    # Gate outcome (stored in ns.gate dict under "decision" key).
    if ns.gate is not None:
        decision = str(ns.gate.get("decision", ""))
        if decision:
            scope[f"{node_id}.decision"] = decision

    # Agent/arbitrary output fields — typed scalars pass through (R3).
    if ns.fields:
        for key, val in ns.fields.items():
            if val is None or isinstance(val, _SCALAR_TYPES):
                scope[f"{node_id}.fields.{key}"] = val
            else:
                # Non-scalar (list/dict) — no scalar model; keep the legacy
                # textual fallback so `in`-style conditions stay evaluable.
                scope[f"{node_id}.fields.{key}"] = str(val)
