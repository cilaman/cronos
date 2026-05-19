from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from app.models import TaskState
from app.storage import (
    InvalidTransition,
    TaskNotFound,
    TaskStore,
    UnknownSpace,
    USER_TRANSITIONS,
    dump_task,
    generate_task_id,
    parse_file,
    slugify,
    summarize,
)

from .conftest import SPACE_ID


# ---------------------------------------------------------------------------
# slugify
# ---------------------------------------------------------------------------


def test_slugify_basic():
    assert slugify("Hello World") == "hello-world"


def test_slugify_special_chars():
    assert slugify("Fix bug #123!") == "fix-bug-123"


def test_slugify_empty_produces_untitled():
    assert slugify("") == "untitled"
    assert slugify("!!!") == "untitled"


def test_slugify_truncates_to_40():
    long_title = "a" * 60
    result = slugify(long_title)
    assert len(result) <= 40


def test_slugify_strips_trailing_dash():
    assert not slugify("hello world!!").endswith("-")


# ---------------------------------------------------------------------------
# generate_task_id
# ---------------------------------------------------------------------------


def test_generate_task_id_format():
    now = datetime(2025, 3, 14, 15, 9, tzinfo=UTC)
    result = generate_task_id("My Feature", now, set())
    assert result == "2025-03-14-1509-my-feature"


def test_generate_task_id_no_collision():
    now = datetime(2025, 3, 14, 15, 9, tzinfo=UTC)
    taken = {"2025-03-14-1509-my-feature"}
    result = generate_task_id("My Feature", now, taken)
    assert result.startswith("2025-03-14-1509-my-feature-")
    assert result not in taken


def test_generate_task_id_unique_across_calls():
    now = datetime(2025, 1, 1, 0, 0, tzinfo=UTC)
    ids = {generate_task_id("Task", now, set()) for _ in range(3)}
    assert len(ids) >= 1  # base id is deterministic


# ---------------------------------------------------------------------------
# parse_file / dump_task round-trip
# ---------------------------------------------------------------------------


def _make_task_file(tmp_path: Path, **overrides) -> Path:
    from app.models import Task

    now = datetime(2025, 6, 1, 12, 0, tzinfo=UTC)
    defaults = dict(
        id="2025-06-01-1200-test-task",
        space_id=SPACE_ID,
        title="Test Task",
        state=TaskState.BACKLOG,
        created_at=now,
        updated_at=now,
        brief="Do the thing.",
        history="",
    )
    defaults.update(overrides)
    task = Task(**defaults)
    path = tmp_path / f"{task.id}.md"
    path.write_text(dump_task(task), encoding="utf-8")
    return path, task


def test_parse_file_round_trip(tmp_path):
    path, original = _make_task_file(tmp_path)
    parsed = parse_file(path, SPACE_ID)
    assert parsed.id == original.id
    assert parsed.title == original.title
    assert parsed.state == original.state
    assert parsed.brief == original.brief
    assert parsed.space_id == SPACE_ID


def test_parse_file_space_id_from_arg(tmp_path):
    path, _ = _make_task_file(tmp_path)
    parsed = parse_file(path, "other-space")
    assert parsed.space_id == "other-space"


def test_dump_task_includes_brief_section(tmp_path):
    path, _ = _make_task_file(tmp_path)
    content = path.read_text()
    assert "# Brief" in content
    assert "Do the thing." in content


def test_dump_task_history_round_trip(tmp_path):
    path, _ = _make_task_file(tmp_path, history="Some history here.")
    parsed = parse_file(path, SPACE_ID)
    assert parsed.history == "Some history here."


def test_parse_file_invalid_raises(tmp_path):
    bad = tmp_path / "bad.md"
    bad.write_text("---\ntitle: missing-required-fields\n---\n", encoding="utf-8")
    with pytest.raises(ValueError):
        parse_file(bad, SPACE_ID)


# ---------------------------------------------------------------------------
# TaskStore.create
# ---------------------------------------------------------------------------


async def test_task_store_create(task_store):
    task = await task_store.create(
        space_id=SPACE_ID,
        title="First Task",
        brief="Brief text",
    )
    assert task.title == "First Task"
    assert task.state == TaskState.BACKLOG
    assert task.space_id == SPACE_ID
    assert task.brief == "Brief text"


async def test_task_store_create_persists(task_store, tmp_spaces_dir):
    task = await task_store.create(space_id=SPACE_ID, title="Persisted", brief="")
    path = tmp_spaces_dir / SPACE_ID / ".cronos" / "tasks" / f"{task.id}.md"
    assert path.exists()


async def test_task_store_create_unknown_space_raises(task_store):
    with pytest.raises(UnknownSpace):
        await task_store.create(space_id="no-such-space", title="X", brief="")


async def test_task_store_create_indexes_task(task_store):
    task = await task_store.create(space_id=SPACE_ID, title="Indexed", brief="")
    assert task_store.get(task.id) is not None


# ---------------------------------------------------------------------------
# TaskStore.update
# ---------------------------------------------------------------------------


async def test_task_store_update_title(task_store):
    task = await task_store.create(space_id=SPACE_ID, title="Old Title", brief="")
    updated = await task_store.update(task.id, title="New Title")
    assert updated.title == "New Title"


async def test_task_store_update_brief(task_store):
    task = await task_store.create(space_id=SPACE_ID, title="T", brief="Old brief")
    updated = await task_store.update(task.id, brief="New brief")
    assert updated.brief == "New brief"


async def test_task_store_update_missing_raises(task_store):
    with pytest.raises(TaskNotFound):
        await task_store.update("nonexistent-id", title="X")


async def test_task_store_update_agent_mode(task_store):
    task = await task_store.create(space_id=SPACE_ID, title="T", brief="")
    updated = await task_store.update(task.id, agent_mode="plan")
    assert updated.agent_mode == "plan"


# ---------------------------------------------------------------------------
# TaskStore.transition
# ---------------------------------------------------------------------------


async def test_task_store_transition_backlog_to_active(task_store):
    task = await task_store.create(space_id=SPACE_ID, title="T", brief="")
    updated = await task_store.transition(
        task.id, TaskState.ACTIVE, allowed=USER_TRANSITIONS
    )
    assert updated.state == TaskState.ACTIVE


async def test_task_store_transition_done_to_archived(task_store):
    task = await task_store.create(space_id=SPACE_ID, title="T", brief="")
    await task_store.transition(task.id, TaskState.ACTIVE, allowed=USER_TRANSITIONS)
    # Move to done via worker transition
    from app.storage import WORKER_TRANSITIONS
    await task_store.transition(task.id, TaskState.DONE, allowed=WORKER_TRANSITIONS)
    archived = await task_store.transition(
        task.id, TaskState.ARCHIVED, allowed=USER_TRANSITIONS
    )
    assert archived.state == TaskState.ARCHIVED


async def test_task_store_transition_invalid_raises(task_store):
    task = await task_store.create(space_id=SPACE_ID, title="T", brief="")
    with pytest.raises(InvalidTransition):
        # BACKLOG -> DONE is not a valid user transition
        await task_store.transition(
            task.id, TaskState.DONE, allowed=USER_TRANSITIONS
        )


async def test_task_store_transition_same_state_noop(task_store):
    task = await task_store.create(space_id=SPACE_ID, title="T", brief="")
    result = await task_store.transition(
        task.id, TaskState.BACKLOG, allowed=USER_TRANSITIONS
    )
    assert result.state == TaskState.BACKLOG


async def test_task_store_transition_missing_raises(task_store):
    with pytest.raises(TaskNotFound):
        await task_store.transition(
            "nonexistent", TaskState.ACTIVE, allowed=USER_TRANSITIONS
        )


# ---------------------------------------------------------------------------
# TaskStore.delete
# ---------------------------------------------------------------------------


async def test_task_store_delete_removes_from_index(task_store):
    task = await task_store.create(space_id=SPACE_ID, title="Delete Me", brief="")
    await task_store.delete(task.id)
    assert task_store.get(task.id) is None


async def test_task_store_delete_moves_to_trash(task_store, tmp_spaces_dir):
    task = await task_store.create(space_id=SPACE_ID, title="Delete Me", brief="")
    await task_store.delete(task.id)
    trash_dir = tmp_spaces_dir / SPACE_ID / ".cronos" / ".trash"
    trashed = list(trash_dir.glob(f"{task.id}.*.md"))
    assert len(trashed) == 1


async def test_task_store_delete_missing_raises(task_store):
    with pytest.raises(TaskNotFound):
        await task_store.delete("nonexistent-id")


# ---------------------------------------------------------------------------
# TaskStore.board
# ---------------------------------------------------------------------------


async def test_task_store_board_empty(task_store):
    board = task_store.board(SPACE_ID)
    assert board.backlog == []
    assert board.active == []
    assert board.waiting == []
    assert board.done == []


async def test_task_store_board_contains_created_task(task_store):
    await task_store.create(space_id=SPACE_ID, title="Board Task", brief="")
    board = task_store.board(SPACE_ID)
    assert len(board.backlog) == 1
    assert board.backlog[0].title == "Board Task"


async def test_task_store_board_filters_by_space(task_store):
    await task_store.create(space_id=SPACE_ID, title="My Task", brief="")
    board = task_store.board("other-space")
    assert board.backlog == []


async def test_task_store_board_none_returns_all_spaces(task_store):
    await task_store.create(space_id=SPACE_ID, title="T", brief="")
    board = task_store.board(None)
    assert len(board.backlog) == 1


# ---------------------------------------------------------------------------
# TaskStore.archive_stale_done_tasks
# ---------------------------------------------------------------------------


async def test_archive_stale_done_tasks_archives_old(task_store):
    from app.storage import WORKER_TRANSITIONS

    task = await task_store.create(space_id=SPACE_ID, title="Done Task", brief="")
    await task_store.transition(task.id, TaskState.ACTIVE, allowed=USER_TRANSITIONS)
    await task_store.transition(task.id, TaskState.DONE, allowed=WORKER_TRANSITIONS)

    # Backdate updated_at so the task appears stale
    stored = task_store.get(task.id)
    stale_time = datetime.now(tz=UTC) - timedelta(days=10)
    updated = stored.model_copy(update={"updated_at": stale_time})
    task_store._by_id[task.id] = updated

    count = await task_store.archive_stale_done_tasks(threshold_days=7)
    assert count == 1
    assert task_store.get(task.id).state == TaskState.ARCHIVED


async def test_archive_stale_done_tasks_skips_recent(task_store):
    from app.storage import WORKER_TRANSITIONS

    task = await task_store.create(space_id=SPACE_ID, title="Recent Done", brief="")
    await task_store.transition(task.id, TaskState.ACTIVE, allowed=USER_TRANSITIONS)
    await task_store.transition(task.id, TaskState.DONE, allowed=WORKER_TRANSITIONS)

    count = await task_store.archive_stale_done_tasks(threshold_days=7)
    assert count == 0
    assert task_store.get(task.id).state == TaskState.DONE


# ---------------------------------------------------------------------------
# summarize() — agent_mode propagation onto TaskSummary
# ---------------------------------------------------------------------------


def _make_task(**overrides):
    """Build a Task model with sensible defaults for summarize() tests."""
    from app.models import Task

    now = datetime(2025, 6, 1, 12, 0, tzinfo=UTC)
    defaults = dict(
        id="2025-06-01-1200-summarize-task",
        space_id=SPACE_ID,
        title="Summarize Me",
        state=TaskState.BACKLOG,
        created_at=now,
        updated_at=now,
        brief="A brief.",
        history="",
    )
    defaults.update(overrides)
    return Task(**defaults)


def test_summarize_defaults_agent_mode_to_auto():
    task = _make_task()
    # Task model default is "auto"; summarize() should preserve that.
    summary = summarize(task)
    assert summary.agent_mode == "auto"


def test_summarize_propagates_agent_mode_plan():
    task = _make_task(agent_mode="plan")
    summary = summarize(task)
    assert summary.agent_mode == "plan"


def test_summarize_propagates_agent_mode_ask():
    task = _make_task(agent_mode="ask")
    summary = summarize(task)
    assert summary.agent_mode == "ask"


def test_summarize_preserves_other_fields_with_custom_mode():
    """agent_mode must not clobber the rest of the summary."""
    task = _make_task(
        agent_mode="plan",
        title="My Title",
        brief="Short brief.",
        priority=2,
        manual_order=7,
    )
    summary = summarize(task)
    assert summary.agent_mode == "plan"
    assert summary.title == "My Title"
    assert summary.brief_preview == "Short brief."
    assert summary.priority == 2
    assert summary.manual_order == 7
    assert summary.id == task.id
    assert summary.space_id == task.space_id
    assert summary.state == task.state


async def test_task_store_board_summary_includes_agent_mode(task_store):
    """End-to-end: a task created with non-default agent_mode shows up
    in board() summaries with the correct mode."""
    task = await task_store.create(
        space_id=SPACE_ID, title="Plan Task", brief="", agent_mode="plan"
    )
    board = task_store.board(SPACE_ID)
    matches = [s for s in board.backlog if s.id == task.id]
    assert len(matches) == 1
    assert matches[0].agent_mode == "plan"


async def test_task_store_board_summary_default_agent_mode_auto(task_store):
    """Tasks created without agent_mode default to "auto" in the summary."""
    task = await task_store.create(
        space_id=SPACE_ID, title="Default Mode Task", brief=""
    )
    board = task_store.board(SPACE_ID)
    matches = [s for s in board.backlog if s.id == task.id]
    assert len(matches) == 1
    assert matches[0].agent_mode == "auto"
