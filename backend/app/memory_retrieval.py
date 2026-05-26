from __future__ import annotations

import re

from .memory_store import MemoryStore
from .models import MemoryItem, Task

_STOP_WORDS = frozenset({
    "a", "an", "the", "is", "it", "in", "on", "at", "to", "for", "of",
    "and", "or", "but", "not", "with", "this", "that", "be", "as", "by",
    "from", "are", "was", "were", "has", "have", "had", "do", "does", "did",
    "will", "would", "could", "should", "may", "might", "must", "can",
    "i", "you", "he", "she", "they", "we", "our", "your", "their", "its",
    "my", "also", "via", "so", "if", "add", "use", "using",
})


def _extract_terms(text: str) -> set[str]:
    """Tokenize text into lowercase terms, removing stop words and short tokens."""
    tokens = re.findall(r"[a-z][a-z0-9_-]*", text.lower())
    return {t for t in tokens if len(t) > 2 and t not in _STOP_WORDS}


def _term_match_score(item: MemoryItem, terms: set[str]) -> float:
    """Fraction of query terms found in item title + body, weighted by confidence."""
    haystack = (item.title + " " + item.body).lower()
    matches = sum(1 for t in terms if t in haystack)
    return (matches / len(terms)) * item.confidence


async def retrieve(task: Task, space_id: str, store: MemoryStore) -> list[MemoryItem]:
    """Return up to 5 memory items most relevant to the task's title and brief.

    Algorithm:
      1. Extract meaningful terms from task title + brief.
      2. Scan index.md for space and global scopes to find candidate item IDs.
      3. Load matching items and score by term coverage × confidence.
      4. Return top-5 by score, with the score field updated to retrieval score.
    """
    terms = _extract_terms(task.title + " " + task.brief)
    if not terms:
        return []

    candidates: dict[str, MemoryItem] = {}
    for scope in (f"space:{space_id}", "global"):
        index_text = await store.read_index(scope)
        if not index_text:
            continue
        for line in index_text.splitlines():
            if not any(t in line.lower() for t in terms):
                continue
            m = re.search(r"\[\[(mem-[^\]]+)\]\]", line)
            if not m:
                continue
            item_id = m.group(1)
            if item_id not in candidates:
                item = await store.get(scope, item_id)
                if item is not None:
                    candidates[item_id] = item

    if not candidates:
        return []

    scored = [
        item.model_copy(update={"score": _term_match_score(item, terms)})
        for item in candidates.values()
    ]
    scored.sort(key=lambda x: x.score, reverse=True)
    return scored[:5]
