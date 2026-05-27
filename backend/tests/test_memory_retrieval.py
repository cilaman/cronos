from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.memory_retrieval import _extract_terms, retrieve
from app.memory_store import MemoryStore
from app.models import MemoryItem, MemoryKind, Task, TaskState


def _make_task(title: str, brief: str = "", space_id: str = "test-space") -> Task:
    now = datetime.now(tz=UTC)
    return Task(
        id="task-001",
        space_id=space_id,
        title=title,
        brief=brief,
        state=TaskState.ACTIVE,
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def store(tmp_path: Path) -> MemoryStore:
    return MemoryStore(tmp_path / "data", tmp_path / "spaces")


# ---------------------------------------------------------------------------
# _extract_terms
# ---------------------------------------------------------------------------


def test_extract_terms_basic() -> None:
    terms = _extract_terms("Fix the asyncio bug in worker pool")
    assert "asyncio" in terms
    assert "worker" in terms
    assert "pool" in terms
    # stop words filtered
    assert "the" not in terms
    assert "in" not in terms


def test_extract_terms_deduplicates() -> None:
    terms = _extract_terms("foo bar foo")
    assert terms == {"foo", "bar"}


def test_extract_terms_empty() -> None:
    assert _extract_terms("") == set()


def test_extract_terms_only_stop_words() -> None:
    assert _extract_terms("a the is it") == set()


def test_extract_terms_short_tokens_filtered() -> None:
    terms = _extract_terms("add db to api")
    assert "db" not in terms
    assert "to" not in terms


# ---------------------------------------------------------------------------
# retrieve
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_retrieve_empty_store(store: MemoryStore) -> None:
    task = _make_task("Fix asyncio worker bug")
    result = await retrieve(task, "test-space", store)
    assert result == []


@pytest.mark.asyncio
async def test_retrieve_returns_matching_items(store: MemoryStore) -> None:
    scope = "space:test-space"
    await store.create(scope=scope, kind=MemoryKind.FACT, title="asyncio worker pool design")
    await store.create(scope=scope, kind=MemoryKind.FACT, title="unrelated database schema")

    task = _make_task("Fix asyncio worker bug")
    results = await retrieve(task, "test-space", store)

    assert len(results) == 1
    assert "asyncio" in results[0].title.lower()


@pytest.mark.asyncio
async def test_retrieve_global_scope(store: MemoryStore) -> None:
    await store.create(scope="global", kind=MemoryKind.PROCEDURE, title="asyncio best practices")
    await store.create(scope="global", kind=MemoryKind.FACT, title="unrelated nginx config")

    task = _make_task("asyncio concurrency patterns")
    results = await retrieve(task, "test-space", store)

    assert len(results) == 1
    assert "asyncio" in results[0].title.lower()


@pytest.mark.asyncio
async def test_retrieve_top5_limit(store: MemoryStore) -> None:
    scope = "space:test-space"
    for i in range(8):
        await store.create(
            scope=scope,
            kind=MemoryKind.FACT,
            title=f"memory retrieval scoring item {i}",
        )

    task = _make_task("memory retrieval scoring")
    results = await retrieve(task, "test-space", store)

    assert len(results) <= 5


@pytest.mark.asyncio
async def test_retrieve_sorted_by_score(store: MemoryStore) -> None:
    scope = "space:test-space"
    # Item with more term matches should rank higher
    await store.create(
        scope=scope,
        kind=MemoryKind.FACT,
        title="asyncio event loop concurrency",
        body="asyncio concurrency patterns for event loop management",
    )
    await store.create(
        scope=scope,
        kind=MemoryKind.FACT,
        title="asyncio basics",
        body="introduction to asyncio",
    )

    task = _make_task("asyncio event loop concurrency patterns")
    results = await retrieve(task, "test-space", store)

    assert len(results) >= 2
    # Higher-scoring item should come first
    assert results[0].score >= results[1].score


@pytest.mark.asyncio
async def test_retrieve_deduplicates_across_scopes(store: MemoryStore) -> None:
    # Items in both scopes can appear; they should all be returned without duplicates
    await store.create(scope="space:test-space", kind=MemoryKind.FACT, title="asyncio worker")
    await store.create(scope="global", kind=MemoryKind.FACT, title="asyncio scheduler")

    task = _make_task("asyncio worker scheduler")
    results = await retrieve(task, "test-space", store)

    ids = [r.id for r in results]
    assert len(ids) == len(set(ids)), "Duplicate items in results"


@pytest.mark.asyncio
async def test_retrieve_no_terms_returns_empty(store: MemoryStore) -> None:
    await store.create(scope="space:test-space", kind=MemoryKind.FACT, title="some fact")
    task = _make_task("a the is")  # only stop words
    results = await retrieve(task, "test-space", store)
    assert results == []


@pytest.mark.asyncio
async def test_retrieve_confidence_affects_score(store: MemoryStore) -> None:
    scope = "space:test-space"
    await store.create(
        scope=scope, kind=MemoryKind.FACT, title="asyncio debugging", confidence=0.9
    )
    await store.create(
        scope=scope, kind=MemoryKind.FACT, title="asyncio debugging", confidence=0.1
    )

    task = _make_task("asyncio debugging")
    results = await retrieve(task, "test-space", store)

    assert len(results) == 2
    assert results[0].score > results[1].score
