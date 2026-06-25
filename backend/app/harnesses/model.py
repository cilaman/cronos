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

  Trigger nodes (NodeType.trigger):
    Trigger nodes come in two flavours: **cron triggers** and **event triggers**.
    The presence of a ``kind`` field in ``data`` distinguishes event triggers from
    cron triggers.  Cron triggers have no ``kind`` field.

    Cron trigger ``data`` fields:
    - ``expression`` (str, required): cron expression in standard 5-field format
      (minute hour day-of-month month day-of-week), e.g. ``'0 * * * *'`` fires
      every hour.  Evaluated by ``croniter``; malformed expressions are
      logged and skipped — the loop does **not** crash.
    - ``timezone`` (str, optional): IANA timezone name (e.g. ``'Europe/Prague'``,
      ``'America/New_York'``).  Defaults to UTC when absent or when the name
      cannot be resolved by ``dateutil.tz``.

    Cron semantics note — **No back-fill of missed ticks across restart**: only
    the current wall-clock time is evaluated each tick.  If the process was
    offline when a scheduled firing was due, that firing is silently skipped.

    Event trigger ``data`` fields — common:
    - ``kind`` (str, required): one of ``'webhook'``, ``'file-change'``, or
      ``'task-state-change'``.  The presence of this field marks the node as an
      event trigger; validation is enforced by ``validator.py::_validate_trigger_nodes``
      (R7).

    Event trigger ``data`` fields — per-kind:

    ``kind='webhook'``:
      - ``webhook_path`` (str, required): logical identifier used as the event_id
        stable key for deduplication; also intended as a future flat-route path.
      - ``auth_token`` (str, required): Bearer token the caller must supply in the
        ``Authorization`` header.  Comparison uses ``secrets.compare_digest()`` to
        avoid timing side-channels.  Tokens shorter than 16 characters trigger a
        one-time ``log.warning``.  **Note**: tokens are stored in plaintext in the
        harness YAML — treat harness files as confidential; a secrets-API migration
        is planned as a follow-up goal.

    ``kind='file-change'``:
      - ``watch_pattern`` (str, required): glob pattern matched via
        ``pathlib.PurePath.match()`` against the path of each changed file
        relative to the space directory (e.g. ``'.cronos/tasks/*.md'``).
        Recursive ``**`` patterns are supported; negation patterns are not (deferred).
      - ``debounce_seconds`` (float, optional): minimum quiet period before the
        trigger re-fires for the same ``(space_id, watch_pattern, file_path)``
        combination.  Defaults to ``0.5`` when absent.

    ``kind='task-state-change'``:
      - ``watched_state`` (str, optional): the task state transition destination
        that causes the trigger to fire.  Defaults to ``'DONE'`` when absent.
        Value must be a valid ``TaskState`` string (e.g. ``'DONE'``, ``'ACTIVE'``,
        ``'WAITING'``).

  Agent nodes have no mandatory ``data`` keys.  The optional ``loop``
  sub-object enables the loop-convergence policy (G3.1):

  - ``until`` (str, optional): an ``eval_condition``-compatible expression
    evaluated after each attempt; when it resolves to ``True`` the loop exits
    normally.
  - ``stall`` (list[str], optional): list of stall-signal names to check.
    Recognised values: ``'recurring_findings'`` (fires when the current
    finding-ID set is non-empty and equal to the prior attempt's set) and
    ``'no_diff_progress'`` (fires when ``fields.diff_bytes`` is not strictly
    less than the prior attempt).
  - ``max`` (int, optional): absolute backstop iteration count.  The loop
    escalates on the ``(max + 1)``-th attempt.  Defaults to ``10`` when
    absent.
  - ``on_exhaust`` (str, optional): action taken when all exit conditions are
    exhausted without the ``until`` condition firing.  Only ``'escalate'`` is
    supported in v1: the run goal is transitioned to ``TaskState.WAITING``
    with a descriptive ``waiting_question`` naming the node and attempt count.
    Default: ``'escalate'``.

  The ``data`` dict is an open ``dict``; the validator passes through the
  ``loop`` sub-object without structural validation (R1 — agent node loop
  data is free-form).
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
