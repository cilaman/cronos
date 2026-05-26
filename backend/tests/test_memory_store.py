from __future__ import annotations

import asyncio
import re
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.memory_store import MemoryStore, MemoryNotFound, dump_memory_item, parse_memory_item
from app.models import MemoryItem


def _now() -> datetime:
    return datetime.now(UTC)


def _make_item(item_id: str = "test-item", scope: str = "global", **kwargs) -> MemoryItem:
    now = _now()
    defaults = dict(
        id=item_id,
        scope=scope,
        kind="fact",
        title="Test fact",
        body="This is the body.",
        confirmed=True,
        confidence=0.9,
        score=1.0,
        last_used_at=now,
        ref_count=0,
        ttl_until=None,
        sources=["task-123"],
        links=[],
        created_at=now,
        updated_at=now,
    )
    defaults.update(kwargs)
    return MemoryItem(**defaults)


@pytest.fixture
def store(tmp_path):
    data_dir = tmp_path / "data"
    spaces_dir = tmp_path / "spaces"
    return MemoryStore(data_dir=data_dir, spaces_dir=spaces_dir)


# ---------------------------------------------------------------------------
# Serialization round-trip
# ---------------------------------------------------------------------------

def test_dump_and_parse_round_trip(tmp_path):
    item = _make_item()
    text = dump_memory_item(item)
    path = tmp_path / "item.md"
    path.write_text(text, encoding="utf-8")
    parsed = parse_memory_item(path)
    assert parsed.id == item.id
    assert parsed.title == item.title
    assert parsed.body == item.body
    assert parsed.kind == item.kind
    assert parsed.confirmed == item.confirmed
    assert abs(parsed.confidence - item.confidence) < 1e-9
    assert parsed.sources == item.sources


def test_dump_includes_frontmatter(tmp_path):
    item = _make_item()
    text = dump_memory_item(item)
    assert text.startswith("---")
    assert "title: Test fact" in text


def test_parse_with_null_ttl(tmp_path):
    item = _make_item(ttl_until=None)
    text = dump_memory_item(item)
    path = tmp_path / "item.md"
    path.write_text(text, encoding="utf-8")
    parsed = parse_memory_item(path)
    assert parsed.ttl_until is None


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

def test_global_scope_path(store, tmp_path):
    data_dir = tmp_path / "data"
    spaces_dir = tmp_path / "spaces"
    s = MemoryStore(data_dir=data_dir, spaces_dir=spaces_dir)
    p = s._item_path("global", "abc")
    assert str(p) == str(data_dir / "memory" / "items" / "abc.md")


def test_space_scope_path(tmp_path):
    s = MemoryStore(data_dir=tmp_path / "data", spaces_dir=tmp_path / "spaces")
    p = s._item_path("space:my-space", "xyz")
    assert str(p) == str(tmp_path / "spaces" / "my-space" / ".cronos" / "memory" / "items" / "xyz.md")


def test_invalid_scope_raises(store):
    with pytest.raises(ValueError, match="Unknown scope"):
        store._items_dir("bad-scope")


# ---------------------------------------------------------------------------
# CRUD — global scope
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_and_get_by_id(store):
    item = _make_item()
    created = await store.create("global", item)
    assert created.id == item.id

    fetched = await store.get_by_id("global", item.id)
    assert fetched is not None
    assert fetched.title == item.title


@pytest.mark.asyncio
async def test_get_all(store):
    await store.create("global", _make_item("a"))
    await store.create("global", _make_item("b"))
    items = await store.get_all("global")
    ids = {i.id for i in items}
    assert ids == {"a", "b"}


@pytest.mark.asyncio
async def test_get_by_id_missing_returns_none(store):
    result = await store.get_by_id("global", "nonexistent")
    assert result is None


@pytest.mark.asyncio
async def test_create_duplicate_raises(store):
    item = _make_item()
    await store.create("global", item)
    with pytest.raises(ValueError, match="already exists"):
        await store.create("global", _make_item())


@pytest.mark.asyncio
async def test_update(store):
    item = _make_item()
    await store.create("global", item)
    updated = await store.update("global", item.id, {"title": "Updated", "confidence": 0.75})
    assert updated.title == "Updated"
    assert abs(updated.confidence - 0.75) < 1e-9

    fetched = await store.get_by_id("global", item.id)
    assert fetched.title == "Updated"


@pytest.mark.asyncio
async def test_update_missing_raises(store):
    with pytest.raises(MemoryNotFound):
        await store.update("global", "nope", {"title": "x"})


@pytest.mark.asyncio
async def test_delete(store):
    item = _make_item()
    await store.create("global", item)
    await store.delete("global", item.id)
    assert await store.get_by_id("global", item.id) is None


@pytest.mark.asyncio
async def test_delete_missing_raises(store):
    with pytest.raises(MemoryNotFound):
        await store.delete("global", "nope")


# ---------------------------------------------------------------------------
# Space scope
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_space_scope_isolation(store):
    a = _make_item("x", scope="space:alpha")
    b = _make_item("x", scope="space:beta")
    await store.create("space:alpha", a)
    await store.create("space:beta", b)

    alpha_items = await store.get_all("space:alpha")
    beta_items = await store.get_all("space:beta")
    assert len(alpha_items) == 1
    assert len(beta_items) == 1


# ---------------------------------------------------------------------------
# Index regeneration
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_index_created_on_write(store, tmp_path):
    item = _make_item(title="My Fact")
    await store.create("global", item)
    index_path = store._index_path("global")
    assert index_path.exists()
    content = index_path.read_text()
    assert "My Fact" in content
    assert item.id in content


@pytest.mark.asyncio
async def test_index_updated_on_delete(store):
    item = _make_item(title="Gone Soon")
    await store.create("global", item)
    await store.delete("global", item.id)
    index_path = store._index_path("global")
    content = index_path.read_text()
    assert "Gone Soon" not in content


# ---------------------------------------------------------------------------
# Atomic writes / concurrent safety
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_concurrent_creates_do_not_corrupt(store):
    items = [_make_item(f"item-{i}", title=f"Fact {i}") for i in range(10)]
    await asyncio.gather(*[store.create("global", item) for item in items])
    all_items = await store.get_all("global")
    assert len(all_items) == 10


@pytest.mark.asyncio
async def test_no_tmp_files_left_behind(store, tmp_path):
    item = _make_item()
    await store.create("global", item)
    items_dir = store._items_dir("global")
    tmp_files = list(items_dir.glob("*.tmp.*"))
    assert tmp_files == []


# ---------------------------------------------------------------------------
# Get-all on empty scope
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_all_empty_scope(store):
    result = await store.get_all("global")
    assert result == []
