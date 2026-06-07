"""Tests for the auto-repair of missing sibling deps in Worker._run_goal.

When a sub-goal carries a depends_on that points at a grandchild of the parent
goal (a non-sibling dep), _run_goal detects the InvalidTransition, resolves
the ancestor sibling, patches depends_on via set_depends_on, re-orders, and
restarts.  The repair fires at most once per _run_goal invocation.
"""
from __future__ import annotations

import logging as logging_mod

import pytest

import app.worker as worker_module
from app.agent import AgentResult, Status
from app.models import TaskState
from app.stats_store import StatsStore
from app.storage import TaskStore
from app.trace_store import TraceStore
from app.worker import Worker

SPACE_ID = "test-space"


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _make_result(*, exit_code: int = 0, status: Status | None = None) -> AgentResult:
    return AgentResult(
        exit_code=exit_code,
        session_id="sess-test",
        final_text="done.",
        stderr_tail="",
        status=status,
        context=None,
        raw_events=[],
        stopped=False,
        result_subtype=None,
    )


@pytest.fixture
async def worker(task_store, tmp_spaces_dir):
    return Worker(
        store=task_store,
        space_store=None,
        stats_store=StatsStore(tmp_spaces_dir),
        trace_store=TraceStore(tmp_spaces_dir),
    )


# ---------------------------------------------------------------------------
# Test 1 — auto-repair triggers and repairs
# ---------------------------------------------------------------------------


async def test_auto_repair_adds_sibling_dep_and_runs_in_order(
    worker, task_store, monkeypatch, caplog
):
    """Auto-repair fires when dep_sg carries a non-sibling dep on prereq_sg's doc.

    The dependent sub-goal (dep_sg) has depends_on=[prereq_doc.id] — a grandchild
    of root, not a sibling.  _topo_children ignores non-sibling deps, so dep_sg
    sorts before prereq_sg alphabetically ("dep" < "prereq") and is processed first.
    transition(dep_sg, ACTIVE) fails → repair walks up prereq_doc → finds prereq_sg
    as the sibling ancestor → calls set_depends_on → restarts loop → prereq_sg runs
    first → dep_sg runs after.

    (In the brief these are called sg_a=prereq and sg_b=dependent.  The sort order
    must be enforced by titles that make the dependent's ID sort before the prereq's
    ID, otherwise the prereq would run first and the dep would already be satisfied.)
    """
    run_order: list[str] = []

    async def fake_run_agent(task, *, user_message, on_event, cancel_event=None, space=None, goal_context=None, **kwargs):
        run_order.append(task.id)
        return _make_result(exit_code=0, status=Status.DONE)

    monkeypatch.setattr(worker_module, "run_agent", fake_run_agent)

    root = await task_store.create(space_id=SPACE_ID, title="Root Goal", brief="g", type="goal")

    # prereq_sg (sg_a in the brief): the prerequisite sub-goal, named so its ID
    # sorts AFTER dep_sg ("prereq" > "dep" alphabetically).
    prereq_sg = await task_store.create(
        space_id=SPACE_ID, title="prereq sg", brief="b", parent_id=root.id, type="goal"
    )
    prereq_doc = await task_store.create(
        space_id=SPACE_ID, title="prereq doc", brief="b", parent_id=prereq_sg.id
    )

    # dep_sg (sg_b in the brief): the dependent sub-goal, named so its ID sorts
    # BEFORE prereq_sg.  It has depends_on=[prereq_doc.id] — a non-sibling
    # (grandchild) dep.  Because there is no sibling dep, _topo_children puts
    # dep_sg first; transition fails; repair fires and adds prereq_sg.id.
    dep_sg = await task_store.create(
        space_id=SPACE_ID, title="dep sg", brief="b", parent_id=root.id, type="goal",
        depends_on=[prereq_doc.id],
    )
    dep_task = await task_store.create(
        space_id=SPACE_ID, title="dep task", brief="b", parent_id=dep_sg.id
    )

    await task_store.transition(
        root.id, TaskState.ACTIVE, allowed={(TaskState.BACKLOG, TaskState.ACTIVE)}
    )

    with caplog.at_level(logging_mod.WARNING, logger="cronos.worker"):
        await worker._run_goal(root.id, None)

    # dep_sg.depends_on now contains prereq_sg.id (sibling dep was added).
    dep_sg_after = task_store.get(dep_sg.id)
    assert prereq_sg.id in dep_sg_after.depends_on

    # Warning log was emitted containing "Auto-repaired".
    repair_logs = [r for r in caplog.records if "Auto-repaired" in r.message]
    assert repair_logs, "Expected at least one Auto-repaired warning"

    # prereq_sg ran before dep_sg.
    assert run_order.index(prereq_doc.id) < run_order.index(dep_task.id)

    # Goal completes successfully.
    assert task_store.get(root.id).state == TaskState.DONE


# ---------------------------------------------------------------------------
# Test 2 — already-correct sibling deps not touched
# ---------------------------------------------------------------------------


async def test_correct_sibling_deps_not_repaired(
    worker, task_store, monkeypatch, caplog
):
    """When sg_b already has depends_on=[sg_a.id], no auto-repair fires.

    Setup:
      root
        ├── sg_a  (no deps)
        │     └── sg_a_task
        └── sg_b  (depends_on=[sg_a.id] — already correct)
              └── sg_b_task
    """
    run_order: list[str] = []

    async def fake_run_agent(task, *, user_message, on_event, cancel_event=None, space=None, goal_context=None, **kwargs):
        run_order.append(task.id)
        return _make_result(exit_code=0, status=Status.DONE)

    monkeypatch.setattr(worker_module, "run_agent", fake_run_agent)

    root = await task_store.create(space_id=SPACE_ID, title="Root Goal", brief="g", type="goal")

    sg_a = await task_store.create(
        space_id=SPACE_ID, title="sg_a", brief="b", parent_id=root.id, type="goal"
    )
    sg_a_task = await task_store.create(
        space_id=SPACE_ID, title="sg_a task", brief="b", parent_id=sg_a.id
    )

    sg_b = await task_store.create(
        space_id=SPACE_ID, title="sg_b", brief="b", parent_id=root.id, type="goal",
        depends_on=[sg_a.id],
    )
    sg_b_task = await task_store.create(
        space_id=SPACE_ID, title="sg_b task", brief="b", parent_id=sg_b.id
    )

    await task_store.transition(
        root.id, TaskState.ACTIVE, allowed={(TaskState.BACKLOG, TaskState.ACTIVE)}
    )

    with caplog.at_level(logging_mod.WARNING, logger="cronos.worker"):
        await worker._run_goal(root.id, None)

    # No auto-repair warning emitted.
    assert not any("Auto-repaired" in r.message for r in caplog.records)

    # Normal execution order preserved: sg_a before sg_b.
    assert run_order.index(sg_a_task.id) < run_order.index(sg_b_task.id)

    # Goal completes successfully.
    assert task_store.get(root.id).state == TaskState.DONE


# ---------------------------------------------------------------------------
# Test 3 — repair capped at 1 attempt; unresolvable dep fails cleanly
# ---------------------------------------------------------------------------


async def test_unresolvable_dep_fails_cleanly_no_infinite_loop(
    worker, task_store, monkeypatch, caplog
):
    """A child whose dep cannot be walked up to any sibling causes clean failure.

    When dep_task is None (nonexistent ID) the parent-chain walk is skipped,
    repaired_any stays False, and the goal ends in WAITING — not an infinite loop.
    The _repaired flag ensures the repair block is entered at most once even if
    the dep ID were partially resolvable on a second pass.

    Setup:
      root
        ├── sg_a  (depends_on=["nonexistent-dep-id"])  ← unresolvable
        │     └── sg_a_task
        └── sg_b  (no deps)
              └── sg_b_task
    """
    async def fake_run_agent(task, *, user_message, on_event, cancel_event=None, space=None, goal_context=None, **kwargs):
        return _make_result(exit_code=0, status=Status.DONE)

    monkeypatch.setattr(worker_module, "run_agent", fake_run_agent)

    root = await task_store.create(space_id=SPACE_ID, title="Root Goal", brief="g", type="goal")

    # sg_a depends on a task that does not exist → repair cannot resolve it.
    sg_a = await task_store.create(
        space_id=SPACE_ID, title="sg_a", brief="b", parent_id=root.id, type="goal",
        depends_on=["nonexistent-dep-id"],
    )
    await task_store.create(
        space_id=SPACE_ID, title="sg_a task", brief="b", parent_id=sg_a.id
    )

    sg_b = await task_store.create(
        space_id=SPACE_ID, title="sg_b", brief="b", parent_id=root.id, type="goal"
    )
    await task_store.create(
        space_id=SPACE_ID, title="sg_b task", brief="b", parent_id=sg_b.id
    )

    await task_store.transition(
        root.id, TaskState.ACTIVE, allowed={(TaskState.BACKLOG, TaskState.ACTIVE)}
    )

    with caplog.at_level(logging_mod.WARNING, logger="cronos.worker"):
        await worker._run_goal(root.id, None)

    # Goal fails cleanly (no infinite loop).
    root_after = task_store.get(root.id)
    assert root_after.state == TaskState.WAITING

    # failed_child_id is reflected: root is in WAITING with a waiting_question set.
    assert root_after.waiting_question is not None

    # No Auto-repaired warning (nothing was repaired — dep_task was None).
    assert not any("Auto-repaired" in r.message for r in caplog.records)
