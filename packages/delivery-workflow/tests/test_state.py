"""Tests for lib/state (StateStore + EventLog + resume_node_status) — R9/R10/R11."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from delivery_workflow.lib.state.events import EventLog
from delivery_workflow.lib.state.store import StateStore, resume_node_status
from delivery_workflow.state_types import BudgetState, NodeState, WorkflowState


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_state(
    run_dir: Path,
    *,
    status: str = "running",
    nodes: dict[str, NodeState] | None = None,
) -> WorkflowState:
    state = WorkflowState(
        spec="delivery/v1",
        run_id="run-test-001",
        status=status,  # type: ignore[arg-type]
        budget=BudgetState(usd_ceiling=25.0, usd_spent=0.0),
        nodes=nodes or {},
    )
    StateStore(run_dir).write(state)
    return state


# ---------------------------------------------------------------------------
# StateStore — basic read/write round-trip (R9)
# ---------------------------------------------------------------------------


def test_state_store_write_creates_file(tmp_path: Path) -> None:
    store = StateStore(tmp_path)
    assert not store.exists()
    _make_state(tmp_path)
    assert store.exists()
    assert (tmp_path / "state.json").exists()


def test_state_store_round_trip_minimal(tmp_path: Path) -> None:
    original = _make_state(tmp_path)
    recovered = StateStore(tmp_path).read()
    assert recovered.spec == original.spec
    assert recovered.run_id == original.run_id
    assert recovered.status == original.status
    assert recovered.budget.usd_ceiling == original.budget.usd_ceiling
    assert recovered.budget.usd_spent == original.budget.usd_spent
    assert recovered.nodes == {}


def test_state_store_round_trip_with_node(tmp_path: Path) -> None:
    node = NodeState(
        status="looping",
        attempt=2,
        gate={"decision": "needs_fix", "errors": []},
        artifact_paths=["attempt2.md"],
        telemetry={"tokens": 41233.0, "usd": 0.62, "seconds": 88.0},
    )
    _make_state(tmp_path, nodes={"review": node})
    recovered = StateStore(tmp_path).read()
    rnode = recovered.nodes["review"]
    assert rnode.status == "looping"
    assert rnode.attempt == 2
    assert rnode.gate == {"decision": "needs_fix", "errors": []}
    assert rnode.artifact_paths == ["attempt2.md"]
    assert rnode.telemetry is not None
    assert rnode.telemetry["tokens"] == 41233.0


def test_state_json_is_human_readable(tmp_path: Path) -> None:
    _make_state(tmp_path, nodes={"scout": NodeState(status="done")})
    raw = (tmp_path / "state.json").read_text()
    data = json.loads(raw)
    assert data["spec"] == "delivery/v1"
    assert "nodes" in data
    assert "scout" in data["nodes"]


def test_state_store_overwrites_on_second_write(tmp_path: Path) -> None:
    store = StateStore(tmp_path)
    s1 = _make_state(tmp_path, status="running")
    s1.status = "done"
    store.write(s1)
    recovered = store.read()
    assert recovered.status == "done"


# ---------------------------------------------------------------------------
# StateStore — atomic write (no torn temp file left behind)
# ---------------------------------------------------------------------------


def test_atomic_write_no_temp_files_left(tmp_path: Path) -> None:
    _make_state(tmp_path)
    tmp_files = list(tmp_path.glob("*.tmp"))
    assert tmp_files == [], f"Temp files found: {tmp_files}"


# ---------------------------------------------------------------------------
# StateStore — patch (R9 read-modify-write)
# ---------------------------------------------------------------------------


def test_patch_updates_status(tmp_path: Path) -> None:
    _make_state(tmp_path, status="running")
    store = StateStore(tmp_path)
    updated = store.patch({"status": "done"})
    assert updated.status == "done"
    assert store.read().status == "done"


def test_patch_updates_budget_spent(tmp_path: Path) -> None:
    _make_state(tmp_path)
    store = StateStore(tmp_path)
    store.patch({"budget": {"usd_ceiling": 25.0, "usd_spent": 4.31}})
    assert store.read().budget.usd_spent == pytest.approx(4.31)


def test_patch_preserves_unrelated_fields(tmp_path: Path) -> None:
    _make_state(tmp_path, nodes={"scout": NodeState(status="done")})
    store = StateStore(tmp_path)
    store.patch({"status": "done"})
    recovered = store.read()
    assert "scout" in recovered.nodes
    assert recovered.nodes["scout"].status == "done"


# ---------------------------------------------------------------------------
# StateStore — resume reconstruction (R11)
# ---------------------------------------------------------------------------


def test_resume_done_node_returns_skip(tmp_path: Path) -> None:
    """R11 AC: a node whose status == 'done' must be skipped on resume."""
    done_node = NodeState(status="done", artifact_paths=["report.md"])
    _make_state(tmp_path, nodes={"scout": done_node})
    recovered = StateStore(tmp_path).read()
    action = resume_node_status(recovered.nodes.get("scout"))
    assert action == "skip"


def test_resume_running_node_returns_redispatch(tmp_path: Path) -> None:
    """R11 AC: a node left 'running' (torn run) must be re-dispatched on resume."""
    running_node = NodeState(status="running")
    _make_state(tmp_path, nodes={"analyst": running_node})
    recovered = StateStore(tmp_path).read()
    action = resume_node_status(recovered.nodes.get("analyst"))
    assert action == "re-dispatch"


def test_resume_missing_node_returns_dispatch(tmp_path: Path) -> None:
    """R11 AC: a node absent from state.json must be dispatched fresh."""
    _make_state(tmp_path, nodes={})
    recovered = StateStore(tmp_path).read()
    action = resume_node_status(recovered.nodes.get("architect"))
    assert action == "dispatch"


def test_resume_all_statuses(tmp_path: Path) -> None:
    """R11: non-done statuses (looping, blocked, failed) all map to re-dispatch."""
    for status in ("looping", "blocked", "failed", "escalated"):
        node = NodeState(status=status)
        action = resume_node_status(node)
        assert action == "re-dispatch", f"Expected re-dispatch for status={status}"


def test_resume_partial_state_json(tmp_path: Path) -> None:
    """Simulate a partial state.json (only some nodes done) and confirm policies."""
    nodes = {
        "scout": NodeState(status="done"),
        "analyst": NodeState(status="running"),
    }
    _make_state(tmp_path, nodes=nodes)
    recovered = StateStore(tmp_path).read()
    assert resume_node_status(recovered.nodes.get("scout")) == "skip"
    assert resume_node_status(recovered.nodes.get("analyst")) == "re-dispatch"
    assert resume_node_status(recovered.nodes.get("designer")) == "dispatch"


# ---------------------------------------------------------------------------
# EventLog — append-only log (R10)
# ---------------------------------------------------------------------------


def test_event_log_empty_before_first_append(tmp_path: Path) -> None:
    log = EventLog(tmp_path)
    assert log.read_all() == []
    assert not (tmp_path / "events.jsonl").exists()


def test_event_log_append_creates_file(tmp_path: Path) -> None:
    log = EventLog(tmp_path)
    log.append({"type": "node_started", "node": "scout"})
    assert (tmp_path / "events.jsonl").exists()


def test_event_log_round_trip(tmp_path: Path) -> None:
    log = EventLog(tmp_path)
    log.append({"type": "node_started", "node": "scout"})
    log.append({"type": "node_done", "node": "scout", "status": "done"})
    events = log.read_all()
    assert len(events) == 2
    assert events[0]["type"] == "node_started"
    assert events[1]["type"] == "node_done"


def test_event_log_auto_injects_ts(tmp_path: Path) -> None:
    log = EventLog(tmp_path)
    log.append({"type": "started"})
    events = log.read_all()
    assert "ts" in events[0]
    assert "T" in events[0]["ts"]  # ISO-8601


def test_event_log_preserves_explicit_ts(tmp_path: Path) -> None:
    log = EventLog(tmp_path)
    log.append({"type": "started", "ts": "2026-01-01T00:00:00+00:00"})
    events = log.read_all()
    assert events[0]["ts"] == "2026-01-01T00:00:00+00:00"


def test_event_log_is_append_only(tmp_path: Path) -> None:
    log = EventLog(tmp_path)
    for i in range(5):
        log.append({"seq": i})
    events = log.read_all()
    assert [e["seq"] for e in events] == [0, 1, 2, 3, 4]


def test_event_log_each_line_is_valid_json(tmp_path: Path) -> None:
    log = EventLog(tmp_path)
    log.append({"type": "budget_exceeded", "usd_spent": 25.01})
    raw = (tmp_path / "events.jsonl").read_text()
    for line in raw.strip().splitlines():
        json.loads(line)  # must not raise


# ---------------------------------------------------------------------------
# Integration — StateStore + EventLog together (R9 + R10)
# ---------------------------------------------------------------------------


def test_state_and_events_coexist(tmp_path: Path) -> None:
    _make_state(tmp_path, nodes={"scout": NodeState(status="done")})
    log = EventLog(tmp_path)
    log.append({"type": "node_done", "node": "scout"})
    log.append({"type": "run_complete"})

    store = StateStore(tmp_path)
    state = store.read()
    assert state.nodes["scout"].status == "done"

    events = log.read_all()
    assert len(events) == 2
    assert events[1]["type"] == "run_complete"


# ---------------------------------------------------------------------------
# Partial-node tolerance — lib.gate writes statusless node entries directly
# into state.json; StateStore.read() must not KeyError on them.
# ---------------------------------------------------------------------------


def test_read_tolerates_node_missing_status(tmp_path: Path) -> None:
    """A node written by lib.gate._write_gate_result has only a `gate` key (no
    `status`). StateStore.read() must default it to 'pending', not raise
    KeyError('status')."""
    state_path = tmp_path / "state.json"
    state_path.write_text(json.dumps({
        "spec": "wf", "run_id": "goal-1", "status": "running",
        "budget": {"usd_ceiling": 0.0, "usd_spent": 0.0},
        "nodes": {
            "scout": {"status": "done", "attempt": 0, "artifact_paths": []},
            # gate node as lib.gate would write it — no status key:
            "g-scout": {"gate": {"decision": "proceed", "errors": []}},
        },
    }))

    recovered = StateStore(tmp_path).read()  # must not raise
    assert recovered.nodes["g-scout"].status == "pending"
    assert recovered.nodes["g-scout"].gate == {"decision": "proceed", "errors": []}
    assert recovered.nodes["scout"].status == "done"


def test_gate_write_then_read_does_not_raise(tmp_path: Path) -> None:
    """End-to-end regression: lib.gate.runGate persists a gate result into a
    bootstrapped state.json (creating a statusless node), and a subsequent
    StateStore.read() succeeds — the KeyError('status') path from the delivery
    runner."""
    from delivery_workflow.lib.gate import runGate

    # Bootstrap a valid state.json (as the delivery driver now does).
    _make_state(tmp_path, status="running")

    # A gate with no checks → proceed; writes nodes.g-scout.gate (no status).
    runGate(
        {"id": "g-scout", "checks": []},
        [],
        space=tmp_path,
        gate_id="g-scout",
        state_path=tmp_path / "state.json",
    )

    recovered = StateStore(tmp_path).read()  # previously KeyError('status')
    assert recovered.nodes["g-scout"].gate is not None
    assert recovered.nodes["g-scout"].status == "pending"
