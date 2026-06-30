"""
tests/test_run_executor_runner_flag.py — Unit tests for CRONOS_HARNESS_RUNNER flag branch (I5).

Tests cover:
1. _read_executor_variant and _write_executor_variant helpers (backward-compat).
2. execute_harness_run_body dispatches to BFS path when flag is unset.
3. execute_harness_run_body dispatches to runner path when CRONOS_HARNESS_RUNNER=1.
4. Resume path follows stored executor_variant, NOT the current env flag (four combinations).
5. Backward-compat: RunState JSON without executor_variant key defaults to 'bfs'.
"""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Import helpers under test.
# ---------------------------------------------------------------------------
from app.run_executor import (
    _DEFAULT_EXECUTOR_VARIANT,
    _EXECUTOR_VARIANT_KEY,
    _read_executor_variant,
    _write_executor_variant,
)


# ===========================================================================
# Section 1: _read_executor_variant — standalone helper tests
# ===========================================================================


class TestReadExecutorVariant:
    """Tests for _read_executor_variant()."""

    def test_returns_bfs_when_file_missing(self, tmp_path):
        """Missing file → backward-compatible default 'bfs'."""
        path = tmp_path / "nonexistent.json"
        assert _read_executor_variant(path) == "bfs"

    def test_returns_bfs_when_key_absent(self, tmp_path):
        """File exists but has no executor_variant key → default 'bfs' (backward compat)."""
        p = tmp_path / "run.json"
        p.write_text(
            json.dumps({
                "run_id": "run-1",
                "harness_id": "h1",
                "goal_task_id": "run-1",
                "nodes_executed": {},
                "status": "running",
                "waiting_node_id": None,
            }),
            encoding="utf-8",
        )
        assert _read_executor_variant(p) == "bfs"

    def test_returns_stored_variant_bfs(self, tmp_path):
        """File contains executor_variant='bfs' → returns 'bfs'."""
        p = tmp_path / "run.json"
        p.write_text(
            json.dumps({
                "run_id": "r", "harness_id": "h", "goal_task_id": "r",
                "nodes_executed": {}, "executor_variant": "bfs",
            }),
            encoding="utf-8",
        )
        assert _read_executor_variant(p) == "bfs"

    def test_returns_stored_variant_runner(self, tmp_path):
        """File contains executor_variant='runner' → returns 'runner'."""
        p = tmp_path / "run.json"
        p.write_text(
            json.dumps({
                "run_id": "r", "harness_id": "h", "goal_task_id": "r",
                "nodes_executed": {}, "executor_variant": "runner",
            }),
            encoding="utf-8",
        )
        assert _read_executor_variant(p) == "runner"

    def test_returns_bfs_on_malformed_json(self, tmp_path):
        """Malformed JSON → fallback to 'bfs'."""
        p = tmp_path / "run.json"
        p.write_text("not-json{{{", encoding="utf-8")
        assert _read_executor_variant(p) == "bfs"


# ===========================================================================
# Section 2: _write_executor_variant — standalone helper tests
# ===========================================================================


class TestWriteExecutorVariant:
    """Tests for _write_executor_variant()."""

    def test_creates_stub_when_file_missing(self, tmp_path):
        """If the file does not exist, write a minimal stub with the variant."""
        p = tmp_path / "run.json"
        _write_executor_variant(p, "runner", "run-id", "h-id")
        data = json.loads(p.read_text(encoding="utf-8"))
        assert data[_EXECUTOR_VARIANT_KEY] == "runner"
        assert data["run_id"] == "run-id"
        assert data["harness_id"] == "h-id"

    def test_patches_existing_file(self, tmp_path):
        """Existing file gets executor_variant key added without losing other fields."""
        p = tmp_path / "run.json"
        original = {
            "run_id": "r",
            "harness_id": "h",
            "goal_task_id": "r",
            "nodes_executed": {"n1": {"status": "done"}},
            "status": "running",
        }
        p.write_text(json.dumps(original), encoding="utf-8")
        _write_executor_variant(p, "bfs", "r", "h")
        data = json.loads(p.read_text(encoding="utf-8"))
        assert data[_EXECUTOR_VARIANT_KEY] == "bfs"
        # Existing fields preserved.
        assert data["nodes_executed"]["n1"]["status"] == "done"

    def test_overwrite_existing_variant(self, tmp_path):
        """Can update an existing executor_variant value."""
        p = tmp_path / "run.json"
        p.write_text(json.dumps({
            "executor_variant": "runner", "run_id": "r",
            "harness_id": "h", "goal_task_id": "r",
            "nodes_executed": {},
        }), encoding="utf-8")
        _write_executor_variant(p, "bfs", "r", "h")
        data = json.loads(p.read_text(encoding="utf-8"))
        assert data[_EXECUTOR_VARIANT_KEY] == "bfs"

    def test_creates_parent_dirs(self, tmp_path):
        """Parent directories are created if missing."""
        p = tmp_path / "deeply" / "nested" / "run.json"
        _write_executor_variant(p, "bfs", "r", "h")
        assert p.exists()


# ===========================================================================
# Section 3: Backward-compat — RunState JSON without executor_variant
# ===========================================================================


class TestBackwardCompat:
    """Backward-compat: old RunState JSON without executor_variant field."""

    def test_old_run_state_without_variant_defaults_to_bfs(self, tmp_path):
        """Loading a pre-SG5 RunState JSON (no executor_variant) returns 'bfs'."""
        p = tmp_path / "old.json"
        # RunState serialised before SG5 — no executor_variant key.
        old_payload = {
            "run_id": "old-run",
            "harness_id": "legacy-harness",
            "goal_task_id": "old-run",
            "nodes_executed": {
                "n1": {
                    "status": "done",
                    "child_task_id": None,
                    "output": None,
                    "reason": None,
                    "started_at": None,
                    "ended_at": None,
                    "wake_at": None,
                    "attempt": 0,
                    "prior_finding_ids": [],
                }
            },
            "status": "running",
            "waiting_node_id": None,
            # No "executor_variant" key — pre-SG5 file.
        }
        p.write_text(json.dumps(old_payload, indent=2), encoding="utf-8")

        variant = _read_executor_variant(p)
        assert variant == "bfs", (
            f"Expected 'bfs' for pre-SG5 RunState (no executor_variant key), got {variant!r}"
        )

    def test_run_state_from_dict_still_loads(self):
        """RunState.from_dict() still loads old JSON cleanly (no executor_variant field)."""
        from app.harnesses.run_state import RunState

        old_payload = {
            "run_id": "old-run",
            "harness_id": "legacy-harness",
            "goal_task_id": "old-run",
            "nodes_executed": {},
            "status": "done",
            "waiting_node_id": None,
        }
        rs = RunState.from_dict(old_payload)
        assert rs.run_id == "old-run"
        assert rs.status == "done"


# ===========================================================================
# Section 4 + 5: execute_harness_run_body dispatch + resume combinations
# ===========================================================================
# Strategy: mock _data_dir() so run_state_path resolves under tmp_path;
#           mock harness_store.get to return a simple MagicMock harness;
#           patch _execute_harness_run_runner and HarnessExecutor.execute
#           to record which path was taken without running real execution.
# ===========================================================================


def _make_run_state_file(tmp_path: Path, space_id: str, task_id: str, variant: str) -> Path:
    """Create a run-state JSON file in the expected harness-runs directory."""
    p = tmp_path / "spaces" / space_id / ".cronos" / "harness-runs" / f"{task_id}.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "run_id": task_id,
        "harness_id": "h1",
        "goal_task_id": task_id,
        "nodes_executed": {},
        "status": "running",
        "waiting_node_id": None,
        "executor_variant": variant,
    }
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return p


def _make_run_executor_with_data_dir(tmp_path: Path):
    """Build a RunExecutor with all stores mocked and DATA_DIR pointing to tmp_path."""
    from app.run_executor import RunExecutor

    worker = MagicMock()
    worker._publish = AsyncMock(return_value=None)

    space_store = MagicMock()
    space_store.spaces_dir = tmp_path / "spaces"

    harness_store = MagicMock()
    dummy_harness = MagicMock()
    harness_store.get = AsyncMock(return_value=dummy_harness)

    store = MagicMock()
    store.finalize_run = AsyncMock(return_value=None)

    executor = RunExecutor(
        worker=worker,
        store=store,
        event_bus=MagicMock(),
        finalizer=MagicMock(),
        space_store=space_store,
        harness_store=harness_store,
        memory_store=None,
        done_sentinel={},
        lease_ttl=30.0,
        heartbeat_interval=10.0,
        memory_retrieval=None,
    )
    return executor


class TestExecuteHarnessRunBodyDispatch:
    """Tests for CRONOS_HARNESS_RUNNER flag branching in execute_harness_run_body."""

    @pytest.mark.asyncio
    async def test_bfs_path_chosen_when_flag_unset(self, tmp_path, monkeypatch):
        """When CRONOS_HARNESS_RUNNER is not set, BFS path is used (initial run)."""
        monkeypatch.delenv("CRONOS_HARNESS_RUNNER", raising=False)

        executor = _make_run_executor_with_data_dir(tmp_path)
        runner_called = []

        async def fake_runner(task_id, harness_id, space_id, **kwargs):
            runner_called.append(task_id)
            return True

        from app.harnesses.run_state import RunState

        async def fake_bfs_execute(self_, task_id, harness, space):
            return RunState(run_id=task_id, harness_id="h1", goal_task_id=task_id)

        with patch.object(executor, "_execute_harness_run_runner", new=fake_runner):
            with patch("app.harnesses.executor.HarnessExecutor.execute",
                       new=fake_bfs_execute):
                with patch("app.run_executor.RunExecutor._data_dir",
                           return_value=tmp_path):
                    result = await executor.execute_harness_run_body(
                        "task-1", "h1", "space-1",
                        initial_run=True,
                        space=MagicMock(),
                    )

        assert len(runner_called) == 0, (
            "Runner path must NOT be called when CRONOS_HARNESS_RUNNER is unset; "
            f"runner_called={runner_called}"
        )

    @pytest.mark.asyncio
    async def test_runner_path_chosen_when_flag_set(self, tmp_path, monkeypatch):
        """When CRONOS_HARNESS_RUNNER=1, runner path is used (initial run)."""
        monkeypatch.setenv("CRONOS_HARNESS_RUNNER", "1")

        executor = _make_run_executor_with_data_dir(tmp_path)
        runner_called = []

        async def fake_runner(task_id, harness_id, space_id, **kwargs):
            runner_called.append(task_id)
            return True

        async def fake_bfs_execute(self_, task_id, harness, space):
            raise AssertionError("BFS must NOT be called when CRONOS_HARNESS_RUNNER=1")

        with patch.object(executor, "_execute_harness_run_runner", new=fake_runner):
            with patch("app.harnesses.executor.HarnessExecutor.execute",
                       new=fake_bfs_execute):
                with patch("app.run_executor.RunExecutor._data_dir",
                           return_value=tmp_path):
                    result = await executor.execute_harness_run_body(
                        "task-2", "h1", "space-1",
                        initial_run=True,
                        space=MagicMock(),
                    )

        assert len(runner_called) == 1, (
            f"Runner path must be called when CRONOS_HARNESS_RUNNER=1; "
            f"runner_called={runner_called}"
        )
        assert runner_called[0] == "task-2"

    @pytest.mark.asyncio
    async def test_executor_variant_persisted_on_initial_bfs_run(self, tmp_path, monkeypatch):
        """When BFS path runs initially (flag unset), executor_variant='bfs' is stored."""
        monkeypatch.delenv("CRONOS_HARNESS_RUNNER", raising=False)

        executor = _make_run_executor_with_data_dir(tmp_path)
        space_id = "space-v"
        task_id = "task-v"

        run_state_path = (
            tmp_path / "spaces" / space_id / ".cronos" / "harness-runs" / f"{task_id}.json"
        )

        from app.harnesses.run_state import RunState

        async def fake_runner(tid, hid, sid, **kw):
            return True

        async def fake_bfs_execute(self_, task_id_, harness, space):
            return RunState(run_id=task_id_, harness_id="h1", goal_task_id=task_id_)

        with patch.object(executor, "_execute_harness_run_runner", new=fake_runner):
            with patch("app.harnesses.executor.HarnessExecutor.execute",
                       new=fake_bfs_execute):
                with patch("app.run_executor.RunExecutor._data_dir",
                           return_value=tmp_path):
                    await executor.execute_harness_run_body(
                        task_id, "h1", space_id,
                        initial_run=True,
                        space=MagicMock(),
                    )

        assert run_state_path.exists(), (
            "Run-state JSON must be written on initial run to persist executor_variant"
        )
        variant = _read_executor_variant(run_state_path)
        assert variant == "bfs", (
            f"executor_variant='bfs' must be stored when CRONOS_HARNESS_RUNNER is unset; "
            f"got {variant!r}"
        )

    @pytest.mark.asyncio
    async def test_executor_variant_persisted_on_initial_runner_run(self, tmp_path, monkeypatch):
        """When runner path runs initially (flag=1), executor_variant='runner' is stored."""
        monkeypatch.setenv("CRONOS_HARNESS_RUNNER", "1")

        executor = _make_run_executor_with_data_dir(tmp_path)
        space_id = "space-r"
        task_id = "task-r"

        run_state_path = (
            tmp_path / "spaces" / space_id / ".cronos" / "harness-runs" / f"{task_id}.json"
        )

        async def fake_runner(tid, hid, sid, **kw):
            return True

        with patch.object(executor, "_execute_harness_run_runner", new=fake_runner):
            with patch("app.run_executor.RunExecutor._data_dir",
                       return_value=tmp_path):
                await executor.execute_harness_run_body(
                    task_id, "h1", space_id,
                    initial_run=True,
                    space=MagicMock(),
                )

        assert run_state_path.exists(), (
            "Run-state JSON must be written on initial run to persist executor_variant"
        )
        variant = _read_executor_variant(run_state_path)
        assert variant == "runner", (
            f"executor_variant='runner' must be stored when CRONOS_HARNESS_RUNNER=1; "
            f"got {variant!r}"
        )


class TestResumeDispatchVariants:
    """Four combinations: (start=bfs, resume=bfs) (start=runner, resume=runner)
    (start=bfs, env=runner) (start=runner, env=bfs).

    The last two must follow the STORED variant, not the current env flag.
    """

    @pytest.mark.asyncio
    async def test_start_bfs_resume_bfs(self, tmp_path, monkeypatch):
        """Stored='bfs', env=unset → resume uses BFS path."""
        monkeypatch.delenv("CRONOS_HARNESS_RUNNER", raising=False)
        _make_run_state_file(tmp_path, "sp", "t1", "bfs")

        executor = _make_run_executor_with_data_dir(tmp_path)
        runner_called = []

        async def fake_runner(tid, hid, sid, **kw):
            runner_called.append(tid)
            return True

        from app.harnesses.run_state import RunState

        async def fake_bfs(self_, task_id, harness, space):
            return RunState(run_id=task_id, harness_id="h1", goal_task_id=task_id)

        with patch.object(executor, "_execute_harness_run_runner", new=fake_runner):
            with patch("app.harnesses.executor.HarnessExecutor.execute", new=fake_bfs):
                with patch("app.run_executor.RunExecutor._data_dir",
                           return_value=tmp_path):
                    await executor.execute_harness_run_body(
                        "t1", "h1", "sp", initial_run=False, space=MagicMock()
                    )

        assert len(runner_called) == 0, (
            "With stored_variant='bfs', resume must use BFS (not runner). "
            f"runner_called={runner_called}"
        )

    @pytest.mark.asyncio
    async def test_start_runner_resume_runner(self, tmp_path, monkeypatch):
        """Stored='runner', env=1 → resume uses runner path."""
        monkeypatch.setenv("CRONOS_HARNESS_RUNNER", "1")
        _make_run_state_file(tmp_path, "sp", "t2", "runner")

        executor = _make_run_executor_with_data_dir(tmp_path)
        runner_called = []

        async def fake_runner(tid, hid, sid, **kw):
            runner_called.append(tid)
            return True

        with patch.object(executor, "_execute_harness_run_runner", new=fake_runner):
            with patch("app.run_executor.RunExecutor._data_dir",
                       return_value=tmp_path):
                await executor.execute_harness_run_body(
                    "t2", "h1", "sp", initial_run=False, space=MagicMock()
                )

        assert len(runner_called) == 1, (
            "With stored_variant='runner', resume must use runner path. "
            f"runner_called={runner_called}"
        )
        assert runner_called[0] == "t2"

    @pytest.mark.asyncio
    async def test_start_bfs_env_now_runner_resume_uses_bfs(self, tmp_path, monkeypatch):
        """Stored='bfs', env=1 on resume → resume STILL uses BFS (stored wins over env flag)."""
        monkeypatch.setenv("CRONOS_HARNESS_RUNNER", "1")  # flag set NOW but stored=bfs
        _make_run_state_file(tmp_path, "sp", "t3", "bfs")

        executor = _make_run_executor_with_data_dir(tmp_path)
        runner_called = []

        async def fake_runner(tid, hid, sid, **kw):
            runner_called.append(tid)
            return True

        from app.harnesses.run_state import RunState

        async def fake_bfs(self_, task_id, harness, space):
            return RunState(run_id=task_id, harness_id="h1", goal_task_id=task_id)

        with patch.object(executor, "_execute_harness_run_runner", new=fake_runner):
            with patch("app.harnesses.executor.HarnessExecutor.execute", new=fake_bfs):
                with patch("app.run_executor.RunExecutor._data_dir",
                           return_value=tmp_path):
                    await executor.execute_harness_run_body(
                        "t3", "h1", "sp", initial_run=False, space=MagicMock()
                    )

        assert len(runner_called) == 0, (
            "Resume with stored_variant='bfs' must use BFS even when CRONOS_HARNESS_RUNNER=1. "
            f"runner_called={runner_called}"
        )

    @pytest.mark.asyncio
    async def test_start_runner_env_now_unset_resume_uses_runner(self, tmp_path, monkeypatch):
        """Stored='runner', env=unset on resume → resume STILL uses runner (stored wins)."""
        monkeypatch.delenv("CRONOS_HARNESS_RUNNER", raising=False)  # flag unset NOW but stored=runner
        _make_run_state_file(tmp_path, "sp", "t4", "runner")

        executor = _make_run_executor_with_data_dir(tmp_path)
        runner_called = []

        async def fake_runner(tid, hid, sid, **kw):
            runner_called.append(tid)
            return True

        with patch.object(executor, "_execute_harness_run_runner", new=fake_runner):
            with patch("app.run_executor.RunExecutor._data_dir",
                       return_value=tmp_path):
                await executor.execute_harness_run_body(
                    "t4", "h1", "sp", initial_run=False, space=MagicMock()
                )

        assert len(runner_called) == 1, (
            "Resume with stored_variant='runner' must use runner even when env flag is unset. "
            f"runner_called={runner_called}"
        )
        assert runner_called[0] == "t4"
