"""backend/tests/test_harness_flag_matrix — CRONOS_HARNESS_RUNNER flag matrix (I7).

Self-registers as a pytest plugin via pytest_plugins so pytest_collection_modifyitems
fires for all test items.  When CRONOS_HARNESS_RUNNER=1, marks two BFS-only tests in
test_harness_executor_e2e.py as xfail (expected: BFS executor intentionally bypassed).
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Self-registration: causes pytest to load this module as a plugin too,
# enabling pytest_collection_modifyitems to run for all collected test items.
# ---------------------------------------------------------------------------
pytest_plugins = ["tests.test_harness_flag_matrix"]

# BFS-only test node IDs — cannot pass when runner path is selected.
_BFS_ONLY_TEST_IDS = frozenset([
    "tests/test_harness_executor_e2e.py::test_worker_initial_run_calls_executor_not_run_agent",
    "tests/test_harness_executor_e2e.py::test_worker_event_worker_plumbing_reaches_run_buffer",
])

_BFS_ONLY_XFAIL_REASON = (
    "BFS-only test: asserts HarnessExecutor.execute is called or BFS-path event "
    "structure; CRONOS_HARNESS_RUNNER=1 selects the runner path so the BFS executor "
    "is intentionally bypassed — not a regression."
)


def pytest_collection_modifyitems(items: list, config) -> None:  # type: ignore[type-arg]
    """Mark BFS-only tests as xfail when CRONOS_HARNESS_RUNNER=1."""
    if os.environ.get("CRONOS_HARNESS_RUNNER") != "1":
        return
    for item in items:
        for bfs_id in _BFS_ONLY_TEST_IDS:
            if item.nodeid == bfs_id or item.nodeid.endswith("/" + bfs_id.lstrip("tests/")):
                item.add_marker(
                    pytest.mark.xfail(reason=_BFS_ONLY_XFAIL_REASON, strict=False)
                )
                break


# ===========================================================================
# Matrix marker tests — prove which execution path was taken
# ===========================================================================


def test_matrix_bfs_path_exercised() -> None:
    """Matrix marker: BFS default (flag absent). Skip when flag=1."""
    if os.environ.get("CRONOS_HARNESS_RUNNER") == "1":
        pytest.skip("Runner flag is set; BFS matrix marker not applicable.")
    from app.run_executor import _DEFAULT_EXECUTOR_VARIANT
    assert _DEFAULT_EXECUTOR_VARIANT == "bfs"


def test_matrix_runner_path_exercised() -> None:
    """Matrix marker: runner path active (flag=1). Skip when flag absent."""
    if os.environ.get("CRONOS_HARNESS_RUNNER") != "1":
        pytest.skip("CRONOS_HARNESS_RUNNER != '1'; runner matrix marker not applicable.")
    assert os.environ.get("CRONOS_HARNESS_RUNNER") == "1"


# ===========================================================================
# Flag dispatch tests
# ===========================================================================


def _make_run_executor(tmp_path, store, space_store, harness_store):
    from app.run_executor import RunExecutor
    w = MagicMock()
    w._publish = AsyncMock(return_value=None)
    return RunExecutor(
        worker=w, store=store, event_bus=MagicMock(), finalizer=MagicMock(),
        space_store=space_store, harness_store=harness_store, memory_store=None,
        done_sentinel={}, lease_ttl=30.0, heartbeat_interval=10.0, memory_retrieval=None,
    )


class TestFlagDispatch:
    """Flag reading and path selection in execute_harness_run_body."""

    @pytest.mark.asyncio
    async def test_flag_unset_selects_bfs(self, tmp_path: Path, monkeypatch) -> None:
        """When CRONOS_HARNESS_RUNNER is absent, BFS path is chosen."""
        from app.run_executor import _read_executor_variant
        monkeypatch.delenv("CRONOS_HARNESS_RUNNER", raising=False)

        space = MagicMock()
        space_store = MagicMock()
        space_store.spaces_dir = tmp_path / "spaces"
        space_store.get = MagicMock(return_value=space)
        store = MagicMock()
        store.finalize_run = AsyncMock()
        harness_store = MagicMock()
        harness_store.get = AsyncMock(return_value=MagicMock())

        bfs_called: list[str] = []
        runner_called: list[str] = []

        async def _fake_bfs(self_ex, run_goal_id, harness_arg, space_arg):
            bfs_called.append(run_goal_id)
            from app.harnesses.run_state import RunState
            return RunState(run_id=run_goal_id, harness_id="h", goal_task_id=run_goal_id)

        async def _fake_runner(task_id, **kwargs):
            runner_called.append(task_id)
            return True

        executor = _make_run_executor(tmp_path, store, space_store, harness_store)
        with patch("app.run_executor.RunExecutor._data_dir", return_value=tmp_path):
            with patch("app.harnesses.executor.HarnessExecutor.execute", _fake_bfs):
                with patch.object(executor, "_execute_harness_run_runner", _fake_runner):
                    await executor.execute_harness_run_body(
                        "t1", "h", "sp", initial_run=True, space=space
                    )

        assert bfs_called == ["t1"], f"BFS must be called when flag absent; got {bfs_called}"
        assert runner_called == [], f"Runner must not be called; got {runner_called}"

        rs_path = tmp_path / "spaces" / "sp" / ".cronos" / "harness-runs" / "t1.json"
        assert _read_executor_variant(rs_path) == "bfs"

    @pytest.mark.asyncio
    async def test_flag_set_to_1_selects_runner(self, tmp_path: Path, monkeypatch) -> None:
        """When CRONOS_HARNESS_RUNNER=1, runner path is chosen."""
        from app.run_executor import _read_executor_variant, _write_executor_variant
        monkeypatch.setenv("CRONOS_HARNESS_RUNNER", "1")

        space = MagicMock()
        space_store = MagicMock()
        space_store.spaces_dir = tmp_path / "spaces"
        space_store.get = MagicMock(return_value=space)
        store = MagicMock()
        store.finalize_run = AsyncMock()
        harness_store = MagicMock()
        harness_store.get = AsyncMock(return_value=MagicMock())

        bfs_called: list[str] = []
        runner_called: list[str] = []

        async def _fake_bfs(self_ex, run_goal_id, harness_arg, space_arg):
            bfs_called.append(run_goal_id)
            from app.harnesses.run_state import RunState
            return RunState(run_id=run_goal_id, harness_id="h", goal_task_id=run_goal_id)

        async def _fake_runner(task_id, harness_id_arg, space_id_arg, **kwargs):
            runner_called.append(task_id)
            rs_path = (
                tmp_path / "spaces" / space_id_arg / ".cronos" / "harness-runs"
                / f"{task_id}.json"
            )
            _write_executor_variant(rs_path, "runner", task_id, harness_id_arg)
            return True

        executor = _make_run_executor(tmp_path, store, space_store, harness_store)
        with patch("app.run_executor.RunExecutor._data_dir", return_value=tmp_path):
            with patch("app.harnesses.executor.HarnessExecutor.execute", _fake_bfs):
                with patch.object(executor, "_execute_harness_run_runner", _fake_runner):
                    await executor.execute_harness_run_body(
                        "t1", "h", "sp", initial_run=True, space=space
                    )

        assert runner_called == ["t1"], f"Runner must be called when flag=1; got {runner_called}"
        assert bfs_called == [], f"BFS must not be called when flag=1; got {bfs_called}"

        rs_path = tmp_path / "spaces" / "sp" / ".cronos" / "harness-runs" / "t1.json"
        assert _read_executor_variant(rs_path) == "runner"

    @pytest.mark.asyncio
    async def test_resume_ignores_flag_uses_stored_variant(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """Resume reads stored executor_variant, NOT the current env flag (R12)."""
        monkeypatch.setenv("CRONOS_HARNESS_RUNNER", "1")
        run_id, space_id = "res-run", "res-space"
        rs_path = tmp_path / "spaces" / space_id / ".cronos" / "harness-runs" / f"{run_id}.json"
        rs_path.parent.mkdir(parents=True, exist_ok=True)
        rs_path.write_text(json.dumps({
            "run_id": run_id, "harness_id": "h", "goal_task_id": run_id,
            "nodes_executed": {}, "status": "blocked",
            "waiting_node_id": "wn", "executor_variant": "bfs",
        }), encoding="utf-8")
        space = MagicMock()
        space_store = MagicMock()
        space_store.spaces_dir = tmp_path / "spaces"
        space_store.get = MagicMock(return_value=space)
        store = MagicMock()
        store.finalize_run = AsyncMock()
        harness_store = MagicMock()
        harness_store.get = AsyncMock(return_value=MagicMock())
        bfs_called: list[str] = []
        runner_called: list[str] = []

        async def _fake_bfs(self_ex, run_goal_id, harness_arg, space_arg):
            bfs_called.append(run_goal_id)
            from app.harnesses.run_state import RunState
            return RunState(run_id=run_goal_id, harness_id="h", goal_task_id=run_goal_id)

        async def _fake_runner(task_id, *args, **kwargs):
            runner_called.append(task_id)
            return True

        executor = _make_run_executor(tmp_path, store, space_store, harness_store)
        with patch("app.run_executor.RunExecutor._data_dir", return_value=tmp_path):
            with patch("app.harnesses.executor.HarnessExecutor.execute", _fake_bfs):
                with patch.object(executor, "_execute_harness_run_runner", _fake_runner):
                    await executor.execute_harness_run_body(
                        run_id, "h", space_id, initial_run=False, space=space
                    )
        assert bfs_called == [run_id], f"BFS must be used (stored='bfs', flag=1); {bfs_called}"
        assert runner_called == [], "Runner must NOT be used when stored='bfs'"


# ===========================================================================
# Symbol stability tests (R12, R14)
# ===========================================================================


class TestSymbolStability:
    """HarnessExecutor class/API must be unchanged (R12, R14)."""

    def test_harnessexecutor_importable(self) -> None:
        from app.harnesses.executor import HarnessExecutor
        assert HarnessExecutor is not None

    def test_execute_signature_unchanged(self) -> None:
        import inspect
        from app.harnesses.executor import HarnessExecutor
        params = list(inspect.signature(HarnessExecutor.execute).parameters.keys())
        assert "run_goal_id" in params and "harness" in params and "space" in params, params

    def test_constructor_signature_unchanged(self) -> None:
        import inspect
        from app.harnesses.executor import HarnessExecutor
        params = list(inspect.signature(HarnessExecutor.__init__).parameters.keys())
        assert "store" in params and "worker_protocol" in params and "tools_resolver" in params, params

    def test_bfs_only_list_documents_two_tests(self) -> None:
        """_BFS_ONLY_TEST_IDS must list 2 BFS-only tests."""
        assert len(_BFS_ONLY_TEST_IDS) == 2, sorted(_BFS_ONLY_TEST_IDS)
