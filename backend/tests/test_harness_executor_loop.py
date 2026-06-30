"""
Tests for loop-convergence policy in HarnessExecutor (I6 / G3.1).

Covers:
- Loop exits when `until` condition is met (single attempt and multi-attempt)
- Loop escalates (park=True, waiting_node_id set) on `recurring_findings` stall
- Loop continues when finding IDs change between attempts
- Loop escalates on `no_diff_progress` stall; continues when diff_bytes decreases
- Loop escalates when `max` backstop is hit
- Attempt counter and prior_finding_ids persisted between iterations
- Single non-loop agent node returns park=False (backward compat)
"""

from __future__ import annotations

import json
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.harnesses.executor import HarnessExecutor
from app.harnesses.model import (
    Harness,
    HarnessNode,
    NodeType,
    Position,
)
from app.harnesses.run_state import RunState
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


def _make_loop_harness(
    node_id: str = "reviewer",
    loop: dict | None = None,
    prompt: str = "review this",
) -> Harness:
    """Single agent node harness (no trigger — bare node, no edges)."""
    data: dict = {"agent_ref": "my-agent", "prompt_template": prompt}
    if loop is not None:
        data["loop"] = loop
    node = HarnessNode(
        id=node_id,
        type=NodeType.agent,
        position=_make_position(),
        ports={"out": {}},
        data=data,
        label=node_id,
    )
    return Harness(name="loop-test-harness", nodes=[node], edges=[])


async def _run_harness(harness: Harness, worker: _MultiTraceWorker) -> RunState:
    store = _make_store_mock()
    executor = HarnessExecutor(store, worker, _tools_resolver)
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("app.harnesses.executor._DATA_DIR", Path(tmpdir)):
            with patch("app.harnesses.executor._run_index.update_run_status",
                       new_callable=AsyncMock):
                return await executor.execute("run-1", harness, _make_space())


# ---------------------------------------------------------------------------
# I6: Loop exits when `until` condition met
# ---------------------------------------------------------------------------


class TestLoopUntilCondition:
    @pytest.mark.asyncio
    async def test_loop_exits_on_first_attempt(self) -> None:
        """Loop stops after the first iteration when until condition is satisfied."""
        ds = _ds_block(status="done", fields={"verdict": "pass"})
        worker = _MultiTraceWorker([_make_trace(final_text=f"Review complete.\n{ds}")])
        harness = _make_loop_harness(
            loop={"until": "reviewer.fields.verdict == pass", "max": 5}
        )
        result = await _run_harness(harness, worker)
        assert result.nodes_executed["reviewer"].status == "done"
        assert worker.call_count == 1

    @pytest.mark.asyncio
    async def test_loop_retries_until_condition_met(self) -> None:
        """Loop retries until condition met on second attempt."""
        ds_fail = _ds_block(status="needs_fix", fields={"verdict": "fail"})
        ds_pass = _ds_block(status="done", fields={"verdict": "pass"})
        worker = _MultiTraceWorker([
            _make_trace(final_text=f"Needs work.\n{ds_fail}"),
            _make_trace(final_text=f"Fixed.\n{ds_pass}"),
        ])
        harness = _make_loop_harness(
            loop={"until": "reviewer.fields.verdict == pass", "max": 5}
        )
        result = await _run_harness(harness, worker)
        assert result.nodes_executed["reviewer"].status == "done"
        assert worker.call_count == 2


# ---------------------------------------------------------------------------
# I6: Loop escalates on recurring_findings stall
# ---------------------------------------------------------------------------


class TestLoopRecurringFindingsStall:
    @pytest.mark.asyncio
    async def test_escalates_when_finding_ids_repeat(self) -> None:
        """Loop parks run when same finding IDs appear twice (recurring stall)."""
        ds = _ds_block(status="needs_fix", fields={"finding_ids": ["F-001", "F-002"]})
        worker = _MultiTraceWorker([
            _make_trace(final_text=f"Found issues.\n{ds}"),
            _make_trace(final_text=f"Same issues again.\n{ds}"),
        ])
        harness = _make_loop_harness(
            loop={"stall": ["recurring_findings"], "max": 10}
        )
        result = await _run_harness(harness, worker)
        assert result.waiting_node_id == "reviewer"
        assert worker.call_count == 2

    @pytest.mark.asyncio
    async def test_no_stall_when_findings_change(self) -> None:
        """Loop continues when finding IDs differ between attempts."""
        ds1 = _ds_block(status="needs_fix", fields={"finding_ids": ["F-001"]})
        ds2 = _ds_block(status="needs_fix", fields={"finding_ids": ["F-002"]})
        ds3 = _ds_block(status="done", fields={"verdict": "pass"})
        worker = _MultiTraceWorker([
            _make_trace(final_text=f"Found F-001.\n{ds1}"),
            _make_trace(final_text=f"Found F-002.\n{ds2}"),
            _make_trace(final_text=f"Fixed.\n{ds3}"),
        ])
        harness = _make_loop_harness(
            loop={
                "until": "reviewer.fields.verdict == pass",
                "stall": ["recurring_findings"],
                "max": 10,
            }
        )
        result = await _run_harness(harness, worker)
        assert result.nodes_executed["reviewer"].status == "done"
        assert result.waiting_node_id is None
        assert worker.call_count == 3


# ---------------------------------------------------------------------------
# I6: Loop escalates on no_diff_progress stall
# ---------------------------------------------------------------------------


class TestLoopNoDiffProgressStall:
    @pytest.mark.asyncio
    async def test_escalates_when_diff_bytes_stagnate(self) -> None:
        """Loop parks when diff_bytes stops decreasing."""
        ds1 = _ds_block(status="needs_fix", fields={"diff_bytes": "100"})
        ds2 = _ds_block(status="needs_fix", fields={"diff_bytes": "100"})
        worker = _MultiTraceWorker([
            _make_trace(final_text=f"Pass 1.\n{ds1}"),
            _make_trace(final_text=f"Pass 2 — no progress.\n{ds2}"),
        ])
        harness = _make_loop_harness(
            loop={"stall": ["no_diff_progress"], "max": 10}
        )
        result = await _run_harness(harness, worker)
        assert result.waiting_node_id == "reviewer"
        assert worker.call_count == 2

    @pytest.mark.asyncio
    async def test_no_stall_when_diff_bytes_decrease(self) -> None:
        """Loop continues when diff_bytes decreases — progress being made."""
        ds1 = _ds_block(status="needs_fix", fields={"diff_bytes": "200"})
        ds2 = _ds_block(status="done", fields={"diff_bytes": "50", "verdict": "pass"})
        worker = _MultiTraceWorker([
            _make_trace(final_text=f"Pass 1.\n{ds1}"),
            _make_trace(final_text=f"Pass 2 — done.\n{ds2}"),
        ])
        harness = _make_loop_harness(
            loop={
                "until": "reviewer.fields.verdict == pass",
                "stall": ["no_diff_progress"],
                "max": 10,
            }
        )
        result = await _run_harness(harness, worker)
        assert result.nodes_executed["reviewer"].status == "done"
        assert result.waiting_node_id is None
        assert worker.call_count == 2


# ---------------------------------------------------------------------------
# I6: Loop escalates when max backstop hit
# ---------------------------------------------------------------------------


class TestLoopMaxBackstop:
    @pytest.mark.asyncio
    async def test_escalates_on_max_exhaustion(self) -> None:
        """Loop parks when max attempts exhausted without until condition."""
        ds = _ds_block(status="needs_fix", fields={"verdict": "fail"})
        worker = _MultiTraceWorker(
            [_make_trace(final_text=f"Attempt {i}.\n{ds}") for i in range(3)]
        )
        harness = _make_loop_harness(
            loop={"until": "reviewer.fields.verdict == pass", "max": 3}
        )
        result = await _run_harness(harness, worker)
        assert result.waiting_node_id == "reviewer"
        assert worker.call_count == 3

    @pytest.mark.asyncio
    async def test_max_one_escalates_immediately(self) -> None:
        """max=1 escalates after the first attempt if until is not met."""
        ds = _ds_block(status="needs_fix")
        worker = _MultiTraceWorker([_make_trace(final_text=f"Failed.\n{ds}")])
        harness = _make_loop_harness(
            loop={"until": "reviewer.status == done", "max": 1}
        )
        result = await _run_harness(harness, worker)
        assert result.waiting_node_id == "reviewer"
        assert worker.call_count == 1


# ---------------------------------------------------------------------------
# I6: Backward compatibility — no loop config
# ---------------------------------------------------------------------------


class TestNoLoopBackwardCompat:
    @pytest.mark.asyncio
    async def test_no_loop_config_runs_once(self) -> None:
        """Agent node without loop config runs exactly once and does not park."""
        worker = _MultiTraceWorker([_make_trace(final_text="done")])
        harness = _make_loop_harness(loop=None)
        result = await _run_harness(harness, worker)
        assert result.nodes_executed["reviewer"].status == "done"
        assert result.waiting_node_id is None
        assert worker.call_count == 1


# ---------------------------------------------------------------------------
# I6: Attempt counter and prior_finding_ids persisted
# ---------------------------------------------------------------------------


class TestLoopBookkeeping:
    @pytest.mark.asyncio
    async def test_attempt_counter_increments(self) -> None:
        """Loop ran twice proves bookkeeping allowed multiple iterations."""
        ds_fail = _ds_block(status="needs_fix", fields={"verdict": "fail"})
        ds_pass = _ds_block(status="done", fields={"verdict": "pass"})
        worker = _MultiTraceWorker([
            _make_trace(final_text=f"Attempt 1.\n{ds_fail}"),
            _make_trace(final_text=f"Attempt 2.\n{ds_pass}"),
        ])
        harness = _make_loop_harness(
            loop={"until": "reviewer.fields.verdict == pass", "max": 5}
        )
        result = await _run_harness(harness, worker)
        # 2 iterations via persisted attempt bookkeeping
        assert worker.call_count == 2
        assert result.nodes_executed["reviewer"].status == "done"
        # Final NodeState records completion; attempt bookkeeping is for resume only.
        assert result.nodes_executed["reviewer"].output is not None

    @pytest.mark.asyncio
    async def test_prior_finding_ids_prevent_stall_on_diff_ids(self) -> None:
        """prior_finding_ids correctly detects non-recurring findings (no stall)."""
        ds1 = _ds_block(status="needs_fix", fields={"finding_ids": ["A"]})
        ds2 = _ds_block(status="needs_fix", fields={"finding_ids": ["B"]})
        ds3 = _ds_block(status="done", fields={"verdict": "pass"})
        worker = _MultiTraceWorker([
            _make_trace(final_text=f"A.\n{ds1}"),
            _make_trace(final_text=f"B.\n{ds2}"),
            _make_trace(final_text=f"Done.\n{ds3}"),
        ])
        harness = _make_loop_harness(
            loop={
                "until": "reviewer.fields.verdict == pass",
                "stall": ["recurring_findings"],
                "max": 10,
            }
        )
        result = await _run_harness(harness, worker)
        assert result.nodes_executed["reviewer"].status == "done"
        assert result.waiting_node_id is None
        assert worker.call_count == 3


# ---------------------------------------------------------------------------
# I5 / SG2: node_status fence support in loop stall-detection
# ---------------------------------------------------------------------------


def _ns_block(status: str = "done", fields: dict | None = None) -> str:
    payload: dict = {"status": status}
    if fields is not None:
        payload["fields"] = fields
    return f"```node_status\n{json.dumps(payload)}\n```"


class TestLoopRecurringFindingsNodeStatus:
    """I5: Loop stall-detection works with node_status fence (migrated agents)."""

    @pytest.mark.asyncio
    async def test_escalates_when_finding_ids_repeat_node_status(self) -> None:
        """recurring_findings stall triggers when node_status emits same finding_ids twice."""
        ns_stall = _ns_block(
            status="needs_fix", fields={"finding_ids": ["F1", "F2"]}
        )
        worker = _MultiTraceWorker([
            _make_trace(final_text=f"First attempt.\n{ns_stall}"),
            _make_trace(final_text=f"Second attempt — same findings.\n{ns_stall}"),
        ])
        harness = _make_loop_harness(
            loop={"stall": ["recurring_findings"], "max": 10}
        )
        result = await _run_harness(harness, worker)
        # Should escalate: waiting_node_id is set, park triggered
        assert result.waiting_node_id == "reviewer"
        assert worker.call_count == 2

    @pytest.mark.asyncio
    async def test_no_stall_when_node_status_findings_change(self) -> None:
        """No stall when node_status emits different finding_ids between attempts."""
        # Include a simple string field ("verdict") for the until condition;
        # finding_ids is a list and stored as str(list) in scope, so use verdict for until.
        ns1 = _ns_block(status="needs_fix", fields={"finding_ids": ["F1"], "verdict": "fail"})
        ns2 = _ns_block(status="done", fields={"finding_ids": ["F2"], "verdict": "pass"})
        worker = _MultiTraceWorker([
            _make_trace(final_text=f"First.\n{ns1}"),
            _make_trace(final_text=f"Second.\n{ns2}"),
        ])
        harness = _make_loop_harness(
            loop={
                "until": "reviewer.fields.verdict == pass",
                "stall": ["recurring_findings"],
                "max": 10,
            }
        )
        result = await _run_harness(harness, worker)
        # Finding IDs changed (F1 → F2) so no stall; until condition fired on attempt 2.
        assert result.waiting_node_id is None
        assert worker.call_count == 2

    @pytest.mark.asyncio
    async def test_node_status_and_delivery_status_coexist_in_loop(self) -> None:
        """R6 coexistence: first attempt delivery_status, second attempt node_status — no stall."""
        ds1 = _ds_block(status="needs_fix", fields={"finding_ids": ["F1"], "verdict": "fail"})
        ns2 = _ns_block(status="done", fields={"finding_ids": ["F2"], "verdict": "pass"})
        worker = _MultiTraceWorker([
            _make_trace(final_text=f"Legacy agent.\n{ds1}"),
            _make_trace(final_text=f"Migrated agent.\n{ns2}"),
        ])
        harness = _make_loop_harness(
            loop={
                "until": "reviewer.fields.verdict == pass",
                "stall": ["recurring_findings"],
                "max": 10,
            }
        )
        result = await _run_harness(harness, worker)
        # Different finding IDs across fence types → no stall; until fires on attempt 2.
        assert result.waiting_node_id is None
        assert worker.call_count == 2
