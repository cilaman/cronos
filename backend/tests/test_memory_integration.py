"""End-to-end integration tests for the memory subsystem.

Covers the four integration seams in sequence:
  1. retrieve    — relevant MemoryItems are fetched from the store for a task
  2. build_prompt injection — retrieved items appear in the agent prompt
  3. MEMORY: parsing + persistence — agent output is parsed and saved as unconfirmed items
  4. retrieval of newly written items — items saved in step 3 are found in a later retrieve
"""
from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.agent import build_prompt
from app.memory_parser import parse_memory_blocks
from app.memory_retrieval import retrieve
from app.memory_store import MemoryStore
from app.models import MemoryKind, Task, TaskState

SPACE_ID = "integ-space"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def store(tmp_path: Path) -> MemoryStore:
    return MemoryStore(tmp_path / "data", tmp_path / "spaces")


def _task(task_id: str, title: str, brief: str = "") -> Task:
    now = datetime.now(tz=UTC)
    return Task(
        id=task_id,
        space_id=SPACE_ID,
        title=title,
        brief=brief,
        state=TaskState.ACTIVE,
        created_at=now,
        updated_at=now,
    )


# ---------------------------------------------------------------------------
# 1. retrieve
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_retrieve_returns_relevant_space_item(store: MemoryStore) -> None:
    scope = f"space:{SPACE_ID}"
    await store.create(scope=scope, kind=MemoryKind.FACT, title="worker pool concurrency model")
    await store.create(scope=scope, kind=MemoryKind.FACT, title="database schema migration")

    task = _task("t-01", "Fix worker pool concurrency bug", "Race condition in asyncio queue")
    results = await retrieve(task, SPACE_ID, store)

    assert len(results) >= 1
    titles = {r.title for r in results}
    assert "worker pool concurrency model" in titles


@pytest.mark.asyncio
async def test_retrieve_returns_relevant_global_item(store: MemoryStore) -> None:
    await store.create(scope="global", kind=MemoryKind.PROCEDURE, title="asyncio event loop best practices")
    await store.create(scope="global", kind=MemoryKind.FACT, title="nginx config location block rules")

    task = _task("t-02", "Debug asyncio event loop", "Investigate loop.run_until_complete behaviour")
    results = await retrieve(task, SPACE_ID, store)

    assert any("asyncio" in r.title.lower() for r in results)


@pytest.mark.asyncio
async def test_retrieve_returns_empty_when_no_match(store: MemoryStore) -> None:
    scope = f"space:{SPACE_ID}"
    await store.create(scope=scope, kind=MemoryKind.FACT, title="completely unrelated nginx tip")

    task = _task("t-03", "Fix asyncio worker pool", "Concurrency issue")
    # "nginx" should not match "asyncio worker pool"
    results = await retrieve(task, SPACE_ID, store)

    assert all("asyncio" in r.title.lower() or "worker" in r.title.lower() for r in results)


@pytest.mark.asyncio
async def test_retrieve_top5_limit(store: MemoryStore) -> None:
    scope = f"space:{SPACE_ID}"
    for i in range(8):
        await store.create(
            scope=scope,
            kind=MemoryKind.FACT,
            title=f"memory store integration test item {i}",
        )

    task = _task("t-04", "memory store integration", "test items retrieval")
    results = await retrieve(task, SPACE_ID, store)

    assert len(results) <= 5


@pytest.mark.asyncio
async def test_retrieve_sorted_by_score_descending(store: MemoryStore) -> None:
    scope = f"space:{SPACE_ID}"
    await store.create(
        scope=scope,
        kind=MemoryKind.FACT,
        title="worker pool asyncio queue concurrency",
        body="worker pool asyncio queue concurrency design notes",
    )
    await store.create(
        scope=scope,
        kind=MemoryKind.FACT,
        title="worker pool basics",
        body="simple worker pool introduction",
    )

    task = _task("t-05", "worker pool asyncio queue concurrency fix")
    results = await retrieve(task, SPACE_ID, store)

    assert len(results) >= 2
    assert results[0].score >= results[1].score


# ---------------------------------------------------------------------------
# 2. build_prompt injection
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_build_prompt_injects_memory_section(store: MemoryStore) -> None:
    scope = f"space:{SPACE_ID}"
    await store.create(
        scope=scope,
        kind=MemoryKind.FACT,
        title="worker pool uses asyncio queue",
        body="Tasks enqueued via asyncio.Queue, processed serially per space",
    )

    task = _task("t-06", "Optimise worker pool queue", "Reduce latency")
    retrieved = await retrieve(task, SPACE_ID, store)
    assert retrieved, "Pre-condition: retrieve must return at least one item"

    prompt = build_prompt(task, None, memory_items=retrieved)

    assert "# Memory Context" in prompt
    assert "worker pool uses asyncio queue" in prompt


@pytest.mark.asyncio
async def test_build_prompt_includes_item_kind_and_body(store: MemoryStore) -> None:
    scope = f"space:{SPACE_ID}"
    await store.create(
        scope=scope,
        kind=MemoryKind.PROCEDURE,
        title="worker pool deployment steps",
        body="Run make deploy then restart the service",
    )

    task = _task("t-07", "Deploy worker pool update")
    retrieved = await retrieve(task, SPACE_ID, store)
    assert retrieved

    prompt = build_prompt(task, None, memory_items=retrieved)

    assert "procedure" in prompt
    assert "Run make deploy" in prompt


def test_build_prompt_without_memory_has_no_memory_section() -> None:
    task = _task("t-08", "Some task", "A brief")
    prompt = build_prompt(task, None)

    assert "# Memory Context" not in prompt


def test_build_prompt_empty_memory_list_has_no_memory_section() -> None:
    task = _task("t-09", "Another task")
    prompt = build_prompt(task, None, memory_items=[])

    assert "# Memory Context" not in prompt


def test_build_prompt_with_multiple_items_lists_all(tmp_path: Path) -> None:
    store = MemoryStore(tmp_path / "data", tmp_path / "spaces")

    # Build items directly without going through the async store
    from app.models import MemoryItem
    now = datetime.now(tz=UTC)
    items = [
        MemoryItem(id="mem-a", scope=f"space:{SPACE_ID}", kind=MemoryKind.FACT,
                   title="First fact", body="Body of first", last_used_at=now),
        MemoryItem(id="mem-b", scope=f"space:{SPACE_ID}", kind=MemoryKind.PROCEDURE,
                   title="Second procedure", body="", last_used_at=now),
    ]
    task = _task("t-10", "Task using memory")
    prompt = build_prompt(task, None, memory_items=items)

    assert "First fact" in prompt
    assert "Second procedure" in prompt
    assert "fact" in prompt
    assert "procedure" in prompt


# ---------------------------------------------------------------------------
# 3. MEMORY: block parsing and persistence
# ---------------------------------------------------------------------------


def test_parse_memory_inline_no_kind() -> None:
    text = "Some work done.\nMEMORY: worker pool uses asyncio.Queue internally\nSTATUS: DONE"
    blocks = parse_memory_blocks(text)

    assert len(blocks) == 1
    assert "worker pool" in blocks[0].content
    assert blocks[0].kind_hint is None


def test_parse_memory_inline_with_fact_kind() -> None:
    text = "MEMORY[fact]: tasks run serially per space\nSTATUS: DONE"
    blocks = parse_memory_blocks(text)

    assert len(blocks) == 1
    assert blocks[0].kind_hint == "fact"
    assert "tasks run serially" in blocks[0].content


def test_parse_memory_inline_with_procedure_kind() -> None:
    text = "MEMORY[procedure]: to deploy, run make deploy\nSTATUS: DONE"
    blocks = parse_memory_blocks(text)

    assert blocks[0].kind_hint == "procedure"


def test_parse_memory_fenced_block() -> None:
    text = (
        "```memory procedure\n"
        "step 1: git pull\n"
        "step 2: make deploy\n"
        "```\n"
        "STATUS: DONE"
    )
    blocks = parse_memory_blocks(text)

    assert len(blocks) == 1
    assert blocks[0].kind_hint == "procedure"
    assert "step 1: git pull" in blocks[0].content
    assert "step 2: make deploy" in blocks[0].content


def test_parse_memory_multiple_markers() -> None:
    text = (
        "Work complete.\n"
        "MEMORY[fact]: worker pool creates one Worker per space\n"
        "MEMORY[observation]: goal sync re-enqueues ACTIVE children after DONE\n"
        "STATUS: DONE"
    )
    blocks = parse_memory_blocks(text)

    assert len(blocks) == 2
    assert {b.kind_hint for b in blocks} == {"fact", "observation"}


@pytest.mark.asyncio
async def test_memory_blocks_persisted_from_agent_output(store: MemoryStore) -> None:
    space_id = SPACE_ID
    task_id = "t-persist"
    run_index = 0
    scope = f"space:{space_id}"

    final_text = (
        "Completed the refactor.\n\n"
        "MEMORY[fact]: worker pool creates one Worker per space\n"
        "MEMORY[observation]: goal sync re-enqueues ACTIVE children after DONE\n\n"
        "STATUS: DONE"
    )

    blocks = parse_memory_blocks(final_text)
    assert len(blocks) == 2

    # Replicate exactly what worker._finalize does
    for block in blocks:
        title = block.content.splitlines()[0][:120]
        await store.create(
            scope=scope,
            kind=block.kind_hint or "observation",
            title=title,
            body=block.content,
            confirmed=False,
            sources=[f"task:{task_id}", f"run:{run_index}"],
        )

    items = await store.list_scope(scope)
    assert len(items) == 2

    kinds = {i.kind for i in items}
    assert MemoryKind.FACT in kinds
    assert MemoryKind.OBSERVATION in kinds

    for item in items:
        assert item.confirmed is False
        assert f"task:{task_id}" in item.sources
        assert f"run:{run_index}" in item.sources


@pytest.mark.asyncio
async def test_memory_blocks_title_truncated_to_120_chars(store: MemoryStore) -> None:
    scope = f"space:{SPACE_ID}"
    long_content = "X" * 200
    text = f"MEMORY: {long_content}\nSTATUS: DONE"
    blocks = parse_memory_blocks(text)

    title = blocks[0].content.splitlines()[0][:120]
    item = await store.create(scope=scope, kind="observation", title=title, body=blocks[0].content)

    assert len(item.title) <= 120


@pytest.mark.asyncio
async def test_memory_blocks_fenced_kind_none_defaults_to_observation(store: MemoryStore) -> None:
    scope = f"space:{SPACE_ID}"
    text = "MEMORY: no kind hint here\nSTATUS: DONE"
    blocks = parse_memory_blocks(text)

    assert blocks[0].kind_hint is None
    item = await store.create(
        scope=scope,
        kind=blocks[0].kind_hint or "observation",
        title=blocks[0].content.splitlines()[0][:120],
        body=blocks[0].content,
    )
    assert item.kind == MemoryKind.OBSERVATION


# ---------------------------------------------------------------------------
# 4. Retrieval of newly written items
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_newly_written_item_is_retrievable(store: MemoryStore) -> None:
    space_id = SPACE_ID
    scope = f"space:{space_id}"
    task = _task("t-new", "Debug worker pool concurrency issue")

    # Nothing in store yet
    initial = await retrieve(task, space_id, store)
    assert initial == []

    # Simulate agent finishing and writing a MEMORY block
    final_text = (
        "Fixed the race condition.\n"
        "MEMORY[fact]: worker pool enqueues tasks via asyncio.Queue per space\n"
        "STATUS: DONE"
    )
    blocks = parse_memory_blocks(final_text)
    for block in blocks:
        title = block.content.splitlines()[0][:120]
        await store.create(
            scope=scope,
            kind=block.kind_hint or "observation",
            title=title,
            body=block.content,
            confirmed=False,
            sources=["task:t-new", "run:0"],
        )

    # Now the same task context should find the new item
    results = await retrieve(task, space_id, store)
    assert len(results) >= 1
    assert any("worker pool" in r.title.lower() for r in results)


@pytest.mark.asyncio
async def test_newly_written_item_retrievable_for_related_task(store: MemoryStore) -> None:
    space_id = SPACE_ID
    scope = f"space:{space_id}"

    # First run: task A writes a memory block
    final_text = (
        "Work done.\n"
        "MEMORY[procedure]: to restart worker pool send SIGTERM to the process\n"
        "STATUS: DONE"
    )
    blocks = parse_memory_blocks(final_text)
    for block in blocks:
        title = block.content.splitlines()[0][:120]
        await store.create(
            scope=scope,
            kind=block.kind_hint or "observation",
            title=title,
            body=block.content,
            confirmed=False,
            sources=["task:t-a", "run:0"],
        )

    # Second run: a related task should find that item
    task_b = _task("t-b", "Restart worker pool service", "Perform controlled restart procedure")
    results = await retrieve(task_b, space_id, store)

    assert len(results) >= 1
    assert any("worker pool" in r.title.lower() for r in results)


# ---------------------------------------------------------------------------
# 5. Full round-trip integration
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_full_round_trip(store: MemoryStore) -> None:
    """Retrieve → inject into prompt → agent writes MEMORY → new item retrievable."""
    space_id = SPACE_ID
    scope = f"space:{space_id}"

    # Stage 1: pre-populate memory
    await store.create(
        scope=scope,
        kind=MemoryKind.FACT,
        title="memory store uses frontmatter markdown files",
        body="Each item stored as a .md file with YAML frontmatter header",
    )

    # Stage 2: retrieve for a related task
    task = _task("t-rt", "Update memory store serialization", "Refactor the frontmatter storage format")
    retrieved = await retrieve(task, space_id, store)
    assert len(retrieved) >= 1, "Pre-condition: memory store item must be retrieved"

    # Stage 3: inject into prompt
    prompt = build_prompt(task, None, memory_items=retrieved)
    assert "# Memory Context" in prompt
    assert "memory store uses frontmatter markdown files" in prompt

    # Stage 4: simulate agent output with new MEMORY block
    agent_output = (
        "Refactored the storage layer.\n"
        "MEMORY[procedure]: to update a memory item call store.update(scope, item_id, **fields)\n"
        "STATUS: DONE"
    )
    blocks = parse_memory_blocks(agent_output)
    assert len(blocks) == 1
    assert blocks[0].kind_hint == "procedure"

    for block in blocks:
        title = block.content.splitlines()[0][:120]
        await store.create(
            scope=scope,
            kind=block.kind_hint or "observation",
            title=title,
            body=block.content,
            confirmed=False,
            sources=["task:t-rt", "run:0"],
        )

    # Stage 5: new item retrievable for a follow-up task
    follow_up = _task("t-rt2", "Fix memory store update method", "Resolve issue with store.update fields")
    follow_results = await retrieve(follow_up, space_id, store)

    assert len(follow_results) >= 1
    assert any("memory" in r.title.lower() or "memory" in r.body.lower() for r in follow_results)

    # Newly written item is unconfirmed (awaiting user review)
    procedure_items = [r for r in follow_results if r.kind == MemoryKind.PROCEDURE]
    assert any(not item.confirmed for item in procedure_items)
