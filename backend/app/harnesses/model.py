"""
backend/app/harnesses/model — Pydantic v2 data models for the harness data layer.

Validation rules enforced here (field/reference checks only):
  R1: node ids are unique within a Harness.
  R2: edge ids are unique within a Harness.
  R3: each edge source/target references a node id that exists in nodes[].
  R4: each edge source/target references a port id that exists in the
      referenced node's ports dict.

Cycle detection (R5) is intentionally NOT done here — it requires full-graph
traversal and is deferred to the store layer (I3 via the validator module I2)
where it has full context before persistence.

Node ``data`` dict conventions (informational — enforced by validator.py):
  Wait nodes (NodeType.wait):
    - ``mode`` (str, required): ``'human'`` or ``'timed'``
    - ``duration_seconds`` (float, required when mode='timed'): sleep duration
    - ``waiting_question`` (str, optional): prompt shown to the human respondent
    - ``max_wait_seconds`` (float, required when mode='human'): guardrail timeout
      preventing a harness from parking forever if no reply arrives (R6).

  Aggregator nodes (NodeType.aggregator):
    - ``mode`` (str, required): ``'all'`` (wait for every predecessor to finish)
      or ``'any'`` (fire as soon as the first predecessor reaches done).

  Decision nodes (NodeType.decision):
    - Routing is driven by ``HarnessEdge.condition`` labels evaluated against
      the predecessor agent's signal; no extra ``data`` fields are required.

  Agent / Trigger nodes have no mandatory ``data`` keys.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field, model_validator


class NodeType(str, Enum):
    """Supported harness node categories."""

    agent = "agent"
    trigger = "trigger"
    decision = "decision"
    wait = "wait"
    aggregator = "aggregator"


class Position(BaseModel):
    """Canvas (x, y) position for a node, used by the frontend renderer."""

    x: float
    y: float


class HarnessNode(BaseModel):
    """A single node in a harness graph."""

    id: str
    type: NodeType
    position: Position
    # ports keyed by port-id; each value is a free-form dict (name, direction, …)
    ports: dict[str, dict] = Field(default_factory=dict)
    # arbitrary node-specific configuration / metadata
    data: dict = Field(default_factory=dict)
    label: str = ""


class NodeRef(BaseModel):
    """Reference to a specific port on a specific node."""

    node_id: str
    port_id: str


class HarnessEdge(BaseModel):
    """A directed edge connecting two node ports."""

    id: str
    source: NodeRef
    target: NodeRef
    # optional guard expression evaluated by the executor; None means unconditional
    condition: str | None = None


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


class Harness(BaseModel):
    """
    Top-level harness graph model.

    Created_at / updated_at are tz-aware UTC datetimes consistent with
    storage.py::_iso convention.

    Cross-field invariants enforced by model_validator (mode='after'):
      - Node IDs must be unique (R1).
      - Edge IDs must be unique (R2).
      - Edge source/target node_id must refer to an existing node (R3).
      - Edge source/target port_id must exist in the referenced node's ports (R4).
    """

    name: str
    description: str = ""
    nodes: list[HarnessNode] = Field(default_factory=list)
    edges: list[HarnessEdge] = Field(default_factory=list)
    variables: dict = Field(default_factory=dict)
    version: str = "1.0"
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)

    @model_validator(mode="after")
    def _check_graph_integrity(self) -> "Harness":
        # R1 — unique node ids
        node_ids = [n.id for n in self.nodes]
        seen_node_ids: set[str] = set()
        for nid in node_ids:
            if nid in seen_node_ids:
                raise ValueError(f"duplicate node id: '{nid}'")
            seen_node_ids.add(nid)

        # Build a lookup: node_id -> node (for R3, R4)
        node_by_id: dict[str, HarnessNode] = {n.id: n for n in self.nodes}

        # R2 — unique edge ids
        seen_edge_ids: set[str] = set()
        for edge in self.edges:
            if edge.id in seen_edge_ids:
                raise ValueError(f"duplicate edge id: '{edge.id}'")
            seen_edge_ids.add(edge.id)

            # R3 — source node exists
            for ref_label, ref in (("source", edge.source), ("target", edge.target)):
                if ref.node_id not in node_by_id:
                    raise ValueError(
                        f"edge '{edge.id}' {ref_label} references unknown node id"
                        f" '{ref.node_id}'"
                    )
                # R4 — port exists on the referenced node
                node = node_by_id[ref.node_id]
                if ref.port_id not in node.ports:
                    raise ValueError(
                        f"edge '{edge.id}' {ref_label} references unknown port"
                        f" '{ref.port_id}' on node '{ref.node_id}'"
                    )

        return self
