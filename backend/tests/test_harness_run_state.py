"""
Tests for backend/app/harnesses/run_state.py

Covers:
  - load() returns None for a non-existent file
  - save_atomic + load round-trip preserves all fields
  - save_atomic is atomic (uses tmpfile + os.replace pattern)
  - NodeState with all fields set
  - in_progress nodes are returned unchanged by load() (caller handles reconciliation)
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from app.harnesses.run_state import NodeState, RunState, load, save_atomic


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _minimal_run_state() -> RunState:
    """Return a RunState with no nodes executed."""
    return RunState(
        run_id="run-001",
        harness_id="harness-abc",
        goal_task_id="task-xyz",
        nodes_executed={},
    )


def _full_run_state() -> RunState:
    """Return a RunState with a variety of node statuses."""
    return RunState(
        run_id="run-002",
        harness_id="harness-def",
        goal_task_id="task-uvw",
        nodes_executed={
            "node-pending": NodeState(status="pending"),
            "node-done": NodeState(
                status="done",
                child_task_id="child-1",
                output="Hello World",
                reason=None,
            ),
            "node-failed": NodeState(
                status="failed",
                child_task_id="child-2",
                output=None,
                reason="agent returned non-zero",
            ),
            "node-skipped": NodeState(
                status="skipped",
                child_task_id=None,
                output=None,
                reason="upstream_failed",
            ),
            "node-in-progress": NodeState(
                status="in_progress",
                child_task_id="child-3",
                output=None,
                reason=None,
            ),
        },
    )


# ---------------------------------------------------------------------------
# load() — non-existent file
# ---------------------------------------------------------------------------


def test_load_returns_none_for_missing_file(tmp_path: Path) -> None:
    """load() must return None when the target path does not exist."""
    result = load(tmp_path / "nonexistent.json")
    assert result is None


def test_load_returns_none_for_missing_file_str(tmp_path: Path) -> None:
    """load() also accepts a str path and returns None if absent."""
    result = load(str(tmp_path / "also_missing.json"))
    assert result is None


# ---------------------------------------------------------------------------
# save_atomic + load round-trip
# ---------------------------------------------------------------------------


def test_round_trip_minimal(tmp_path: Path) -> None:
    """save_atomic + load preserves a minimal RunState."""
    state = _minimal_run_state()
    target = tmp_path / "state.json"
    save_atomic(target, state)
    loaded = load(target)

    assert loaded is not None
    assert loaded.run_id == state.run_id
    assert loaded.harness_id == state.harness_id
    assert loaded.goal_task_id == state.goal_task_id
    assert loaded.nodes_executed == {}


def test_round_trip_full(tmp_path: Path) -> None:
    """save_atomic + load round-trip preserves all NodeState fields."""
    state = _full_run_state()
    target = tmp_path / "full_state.json"
    save_atomic(target, state)
    loaded = load(target)

    assert loaded is not None
    assert loaded.run_id == state.run_id
    assert loaded.harness_id == state.harness_id
    assert loaded.goal_task_id == state.goal_task_id

    # Verify each node
    assert set(loaded.nodes_executed.keys()) == set(state.nodes_executed.keys())

    for node_id, orig in state.nodes_executed.items():
        restored = loaded.nodes_executed[node_id]
        assert restored.status == orig.status, f"status mismatch for {node_id}"
        assert restored.child_task_id == orig.child_task_id, f"child_task_id mismatch for {node_id}"
        assert restored.output == orig.output, f"output mismatch for {node_id}"
        assert restored.reason == orig.reason, f"reason mismatch for {node_id}"


def test_round_trip_node_state_all_fields(tmp_path: Path) -> None:
    """NodeState with every field populated survives a full round-trip."""
    state = RunState(
        run_id="run-all-fields",
        harness_id="h1",
        goal_task_id="g1",
        nodes_executed={
            "n1": NodeState(
                status="done",
                child_task_id="ct-999",
                output="some output text",
                reason="custom reason",
            )
        },
    )
    target = tmp_path / "all_fields.json"
    save_atomic(target, state)
    loaded = load(target)

    assert loaded is not None
    ns = loaded.nodes_executed["n1"]
    assert ns.status == "done"
    assert ns.child_task_id == "ct-999"
    assert ns.output == "some output text"
    assert ns.reason == "custom reason"


def test_round_trip_preserves_string_path(tmp_path: Path) -> None:
    """save_atomic and load accept str as well as Path."""
    state = _minimal_run_state()
    target = str(tmp_path / "str_path.json")
    save_atomic(target, state)
    loaded = load(target)
    assert loaded is not None
    assert loaded.run_id == state.run_id


# ---------------------------------------------------------------------------
# save_atomic is atomic (tmpfile + os.replace pattern)
# ---------------------------------------------------------------------------


def test_save_atomic_uses_tmpfile_and_replace(tmp_path: Path) -> None:
    """
    save_atomic must write via a temp file and call os.replace().

    We spy on os.replace to confirm it is called, and verify that the
    final file is written correctly.
    """
    state = _minimal_run_state()
    target = tmp_path / "atomic.json"

    replace_calls: list[tuple[str, str]] = []
    real_replace = os.replace

    def spy_replace(src: str, dst: str) -> None:
        replace_calls.append((src, str(dst)))
        real_replace(src, dst)

    with patch("app.harnesses.run_state.os.replace", side_effect=spy_replace):
        save_atomic(target, state)

    # os.replace must have been called exactly once
    assert len(replace_calls) == 1, "os.replace should be called exactly once"
    src_path, dst_path = replace_calls[0]

    # The destination must be the target path
    assert Path(dst_path) == target

    # The source (tmpfile) must have been in the same directory as the target
    assert Path(src_path).parent == target.parent

    # The tmpfile should no longer exist (was replaced / moved)
    assert not Path(src_path).exists(), "tmp file should not remain after os.replace"

    # The target file exists and is valid JSON
    assert target.exists()
    with target.open() as fh:
        data = json.load(fh)
    assert data["run_id"] == state.run_id


def test_save_atomic_creates_parent_dirs(tmp_path: Path) -> None:
    """save_atomic creates parent directories if they do not exist."""
    deep = tmp_path / "a" / "b" / "c" / "state.json"
    state = _minimal_run_state()
    save_atomic(deep, state)
    assert deep.exists()
    loaded = load(deep)
    assert loaded is not None
    assert loaded.run_id == state.run_id


def test_save_atomic_overwrites_existing_file(tmp_path: Path) -> None:
    """save_atomic replaces an existing file with the new state."""
    target = tmp_path / "overwrite.json"
    state_v1 = RunState(
        run_id="v1", harness_id="h", goal_task_id="g", nodes_executed={}
    )
    state_v2 = RunState(
        run_id="v2",
        harness_id="h",
        goal_task_id="g",
        nodes_executed={
            "n": NodeState(status="done", output="v2 output")
        },
    )
    save_atomic(target, state_v1)
    save_atomic(target, state_v2)

    loaded = load(target)
    assert loaded is not None
    assert loaded.run_id == "v2"
    assert loaded.nodes_executed["n"].output == "v2 output"


# ---------------------------------------------------------------------------
# in_progress → caller handles reconciliation (load does NOT auto-convert)
# ---------------------------------------------------------------------------


def test_load_does_not_convert_in_progress_to_pending(tmp_path: Path) -> None:
    """
    load() must return in_progress nodes as-is.

    The caller (HarnessExecutor) is responsible for reconciling in_progress
    nodes against the live TaskStore — load() must not auto-convert them.
    """
    state = RunState(
        run_id="resume-test",
        harness_id="h1",
        goal_task_id="g1",
        nodes_executed={
            "completed": NodeState(status="done", child_task_id="c1", output="ok"),
            "interrupted": NodeState(
                status="in_progress",
                child_task_id="c2",
                output=None,
            ),
        },
    )
    target = tmp_path / "resume.json"
    save_atomic(target, state)
    loaded = load(target)

    assert loaded is not None
    # 'done' node must still be 'done'
    assert loaded.nodes_executed["completed"].status == "done"
    # 'in_progress' node must remain 'in_progress'; caller reconciles
    assert loaded.nodes_executed["interrupted"].status == "in_progress"
    assert loaded.nodes_executed["interrupted"].child_task_id == "c2"


def test_load_in_progress_child_task_id_preserved(tmp_path: Path) -> None:
    """
    After loading, the child_task_id of an in_progress node is available
    so the executor can query TaskStore for reconciliation.
    """
    state = RunState(
        run_id="r1",
        harness_id="h1",
        goal_task_id="g1",
        nodes_executed={
            "node-wip": NodeState(
                status="in_progress",
                child_task_id="child-task-42",
            )
        },
    )
    target = tmp_path / "wip.json"
    save_atomic(target, state)
    loaded = load(target)

    assert loaded is not None
    assert loaded.nodes_executed["node-wip"].child_task_id == "child-task-42"


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_load_raises_on_invalid_json(tmp_path: Path) -> None:
    """load() raises an exception when the file contains invalid JSON."""
    bad = tmp_path / "bad.json"
    bad.write_text("NOT VALID JSON {{{", encoding="utf-8")
    with pytest.raises(Exception):
        load(bad)


def test_run_state_to_dict_and_from_dict(tmp_path: Path) -> None:
    """to_dict / from_dict are inverses of each other."""
    original = _full_run_state()
    d = original.to_dict()
    restored = RunState.from_dict(d)

    assert restored.run_id == original.run_id
    assert restored.harness_id == original.harness_id
    assert restored.goal_task_id == original.goal_task_id
    for node_id, orig_ns in original.nodes_executed.items():
        rest_ns = restored.nodes_executed[node_id]
        assert rest_ns.status == orig_ns.status
        assert rest_ns.child_task_id == orig_ns.child_task_id
        assert rest_ns.output == orig_ns.output
        assert rest_ns.reason == orig_ns.reason


# ---------------------------------------------------------------------------
# waiting_node_id — default, set, clear, serialisation
# ---------------------------------------------------------------------------


def test_waiting_node_id_defaults_to_none() -> None:
    """RunState.waiting_node_id must default to None when not provided."""
    state = RunState(
        run_id="r1",
        harness_id="h1",
        goal_task_id="g1",
    )
    assert state.waiting_node_id is None


def test_waiting_node_id_set_and_retrieve() -> None:
    """Setting waiting_node_id to a node id is reflected on the instance."""
    state = RunState(
        run_id="r1",
        harness_id="h1",
        goal_task_id="g1",
    )
    state.waiting_node_id = "wait-node-42"
    assert state.waiting_node_id == "wait-node-42"


def test_waiting_node_id_clear() -> None:
    """Clearing waiting_node_id (setting back to None) works correctly."""
    state = RunState(
        run_id="r1",
        harness_id="h1",
        goal_task_id="g1",
        waiting_node_id="wait-node-42",
    )
    assert state.waiting_node_id == "wait-node-42"
    state.waiting_node_id = None
    assert state.waiting_node_id is None


def test_waiting_node_id_serialisation_round_trip(tmp_path: Path) -> None:
    """waiting_node_id survives a save_atomic + load round-trip."""
    state = RunState(
        run_id="r-wait",
        harness_id="h-wait",
        goal_task_id="g-wait",
        waiting_node_id="wait-node-99",
    )
    target = tmp_path / "wait_state.json"
    save_atomic(target, state)
    loaded = load(target)

    assert loaded is not None
    assert loaded.waiting_node_id == "wait-node-99"


def test_waiting_node_id_none_serialisation_round_trip(tmp_path: Path) -> None:
    """waiting_node_id=None survives a save_atomic + load round-trip."""
    state = RunState(
        run_id="r-no-wait",
        harness_id="h-no-wait",
        goal_task_id="g-no-wait",
        waiting_node_id=None,
    )
    target = tmp_path / "no_wait_state.json"
    save_atomic(target, state)
    loaded = load(target)

    assert loaded is not None
    assert loaded.waiting_node_id is None


def test_waiting_node_id_to_dict_and_from_dict() -> None:
    """to_dict/from_dict round-trip preserves waiting_node_id."""
    state = RunState(
        run_id="r1",
        harness_id="h1",
        goal_task_id="g1",
        waiting_node_id="wait-abc",
    )
    d = state.to_dict()
    assert d["waiting_node_id"] == "wait-abc"

    restored = RunState.from_dict(d)
    assert restored.waiting_node_id == "wait-abc"


def test_waiting_node_id_from_dict_missing_key() -> None:
    """from_dict gracefully handles older payloads that lack waiting_node_id."""
    data = {
        "run_id": "old-run",
        "harness_id": "h1",
        "goal_task_id": "g1",
        "nodes_executed": {},
        # no "waiting_node_id" key — simulates a pre-I2 persisted file
    }
    restored = RunState.from_dict(data)
    assert restored.waiting_node_id is None


def test_waiting_node_id_cleared_after_set_serialises_as_none(tmp_path: Path) -> None:
    """After clearing waiting_node_id, the persisted file reflects None."""
    state = RunState(
        run_id="r-clear",
        harness_id="h1",
        goal_task_id="g1",
        waiting_node_id="wait-node-77",
    )
    target = tmp_path / "clear_test.json"
    save_atomic(target, state)

    # Simulate executor clearing waiting_node_id on resume
    state.waiting_node_id = None
    save_atomic(target, state)

    loaded = load(target)
    assert loaded is not None
    assert loaded.waiting_node_id is None


# ---------------------------------------------------------------------------
# NodeState status='in_progress' validity for control-flow nodes
# ---------------------------------------------------------------------------


def test_node_state_in_progress_is_valid() -> None:
    """NodeState accepts status='in_progress' (valid for control-flow nodes)."""
    ns = NodeState(status="in_progress")
    assert ns.status == "in_progress"


def test_node_state_in_progress_in_run_state() -> None:
    """RunState can hold a control-flow node with status='in_progress'."""
    state = RunState(
        run_id="r-cf",
        harness_id="h1",
        goal_task_id="g1",
        nodes_executed={
            "decision-1": NodeState(status="in_progress"),
        },
    )
    assert state.nodes_executed["decision-1"].status == "in_progress"


def test_node_state_in_progress_round_trip(tmp_path: Path) -> None:
    """
    A control-flow node with status='in_progress' survives a save/load cycle
    unchanged — the executor is responsible for reconciling it, not load().
    """
    state = RunState(
        run_id="r-cf-rt",
        harness_id="h1",
        goal_task_id="g1",
        nodes_executed={
            "wait-1": NodeState(
                status="in_progress",
                child_task_id=None,
                reason=None,
            ),
        },
        waiting_node_id="wait-1",
    )
    target = tmp_path / "cf_state.json"
    save_atomic(target, state)
    loaded = load(target)

    assert loaded is not None
    assert loaded.nodes_executed["wait-1"].status == "in_progress"
    assert loaded.waiting_node_id == "wait-1"
