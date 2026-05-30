from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.memory_lifecycle import (
    BOOST_FACTOR,
    CONFIRM_MIN_USES,
    MAX_SCORE,
    TTL_EXTENSION_PER_BOOST_DAYS,
    boost,
    should_auto_confirm,
)


_NOW = datetime(2026, 5, 1, 12, 0, 0, tzinfo=UTC)


# ---------------------------------------------------------------------------
# boost
# ---------------------------------------------------------------------------


def test_boost_multiplies_score_by_factor() -> None:
    new_score, _ = boost(1.0, None, _NOW)
    assert new_score == pytest.approx(BOOST_FACTOR)


def test_boost_caps_score_at_max() -> None:
    new_score, _ = boost(MAX_SCORE, None, _NOW)
    assert new_score == pytest.approx(MAX_SCORE)


def test_boost_sets_ttl_when_none() -> None:
    _, new_ttl = boost(1.0, None, _NOW)
    assert new_ttl == _NOW + timedelta(days=TTL_EXTENSION_PER_BOOST_DAYS)


def test_boost_extends_ttl_from_now_when_ttl_is_past() -> None:
    past_ttl = _NOW - timedelta(days=1)
    _, new_ttl = boost(1.0, past_ttl, _NOW)
    assert new_ttl == _NOW + timedelta(days=TTL_EXTENSION_PER_BOOST_DAYS)


def test_boost_extends_ttl_from_existing_when_ttl_is_future() -> None:
    future_ttl = _NOW + timedelta(days=100)
    _, new_ttl = boost(1.0, future_ttl, _NOW)
    assert new_ttl == future_ttl + timedelta(days=TTL_EXTENSION_PER_BOOST_DAYS)


def test_boost_returns_tuple() -> None:
    result = boost(0.5, None, _NOW)
    assert isinstance(result, tuple)
    assert len(result) == 2


# ---------------------------------------------------------------------------
# should_auto_confirm
# ---------------------------------------------------------------------------


def test_should_auto_confirm_true_at_threshold() -> None:
    assert should_auto_confirm(CONFIRM_MIN_USES) is True


def test_should_auto_confirm_true_above_threshold() -> None:
    assert should_auto_confirm(CONFIRM_MIN_USES + 5) is True


def test_should_auto_confirm_false_below_threshold() -> None:
    assert should_auto_confirm(CONFIRM_MIN_USES - 1) is False


def test_should_auto_confirm_false_at_zero() -> None:
    assert should_auto_confirm(0) is False
