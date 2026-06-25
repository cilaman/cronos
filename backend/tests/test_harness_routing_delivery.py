"""
Tests for delivery_status-driven routing in the harness executor (I7 / G3.2 + G3.3).

These tests verify the end-to-end path:
  agent output → parse_delivery_status_block → _enrich_scope_from_delivery_status
  → eval_condition (dotted-path) → edge_matches → decision routing.

Covers:
- _enrich_scope_from_delivery_status: status, fields, normalisation, hyphenated keys
- eval_condition with delivery_status-enriched scope: verdict, status, conjunction, missing key
- Full harness run routes correctly on pass/fail verdict in delivery_status
- Full harness run falls through to default edge when no delivery_status block emitted
"""

from __future__ import annotations

import json
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.harnesses.decision import eval_condition
from app.harnesses.executor import HarnessExecutor, _enrich_scope_from_delivery_status
from app.harnesses.model import (
    Harness,
    HarnessEdge,
    HarnessNode,
    NodeRef,
    NodeType,
    Position,
)
from app.harnesses.run_state import NodeState, RunState
from app.models import AiToolEntry, Space, TaskState
from app.trace_parser import RunTrace


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_space(space_id: str = "test-space") -> Space:
    now = datetime.now(tz=UTC)
    return Space(
        id=space_id,
        name="Test Space",
        color="#123456",
        created_at=now,
        updated_at=now,
    )


def _make_position() -> Position:
    return Position(x=0.0, y=0.0)


def _ds_block(status: str = "done", fields: dict | None = None) -> str:
    payload: dict = {"status": status}
    if fields is not None:
        payload["fields"] = fields
    return f"```delivery_status\n{json.dumps(payload)}\n```"


def _make_trace(final_text: str = "output", exit_reason: str = "DONE") -> RunTrace:
    now = datetime.now(tz=UTC)
    return RunTrace(
        task_id="child-task-id",
        space_id="test-space",
        run_index=0,
        session_id=None,
        model="sonnet",
        mode="auto",
        started_at=now,
        ended_at=now,
        duration_seconds=0.0,
        exit_reason=exit_reason,
        final_text_snippet=final_text,
        parent_run_id=None,
    )


def _tools_resolver(space_id: str, agent_ref: str) -> AiToolEntry | None:
    return None


def _make_store_mock(space_id: str = "test-space") -> MagicMock:
    store = MagicMock()
    _counter = [0]

    async def create(*, space_id, title, brief, parent_id=None, **kwargs):
        _counter[0] += 1
        task = MagicMock()
        task.id = f"task-{_counter[0]}"
        task.state = TaskState.DONE
        return task

    store.create = create
    store.get = MagicMock(return_value=None)
    return store


def _agent_node(node_id: str, prompt: str = "do work") -> HarnessNode:
    """Agent node — 'out' port used as both source and target (existing test convention)."""
    return HarnessNode(
        id=node_id,
        type=NodeType.agent,
        position=_make_position(),
        ports={"out": {}},
        data={"agent_ref": "my-agent", "prompt_template": prompt},
        label=node_id,
    )


def _decision_node(node_id: str,
                   yes_port: str = "yes", no_port: str = "no") -> HarnessNode:
    """Decision node with in + two outgoing ports."""
    return HarnessNode(
        id=node_id,
        type=NodeType.decision,
        position=_make_position(),
        ports={"in": {}, yes_port: {}, no_port: {}},
        data={},
        label=node_id,
    )


def _edge(eid: str, src: str, tgt: str,
          src_port: str = "out", tgt_port: str = "out",
          condition: str | None = None) -> HarnessEdge:
    return HarnessEdge(
        id=eid,
        source=NodeRef(node_id=src, port_id=src_port),
        target=NodeRef(node_id=tgt, port_id=tgt_port),
        condition=condition,
    )


class _MultiTraceWorker:
    """WorkerProtocol stub returning different traces per call."""

    def __init__(self, traces: list[RunTrace],
                 default_state: TaskState = TaskState.DONE) -> None:
        self._traces = list(traces)
        self._default_state = default_state
        self.call_count = 0

    async def run_agent(self, task_id: str, **kwargs) -> RunTrace:
        self.call_count += 1
        if self._traces:
            return self._traces.pop(0)
        return _make_trace()

    async def finalize_child(self, task_id: str, trace: RunTrace) -> TaskState:
        return self._default_state

    def _publish(self, task_id: str, event: dict) -> None:
        pass


async def _run_harness(harness: Harness, worker: _MultiTraceWorker) -> RunState:
    store = _make_store_mock()
    executor = HarnessExecutor(store, worker, _tools_resolver)
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("app.harnesses.executor._DATA_DIR", Path(tmpdir)):
            with patch("app.harnesses.executor._run_index.update_run_status",
                       new_callable=AsyncMock):
                return await executor.execute("run-1", harness, _make_space())


# ---------------------------------------------------------------------------
# Unit tests: _enrich_scope_from_delivery_status
# ---------------------------------------------------------------------------


class TestEnrichScopeDirect:
    def test_enriches_status_and_fields(self) -> None:
        output = _ds_block(status="done", fields={"verdict": "pass", "count": "3"})
        scope: dict[str, str] = {}
        _enrich_scope_from_delivery_status("reviewer", output, scope)
        assert scope["reviewer.status"] == "done"
        assert scope["reviewer.fields.verdict"] == "pass"
        assert scope["reviewer.fields.count"] == "3"

    def test_no_side_effects_on_missing_block(self) -> None:
        output = "No delivery_status block here. STATUS: DONE"
        scope: dict[str, str] = {"reviewer": "some output"}
        _enrich_scope_from_delivery_status("reviewer", output, scope)
        assert scope == {"reviewer": "some output"}

    def test_status_normalised_to_lowercase(self) -> None:
        output = _ds_block(status="DONE")
        scope: dict[str, str] = {}
        _enrich_scope_from_delivery_status("n1", output, scope)
        assert scope["n1.status"] == "done"

    def test_hyphenated_field_name(self) -> None:
        output = _ds_block(status="done", fields={"finding-count": "7"})
        scope: dict[str, str] = {}
        _enrich_scope_from_delivery_status("n1", output, scope)
        assert scope["n1.fields.finding-count"] == "7"

    def test_empty_output_is_noop(self) -> None:
        scope: dict[str, str] = {}
        _enrich_scope_from_delivery_status("n1", "", scope)
        assert scope == {}

    def test_fields_values_coerced_to_str(self) -> None:
        output = _ds_block(status="done", fields={"count": 5})  # type: ignore[arg-type]
        scope: dict[str, str] = {}
        _enrich_scope_from_delivery_status("n1", output, scope)
        assert scope["n1.fields.count"] == "5"


# ---------------------------------------------------------------------------
# Unit tests: eval_condition with delivery_status scope
# ---------------------------------------------------------------------------


class TestEvalConditionWithDeliveryStatusScope:
    def test_routes_on_verdict_pass(self) -> None:
        scope = {"reviewer.fields.verdict": "pass", "reviewer.status": "done"}
        assert eval_condition("reviewer.fields.verdict == pass", scope) is True
        assert eval_condition("reviewer.fields.verdict == fail", scope) is False

    def test_routes_on_status(self) -> None:
        scope = {"reviewer.status": "needs_fix"}
        assert eval_condition("reviewer.status == needs_fix", scope) is True
        assert eval_condition("reviewer.status == done", scope) is False

    def test_conjunction_all_true(self) -> None:
        scope = {
            "reviewer.status": "done",
            "reviewer.fields.verdict": "pass",
        }
        cond = "reviewer.status == done && reviewer.fields.verdict == pass"
        assert eval_condition(cond, scope) is True

    def test_conjunction_partial_false(self) -> None:
        scope = {
            "reviewer.status": "done",
            "reviewer.fields.verdict": "fail",
        }
        cond = "reviewer.status == done && reviewer.fields.verdict == pass"
        assert eval_condition(cond, scope) is False

    def test_missing_key_returns_false(self) -> None:
        scope: dict[str, str] = {}
        assert eval_condition("reviewer.fields.verdict == pass", scope) is False

    def test_hyphenated_field_in_condition(self) -> None:
        scope = {"n1.fields.finding-count": "0"}
        assert eval_condition("n1.fields.finding-count == 0", scope) is True

    def test_not_equal_operator(self) -> None:
        scope = {"reviewer.status": "needs_fix"}
        assert eval_condition("reviewer.status != done", scope) is True
        assert eval_condition("reviewer.status != needs_fix", scope) is False


# ---------------------------------------------------------------------------
# Integration tests: full harness run routing
# ---------------------------------------------------------------------------


class TestHarnessRoutingWithDeliveryStatus:
    @pytest.mark.asyncio
    async def test_routes_to_pass_branch_on_pass_verdict(self) -> None:
        """Full executor run routes to pass-node when agent emits verdict==pass."""
        ds = _ds_block(status="done", fields={"verdict": "pass"})
        agent_output = f"Review complete.\n{ds}"
        worker = _MultiTraceWorker([
            _make_trace(final_text=agent_output),      # reviewer
            _make_trace(final_text="pass flow done"),  # pass-node
        ])

        review = _agent_node("review")
        gate = _decision_node("gate")
        pass_node = _agent_node("pass-node")
        fail_node = _agent_node("fail-node")

        harness = Harness(
            name="routing-pass",
            nodes=[review, gate, pass_node, fail_node],
            edges=[
                _edge("e1", "review", "gate", tgt_port="in"),
                _edge("e2", "gate", "pass-node",
                      src_port="yes", condition="review.fields.verdict == pass"),
                _edge("e3", "gate", "fail-node",
                      src_port="no", condition="review.fields.verdict == fail"),
            ],
        )

        result = await _run_harness(harness, worker)

        assert result.nodes_executed.get("pass-node") is not None
        assert result.nodes_executed["pass-node"].status == "done"
        fail_ns = result.nodes_executed.get("fail-node")
        assert fail_ns is None or fail_ns.status == "skipped"
        assert worker.call_count == 2

    @pytest.mark.asyncio
    async def test_routes_to_fail_branch_on_fail_verdict(self) -> None:
        """Full executor run routes to fail-node when agent emits verdict==fail."""
        ds = _ds_block(status="needs_fix", fields={"verdict": "fail"})
        agent_output = f"Review found issues.\n{ds}"
        worker = _MultiTraceWorker([
            _make_trace(final_text=agent_output),      # reviewer
            _make_trace(final_text="fail flow done"),  # fail-node
        ])

        review = _agent_node("review")
        gate = _decision_node("gate")
        pass_node = _agent_node("pass-node")
        fail_node = _agent_node("fail-node")

        harness = Harness(
            name="routing-fail",
            nodes=[review, gate, pass_node, fail_node],
            edges=[
                _edge("e1", "review", "gate", tgt_port="in"),
                _edge("e2", "gate", "pass-node",
                      src_port="yes", condition="review.fields.verdict == pass"),
                _edge("e3", "gate", "fail-node",
                      src_port="no", condition="review.fields.verdict == fail"),
            ],
        )

        result = await _run_harness(harness, worker)

        assert result.nodes_executed.get("fail-node") is not None
        assert result.nodes_executed["fail-node"].status == "done"
        pass_ns = result.nodes_executed.get("pass-node")
        assert pass_ns is None or pass_ns.status == "skipped"
        assert worker.call_count == 2

    @pytest.mark.asyncio
    async def test_no_delivery_status_falls_to_default_edge(self) -> None:
        """When agent emits no delivery_status block, conditional edge is not met → default edge taken."""
        worker = _MultiTraceWorker([
            _make_trace(final_text="No block here. STATUS: DONE"),  # review
            _make_trace(final_text="default flow done"),             # default-node
        ])

        review = _agent_node("review")
        gate = _decision_node("gate")
        pass_node = _agent_node("pass-node")
        default_node = _agent_node("default-node")

        harness = Harness(
            name="routing-no-ds",
            nodes=[review, gate, pass_node, default_node],
            edges=[
                _edge("e1", "review", "gate", tgt_port="in"),
                # Conditional edge — won't match (no delivery_status → key absent)
                _edge("e2", "gate", "pass-node",
                      src_port="yes", condition="review.fields.verdict == pass"),
                # Unconditional default edge
                _edge("e3", "gate", "default-node", src_port="no"),
            ],
        )

        result = await _run_harness(harness, worker)

        # Default edge taken
        assert result.nodes_executed.get("default-node") is not None
        assert result.nodes_executed["default-node"].status == "done"
        pass_ns = result.nodes_executed.get("pass-node")
        assert pass_ns is None or pass_ns.status == "skipped"

    @pytest.mark.asyncio
    async def test_conjunction_condition_routing(self) -> None:
        """Conjunction condition on status && verdict both present routes correctly."""
        ds = _ds_block(status="done", fields={"verdict": "pass"})
        worker = _MultiTraceWorker([
            _make_trace(final_text=f"Complete.\n{ds}"),   # review
            _make_trace(final_text="both conditions met"),  # target node
        ])

        review = _agent_node("review")
        gate = _decision_node("gate")
        target = _agent_node("target")
        fallback = _agent_node("fallback")

        harness = Harness(
            name="routing-conjunction",
            nodes=[review, gate, target, fallback],
            edges=[
                _edge("e1", "review", "gate", tgt_port="in"),
                _edge("e2", "gate", "target",
                      src_port="yes",
                      condition="review.status == done && review.fields.verdict == pass"),
                _edge("e3", "gate", "fallback", src_port="no"),
            ],
        )

        result = await _run_harness(harness, worker)

        assert result.nodes_executed.get("target") is not None
        assert result.nodes_executed["target"].status == "done"
        fb_ns = result.nodes_executed.get("fallback")
        assert fb_ns is None or fb_ns.status == "skipped"
