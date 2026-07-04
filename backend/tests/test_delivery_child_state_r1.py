"""R1 regression — delivery child Kanban state from the node_status envelope (D13).

Pre-R1, the child task's board state came from the backend STATUS-marker
mapping while the pipeline node status came separately from fence parsing —
the board could show the child DONE while the node read failed, or vice
versa.  R1 derives both from the SAME parsed envelope:

* ``run_delivery_child`` parses the envelope with the exact pair the trace
  parser uses (``parse_node_status_fence(final_assistant_text(raw_events))``,
  == ``trace.node_status``) and passes the mapped state to ``finalize_child``
  as an override.
* Infra failures (spawn exception, missing result, user stop, crash) still
  force WAITING, and the loaded trace is suppressed for the adapter so a
  stale/crashed trace can never credit the node while the board says WAITING.
"""
from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agent import Status
from app.finalizer import Finalizer
from app.models import TaskState
from app.run_executor import RunExecutor, _delivery_child_state_from_envelope


# ---------------------------------------------------------------------------
# _delivery_child_state_from_envelope — the mapping table
# ---------------------------------------------------------------------------


class TestEnvelopeStateMapping:
    def test_done_maps_to_done(self):
        state, q = _delivery_child_state_from_envelope({"status": "done"})
        assert state == TaskState.DONE
        assert q is None

    def test_needs_fix_maps_to_done(self):
        """dispatch.py maps AgentResult needs_fix → node done (the verdict
        routes the fix loop); the board must agree."""
        state, q = _delivery_child_state_from_envelope({"status": "needs_fix"})
        assert state == TaskState.DONE
        assert q is None

    def test_blocked_maps_to_waiting_with_open_questions(self):
        state, q = _delivery_child_state_from_envelope(
            {"status": "blocked", "open_questions": ["Which DB?", "Which region?"]}
        )
        assert state == TaskState.WAITING
        assert q == "Which DB?; Which region?"

    def test_failed_maps_to_waiting(self):
        state, q = _delivery_child_state_from_envelope({"status": "failed"})
        assert state == TaskState.WAITING
        assert "failed" in q

    def test_unknown_status_maps_to_waiting_with_marker(self):
        state, q = _delivery_child_state_from_envelope({"status": "WAIT"})
        assert state == TaskState.WAITING
        assert "unknown_status:WAIT" in q

    def test_no_envelope_maps_to_waiting(self):
        state, q = _delivery_child_state_from_envelope(None)
        assert state == TaskState.WAITING
        assert "no node_status fence" in q

    def test_no_envelope_with_agent_question_puts_question_first(self):
        state, q = _delivery_child_state_from_envelope(
            None, agent_question="Which auth flow should I use?"
        )
        assert state == TaskState.WAITING
        assert q.startswith("Which auth flow should I use?")
        # The fence diagnostic stays, AFTER the agent's own question.
        assert (
            q.index("Which auth flow should I use?")
            < q.index("no node_status fence")
        )

    def test_no_envelope_without_agent_question_keeps_legacy_message(self):
        state, q = _delivery_child_state_from_envelope(None, agent_question=None)
        assert state == TaskState.WAITING
        assert q == (
            "Delivery node emitted no node_status fence — the pipeline "
            "classified it failed."
        )

    def test_agent_question_ignored_when_envelope_present(self):
        state, q = _delivery_child_state_from_envelope(
            {"status": "failed"}, agent_question="Which auth flow?"
        )
        assert state == TaskState.WAITING
        assert "Which auth flow?" not in q

    def test_status_is_case_insensitive_for_known_values(self):
        state, _ = _delivery_child_state_from_envelope({"status": "Done"})
        assert state == TaskState.DONE


# ---------------------------------------------------------------------------
# Finalizer.finalize_child — state_override semantics
# ---------------------------------------------------------------------------


def _make_finalizer() -> tuple[Finalizer, MagicMock]:
    store = MagicMock()
    store.get = MagicMock(return_value=None)  # skip the telemetry tail
    store.finalize_run = AsyncMock()
    bus = MagicMock()
    se = MagicMock()
    se.stats_store = None
    se.trace_store = None
    fn = Finalizer(
        store=store,
        event_bus=bus,
        side_effects=se,
        space_store=None,
        pool=None,
        on_task_state_change=None,
        auto_resume_counts={},
        enqueue_fn=AsyncMock(),
        done_sentinel={"type": "stream_end"},
    )
    return fn, store


def _result(
    status: Status | None = None,
    exit_code: int = 0,
    stopped: bool = False,
) -> MagicMock:
    r = MagicMock()
    r.status = status
    r.exit_code = exit_code
    r.stopped = stopped
    r.final_text = "some text"
    r.context = None
    r.session_id = "sess-1"
    r.raw_events = []
    r.stderr_tail = ""
    return r


_STARTED = datetime(2026, 7, 1, 12, 0, 0, tzinfo=UTC)


@pytest.mark.asyncio
async def test_override_done_wins_over_missing_status_marker():
    """The D13 case: envelope says done, no STATUS marker → child DONE
    (previously WAITING 'Run ended without STATUS marker')."""
    fn, store = _make_finalizer()
    state = await fn.finalize_child(
        "c1", _result(status=None), None,
        started_at=_STARTED, state_override=TaskState.DONE,
    )
    assert state == TaskState.DONE
    assert store.finalize_run.await_args.kwargs["waiting_question"] is None


@pytest.mark.asyncio
async def test_override_waiting_carries_question():
    """Inverse D13 case: STATUS DONE but envelope says failed → WAITING."""
    fn, store = _make_finalizer()
    state = await fn.finalize_child(
        "c1", _result(status=Status.DONE), None,
        started_at=_STARTED,
        state_override=TaskState.WAITING,
        waiting_question_override="Delivery node reported status=failed.",
    )
    assert state == TaskState.WAITING
    assert (
        store.finalize_run.await_args.kwargs["waiting_question"]
        == "Delivery node reported status=failed."
    )


@pytest.mark.asyncio
async def test_crash_outranks_override():
    """Infra failure: non-zero exit forces WAITING even when the final text
    carried a done envelope (and even though the generic chain would have let
    Status.DONE beat the crash check)."""
    fn, store = _make_finalizer()
    state = await fn.finalize_child(
        "c1", _result(status=Status.DONE, exit_code=137), None,
        started_at=_STARTED, state_override=TaskState.DONE,
    )
    assert state == TaskState.WAITING
    assert store.finalize_run.await_args.kwargs["waiting_question"] is not None


@pytest.mark.asyncio
async def test_stopped_outranks_override():
    fn, store = _make_finalizer()
    state = await fn.finalize_child(
        "c1", _result(stopped=True), None,
        started_at=_STARTED, state_override=TaskState.DONE,
    )
    assert state == TaskState.WAITING
    assert store.finalize_run.await_args.kwargs["waiting_question"] == "Stopped by user."


@pytest.mark.asyncio
async def test_run_exception_outranks_override():
    fn, store = _make_finalizer()
    state = await fn.finalize_child(
        "c1", None, "spawn failed",
        started_at=_STARTED, state_override=TaskState.DONE,
    )
    assert state == TaskState.WAITING


@pytest.mark.asyncio
async def test_no_override_keeps_generic_mapping():
    fn, _ = _make_finalizer()
    state = await fn.finalize_child(
        "c1", _result(status=Status.DONE), None, started_at=_STARTED,
    )
    assert state == TaskState.DONE


# ---------------------------------------------------------------------------
# run_delivery_child — wiring: envelope → finalize_child override; infra →
# trace suppression for the adapter.
# ---------------------------------------------------------------------------


def _fence_events(status: str) -> list[dict]:
    env = {
        "status": status,
        "artifact_paths": ["r.md"],
        "produces": "research",
        "fields": {},
        "open_questions": [],
    }
    prose = "long prose paragraph. " * 500  # >10k chars, fence at the very end
    return [
        {
            "type": "assistant",
            "message": {
                "usage": {},
                "content": [
                    {"type": "text", "text": prose + f"```node_status\n{json.dumps(env)}\n```"}
                ],
            },
        }
    ]


def _agent_result(
    raw_events: list[dict] | None = None,
    exit_code: int = 0,
    stopped: bool = False,
    context: str | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        status=Status.DONE,
        stopped=stopped,
        exit_code=exit_code,
        raw_events=raw_events or [],
        final_text="",
        session_id=None,
        stderr_tail="",
        context=context,
    )


def _make_executor() -> tuple[RunExecutor, MagicMock, MagicMock]:
    goal = SimpleNamespace(id="goal-1", space_id="sp1", title="G", brief="")
    child = SimpleNamespace(
        id="child-1", space_id="sp1", title="[delivery] scout",
        state=TaskState.BACKLOG, brief="", agent_model="default", agent_mode="auto",
    )
    store = MagicMock()
    store.get = MagicMock(
        side_effect=lambda tid: {"goal-1": goal, "child-1": child}.get(tid)
    )
    store.create = AsyncMock(return_value=child)
    store.transition = AsyncMock()

    worker = MagicMock()
    worker._current_id = None
    worker._current_cancel = None
    worker._current_child_id = None
    worker._pool = None
    worker.stats_store = None
    worker.memory_store = None
    worker.space_store = None
    worker._publish = AsyncMock()
    worker.trace_store = MagicMock()
    worker.trace_store.load_latest = AsyncMock(
        return_value=SimpleNamespace(node_status={"status": "done"})
    )

    bus = MagicMock()
    finalizer = MagicMock()
    finalizer.finalize_child = AsyncMock(return_value=TaskState.DONE)

    ex = RunExecutor(
        worker=worker,
        store=store,
        event_bus=bus,
        finalizer=finalizer,
        space_store=None,
        harness_store=None,
        memory_store=None,
        done_sentinel={"type": "stream_end"},
        lease_ttl=30.0,
        heartbeat_interval=5.0,
        memory_retrieval=MagicMock(),
    )
    return ex, finalizer, worker


async def _run(ex: RunExecutor, agent_result, run_agent_raises: bool = False):
    if run_agent_raises:
        run_agent = AsyncMock(side_effect=RuntimeError("spawn failed"))
    else:
        run_agent = AsyncMock(return_value=agent_result)
    with patch("app.worker.run_agent", run_agent):
        return await ex.run_delivery_child(
            "goal-1", "scout", {"node_id": "scout"},
            cancel_event=asyncio.Event(), goal_context="",
        )


@pytest.mark.asyncio
async def test_done_envelope_passes_done_override():
    ex, finalizer, _ = _make_executor()
    await _run(ex, _agent_result(raw_events=_fence_events("done")))
    kwargs = finalizer.finalize_child.await_args.kwargs
    assert kwargs["state_override"] == TaskState.DONE
    assert kwargs["waiting_question_override"] is None


@pytest.mark.asyncio
async def test_failed_envelope_passes_waiting_override():
    ex, finalizer, _ = _make_executor()
    await _run(ex, _agent_result(raw_events=_fence_events("failed")))
    kwargs = finalizer.finalize_child.await_args.kwargs
    assert kwargs["state_override"] == TaskState.WAITING
    assert "failed" in kwargs["waiting_question_override"]


@pytest.mark.asyncio
async def test_missing_fence_passes_waiting_override():
    ex, finalizer, _ = _make_executor()
    await _run(ex, _agent_result(raw_events=[]))
    kwargs = finalizer.finalize_child.await_args.kwargs
    assert kwargs["state_override"] == TaskState.WAITING
    assert "no node_status fence" in kwargs["waiting_question_override"]


@pytest.mark.asyncio
async def test_missing_fence_surfaces_agent_question():
    """A no-fence child that asked a real question (parse_status summary in
    AgentResult.context) shows that question on the board, not only the
    generic fence diagnostic."""
    ex, finalizer, _ = _make_executor()
    await _run(
        ex, _agent_result(raw_events=[], context="Which DB should I use?")
    )
    kwargs = finalizer.finalize_child.await_args.kwargs
    assert kwargs["state_override"] == TaskState.WAITING
    q = kwargs["waiting_question_override"]
    assert q.startswith("Which DB should I use?")
    assert "no node_status fence" in q


@pytest.mark.asyncio
async def test_clean_run_returns_fresh_trace():
    ex, _, worker = _make_executor()
    returned = await _run(ex, _agent_result(raw_events=_fence_events("done")))
    assert returned is not None
    assert returned.node_status == {"status": "done"}
    worker.trace_store.load_latest.assert_awaited_once()


@pytest.mark.asyncio
async def test_spawn_exception_suppresses_trace():
    """A stale trace from an earlier run must never classify this node."""
    ex, finalizer, worker = _make_executor()
    returned = await _run(ex, None, run_agent_raises=True)
    assert returned is None
    worker.trace_store.load_latest.assert_not_awaited()
    # No envelope override on infra failure — generic WAITING path.
    kwargs = finalizer.finalize_child.await_args.kwargs
    assert kwargs["state_override"] is None


@pytest.mark.asyncio
async def test_crash_suppresses_trace():
    ex, _, worker = _make_executor()
    returned = await _run(
        ex, _agent_result(raw_events=_fence_events("done"), exit_code=1)
    )
    assert returned is None
    worker.trace_store.load_latest.assert_not_awaited()


@pytest.mark.asyncio
async def test_stopped_suppresses_trace():
    ex, _, worker = _make_executor()
    returned = await _run(
        ex, _agent_result(raw_events=_fence_events("done"), stopped=True)
    )
    assert returned is None
    worker.trace_store.load_latest.assert_not_awaited()


# ---------------------------------------------------------------------------
# run_delivery_child — brief composition: the shared package sections
# (delivery_workflow.briefs) so the child hears the node_status contract.
# ---------------------------------------------------------------------------


async def _run_with_inputs(ex: RunExecutor, agent_ref: str, inputs: dict) -> str:
    run_agent = AsyncMock(
        return_value=_agent_result(raw_events=_fence_events("done"))
    )
    with patch("app.worker.run_agent", run_agent):
        await ex.run_delivery_child(
            "goal-1", agent_ref, inputs,
            cancel_event=asyncio.Event(), goal_context="",
        )
    return ex.store.create.await_args.kwargs["brief"]


@pytest.mark.asyncio
async def test_brief_contains_shared_sections_in_order():
    ex, _, _ = _make_executor()
    brief = await _run_with_inputs(
        ex, "analyst",
        {
            "node_id": "analyze",
            "attempt": 2,
            "produces": {"class": "analysis"},
            "scope": {"research.fields.topic": "auth"},
            "artifact_paths": ["docs/research.md"],
        },
    )
    contract_pos = brief.index("## Return contract")
    positions = [
        brief.index("# Agent: analyst"),
        # A line from the packaged analyst role definition (agents/analyst.md).
        brief.index("REQ-id"),
        brief.index(
            "You are agent 'analyst' executing workflow node 'analyze' "
            "(attempt 2)."
        ),
        brief.index("slug: g"),
        brief.index("- docs/research.md"),
        brief.index("This node produces an artifact of class: analysis"),
        brief.index('"research.fields.topic": "auth"'),
        contract_pos,
        # The role definition carries its own node_status example — anchor
        # the contract's fence AFTER the header.
        brief.index("```node_status", contract_pos),
        brief.index("<!-- delivery-node: analyze -->"),
    ]
    assert positions == sorted(positions)
    assert brief.splitlines()[0] == "# Agent: analyst"
    assert brief.splitlines()[-1] == "<!-- delivery-node: analyze -->"


@pytest.mark.asyncio
async def test_brief_unknown_agent_ref_keeps_contract_and_sentinel():
    """No packaged role definition → no role section, but the return
    contract and sentinel are unconditional."""
    ex, _, _ = _make_executor()
    brief = await _run_with_inputs(
        ex, "custom-thing", {"node_id": "custom-thing"},
    )
    assert "## Return contract" in brief
    assert "```node_status" in brief
    assert brief.splitlines()[-1] == "<!-- delivery-node: custom-thing -->"
    # Header flows straight into the identity line — no role definition.
    assert (
        "# Agent: custom-thing\n\nYou are agent 'custom-thing'" in brief
    )


@pytest.mark.asyncio
async def test_brief_omits_produces_line_when_absent():
    ex, _, _ = _make_executor()
    brief = await _run_with_inputs(ex, "scout", {"node_id": "scout"})
    assert "This node produces an artifact of class:" not in brief
    assert "## Return contract" in brief


@pytest.mark.asyncio
async def test_brief_carries_human_signoff_answers_before_contract():
    """R7/OD-2: reject feedback in the scope (`<node>.fields.answer`) must
    reach the re-run child's brief, ahead of the return contract."""
    ex, _, _ = _make_executor()
    brief = await _run_with_inputs(
        ex, "architect",
        {
            "node_id": "design",
            "scope": {
                "signoff-design.fields.answer": "no — change X",
                "signoff-design.fields.verdict": "reject",
            },
        },
    )
    section_pos = brief.index("## Human sign-off answers")
    assert "- signoff-design (reject): no — change X" in brief
    assert section_pos < brief.index("## Return contract")


@pytest.mark.asyncio
async def test_brief_omits_answer_section_when_scope_has_no_answers():
    ex, _, _ = _make_executor()
    brief = await _run_with_inputs(
        ex, "architect",
        {"node_id": "design", "scope": {"analyze.fields.has_ui": False}},
    )
    assert "## Human sign-off answers" not in brief
