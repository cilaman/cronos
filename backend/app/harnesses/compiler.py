"""
backend/app/harnesses/compiler — Compiler B: pure Harness → IRGraph translation.

This module contains a single public function:

    compile(harness: Harness) -> IRGraph

It translates the Cronos harness data model (HarnessNode, HarnessEdge, Harness)
into the portable Intermediate Representation (IRNode, IREdge, IRGraph) consumed
by the delivery-workflow runner.

Import boundary (R13): this file imports ONLY from:
  - .model  (Harness, HarnessNode, HarnessEdge, NodeType)
  - ir       (IRNode, IREdge, IRGraph, LoopPolicy) via packages/delivery-workflow

No app.* imports, no runner/lib/adapters imports.
"""

from __future__ import annotations

import logging
from typing import Literal

from delivery_workflow.ir import IREdge, IRGraph, IRNode, LoopPolicy

from .model import Harness, NodeType  # noqa: E402

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Node-type mapping
# ---------------------------------------------------------------------------

# Maps Cronos NodeType enum values to IR kind strings.
# Wait nodes require additional disambiguation (see _node_kind).
_SIMPLE_KIND_MAP: dict[str, Literal["agent", "trigger", "decision", "aggregator"]] = {
    NodeType.agent.value: "agent",
    NodeType.trigger.value: "trigger",
    NodeType.decision.value: "decision",
    NodeType.aggregator.value: "aggregator",
}

# Wait-node mode → IR kind table (R2).
_WAIT_KIND_MAP: dict[str, Literal["human", "wait"]] = {
    "human": "human",
    "timed": "wait",
}


def _node_kind(node_type: NodeType, data: dict) -> str:
    """Return the IR kind string for a Cronos node.

    For all node types except ``wait``, the mapping is 1:1 via
    ``_SIMPLE_KIND_MAP``.

    For wait nodes, ``data.mode`` drives the disambiguation (R2):
      - ``'human'`` → ``'human'``
      - ``'timed'`` → ``'wait'``
      - absent / unknown → ``'wait'`` with a warning log

    Parameters
    ----------
    node_type:
        The ``NodeType`` enum value of the Cronos node.
    data:
        The node's ``data`` dict.

    Returns
    -------
    str
        An IR kind string accepted by ``IRNode.kind``.
    """
    if node_type != NodeType.wait:
        return _SIMPLE_KIND_MAP[node_type.value]

    # Wait-node disambiguation.
    mode: str | None = data.get("mode") if data else None
    if mode is None:
        log.warning(
            "Wait node has no 'mode' in data; defaulting IR kind to 'wait'. "
            "Set data.mode='human' or data.mode='timed' to suppress this warning."
        )
        return "wait"

    kind = _WAIT_KIND_MAP.get(mode)
    if kind is None:
        log.warning(
            "Wait node has unrecognised data.mode=%r; defaulting IR kind to 'wait'.",
            mode,
        )
        return "wait"

    return kind


# ---------------------------------------------------------------------------
# LoopPolicy construction
# ---------------------------------------------------------------------------

_DEFAULT_LOOP_MAX = 10  # R3: default max (NOT the runner's default of 5)


def _build_loop_policy(loop_data: dict) -> LoopPolicy:
    """Construct a LoopPolicy from a harness agent node's ``loop`` sub-dict.

    Parameters
    ----------
    loop_data:
        The ``loop`` sub-dict from an agent node's ``data`` field.
        Expected keys: ``until`` (str), ``stall`` (list[str]),
        ``max`` (int), ``on_exhaust`` (str).

    Returns
    -------
    LoopPolicy
        Populated from *loop_data*.  Absent keys use the Cronos-layer
        defaults (``max=10``, ``on_exhaust='escalate'``).
    """
    until: str = str(loop_data.get("until", ""))
    stall: list[str] = list(loop_data.get("stall") or [])
    max_iter: int = int(loop_data.get("max", _DEFAULT_LOOP_MAX))
    on_exhaust: str = str(loop_data.get("on_exhaust", "escalate"))
    return LoopPolicy(
        until=until,
        stall=stall,
        max=max_iter,
        on_exhaust=on_exhaust,  # type: ignore[arg-type]
    )


# ---------------------------------------------------------------------------
# Public compile() function
# ---------------------------------------------------------------------------


def compile(harness: Harness) -> IRGraph:  # noqa: A001
    """Translate a Cronos Harness into a portable IRGraph.

    This is a pure function (no I/O, no app-runtime side-effects).  It maps:

    - ``HarnessNode``  → ``IRNode``  (1:1, with kind disambiguation for wait nodes)
    - ``HarnessEdge``  → ``IREdge``  (condition → when, source.port_id → port)
    - ``Harness.variables`` → ``IRGraph.variables``
    - ``Harness`` metadata (name, description, version) → ``IRGraph.metadata``

    Parameters
    ----------
    harness:
        The validated Cronos harness to compile.  Must satisfy Harness model
        invariants (unique node ids, valid edge references, etc.).

    Returns
    -------
    IRGraph
        A complete IR representation ready to be passed to the delivery-workflow
        runner.

    Notes
    -----
    - Loop policies (R3): agent nodes with a ``loop`` sub-dict in ``data``
      produce an ``IRNode.loop = LoopPolicy(...)`` with ``max`` defaulting to
      ``10`` (the Cronos-layer default, distinct from the runner's default of 5).
    - Non-agent node types never carry a loop policy (the runner does not
      support loops on control-flow nodes).
    - Wait-node disambiguation (R2): ``data.mode`` drives ``IRNode.kind``:
        'human' → 'human', 'timed' → 'wait', absent → 'wait' + warning.
    - Edge port (OQ-1 recommendation): encoded as ``source.port_id`` only,
      since the runner ignores port for routing.
    - Import boundary (R13): this function does not import from app.*, runner.*,
      lib.*, or adapters.*.
    """
    ir_nodes: list[IRNode] = []
    for hn in harness.nodes:
        kind = _node_kind(hn.type, hn.data)

        # Build node data dict — pass through all data fields as-is.
        # The runner reads kind-specific parameters from this dict.
        node_data: dict = dict(hn.data) if hn.data else {}

        # Loop policy — only applicable to agent nodes.
        loop: LoopPolicy | None = None
        if hn.type == NodeType.agent:
            loop_raw = node_data.get("loop")
            if isinstance(loop_raw, dict):
                loop = _build_loop_policy(loop_raw)

        ir_nodes.append(
            IRNode(
                id=hn.id,
                kind=kind,  # type: ignore[arg-type]
                data=node_data,
                loop=loop,
            )
        )

    ir_edges: list[IREdge] = []
    for he in harness.edges:
        ir_edges.append(
            IREdge(
                source=he.source.node_id,
                target=he.target.node_id,
                # condition=None means unconditional in the harness model;
                # IREdge.when="" means unconditional in the runner (R1).
                when=he.condition if he.condition is not None else "",
                # Encode port as source.port_id only (OQ-1 recommendation).
                # The runner ignores port for routing; it is reserved for the
                # future visualiser.
                port=he.source.port_id,
            )
        )

    metadata: dict = {
        "name": harness.name,
        "description": harness.description,
        "version": harness.version,
        "created_at": harness.created_at.isoformat(),
        "updated_at": harness.updated_at.isoformat(),
    }

    return IRGraph(
        nodes=ir_nodes,
        edges=ir_edges,
        variables=dict(harness.variables),
        metadata=metadata,
    )
