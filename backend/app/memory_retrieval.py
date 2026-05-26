from __future__ import annotations

import re

from .memory_store import MemoryStore
from .models import MemoryItem, Task

_MAX_RESULTS = 5

_STOP_WORDS = frozenset(
    "a an the and or but in on at to of for is are was were be been being "
    "have has had do does did will would could should may might shall can "
    "this that these those it its with from by as".split()
)


def _terms(text: str) -> set[str]:
    words = re.findall(r"[a-z0-9]+", text.lower())
    return {w for w in words if w not in _STOP_WORDS and len(w) > 2}


def _score(item: MemoryItem, query_terms: set[str]) -> float:
    if not query_terms:
        return 0.0
    item_terms = _terms(item.title + " " + item.body)
    overlap = len(query_terms & item_terms)
    if overlap == 0:
        return 0.0
    return (overlap / len(query_terms)) * item.confidence


async def retrieve(task: Task, space_id: str, store: MemoryStore) -> list[MemoryItem]:
    """Return up to 5 memory items most relevant to the task's title and brief."""
    query_terms = _terms(task.title + " " + task.brief)
    if not query_terms:
        return []

    candidates = store.list_scope("global") + store.list_scope(f"space:{space_id}")
    scored: list[MemoryItem] = []
    for item in candidates:
        s = _score(item, query_terms)
        if s > 0:
            scored.append(item.model_copy(update={"score": s}))

    scored.sort(key=lambda m: m.score, reverse=True)
    return scored[:_MAX_RESULTS]
