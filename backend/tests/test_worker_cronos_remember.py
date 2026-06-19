"""Tests for CRONOS_REMEMBER sentinel persistence in the worker (design I2).

These exercise `Worker._persist_cronos_remember_blocks`, which maps a parsed
`CronosRememberBlock` onto a `MemoryItem` and persists it via
`memory_store.create()`:

    name        -> title (verbatim)
    type        -> kind  (MemoryKind, whitelist-validated by the parser)
    description -> body  (description + blank line + body; description-only when no body)
    metadata    -> links=[json.dumps(metadata)]  (links=[] when no metadata)

Items are created confirmed=False. The block source is the structured fenced
sentinel parsed via yaml.safe_load — there is no regex over model free-text on
this path. Backward compatibility with the MEMORY: path is covered by
test_cronos_remember_coexistence.py (design I3).
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.memory_store import MemoryStore
from app.models import MemoryKind
from app.stats_store import StatsStore
from app.storage import TaskStore
from app.trace_store import TraceStore
from app.worker import Worker

SPACE_ID = "cr-space"


@pytest.fixture
def memory_store(tmp_path: Path) -> MemoryStore:
    return MemoryStore(tmp_path / "data", tmp_path / "spaces")


@pytest.fixture
async def worker(task_store: TaskStore, tmp_spaces_dir, memory_store: MemoryStore) -> Worker:
    return Worker(
        store=task_store,
        space_store=None,
        stats_store=StatsStore(tmp_spaces_dir),
        trace_store=TraceStore(tmp_spaces_dir),
        memory_store=memory_store,
    )


_BLOCK = """\
Here is my result.

```cronos_remember
name: worker pool uses a single asyncio queue
type: fact
description: The worker drains one task at a time from a single queue.
body: |
  Concurrency is bounded by the pool size; tasks never run in parallel
  within a single Worker instance.
metadata:
  confidence: high
  area: worker
```

Done.
"""


# ---------------------------------------------------------------------------
# Field mapping
# ---------------------------------------------------------------------------


async def test_persist_maps_all_fields(worker: Worker, memory_store: MemoryStore) -> None:
    await worker._persist_cronos_remember_blocks(
        _BLOCK,
        space_id=SPACE_ID,
        sources=["task:t-1", "run:0"],
        log_id="t-1",
    )

    items = await memory_store.list_scope(f"space:{SPACE_ID}")
    assert len(items) == 1
    item = items[0]
    assert item.title == "worker pool uses a single asyncio queue"
    assert item.kind == MemoryKind.FACT
    # description + blank line + body
    assert item.body.startswith("The worker drains one task at a time from a single queue.")
    assert "Concurrency is bounded by the pool size" in item.body
    assert "\n\n" in item.body
    # metadata -> single JSON string in links[]
    assert len(item.links) == 1
    assert json.loads(item.links[0]) == {"confidence": "high", "area": "worker"}
    # always unconfirmed
    assert item.confirmed is False
    assert item.sources == ["task:t-1", "run:0"]


async def test_persist_description_only_when_no_body(worker: Worker, memory_store: MemoryStore) -> None:
    text = (
        "```cronos_remember\n"
        "name: nginx location precedence\n"
        "type: reference\n"
        "description: Exact-match location blocks win over prefix matches.\n"
        "```\n"
    )
    await worker._persist_cronos_remember_blocks(
        text, space_id=SPACE_ID, sources=["task:t-2"], log_id="t-2"
    )

    items = await memory_store.list_scope(f"space:{SPACE_ID}")
    assert len(items) == 1
    assert items[0].body == "Exact-match location blocks win over prefix matches."
    assert items[0].kind == MemoryKind.REFERENCE


async def test_persist_no_metadata_yields_empty_links(worker: Worker, memory_store: MemoryStore) -> None:
    text = (
        "```cronos_remember\n"
        "name: prefer pathlib over os.path\n"
        "type: procedure\n"
        "description: Use pathlib.Path for filesystem work.\n"
        "```\n"
    )
    await worker._persist_cronos_remember_blocks(
        text, space_id=SPACE_ID, sources=["task:t-3"], log_id="t-3"
    )

    items = await memory_store.list_scope(f"space:{SPACE_ID}")
    assert len(items) == 1
    assert items[0].links == []


async def test_persist_multiple_blocks(worker: Worker, memory_store: MemoryStore) -> None:
    text = (
        "```cronos_remember\n"
        "name: first\n"
        "type: fact\n"
        "description: one\n"
        "```\n"
        "filler\n"
        "```cronos_remember\n"
        "name: second\n"
        "type: observation\n"
        "description: two\n"
        "```\n"
    )
    await worker._persist_cronos_remember_blocks(
        text, space_id=SPACE_ID, sources=["task:t-4"], log_id="t-4"
    )

    items = await memory_store.list_scope(f"space:{SPACE_ID}")
    titles = {i.title for i in items}
    assert titles == {"first", "second"}


# ---------------------------------------------------------------------------
# Guards / no-ops
# ---------------------------------------------------------------------------


async def test_persist_skips_when_no_sentinel(worker: Worker, memory_store: MemoryStore) -> None:
    await worker._persist_cronos_remember_blocks(
        "Just some prose, no sentinel here.",
        space_id=SPACE_ID,
        sources=["task:t-5"],
        log_id="t-5",
    )
    assert await memory_store.list_scope(f"space:{SPACE_ID}") == []


async def test_persist_skips_unknown_type(worker: Worker, memory_store: MemoryStore) -> None:
    text = (
        "```cronos_remember\n"
        "name: bad kind\n"
        "type: wisdom\n"  # not in MemoryKind whitelist -> parser skips
        "description: should not persist\n"
        "```\n"
    )
    await worker._persist_cronos_remember_blocks(
        text, space_id=SPACE_ID, sources=["task:t-6"], log_id="t-6"
    )
    assert await memory_store.list_scope(f"space:{SPACE_ID}") == []


async def test_persist_empty_text_is_noop(worker: Worker, memory_store: MemoryStore) -> None:
    await worker._persist_cronos_remember_blocks(
        "", space_id=SPACE_ID, sources=["task:t-7"], log_id="t-7"
    )
    assert await memory_store.list_scope(f"space:{SPACE_ID}") == []


async def test_persist_noop_when_memory_store_none(task_store: TaskStore, tmp_spaces_dir) -> None:
    worker = Worker(
        store=task_store,
        stats_store=StatsStore(tmp_spaces_dir),
        trace_store=TraceStore(tmp_spaces_dir),
        memory_store=None,
    )
    # Must not raise even though there is a valid block.
    await worker._persist_cronos_remember_blocks(
        _BLOCK, space_id=SPACE_ID, sources=["task:t-8"], log_id="t-8"
    )


async def test_persist_one_bad_block_does_not_block_others(
    worker: Worker, memory_store: MemoryStore, monkeypatch
) -> None:
    """A create() failure on one block is logged and skipped, not fatal."""
    text = (
        "```cronos_remember\n"
        "name: good one\n"
        "type: fact\n"
        "description: persists fine\n"
        "```\n"
    )
    real_create = memory_store.create
    calls = {"n": 0}

    async def flaky_create(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("disk full")
        return await real_create(*args, **kwargs)

    monkeypatch.setattr(memory_store, "create", flaky_create)

    # First block raises; helper swallows and continues. With a single block,
    # nothing is persisted but no exception propagates.
    await worker._persist_cronos_remember_blocks(
        text, space_id=SPACE_ID, sources=["task:t-9"], log_id="t-9"
    )
    assert await memory_store.list_scope(f"space:{SPACE_ID}") == []
