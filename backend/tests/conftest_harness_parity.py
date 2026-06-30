"""
backend/tests/conftest_harness_parity — Synthetic Harness fixtures for parity tests.

These fixtures construct Harness objects in-process (no YAML files on disk).
Each scenario exercises a distinct control-flow path to verify that the BFS
HarnessExecutor and the delivery-workflow runner produce identical outcomes.

Parity scope
------------
Control-flow parity only: this module tests that both execution paths
traverse the same nodes in the same order and produce the same per-node
status (done/failed/skipped/blocked) and the same final run outcome
(done/failed/blocked).  Agent fidelity (real CLI timing, streaming output,
partial output buffering) is explicitly out of scope and is deferred to
shadow-mode production testing (see design-report ## Deferred §3).

Scenarios
---------
1. LINEAR — trigger + agent: simple two-node path; both paths should
   produce outcome=done with trigger and agent both at status=done.

2. DECISION_AGGREGATOR_ALL — trigger → agent → decision → (branch-a, branch-b)
   → aggregator(all) → final-agent: exercises branching where BOTH branches
   must complete before the aggregator fires.

3. DECISION_AGGREGATOR_ANY — same topology but aggregator(any); fires when the
   FIRST branch completes (we only add one branch to simplify the scenario).

4. HUMAN_WAIT — trigger → wait(human) → agent: human-wait parking.
   Both paths park on first run (outcome=blocked); on resume both proceed to
   completion.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.harnesses.model import (
    Harness,
    HarnessEdge,
    HarnessNode,
    NodeRef,
    NodeType,
    Position,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _pos() -> Position:
    return Position(x=0.0, y=0.0)


def _node(
    node_id: str,
    node_type: NodeType,
    data: dict | None = None,
    label: str = "",
    ports: dict | None = None,
) -> HarnessNode:
    """Build a minimal HarnessNode."""
    if ports is None:
        ports = {
            "in": {"direction": "input"},
            "out": {"direction": "output"},
        }
    return HarnessNode(
        id=node_id,
        type=node_type,
        position=_pos(),
        ports=ports,
        data=data or {},
        label=label or node_id,
    )


def _edge(
    edge_id: str,
    src_node: str,
    src_port: str,
    tgt_node: str,
    tgt_port: str,
    condition: str | None = None,
) -> HarnessEdge:
    """Build a minimal HarnessEdge."""
    return HarnessEdge(
        id=edge_id,
        source=NodeRef(node_id=src_node, port_id=src_port),
        target=NodeRef(node_id=tgt_node, port_id=tgt_port),
        condition=condition,
    )


def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


# ---------------------------------------------------------------------------
# Scenario 1: LINEAR — trigger + agent
# ---------------------------------------------------------------------------


@pytest.fixture
def harness_linear() -> Harness:
    """Trigger → Agent: simplest possible two-node linear path.

    Expected outcome: both paths produce status=done for trigger and agent
    nodes; final run outcome = done.
    """
    trigger = _node(
        "trigger-1",
        NodeType.trigger,
        data={"expression": "0 * * * *"},
        ports={"out": {"direction": "output"}},
    )
    agent = _node(
        "agent-1",
        NodeType.agent,
        data={"agent_ref": "test-agent", "prompt_template": "do something"},
    )
    edge = _edge("e1", "trigger-1", "out", "agent-1", "in")

    return Harness(
        name="linear-parity",
        nodes=[trigger, agent],
        edges=[edge],
        variables={},
        created_at=_now(),
        updated_at=_now(),
    )


# ---------------------------------------------------------------------------
# Scenario 2: AGGREGATOR_ALL — two branches fan-out + aggregator(all) + final
# ---------------------------------------------------------------------------


@pytest.fixture
def harness_decision_agg_all() -> Harness:
    """Trigger -> Agent-Main -> (Branch-A, Branch-B) -> Aggregator(all) -> Final.

    Direct fan-out (no decision node): agent-main has two outgoing edges,
    one to branch-a and one to branch-b.  Both branches must complete before
    the aggregator fires.  Expected outcome: all nodes done; final run = done.

    This topology avoids the BFS decision-node single-edge-winner issue:
    the BFS executor follows ALL outgoing edges from a non-decision node.

    NOTE: The aggregator node's data includes 'inputs.from' listing the
    branch predecessor IDs so the runner's dispatch layer can resolve them
    without reading harness edges (the runner reads from node.data, not graph
    structure for aggregator predecessors).
    """
    trigger = _node(
        "trigger-1",
        NodeType.trigger,
        data={},
        ports={"out": {"direction": "output"}},
    )
    agent_main = _node(
        "agent-main",
        NodeType.agent,
        data={"agent_ref": "test-agent", "prompt_template": "main task"},
        ports={"in": {"direction": "input"}, "out-a": {"direction": "output"}, "out-b": {"direction": "output"}},
    )
    branch_a = _node(
        "branch-a",
        NodeType.agent,
        data={"agent_ref": "test-agent", "prompt_template": "branch a task"},
    )
    branch_b = _node(
        "branch-b",
        NodeType.agent,
        data={"agent_ref": "test-agent", "prompt_template": "branch b task"},
    )
    aggregator = _node(
        "agg-all",
        NodeType.aggregator,
        data={
            "mode": "all",
            # 'inputs.from' tells the runner's dispatch layer which nodes are predecessors.
            "inputs": {"from": ["branch-a", "branch-b"]},
        },
        ports={
            "in-a": {"direction": "input"},
            "in-b": {"direction": "input"},
            "out": {"direction": "output"},
        },
    )
    final_agent = _node(
        "agent-final",
        NodeType.agent,
        data={"agent_ref": "test-agent", "prompt_template": "final task"},
        ports={"in": {"direction": "input"}, "out": {"direction": "output"}},
    )

    edges = [
        _edge("e1", "trigger-1", "out", "agent-main", "in"),
        # Direct fan-out from agent-main to both branches.
        _edge("e2", "agent-main", "out-a", "branch-a", "in"),
        _edge("e3", "agent-main", "out-b", "branch-b", "in"),
        _edge("e4", "branch-a", "out", "agg-all", "in-a"),
        _edge("e5", "branch-b", "out", "agg-all", "in-b"),
        _edge("e6", "agg-all", "out", "agent-final", "in"),
    ]

    return Harness(
        name="decision-agg-all-parity",
        nodes=[trigger, agent_main, branch_a, branch_b, aggregator, final_agent],
        edges=edges,
        variables={},
        created_at=_now(),
        updated_at=_now(),
    )


# ---------------------------------------------------------------------------
# Scenario 3: DECISION_AGGREGATOR_ANY — branching with any-mode aggregator
# ---------------------------------------------------------------------------


@pytest.fixture
def harness_decision_agg_any() -> Harness:
    """Trigger → Agent → Decision → Branch-A → Aggregator(any) → Final.

    Single branch scenario: aggregator(any) fires when the one predecessor
    (branch-a) completes.  Expected outcome: all nodes done.

    NOTE: Aggregator node data includes 'inputs.from': ['branch-a'] for
    the runner's dispatch layer.
    """
    trigger = _node(
        "trigger-1",
        NodeType.trigger,
        data={},
        ports={"out": {"direction": "output"}},
    )
    agent_main = _node(
        "agent-main",
        NodeType.agent,
        data={"agent_ref": "test-agent", "prompt_template": "main task"},
    )
    decision = _node(
        "decision-1",
        NodeType.decision,
        data={},
        ports={"in": {"direction": "input"}, "yes": {"direction": "output"}, "no": {"direction": "output"}},
    )
    branch_a = _node(
        "branch-a",
        NodeType.agent,
        data={"agent_ref": "test-agent", "prompt_template": "branch a task"},
    )
    aggregator = _node(
        "agg-any",
        NodeType.aggregator,
        data={
            "mode": "any",
            "inputs": {"from": ["branch-a"]},
        },
        ports={
            "in-a": {"direction": "input"},
            "out": {"direction": "output"},
        },
    )
    final_agent = _node(
        "agent-final",
        NodeType.agent,
        data={"agent_ref": "test-agent", "prompt_template": "final task"},
        ports={"in": {"direction": "input"}, "out": {"direction": "output"}},
    )

    edges = [
        _edge("e1", "trigger-1", "out", "agent-main", "in"),
        _edge("e2", "agent-main", "out", "decision-1", "in"),
        _edge("e3", "decision-1", "yes", "branch-a", "in"),
        _edge("e4", "branch-a", "out", "agg-any", "in-a"),
        _edge("e5", "agg-any", "out", "agent-final", "in"),
    ]

    return Harness(
        name="decision-agg-any-parity",
        nodes=[trigger, agent_main, decision, branch_a, aggregator, final_agent],
        edges=edges,
        variables={},
        created_at=_now(),
        updated_at=_now(),
    )


# ---------------------------------------------------------------------------
# Scenario 4: HUMAN_WAIT — park + resume
# ---------------------------------------------------------------------------


@pytest.fixture
def harness_human_wait() -> Harness:
    """Trigger → Wait(human) → Agent.

    First run: both paths park at the wait node.
    Resume run: both paths proceed from the wait node's successors and complete.

    The wait node uses data={'mode': 'human', 'max_wait_seconds': 300} which
    is the canonical human-wait configuration.  The HarnessExecutorAdapter
    discriminates '[wait/human]' prefix from the runner's dispatch layer
    to set WorkflowState.status='blocked'.
    """
    trigger = _node(
        "trigger-1",
        NodeType.trigger,
        data={},
        ports={"out": {"direction": "output"}},
    )
    wait = _node(
        "wait-1",
        NodeType.wait,
        data={"mode": "human", "max_wait_seconds": 300, "waiting_question": "Please review and approve."},
        ports={"in": {"direction": "input"}, "out": {"direction": "output"}},
    )
    agent = _node(
        "agent-final",
        NodeType.agent,
        data={"agent_ref": "test-agent", "prompt_template": "post-wait task"},
    )

    edges = [
        _edge("e1", "trigger-1", "out", "wait-1", "in"),
        _edge("e2", "wait-1", "out", "agent-final", "in"),
    ]

    return Harness(
        name="human-wait-parity",
        nodes=[trigger, wait, agent],
        edges=edges,
        variables={},
        created_at=_now(),
        updated_at=_now(),
    )
