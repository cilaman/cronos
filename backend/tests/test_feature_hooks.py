"""Tests for backend/app/feature_hooks.py — I2 acceptance criteria.

Verifies:
- Both hook functions exist and are importable.
- Both are coroutine functions (async def).
- Signatures match the locked S3/S4 contracts.
- Both return None when awaited.
- Module docstring marks them as S3/S4 contracts.
"""

from __future__ import annotations

import asyncio
import inspect
from typing import get_args, get_origin, Literal, Union
from datetime import datetime

import pytest

from app.feature_hooks import enqueue_feature_decomposition, mirror_feature_to_github
from app.models import FeatureState, Space, Task, TaskState


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_task(**kwargs) -> Task:
    defaults = dict(
        id="task-1",
        space_id="space-1",
        title="Test feature",
        state=TaskState.BACKLOG,
        created_at=datetime(2024, 1, 1),
        updated_at=datetime(2024, 1, 1),
        type="feature",
        feature_state=FeatureState.BACKLOG,
        feature_key="FEAT-001",
    )
    defaults.update(kwargs)
    return Task(**defaults)


def _make_space(**kwargs) -> Space:
    defaults = dict(
        id="space-1",
        name="Test Space",
        color="#15803D",
        created_at=datetime(2024, 1, 1),
        updated_at=datetime(2024, 1, 1),
        git_repo_url="https://github.com/example/repo.git",
    )
    defaults.update(kwargs)
    return Space(**defaults)


# ---------------------------------------------------------------------------
# Existence and async contract
# ---------------------------------------------------------------------------


def test_mirror_feature_to_github_exists():
    """mirror_feature_to_github must be importable from feature_hooks."""
    import app.feature_hooks as fh
    assert hasattr(fh, "mirror_feature_to_github")


def test_enqueue_feature_decomposition_exists():
    """enqueue_feature_decomposition must be importable from feature_hooks."""
    import app.feature_hooks as fh
    assert hasattr(fh, "enqueue_feature_decomposition")


def test_mirror_is_coroutine_function():
    """mirror_feature_to_github must be declared with async def."""
    assert inspect.iscoroutinefunction(mirror_feature_to_github), (
        "mirror_feature_to_github must be a coroutine function (async def)"
    )


def test_enqueue_is_coroutine_function():
    """enqueue_feature_decomposition must be declared with async def."""
    assert inspect.iscoroutinefunction(enqueue_feature_decomposition), (
        "enqueue_feature_decomposition must be a coroutine function (async def)"
    )


# ---------------------------------------------------------------------------
# Return value — both must return None
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_mirror_returns_none():
    task = _make_task()
    space = _make_space()
    result = await mirror_feature_to_github(task, space=space, reason="create")
    assert result is None


@pytest.mark.asyncio
async def test_enqueue_returns_none():
    task = _make_task()
    result = await enqueue_feature_decomposition(task)
    assert result is None


@pytest.mark.asyncio
async def test_mirror_returns_none_all_reasons():
    """Verify None for all three reason values."""
    task = _make_task()
    space = _make_space()
    for reason in ("create", "state_change", "edit"):
        result = await mirror_feature_to_github(task, space=space, reason=reason)
        assert result is None, f"Expected None for reason={reason!r}"


# ---------------------------------------------------------------------------
# Signature inspection — S3/S4 contract
# ---------------------------------------------------------------------------


def test_mirror_signature_parameters():
    """mirror_feature_to_github must accept task, *, space, reason."""
    sig = inspect.signature(mirror_feature_to_github)
    params = sig.parameters

    assert "task" in params, "mirror_feature_to_github must have a 'task' parameter"
    assert "space" in params, "mirror_feature_to_github must have a 'space' keyword parameter"
    assert "reason" in params, "mirror_feature_to_github must have a 'reason' keyword parameter"

    # space and reason must be keyword-only
    assert params["space"].kind == inspect.Parameter.KEYWORD_ONLY, (
        "'space' must be keyword-only (defined after *)"
    )
    assert params["reason"].kind == inspect.Parameter.KEYWORD_ONLY, (
        "'reason' must be keyword-only (defined after *)"
    )


def test_enqueue_signature_parameters():
    """enqueue_feature_decomposition must accept a single 'task' parameter."""
    sig = inspect.signature(enqueue_feature_decomposition)
    params = sig.parameters
    assert "task" in params, "enqueue_feature_decomposition must have a 'task' parameter"


def test_mirror_accepts_task_and_space_objects():
    """mirror_feature_to_github must accept Task + Space without TypeError."""
    task = _make_task()
    space = _make_space()
    # Calling the function should not raise a TypeError for wrong argument types
    coro = mirror_feature_to_github(task, space=space, reason="edit")
    assert inspect.iscoroutine(coro)
    # Clean up the coroutine without running it
    coro.close()


def test_enqueue_accepts_task_object():
    """enqueue_feature_decomposition must accept a Task without TypeError."""
    task = _make_task()
    coro = enqueue_feature_decomposition(task)
    assert inspect.iscoroutine(coro)
    coro.close()


# ---------------------------------------------------------------------------
# Module docstring marks S3/S4 contracts
# ---------------------------------------------------------------------------


def test_module_docstring_mentions_s3_contract():
    """Module docstring must reference 'S3 contract'."""
    import app.feature_hooks as fh
    assert fh.__doc__ is not None, "feature_hooks.py must have a module docstring"
    assert "S3" in fh.__doc__, "Module docstring must mention 'S3 contract'"


def test_module_docstring_mentions_s4_contract():
    """Module docstring must reference 'S4 contract'."""
    import app.feature_hooks as fh
    assert fh.__doc__ is not None, "feature_hooks.py must have a module docstring"
    assert "S4" in fh.__doc__, "Module docstring must mention 'S4 contract'"


def test_mirror_function_docstring_mentions_s3():
    """mirror_feature_to_github docstring must mention S3 contract."""
    assert mirror_feature_to_github.__doc__ is not None
    assert "S3" in mirror_feature_to_github.__doc__


def test_enqueue_function_docstring_mentions_s4():
    """enqueue_feature_decomposition docstring must mention S4 contract."""
    assert enqueue_feature_decomposition.__doc__ is not None
    assert "S4" in enqueue_feature_decomposition.__doc__
