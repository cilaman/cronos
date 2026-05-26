from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.memory_store import MemoryNotFound, MemoryStore
from app.models import MemoryKind


@pytest.fixture
def store(tmp_path: Path) -> MemoryStore:
    data_dir = tmp_path / "data"
    spaces_dir = tmp_path / "spaces"
    return MemoryStore(data_dir, spaces_dir)


# ---------------------------------------------------------------------------
# create
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_returns_item(store: MemoryStore) -> None:
    item = await store.create(scope="global", kind=MemoryKind.FACT, title="Test fact")
    assert item.id.startswith("mem-")
    assert item.scope == "global"
    assert item.kind == MemoryKind.FACT
    assert item.title == "Test fact"


@pytest.mark.asyncio
async def test_create_writes_file(store: MemoryStore, tmp_path: Path) -> None:
    await store.create(scope="global", kind=MemoryKind.PROCEDURE, title="A procedure", body="Step 1")
    items_dir = tmp_path / "data" / "memory" / "items"
    md_files = list(items_dir.glob("*.md"))
    assert len(md_files) == 1
    content = md_files[0].read_text()
    assert "A procedure" in content
    assert "Step 1" in content


@pytest.mark.asyncio
async def test_create_per_space_scope(store: MemoryStore, tmp_path: Path) -> None:
    scope = "space:my-space"
    await store.create(scope=scope, kind=MemoryKind.OBSERVATION, title="Obs 1")
    items_dir = tmp_path / "spaces" / "my-space" / ".cronos" / "memory" / "items"
    assert any(items_dir.glob("*.md"))


@pytest.mark.asyncio
async def test_create_rebuilds_index(store: MemoryStore, tmp_path: Path) -> None:
    await store.create(scope="global", kind=MemoryKind.FACT, title="Indexed fact")
    index_path = tmp_path / "data" / "memory" / "index.md"
    assert index_path.exists()
    content = index_path.read_text()
    assert "Memory Index — global" in content
    assert "Indexed fact" in content


# ---------------------------------------------------------------------------
# get
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_existing(store: MemoryStore) -> None:
    item = await store.create(scope="global", kind=MemoryKind.FACT, title="Retrievable")
    loaded = await store.get("global", item.id)
    assert loaded is not None
    assert loaded.id == item.id
    assert loaded.title == "Retrievable"


@pytest.mark.asyncio
async def test_get_missing_returns_none(store: MemoryStore) -> None:
    result = await store.get("global", "nonexistent-id")
    assert result is None


# ---------------------------------------------------------------------------
# list_scope
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_scope_empty(store: MemoryStore) -> None:
    items = await store.list_scope("global")
    assert items == []


@pytest.mark.asyncio
async def test_list_scope_multiple(store: MemoryStore) -> None:
    await store.create(scope="global", kind=MemoryKind.FACT, title="F1")
    await store.create(scope="global", kind=MemoryKind.PROCEDURE, title="P1")
    items = await store.list_scope("global")
    assert len(items) == 2
    titles = {i.title for i in items}
    assert titles == {"F1", "P1"}


# ---------------------------------------------------------------------------
# update
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_title(store: MemoryStore) -> None:
    item = await store.create(scope="global", kind=MemoryKind.FACT, title="Original")
    updated = await store.update("global", item.id, title="Renamed")
    assert updated.title == "Renamed"


@pytest.mark.asyncio
async def test_update_score_and_confirmed(store: MemoryStore) -> None:
    item = await store.create(scope="global", kind=MemoryKind.FACT, title="Scored")
    updated = await store.update("global", item.id, score=0.9, confirmed=True)
    assert updated.score == pytest.approx(0.9)
    assert updated.confirmed is True


@pytest.mark.asyncio
async def test_update_missing_raises(store: MemoryStore) -> None:
    with pytest.raises(MemoryNotFound):
        await store.update("global", "no-such-id", title="X")


@pytest.mark.asyncio
async def test_update_rebuilds_index(store: MemoryStore, tmp_path: Path) -> None:
    item = await store.create(scope="global", kind=MemoryKind.FACT, title="Old title")
    await store.update("global", item.id, title="New title")
    index = (tmp_path / "data" / "memory" / "index.md").read_text()
    assert "New title" in index
    assert "Old title" not in index


# ---------------------------------------------------------------------------
# delete
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_removes_file(store: MemoryStore, tmp_path: Path) -> None:
    item = await store.create(scope="global", kind=MemoryKind.FACT, title="ToDelete")
    await store.delete("global", item.id)
    path = tmp_path / "data" / "memory" / "items" / f"{item.id}.md"
    assert not path.exists()


@pytest.mark.asyncio
async def test_delete_missing_raises(store: MemoryStore) -> None:
    with pytest.raises(MemoryNotFound):
        await store.delete("global", "ghost-id")


@pytest.mark.asyncio
async def test_delete_rebuilds_index(store: MemoryStore, tmp_path: Path) -> None:
    item = await store.create(scope="global", kind=MemoryKind.FACT, title="Ephemeral")
    await store.delete("global", item.id)
    index = (tmp_path / "data" / "memory" / "index.md").read_text()
    assert "Ephemeral" not in index


# ---------------------------------------------------------------------------
# rebuild_index format
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_index_groups_by_kind(store: MemoryStore, tmp_path: Path) -> None:
    await store.create(scope="global", kind=MemoryKind.FACT, title="Fact A", score=0.5)
    await store.create(scope="global", kind=MemoryKind.PROCEDURE, title="Proc B", score=0.8)
    await store.create(scope="global", kind=MemoryKind.REFERENCE, title="Ref C")
    index = (tmp_path / "data" / "memory" / "index.md").read_text()
    assert "## Facts" in index
    assert "## Procedures" in index
    assert "## References" in index
    assert "Fact A" in index
    assert "Proc B" in index
    assert "Ref C" in index


@pytest.mark.asyncio
async def test_index_sorts_by_score_descending(store: MemoryStore, tmp_path: Path) -> None:
    await store.create(scope="global", kind=MemoryKind.FACT, title="Low", score=0.1)
    await store.create(scope="global", kind=MemoryKind.FACT, title="High", score=0.9)
    index = (tmp_path / "data" / "memory" / "index.md").read_text()
    pos_high = index.index("High")
    pos_low = index.index("Low")
    assert pos_high < pos_low


@pytest.mark.asyncio
async def test_index_confirmed_badge(store: MemoryStore, tmp_path: Path) -> None:
    item = await store.create(scope="global", kind=MemoryKind.FACT, title="Confirmed", confirmed=True)
    index = (tmp_path / "data" / "memory" / "index.md").read_text()
    assert "✓" in index


@pytest.mark.asyncio
async def test_index_unconfirmed_badge(store: MemoryStore, tmp_path: Path) -> None:
    await store.create(scope="global", kind=MemoryKind.FACT, title="Unconfirmed", confirmed=False)
    index = (tmp_path / "data" / "memory" / "index.md").read_text()
    assert "?" in index


@pytest.mark.asyncio
async def test_index_contains_wikilink(store: MemoryStore, tmp_path: Path) -> None:
    item = await store.create(scope="global", kind=MemoryKind.FACT, title="Wiki link fact")
    index = (tmp_path / "data" / "memory" / "index.md").read_text()
    assert f"[[{item.id}]]" in index


@pytest.mark.asyncio
async def test_index_header_has_scope(store: MemoryStore, tmp_path: Path) -> None:
    scope = "space:proj-x"
    await store.create(scope=scope, kind=MemoryKind.FACT, title="Scoped")
    index_path = tmp_path / "spaces" / "proj-x" / ".cronos" / "memory" / "index.md"
    index = index_path.read_text()
    assert f"Memory Index — {scope}" in index


# ---------------------------------------------------------------------------
# get — access boost
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_increments_ref_count(store: MemoryStore) -> None:
    item = await store.create(scope="global", kind=MemoryKind.FACT, title="Boosted")
    assert item.ref_count == 0
    loaded = await store.get("global", item.id)
    assert loaded is not None
    assert loaded.ref_count == 1


@pytest.mark.asyncio
async def test_get_increases_score(store: MemoryStore) -> None:
    item = await store.create(scope="global", kind=MemoryKind.FACT, title="Scored", score=1.0)
    loaded = await store.get("global", item.id)
    assert loaded is not None
    assert loaded.score > 1.0


@pytest.mark.asyncio
async def test_get_persists_boost_to_disk(store: MemoryStore, tmp_path: Path) -> None:
    item = await store.create(scope="global", kind=MemoryKind.FACT, title="Persist")
    await store.get("global", item.id)
    reloaded = await store.get("global", item.id)
    assert reloaded is not None
    assert reloaded.ref_count == 2


@pytest.mark.asyncio
async def test_get_sets_ttl_until(store: MemoryStore) -> None:
    item = await store.create(scope="global", kind=MemoryKind.FACT, title="TTL")
    assert item.ttl_until is None
    loaded = await store.get("global", item.id)
    assert loaded is not None
    assert loaded.ttl_until is not None


@pytest.mark.asyncio
async def test_get_auto_confirms_after_threshold(store: MemoryStore) -> None:
    from app.memory_lifecycle import CONFIRM_MIN_USES as CONFIRM_THRESHOLD

    item = await store.create(scope="global", kind=MemoryKind.FACT, title="Autoconfirm")
    assert item.confirmed is False
    for _ in range(CONFIRM_THRESHOLD):
        loaded = await store.get("global", item.id)
    assert loaded is not None
    assert loaded.confirmed is True


@pytest.mark.asyncio
async def test_get_auto_confirm_rebuilds_index(store: MemoryStore, tmp_path: Path) -> None:
    from app.memory_lifecycle import CONFIRM_MIN_USES as CONFIRM_THRESHOLD

    item = await store.create(scope="global", kind=MemoryKind.FACT, title="IndexConfirm")
    for _ in range(CONFIRM_THRESHOLD):
        await store.get("global", item.id)
    index = (tmp_path / "data" / "memory" / "index.md").read_text()
    assert "✓" in index
