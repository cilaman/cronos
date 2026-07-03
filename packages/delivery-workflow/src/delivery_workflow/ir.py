"""
packages/delivery-workflow/ir.py — Shared Intermediate Representation (IR) types.

These dataclasses form the portable, app-free layer between Compiler A (spec → IR)
and the cyclic work-list runner (IR → WorkflowState).  No app.* imports are
permitted here (enforced by .importlinter).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


@dataclass
class LoopPolicy:
    """Per-node loop configuration harvested from the ``loop:`` stanza in the spec.

    Attributes
    ----------
    until:
        A condition expression (evaluated by ``lib.conditions.eval_condition``)
        that must be True for the loop to exit.  Example:
        ``"review.fields.verdict == 'pass'"``.
    stall:
        List of stall-detection heuristic names (e.g. ``['recurring_findings',
        'no_diff_progress']``).  Stored verbatim; evaluation is deferred to a
        future version.
    max:
        Hard ceiling on the number of loop iterations for this node (per
        ``LoopPolicy.max`` in the design).  The runner increments
        ``NodeState.attempt`` and, when exceeded, emits
        ``RunEscalated(kind="loop")`` to the ``HostPort`` per ``on_exhaust``
        (the executor surface has no escalate hook since R10b).
    on_exhaust:
        Action to take when ``max`` iterations are reached without the
        ``until`` condition becoming True.
    """

    until: str
    stall: list[str] = field(default_factory=list)
    max: int = 5
    on_exhaust: Literal["escalate", "stop"] = "escalate"


@dataclass
class IRNode:
    """A single node in the Intermediate Representation graph.

    Attributes
    ----------
    id:
        Unique node identifier (matches the spec ``id:`` field).
    kind:
        One of the 8 supported node kinds.
    data:
        Raw node configuration dict from the spec (e.g. agent, checks,
        prompt, mode, command, etc.).  The runner dispatches on ``kind`` and
        reads ``data`` for kind-specific parameters (an ``exec`` node reads
        ``command``/``timeout``/``produces``).
    loop:
        Optional loop policy; None for nodes without a ``loop:`` stanza.
    """

    id: str
    kind: Literal[
        "agent", "gate", "human", "decision", "wait", "aggregator", "trigger", "exec"
    ]
    data: dict = field(default_factory=dict)
    loop: LoopPolicy | None = None


@dataclass
class IREdge:
    """A directed edge in the IR graph.

    Attributes
    ----------
    source:
        Source node id.
    target:
        Target node id.
    when:
        Condition expression string.  Empty string ``""`` means unconditional
        (the runner evaluates it as True without calling eval_condition).
    port:
        Optional port label (e.g. ``'yes'``, ``'no'`` for decision nodes).
        The runner ignores this field; reserved for future visualiser use.
    """

    source: str
    target: str
    when: str = ""
    port: str | None = None


@dataclass
class IRGraph:
    """The complete IR for a single workflow spec.

    Attributes
    ----------
    nodes:
        Ordered list of IRNode objects.
    edges:
        List of IREdge objects (may contain back-edges for cyclic workflows).
    variables:
        Root-level variable defaults (forwarded from ``defaults:`` stanza
        in the spec; merged into the runner scope before any node runs).
    metadata:
        Freeform metadata from the spec (e.g. ``{'budget': {'usd_ceiling': 25.0}}``,
        ``'name'``, etc.).  The driver reads ``metadata['budget']`` to pass
        the ceiling to the adapter.
    """

    nodes: list[IRNode] = field(default_factory=list)
    edges: list[IREdge] = field(default_factory=list)
    variables: dict = field(default_factory=dict)
    metadata: dict = field(default_factory=dict)

    @property
    def entry_nodes(self) -> list[str]:
        """Return node ids with no FORWARD-edge predecessors.

        A "forward edge" is one where the source node appears EARLIER in the
        nodes list than the target node.  Back-edges (source position ≥ target
        position) are excluded from the entry-node computation so that cyclic
        graphs (e.g. implement → review → implement) still produce correct
        entry nodes.

        These are the nodes the runner seeds into the work-list on startup.
        In a valid delivery workflow, this is typically the trigger or the
        first agent node (e.g. "scout").
        """
        node_pos: dict[str, int] = {n.id: i for i, n in enumerate(self.nodes)}
        # Targets that have at least one FORWARD-edge incoming.
        forward_targets: set[str] = {
            e.target
            for e in self.edges
            if node_pos.get(e.source, 0) < node_pos.get(e.target, len(self.nodes))
        }
        return [n.id for n in self.nodes if n.id not in forward_targets]
