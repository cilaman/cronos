"""Feature/fix state-machine transition tables.

Pure data module — imports only from app.models.  Never import from
app.storage here; that would create a circular dependency because storage.py
imports from models.py and would need to import from this module too.

Usage
-----
from app.feature_state import FEATURE_USER_TRANSITIONS, FEATURE_WORKER_TRANSITIONS

Pass the appropriate frozenset as the ``allowed`` argument to
``TaskStore.transition_feature(task_id, new_state, allowed=...)``.
"""

from app.models import FeatureState

# ---------------------------------------------------------------------------
# Allowed transitions initiated by a human user via the API.
# ---------------------------------------------------------------------------
FEATURE_USER_TRANSITIONS: frozenset[tuple[FeatureState, FeatureState]] = frozenset(
    {
        (FeatureState.BACKLOG, FeatureState.PROCESSING),
        (FeatureState.PROCESSING, FeatureState.BACKLOG),
        (FeatureState.PLANNED, FeatureState.PROCESSING),
        (FeatureState.WAITING, FeatureState.PROCESSING),
        (FeatureState.WAITING, FeatureState.PLANNED),
        (FeatureState.PLANNED, FeatureState.DONE),
        (FeatureState.DONE, FeatureState.BACKLOG),
    }
)

# ---------------------------------------------------------------------------
# Allowed transitions initiated by the background worker / agent.
# ---------------------------------------------------------------------------
FEATURE_WORKER_TRANSITIONS: frozenset[tuple[FeatureState, FeatureState]] = frozenset(
    {
        (FeatureState.PROCESSING, FeatureState.PLANNED),
        (FeatureState.PROCESSING, FeatureState.WAITING),
        (FeatureState.PLANNED, FeatureState.WAITING),
        (FeatureState.WAITING, FeatureState.PLANNED),
        (FeatureState.PLANNED, FeatureState.DONE),
    }
)
