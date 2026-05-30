from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta

DECAY_HALF_LIFE_DAYS: float = 14.0
BOOST_FACTOR: float = 1.2
MAX_SCORE: float = 10.0
PRUNE_THRESHOLD: float = 0.1
TTL_EXTENSION_PER_BOOST_DAYS: int = 7
CONFIRM_MIN_USES: int = 3


def decay(score: float, last_used_at: datetime, now: datetime) -> float:
    """Return score after exponential half-life decay since last_used_at."""
    days_elapsed = (now - last_used_at).total_seconds() / 86400.0
    if days_elapsed <= 0:
        return score
    return score * math.pow(0.5, days_elapsed / DECAY_HALF_LIFE_DAYS)


def boost(
    score: float, ttl_until: datetime | None, now: datetime
) -> tuple[float, datetime]:
    """Return (boosted_score, new_ttl) after an access boost.

    Score is multiplied by BOOST_FACTOR, capped at MAX_SCORE.
    TTL is extended by TTL_EXTENSION_PER_BOOST_DAYS from the later of now or current ttl_until.
    """
    new_score = min(score * BOOST_FACTOR, MAX_SCORE)
    base = max(ttl_until, now) if ttl_until is not None else now
    new_ttl = base + timedelta(days=TTL_EXTENSION_PER_BOOST_DAYS)
    return new_score, new_ttl


def should_prune(score: float, ttl_until: datetime | None, now: datetime) -> bool:
    """Return True when the item has expired AND its score is below the prune threshold."""
    if ttl_until is None:
        return False
    return now >= ttl_until and score < PRUNE_THRESHOLD


def should_auto_confirm(ref_count: int) -> bool:
    """Return True when the item has been used enough times to be auto-confirmed."""
    return ref_count >= CONFIRM_MIN_USES
