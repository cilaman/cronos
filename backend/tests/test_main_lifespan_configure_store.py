"""Smoke test: lifespan startup wires feature_hooks.configure_store(task_store).

F1 fix verification (I5 / review-report-featurefix-github-issues--attempt1):
  backend/app/main.py lifespan must call feature_hooks.configure_store(task_store)
  so that mirror_feature_to_github can persist issue refs in production.

  Without this wiring, feature_hooks._task_store is None and set_issue_refs
  is silently skipped on every mirror call (graceful degradation logged at
  WARNING).

This test file verifies:
  1. configure_store(store) correctly sets feature_hooks._task_store.
  2. main.py source imports feature_hooks and calls configure_store(task_store).
  3. A mocked lifespan startup sequence (patching all heavy I/O) results in
     feature_hooks._task_store being the same TaskStore as app.state.store.
"""

from __future__ import annotations

import inspect
from unittest.mock import AsyncMock, MagicMock, call, patch


# ---------------------------------------------------------------------------
# Direct unit tests of feature_hooks.configure_store
# ---------------------------------------------------------------------------


def test_configure_store_sets_module_level_task_store():
    """configure_store(store) sets feature_hooks._task_store to the given store."""
    import app.feature_hooks as fh

    original = fh._task_store
    try:
        mock_store = MagicMock()
        fh.configure_store(mock_store)
        assert fh._task_store is mock_store, (
            f"Expected _task_store to be the mock store, got {fh._task_store!r}"
        )
    finally:
        # Restore original value to avoid polluting other tests
        fh._task_store = original


def test_configure_store_is_idempotent():
    """Calling configure_store twice replaces _task_store with the second store."""
    import app.feature_hooks as fh

    original = fh._task_store
    try:
        store_a = MagicMock()
        store_b = MagicMock()
        fh.configure_store(store_a)
        assert fh._task_store is store_a
        fh.configure_store(store_b)
        assert fh._task_store is store_b, (
            "Second configure_store call must replace _task_store with the new store"
        )
    finally:
        fh._task_store = original


# ---------------------------------------------------------------------------
# Source-level wiring check: main.py calls configure_store after app.state.store
# ---------------------------------------------------------------------------


def test_main_imports_feature_hooks():
    """app.main imports feature_hooks (prerequisite for the configure_store wiring)."""
    import app.main as main_module

    source = inspect.getsource(main_module)
    assert "feature_hooks" in source, (
        "app.main must import or reference feature_hooks to call configure_store"
    )


def test_main_calls_configure_store_in_source():
    """app.main source contains the configure_store call.

    This is a static check that the wiring line exists in main.py.
    It guards against the accidental removal of configure_store(task_store).
    """
    import app.main as main_module

    source = inspect.getsource(main_module)
    assert "configure_store" in source, (
        "app.main must call feature_hooks.configure_store(task_store) in the lifespan. "
        "The wiring is missing — add `feature_hooks.configure_store(task_store)` "
        "immediately after `app.state.store = task_store` in the lifespan startup."
    )


def test_main_configure_store_called_after_app_state_store():
    """configure_store(task_store) appears AFTER 'app.state.store = task_store' in main.py.

    Checks line ordering via source inspection to ensure the store is configured
    before configure_store is invoked.
    """
    import app.main as main_module

    source = inspect.getsource(main_module)
    store_assign_idx = source.find("app.state.store = task_store")
    configure_store_idx = source.find("configure_store(task_store)")

    assert store_assign_idx >= 0, (
        "app.main must assign app.state.store = task_store in the lifespan"
    )
    assert configure_store_idx >= 0, (
        "app.main must call configure_store(task_store) in the lifespan"
    )
    assert configure_store_idx > store_assign_idx, (
        "configure_store(task_store) must appear AFTER app.state.store = task_store "
        "in main.py source (store_assign at char %d, configure_store at char %d)" % (
            store_assign_idx, configure_store_idx
        )
    )


# ---------------------------------------------------------------------------
# Functional wiring: configure_store is called with the correct TaskStore
# ---------------------------------------------------------------------------


def test_configure_store_called_during_mocked_lifespan(monkeypatch, tmp_path):
    """Patching configure_store reveals it is called exactly once with the TaskStore.

    The lifespan's heavy I/O (file watch, worker pool, cron loop) is stubbed
    out.  We verify that configure_store is invoked and that the argument
    is a TaskStore (the same object later assigned to app.state.store).

    This is a functional complement to the source-level tests above.
    """
    monkeypatch.setenv("CRONOS_BASIC_AUTH_USER", "user")
    monkeypatch.setenv("CRONOS_BASIC_AUTH_PASSWORD", "pass")
    monkeypatch.setenv("CRONOS_DATA_DIR", str(tmp_path))

    import app.feature_hooks as fh
    import app.main as main_module

    captured_calls: list = []

    real_configure_store = fh.configure_store

    def _capturing_configure_store(store):
        captured_calls.append(store)
        real_configure_store(store)

    original = fh._task_store
    try:
        with (
            patch.object(fh, "configure_store", side_effect=_capturing_configure_store),
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

            # TestClient runs the lifespan (startup + shutdown) unless lifespan=False.
            # We need startup to run to exercise configure_store wiring.
            with TestClient(app) as client:
                # After startup, configure_store must have been called
                assert len(captured_calls) == 1, (
                    f"configure_store must be called exactly once during lifespan startup, "
                    f"but was called {len(captured_calls)} time(s)"
                )
                # The argument must be the same TaskStore as app.state.store
                assert captured_calls[0] is app.state.store, (
                    "configure_store must be called with app.state.store (the canonical "
                    "TaskStore), but got a different object: %r vs %r" % (
                        captured_calls[0], app.state.store
                    )
                )
    finally:
        fh._task_store = original
