"""Smoke test: lifespan startup wires feature_hooks.configure_pool(worker_pool).

F1 fix verification (I11 / review-report-featurefix-worker-decompose--attempt1):
  backend/app/main.py lifespan must call feature_hooks.configure_pool(worker_pool)
  so that enqueue_feature_decomposition can submit decomposition tasks to the
  background pool in production.

  Without this wiring, feature_hooks._worker_pool is None and the entire
  POST /api/features/{id}/process -> _run_feature_decompose code path is a
  silent no-op (graceful degradation logged at WARNING).

This test file mirrors test_main_lifespan_configure_store.py and verifies:
  1. configure_pool(pool) correctly sets feature_hooks._worker_pool.
  2. main.py source imports feature_hooks and calls configure_pool(worker_pool).
  3. configure_pool is called AFTER the WorkerPool is constructed.
  4. A mocked lifespan startup sequence results in feature_hooks._worker_pool
     being the same WorkerPool as app.state.worker_pool.
"""

from __future__ import annotations

import inspect
from unittest.mock import AsyncMock, MagicMock, patch


# ---------------------------------------------------------------------------
# Direct unit tests of feature_hooks.configure_pool
# ---------------------------------------------------------------------------


def test_configure_pool_sets_module_level_worker_pool():
    """configure_pool(pool) sets feature_hooks._worker_pool to the given pool."""
    import app.feature_hooks as fh

    original = fh._worker_pool
    try:
        mock_pool = MagicMock()
        fh.configure_pool(mock_pool)
        assert fh._worker_pool is mock_pool, (
            f"Expected _worker_pool to be the mock pool, got {fh._worker_pool!r}"
        )
    finally:
        fh._worker_pool = original


def test_configure_pool_is_idempotent():
    """Calling configure_pool twice replaces _worker_pool with the second pool."""
    import app.feature_hooks as fh

    original = fh._worker_pool
    try:
        pool_a = MagicMock()
        pool_b = MagicMock()
        fh.configure_pool(pool_a)
        assert fh._worker_pool is pool_a
        fh.configure_pool(pool_b)
        assert fh._worker_pool is pool_b, (
            "Second configure_pool call must replace _worker_pool with the new pool"
        )
    finally:
        fh._worker_pool = original


# ---------------------------------------------------------------------------
# Source-level wiring check: main.py calls configure_pool after WorkerPool init
# ---------------------------------------------------------------------------


def test_main_calls_configure_pool_in_source():
    """app.main source contains the configure_pool call.

    Static guard against accidental removal of feature_hooks.configure_pool(worker_pool).
    """
    import app.main as main_module

    source = inspect.getsource(main_module)
    assert "configure_pool" in source, (
        "app.main must call feature_hooks.configure_pool(worker_pool) in the lifespan. "
        "The wiring is missing — add `feature_hooks.configure_pool(worker_pool)` "
        "immediately after the WorkerPool constructor in lifespan startup."
    )


def test_main_configure_pool_called_after_worker_pool_construction():
    """configure_pool(worker_pool) appears AFTER `worker_pool = WorkerPool(...)` in main.py.

    Ordering check via source inspection: the pool must be constructed before
    it is wired into feature_hooks.
    """
    import app.main as main_module

    source = inspect.getsource(main_module)
    pool_construct_idx = source.find("worker_pool = WorkerPool(")
    configure_pool_idx = source.find("configure_pool(worker_pool)")

    assert pool_construct_idx >= 0, (
        "app.main must construct `worker_pool = WorkerPool(...)` in the lifespan"
    )
    assert configure_pool_idx >= 0, (
        "app.main must call configure_pool(worker_pool) in the lifespan"
    )
    assert configure_pool_idx > pool_construct_idx, (
        "configure_pool(worker_pool) must appear AFTER `worker_pool = WorkerPool(...)` "
        "in main.py source (pool_construct at char %d, configure_pool at char %d)" % (
            pool_construct_idx, configure_pool_idx
        )
    )


# ---------------------------------------------------------------------------
# Functional wiring: configure_pool is called with the canonical WorkerPool
# ---------------------------------------------------------------------------


def test_configure_pool_called_during_mocked_lifespan(monkeypatch, tmp_path):
    """Patching configure_pool reveals it is called exactly once with the WorkerPool.

    The lifespan's heavy I/O is stubbed out (mirroring
    test_main_lifespan_configure_store.py).  We verify configure_pool is
    invoked once and that the argument is the same object later assigned
    to app.state.worker_pool.
    """
    monkeypatch.setenv("CRONOS_BASIC_AUTH_USER", "user")
    monkeypatch.setenv("CRONOS_BASIC_AUTH_PASSWORD", "pass")
    monkeypatch.setenv("CRONOS_DATA_DIR", str(tmp_path))

    import app.feature_hooks as fh

    captured_calls: list = []

    real_configure_pool = fh.configure_pool

    def _capturing_configure_pool(pool):
        captured_calls.append(pool)
        real_configure_pool(pool)

    original = fh._worker_pool
    try:
        with (
            patch.object(fh, "configure_pool", side_effect=_capturing_configure_pool),
            patch("app.main.SpaceStore.reload_all", new_callable=AsyncMock),
            patch("app.main.SpaceStore.count", return_value=1),
            patch("app.main.TaskStore.reload_all", new_callable=AsyncMock),
            patch("app.main.WorkerPool.start_for_space", new_callable=AsyncMock),
            patch("app.main.WorkerPool.get", return_value=None),
            patch("app.main.watch_spaces_dir", new_callable=AsyncMock),
            patch("app.main.auto_archive_loop", new_callable=AsyncMock),
            patch("app.main.memory_prune_loop", new_callable=AsyncMock),
            patch("app.main.discovery_refresh_loop", new_callable=AsyncMock),
            patch("app.main.evolve_tools_loop", new_callable=AsyncMock),
            patch("app.main.cron_loop", new_callable=AsyncMock),
        ):
            from fastapi.testclient import TestClient
            from app.main import app

            with TestClient(app) as client:
                assert len(captured_calls) == 1, (
                    f"configure_pool must be called exactly once during lifespan startup, "
                    f"but was called {len(captured_calls)} time(s)"
                )
                assert captured_calls[0] is app.state.worker_pool, (
                    "configure_pool must be called with app.state.worker_pool (the canonical "
                    "WorkerPool), but got a different object: %r vs %r" % (
                        captured_calls[0], app.state.worker_pool
                    )
                )
    finally:
        fh._worker_pool = original
