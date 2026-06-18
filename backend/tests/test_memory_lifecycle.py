from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.memory_lifecycle import (
    BOOST_AMOUNT,
    CONFIRM_MIN_USES,
    MAX_SCORE,
    PRUNE_THRESHOLD,
    TTL_EXTENSION_PER_BOOST_DAYS,
    boost,
    should_auto_confirm,
    should_prune,
)


_NOW = datetime(2026, 5, 1, 12, 0, 0, tzinfo=UTC)


# ---------------------------------------------------------------------------
# boost
# ---------------------------------------------------------------------------


def test_boost_adds_boost_amount_to_score() -> None:
    new_score, _ = boost(1.0, None, _NOW)
    assert new_score == pytest.approx(1.0 + BOOST_AMOUNT)


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


def test_boost_from_zero_exceeds_prune_threshold() -> None:
    """R4: boosting a brand-new item (score=0.0) must lift it above PRUNE_THRESHOLD.

    Ensures BOOST_AMOUNT is large enough that items boosted from zero are not
    immediately eligible for pruning.
    """
    new_score, _ = boost(0.0, None, _NOW)
    assert new_score > 0.0
    assert new_score > PRUNE_THRESHOLD


def test_should_prune_after_boost_from_zero() -> None:
    """R7: an item boosted from score=0.0 must not be prunable even when expired.

    should_prune() returns True only when both conditions hold:
      - now >= ttl_until  (item is TTL-expired), AND
      - score < PRUNE_THRESHOLD
    After a single boost from 0.0, score == BOOST_AMOUNT (0.5) which is well
    above PRUNE_THRESHOLD (0.1), so should_prune() must return False.
    """
    boosted_score, new_ttl = boost(0.0, None, _NOW)
    # Simulate time advancing past the TTL so the expiry condition is met.
    expired_now = new_ttl + timedelta(days=1)
    assert should_prune(boosted_score, new_ttl, expired_now) is False


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
