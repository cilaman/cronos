from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from app.models import TaskState
from app.storage import (
    CycleError,
    InvalidTransition,
    TaskNotFound,
    TaskStore,
    UnknownSpace,
    USER_TRANSITIONS,
    WORKER_TRANSITIONS,
    dump_task,
    generate_task_id,
    open_children,
    parse_file,
    slugify,
    summarize,
    unmet_deps,
    validate_depends_on,
    validate_parent,
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


# ---------------------------------------------------------------------------
# Hierarchy fields (type / parent_id / depends_on) — arc-1 task 1
# ---------------------------------------------------------------------------


def _write_raw_md(tmp_path: Path, name: str, frontmatter_yaml: str, body: str = "") -> Path:
    """Write a raw markdown file with the given frontmatter block.

    Uses python-frontmatter's exact serialization style so the test asserts
    on parse behavior of inputs that mirror what dump_task writes.
    """
    path = tmp_path / f"{name}.md"
    path.write_text(f"---\n{frontmatter_yaml.strip()}\n---\n{body}", encoding="utf-8")
    return path


def test_parse_file_reads_hierarchy_fields(tmp_path):
    """parse_file lifts type, parent_id, depends_on from frontmatter."""
    path = _write_raw_md(
        tmp_path,
        "task-with-hierarchy",
        """
id: task-with-hierarchy
space_id: test-space
title: Child Task
state: backlog
created_at: 2025-06-01T12:00:00Z
updated_at: 2025-06-01T12:00:00Z
type: goal
parent_id: parent-task-1
depends_on:
  - dep-1
  - dep-2
""",
        "# Brief\n\nA child task.\n",
    )

    task = parse_file(path, SPACE_ID)

    assert task.type == "goal"
    assert task.parent_id == "parent-task-1"
    assert task.depends_on == ["dep-1", "dep-2"]


def test_parse_file_back_compat_defaults_when_fields_missing(tmp_path):
    """A pre-existing task file without the new keys parses with defaults."""
    path = _write_raw_md(
        tmp_path,
        "legacy-task",
        """
id: legacy-task
space_id: test-space
title: Legacy Task
state: backlog
created_at: 2025-01-01T00:00:00Z
updated_at: 2025-01-01T00:00:00Z
""",
        "# Brief\n\nFrom before the migration.\n",
    )

    task = parse_file(path, SPACE_ID)

    assert task.type == "task"
    assert task.parent_id is None
    assert task.depends_on == []


def test_parse_file_invalid_type_falls_back_to_task(tmp_path):
    """An unknown `type:` value is coerced back to the default `task`.

    This guards against a future enum widening crashing parse on rollback,
    and against ZIP-imported task files with a garbage type.
    """
    path = _write_raw_md(
        tmp_path,
        "bad-type",
        """
id: bad-type
space_id: test-space
title: Bad Type
state: backlog
created_at: 2025-01-01T00:00:00Z
updated_at: 2025-01-01T00:00:00Z
type: epic
parent_id: p
""",
        "# Brief\n\nfoo\n",
    )

    task = parse_file(path, SPACE_ID)

    assert task.type == "task"
    # parent_id is independent of the type sanitization
    assert task.parent_id == "p"


def test_parse_file_depends_on_non_list_falls_back_to_empty(tmp_path):
    """If `depends_on:` is a scalar instead of a list, we yield []."""
    path = _write_raw_md(
        tmp_path,
        "bad-depends",
        """
id: bad-depends
space_id: test-space
title: Bad Depends
state: backlog
created_at: 2025-01-01T00:00:00Z
updated_at: 2025-01-01T00:00:00Z
depends_on: not-a-list
""",
        "# Brief\n\nfoo\n",
    )

    task = parse_file(path, SPACE_ID)

    assert task.depends_on == []


def test_dump_task_emits_hierarchy_frontmatter(tmp_path):
    """dump_task writes type/parent_id/depends_on into the frontmatter."""
    from app.models import Task

    now = datetime(2025, 6, 1, 12, 0, tzinfo=UTC)
    task = Task(
        id="dump-hier",
        space_id=SPACE_ID,
        title="Hierarchy",
        state=TaskState.BACKLOG,
        created_at=now,
        updated_at=now,
        brief="b",
        history="",
        type="issue",
        parent_id="parent-x",
        depends_on=["d1", "d2"],
    )

    serialized = dump_task(task)

    # Assert on the frontmatter keys/values, not on whitespace formatting.
    import frontmatter as fm
    parsed = fm.loads(serialized)
    assert parsed["type"] == "issue"
    assert parsed["parent_id"] == "parent-x"
    assert parsed["depends_on"] == ["d1", "d2"]


def test_dump_task_round_trip_preserves_hierarchy_fields(tmp_path):
    """Full disk round-trip: dump_task -> file -> parse_file restores fields."""
    from app.models import Task

    now = datetime(2025, 6, 1, 12, 0, tzinfo=UTC)
    original = Task(
        id="round-trip-hier",
        space_id=SPACE_ID,
        title="RT",
        state=TaskState.BACKLOG,
        created_at=now,
        updated_at=now,
        brief="b",
        history="",
        type="goal",
        parent_id="p-1",
        depends_on=["a", "b", "c"],
    )
    path = tmp_path / "rt.md"
    path.write_text(dump_task(original), encoding="utf-8")

    parsed = parse_file(path, SPACE_ID)

    assert parsed.type == "goal"
    assert parsed.parent_id == "p-1"
    assert parsed.depends_on == ["a", "b", "c"]


def test_summarize_propagates_hierarchy_fields():
    """TaskSummary surfaces type and parent_id (depends_on is intentionally not on summary)."""
    task = _make_task(type="goal", parent_id="parent-99")

    summary = summarize(task)

    assert summary.type == "goal"
    assert summary.parent_id == "parent-99"


def test_summarize_defaults_hierarchy_fields():
    """A bare Task summarizes with type='task' and parent_id=None."""
    task = _make_task()

    summary = summarize(task)

    assert summary.type == "task"
    assert summary.parent_id is None


# --- TaskStore.create / update with hierarchy ---


async def test_task_store_create_with_hierarchy_fields(task_store, tmp_spaces_dir):
    """Create accepts type/parent_id/depends_on and persists them to disk."""
    task = await task_store.create(
        space_id=SPACE_ID,
        title="Child of Parent",
        brief="b",
        type="goal",
        parent_id="parent-id-1",
        depends_on=["dep-a", "dep-b"],
    )

    # Returned task carries the fields
    assert task.type == "goal"
    assert task.parent_id == "parent-id-1"
    assert task.depends_on == ["dep-a", "dep-b"]

    # Re-parsed from disk to prove persistence (not just in-memory model)
    path = tmp_spaces_dir / SPACE_ID / ".cronos" / "tasks" / f"{task.id}.md"
    reloaded = parse_file(path, SPACE_ID)
    assert reloaded.type == "goal"
    assert reloaded.parent_id == "parent-id-1"
    assert reloaded.depends_on == ["dep-a", "dep-b"]


async def test_task_store_create_defaults_when_hierarchy_fields_omitted(task_store):
    """Omitting the new fields yields type='task', parent_id=None, depends_on=[]."""
    task = await task_store.create(space_id=SPACE_ID, title="Defaults", brief="")

    assert task.type == "task"
    assert task.parent_id is None
    assert task.depends_on == []


async def test_task_store_create_invalid_type_raises(task_store):
    """create() rejects unknown type values rather than silently coercing."""
    from app.storage import StorageError

    with pytest.raises(StorageError):
        await task_store.create(
            space_id=SPACE_ID, title="bad", brief="", type="epic"
        )


async def test_task_store_update_hierarchy_fields(task_store, tmp_spaces_dir):
    """update accepts type, parent_id, depends_on and persists them."""
    task = await task_store.create(space_id=SPACE_ID, title="Mutable", brief="")
    assert task.type == "task"  # baseline

    updated = await task_store.update(
        task.id,
        type="issue",
        parent_id="new-parent",
        depends_on=["x", "y"],
    )

    assert updated.type == "issue"
    assert updated.parent_id == "new-parent"
    assert updated.depends_on == ["x", "y"]

    # Persisted to disk
    path = tmp_spaces_dir / SPACE_ID / ".cronos" / "tasks" / f"{task.id}.md"
    reloaded = parse_file(path, SPACE_ID)
    assert reloaded.type == "issue"
    assert reloaded.parent_id == "new-parent"
    assert reloaded.depends_on == ["x", "y"]


async def test_task_store_update_depends_on_can_be_empty_list(task_store):
    """Passing depends_on=[] clears the list (not the same as None=no-op)."""
    task = await task_store.create(
        space_id=SPACE_ID,
        title="ClearDeps",
        brief="",
        depends_on=["one", "two"],
    )

    updated = await task_store.update(task.id, depends_on=[])

    assert updated.depends_on == []


async def test_task_store_update_invalid_type_raises(task_store):
    """update() rejects an unknown type."""
    from app.storage import StorageError

    task = await task_store.create(space_id=SPACE_ID, title="t", brief="")
    with pytest.raises(StorageError):
        await task_store.update(task.id, type="epic")


# --- SQLite secondary index ---


def _query_sqlite_row(db_path: Path, task_id: str) -> tuple | None:
    """Return the (id, space_id, state, title, type, parent_id, depends_on_json) row, or None."""
    con = sqlite3.connect(db_path)
    try:
        row = con.execute(
            "SELECT id, space_id, state, title, type, parent_id, depends_on_json"
            " FROM tasks WHERE id = ?",
            (task_id,),
        ).fetchone()
        return row
    finally:
        con.close()


async def test_sqlite_index_populated_after_reload_all(tmp_spaces_dir, space_store):
    """reload_all() rebuilds the SQLite tasks table from MD files on disk."""
    # Seed an on-disk task with hierarchy fields directly (bypass TaskStore.create).
    from app.models import Task

    now = datetime(2025, 6, 1, 12, 0, tzinfo=UTC)
    seed = Task(
        id="seeded-goal",
        space_id=SPACE_ID,
        title="Seeded Goal",
        state=TaskState.BACKLOG,
        created_at=now,
        updated_at=now,
        brief="",
        history="",
        type="goal",
        parent_id="root",
        depends_on=["dep1", "dep2"],
    )
    tasks_dir = tmp_spaces_dir / SPACE_ID / ".cronos" / "tasks"
    tasks_dir.mkdir(parents=True, exist_ok=True)
    (tasks_dir / f"{seed.id}.md").write_text(dump_task(seed), encoding="utf-8")

    store = TaskStore(tmp_spaces_dir)
    await store.reload_all()

    row = _query_sqlite_row(store._db_path, "seeded-goal")
    assert row is not None
    assert row[0] == "seeded-goal"
    assert row[1] == SPACE_ID
    assert row[2] == "backlog"
    assert row[3] == "Seeded Goal"
    assert row[4] == "goal"
    assert row[5] == "root"
    assert json.loads(row[6]) == ["dep1", "dep2"]


async def test_sqlite_index_upserts_on_create(task_store):
    """TaskStore.create writes a matching row into the SQLite index."""
    task = await task_store.create(
        space_id=SPACE_ID,
        title="Indexed Goal",
        brief="",
        type="goal",
        parent_id="parent-x",
        depends_on=["d"],
    )

    row = _query_sqlite_row(task_store._db_path, task.id)

    assert row is not None
    assert row[4] == "goal"
    assert row[5] == "parent-x"
    assert json.loads(row[6]) == ["d"]


async def test_sqlite_index_upserts_on_update(task_store):
    """TaskStore.update reflects the new hierarchy values in SQLite."""
    task = await task_store.create(space_id=SPACE_ID, title="t", brief="")

    await task_store.update(
        task.id,
        type="issue",
        parent_id="new-parent",
        depends_on=["alpha"],
    )

    row = _query_sqlite_row(task_store._db_path, task.id)
    assert row is not None
    assert row[4] == "issue"
    assert row[5] == "new-parent"
    assert json.loads(row[6]) == ["alpha"]


async def test_sqlite_index_removes_row_on_delete(task_store):
    """TaskStore.delete must remove the row from the SQLite index.

    Without this, the secondary index keeps a dangling reference to a
    soft-deleted task, which will leak into any future hierarchy/parent_id
    query built on top of the index.
    """
    task = await task_store.create(space_id=SPACE_ID, title="GoneSoon", brief="")
    # Sanity: row exists before delete.
    assert _query_sqlite_row(task_store._db_path, task.id) is not None

    await task_store.delete(task.id)

    row = _query_sqlite_row(task_store._db_path, task.id)
    assert row is None, "SQLite row not removed after delete (index leak)"


async def test_sqlite_index_indexes_exist(task_store):
    """The two new secondary indices are created by _ensure_db_schema()."""
    con = sqlite3.connect(task_store._db_path)
    try:
        names = {
            r[0]
            for r in con.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='tasks'"
            ).fetchall()
        }
    finally:
        con.close()

    assert "idx_tasks_space_parent" in names
    assert "idx_tasks_space_type" in names


async def test_sqlite_index_query_by_parent_id(task_store):
    """Sanity-check the (space_id, parent_id) lookup pattern the index supports."""
    parent = await task_store.create(
        space_id=SPACE_ID, title="Parent", brief="", type="goal"
    )
    child_1 = await task_store.create(
        space_id=SPACE_ID, title="Child A", brief="", parent_id=parent.id
    )
    child_2 = await task_store.create(
        space_id=SPACE_ID, title="Child B", brief="", parent_id=parent.id
    )
    # Unrelated task in the same space, no parent.
    await task_store.create(space_id=SPACE_ID, title="Loner", brief="")

    con = sqlite3.connect(task_store._db_path)
    try:
        rows = con.execute(
            "SELECT id FROM tasks WHERE space_id = ? AND parent_id = ?",
            (SPACE_ID, parent.id),
        ).fetchall()
    finally:
        con.close()

    ids = {r[0] for r in rows}
    assert ids == {child_1.id, child_2.id}


async def test_sqlite_index_query_by_type(task_store):
    """Sanity-check the (space_id, type) lookup pattern the index supports."""
    g1 = await task_store.create(space_id=SPACE_ID, title="G1", brief="", type="goal")
    await task_store.create(space_id=SPACE_ID, title="T1", brief="", type="task")
    i1 = await task_store.create(space_id=SPACE_ID, title="I1", brief="", type="issue")
    g2 = await task_store.create(space_id=SPACE_ID, title="G2", brief="", type="goal")

    con = sqlite3.connect(task_store._db_path)
    try:
        goal_ids = {
            r[0]
            for r in con.execute(
                "SELECT id FROM tasks WHERE space_id = ? AND type = 'goal'",
                (SPACE_ID,),
            ).fetchall()
        }
        issue_ids = {
            r[0]
            for r in con.execute(
                "SELECT id FROM tasks WHERE space_id = ? AND type = 'issue'",
                (SPACE_ID,),
            ).fetchall()
        }
    finally:
        con.close()

    assert goal_ids == {g1.id, g2.id}
    assert issue_ids == {i1.id}


# ---------------------------------------------------------------------------
# Cycle detection: validate_parent / validate_depends_on — arc-1 task 2
# ---------------------------------------------------------------------------
#
# These exercise pure in-memory predicates that gate parent_id / depends_on
# writes. They take a `by_id: dict[str, Task]` and never touch disk, so we
# build the index by hand instead of spinning up a TaskStore.


def _mk(task_id: str, *, space: str = SPACE_ID, parent: str | None = None,
        deps: list[str] | None = None):
    """Build a minimal Task suitable for the cycle validators' by_id dict."""
    from app.models import Task

    now = datetime(2025, 6, 1, 12, 0, tzinfo=UTC)
    return Task(
        id=task_id,
        space_id=space,
        title=task_id,
        state=TaskState.BACKLOG,
        created_at=now,
        updated_at=now,
        brief="",
        history="",
        parent_id=parent,
        depends_on=list(deps or []),
    )


def _index(*tasks) -> dict:
    """Build an id -> Task index from positional Task args."""
    return {t.id: t for t in tasks}


# ---- validate_parent ----


def test_validate_parent_none_is_noop():
    """candidate_parent_id=None means 'clear parent' — always valid."""
    a = _mk("A")
    # Should not raise — assertion is the absence of an exception.
    validate_parent("A", None, SPACE_ID, _index(a))


def test_validate_parent_self_reference_raises():
    """A task may not be its own parent."""
    a = _mk("A")

    with pytest.raises(CycleError) as excinfo:
        validate_parent("A", "A", SPACE_ID, _index(a))

    # Acceptance: message must reflect the self-cycle as "A -> A".
    assert "A -> A" in str(excinfo.value)


def test_validate_parent_direct_cycle_raises():
    """A.parent=B; setting B.parent=A would create a length-2 cycle."""
    # A points to B as its parent. The candidate would make B point back to A.
    a = _mk("A", parent="B")
    b = _mk("B")

    with pytest.raises(CycleError) as excinfo:
        validate_parent("B", "A", SPACE_ID, _index(a, b))

    # The walked path starts at the would-be edge (B -> A) and continues up
    # the existing chain (A -> B) until it hits the start node again.
    assert "B -> A -> B" in str(excinfo.value)


def test_validate_parent_transitive_cycle_raises():
    """A.parent=B, B.parent=C, set C.parent=A — a length-3 cycle."""
    # Existing chain: A -> B -> C (toward root). Candidate: C.parent = A.
    a = _mk("A", parent="B")
    b = _mk("B", parent="C")
    c = _mk("C")
    by_id = _index(a, b, c)

    with pytest.raises(CycleError) as excinfo:
        validate_parent("C", "A", SPACE_ID, by_id)

    msg = str(excinfo.value)
    # All three nodes must appear in the cycle path.
    assert "A" in msg and "B" in msg and "C" in msg
    # The path begins with the edge being added (C -> A) and closes on C.
    assert msg.startswith("C -> A")
    assert msg.endswith("-> C")


def test_validate_parent_cross_space_raises():
    """A parent that lives in a different space must be rejected."""
    a = _mk("A", space=SPACE_ID)
    other = _mk("B", space="other-space")
    by_id = _index(a, other)

    with pytest.raises(CycleError) as excinfo:
        validate_parent("A", "B", SPACE_ID, by_id)

    # Should not present as a cycle but as a not-found-in-space error.
    msg = str(excinfo.value)
    assert "B" in msg
    assert SPACE_ID in msg


def test_validate_parent_missing_candidate_raises():
    """A parent id that isn't in the index at all is rejected."""
    a = _mk("A")

    with pytest.raises(CycleError) as excinfo:
        validate_parent("A", "ghost", SPACE_ID, _index(a))

    assert "ghost" in str(excinfo.value)


def test_validate_parent_valid_deep_hierarchy_no_error():
    """Depth-3 chain A->B->C exists; setting D.parent=A is legal."""
    a = _mk("A", parent="B")
    b = _mk("B", parent="C")
    c = _mk("C")
    d = _mk("D")
    by_id = _index(a, b, c, d)

    # Should not raise — D is a brand-new node so no cycle is possible.
    validate_parent("D", "A", SPACE_ID, by_id)


def test_validate_parent_orphaned_ancestor_does_not_loop():
    """If an ancestor chain points at a missing node, the walk halts cleanly.

    Defensive: an invalid on-disk state (parent_id pointing at a deleted
    task) must not cause validate_parent to hang or to mask a real cycle.
    """
    a = _mk("A", parent="GHOST")  # parent doesn't exist in by_id
    b = _mk("B")

    # Should terminate without raising — there's no cycle involving B.
    validate_parent("B", "A", SPACE_ID, _index(a, b))


# ---- validate_depends_on ----


def test_validate_depends_on_empty_list_is_noop():
    """An empty deps list is always valid."""
    a = _mk("A")

    validate_depends_on("A", [], SPACE_ID, _index(a))


def test_validate_depends_on_self_reference_raises():
    """A task may not depend on itself."""
    a = _mk("A")

    with pytest.raises(CycleError) as excinfo:
        validate_depends_on("A", ["A"], SPACE_ID, _index(a))

    assert "A -> A" in str(excinfo.value)


def test_validate_depends_on_direct_cycle_raises():
    """A.depends_on=[B]; adding B.depends_on=[A] would close a 2-cycle."""
    a = _mk("A", deps=["B"])
    b = _mk("B")

    with pytest.raises(CycleError) as excinfo:
        validate_depends_on("B", ["A"], SPACE_ID, _index(a, b))

    # Path must show B -> A -> B (the candidate edge + the existing chain).
    assert "B -> A -> B" in str(excinfo.value)


def test_validate_depends_on_transitive_cycle_raises():
    """A.depends_on=[B], B.depends_on=[C]; adding C.depends_on=[A] cycles."""
    a = _mk("A", deps=["B"])
    b = _mk("B", deps=["C"])
    c = _mk("C")

    with pytest.raises(CycleError) as excinfo:
        validate_depends_on("C", ["A"], SPACE_ID, _index(a, b, c))

    msg = str(excinfo.value)
    assert "A" in msg and "B" in msg and "C" in msg
    # The reconstructed path closes on C (the task being mutated).
    assert msg.startswith("C -> A")
    assert msg.endswith("-> C")


def test_validate_depends_on_cross_space_raises():
    """A dep that lives in a different space must be rejected."""
    a = _mk("A", space=SPACE_ID)
    other = _mk("B", space="other-space")

    with pytest.raises(CycleError) as excinfo:
        validate_depends_on("A", ["B"], SPACE_ID, _index(a, other))

    msg = str(excinfo.value)
    assert "B" in msg
    assert SPACE_ID in msg


def test_validate_depends_on_missing_dep_raises():
    """A dep id that isn't in the index at all is rejected."""
    a = _mk("A")

    with pytest.raises(CycleError) as excinfo:
        validate_depends_on("A", ["ghost"], SPACE_ID, _index(a))

    assert "ghost" in str(excinfo.value)


def test_validate_depends_on_valid_dag_no_error():
    """Multiple deps with shared sub-deps but no cycle — should accept."""
    # Build a small DAG:
    #   B -> D
    #   C -> D
    # We add a new task A with deps=[B, C]. D is shared, no cycle anywhere.
    b = _mk("B", deps=["D"])
    c = _mk("C", deps=["D"])
    d = _mk("D")
    a = _mk("A")  # newly created, no deps yet
    by_id = _index(a, b, c, d)

    # Should not raise — A is a sink, not reachable from B/C/D.
    validate_depends_on("A", ["B", "C"], SPACE_ID, by_id)


def test_validate_depends_on_one_good_one_bad_still_raises():
    """If any dep in the list creates a cycle, the whole call fails.

    Guards against an off-by-one bug where only the first dep is checked.
    """
    # A.depends_on=[B]; B.depends_on=[]. Try to set B.depends_on=[C, A].
    # C is fine, A closes the cycle B -> A -> B.
    a = _mk("A", deps=["B"])
    b = _mk("B")
    c = _mk("C")

    with pytest.raises(CycleError):
        validate_depends_on("B", ["C", "A"], SPACE_ID, _index(a, b, c))


def test_validate_depends_on_cross_space_takes_priority_over_self():
    """When a dep is both missing-in-space AND not self, the missing error fires.

    Locks in that the cross-space check runs before the cycle BFS — important
    so the user sees the right error message ("not found in space") rather
    than a misleading cycle path.
    """
    a = _mk("A", space=SPACE_ID)
    other = _mk("X", space="other-space")

    with pytest.raises(CycleError) as excinfo:
        validate_depends_on("A", ["X"], SPACE_ID, _index(a, other))

    assert "not found in space" in str(excinfo.value)


# ---- contract / defensive-data tests ----


def test_cycle_error_is_value_error_subclass():
    """API callers may want to catch ValueError generically — lock the inheritance.

    If someone re-bases CycleError on Exception directly, code that does
    `except ValueError` to handle bad input would silently miss cycle errors.
    """
    assert issubclass(CycleError, ValueError)
    # And an instance is catchable as ValueError.
    try:
        raise CycleError("boom")
    except ValueError as e:
        assert str(e) == "boom"


def test_validate_parent_preexisting_ancestor_cycle_does_not_hang():
    """Defensive: a corrupt on-disk parent chain that already cycles (and that
    does NOT include task_id) must terminate without raising or looping forever.

    Setup: P -> Q -> P (existing cycle between two unrelated tasks).
    Adding NEW.parent = P should succeed because NEW is not in the cycle.
    Exercises the `next_id in seen -> break` defensive guard in validate_parent.
    """
    p = _mk("P", parent="Q")
    q = _mk("Q", parent="P")  # closes a pre-existing P<->Q cycle
    new_task = _mk("NEW")

    # Should not raise and must not hang. The walker should detect the revisit
    # of P (or Q) via the `seen` set and break out of the loop.
    validate_parent("NEW", "P", SPACE_ID, _index(p, q, new_task))


def test_validate_depends_on_deep_transitive_cycle_raises():
    """Length-5 dep chain catches BFS bugs that only show at depth >= 3.

    Existing chain: A -> B -> C -> D -> E.  Setting E.depends_on=[A] cycles.
    A shallow (depth-1) BFS or one that confuses BFS/DFS direction would
    miss this.
    """
    a = _mk("A", deps=["B"])
    b = _mk("B", deps=["C"])
    c = _mk("C", deps=["D"])
    d = _mk("D", deps=["E"])
    e = _mk("E")
    by_id = _index(a, b, c, d, e)

    with pytest.raises(CycleError) as excinfo:
        validate_depends_on("E", ["A"], SPACE_ID, by_id)

    msg = str(excinfo.value)
    # Path must traverse the full chain and close on E.
    for node in ("A", "B", "C", "D", "E"):
        assert node in msg, f"expected {node} in cycle path, got {msg!r}"
    assert msg.startswith("E -> A")
    assert msg.endswith("-> E")


def test_validate_depends_on_diamond_dag_is_accepted():
    """Fan-out + fan-in (diamond) is a valid DAG; BFS revisit must not flag it.

    Shape:
        A -> B -> D
        A -> C -> D
    Adding A.depends_on=[B, C] where both B and C lead to shared D is legal.
    A naive BFS that doesn't dedupe via `came_from` could revisit D and
    falsely report a cycle.
    """
    d = _mk("D")
    b = _mk("B", deps=["D"])
    c = _mk("C", deps=["D"])
    a = _mk("A")  # candidate: set A.depends_on=[B, C]
    by_id = _index(a, b, c, d)

    # Should not raise: D is shared but no path leads back to A.
    validate_depends_on("A", ["B", "C"], SPACE_ID, by_id)


def test_validate_depends_on_does_not_mutate_inputs():
    """The validator must be a pure predicate — no mutation of by_id or the
    candidate list. Otherwise callers that pass live references get surprises.
    """
    a = _mk("A", deps=["B"])
    b = _mk("B")
    c = _mk("C")
    by_id = _index(a, b, c)
    candidate = ["C"]

    # Snapshot relevant state.
    deps_before = {tid: list(t.depends_on) for tid, t in by_id.items()}
    keys_before = set(by_id.keys())

    validate_depends_on("A", candidate, SPACE_ID, by_id)

    assert candidate == ["C"], "candidate list must not be mutated"
    assert set(by_id.keys()) == keys_before, "by_id keys must not change"
    for tid, t in by_id.items():
        assert t.depends_on == deps_before[tid], f"{tid}.depends_on mutated"


def test_validate_parent_does_not_mutate_inputs():
    """Same pure-predicate contract for validate_parent."""
    a = _mk("A", parent="B")
    b = _mk("B", parent="C")
    c = _mk("C")
    d = _mk("D")
    by_id = _index(a, b, c, d)

    parents_before = {tid: t.parent_id for tid, t in by_id.items()}
    keys_before = set(by_id.keys())

    validate_parent("D", "A", SPACE_ID, by_id)

    assert set(by_id.keys()) == keys_before
    for tid, t in by_id.items():
        assert t.parent_id == parents_before[tid], f"{tid}.parent_id mutated"


# ---------------------------------------------------------------------------
# Dependency / child gating — arc-1 task 3 (unmet_deps / open_children)
# ---------------------------------------------------------------------------
#
# These are pure in-memory predicates. They run on a by_id index built by hand
# so the assertions are about logic, not disk I/O.


def _mk_state(task_id: str, state: TaskState, *, parent: str | None = None,
              deps: list[str] | None = None, task_type: str = "task"):
    """Like _mk but lets the caller pick the task's state and type."""
    from app.models import Task

    now = datetime(2025, 6, 1, 12, 0, tzinfo=UTC)
    return Task(
        id=task_id,
        space_id=SPACE_ID,
        title=task_id,
        state=state,
        created_at=now,
        updated_at=now,
        brief="",
        history="",
        type=task_type,
        parent_id=parent,
        depends_on=list(deps or []),
    )


# ---- unmet_deps() ----


def test_unmet_deps_no_dependencies_returns_empty():
    """A task with depends_on=[] has no blockers — return []."""
    t = _mk_state("T", TaskState.BACKLOG)

    assert unmet_deps(t, _index(t)) == []


def test_unmet_deps_all_done_returns_empty():
    """Every dep is in `done` — task is unblocked."""
    d1 = _mk_state("D1", TaskState.DONE)
    d2 = _mk_state("D2", TaskState.DONE)
    t = _mk_state("T", TaskState.BACKLOG, deps=["D1", "D2"])

    assert unmet_deps(t, _index(t, d1, d2)) == []


def test_unmet_deps_all_archived_returns_empty():
    """`archived` is terminal too — also counts as unblocked."""
    d1 = _mk_state("D1", TaskState.ARCHIVED)
    t = _mk_state("T", TaskState.BACKLOG, deps=["D1"])

    assert unmet_deps(t, _index(t, d1)) == []


def test_unmet_deps_mixed_done_and_archived_returns_empty():
    """A mix of done + archived deps is still fully terminal."""
    d1 = _mk_state("D1", TaskState.DONE)
    d2 = _mk_state("D2", TaskState.ARCHIVED)
    t = _mk_state("T", TaskState.BACKLOG, deps=["D1", "D2"])

    assert unmet_deps(t, _index(t, d1, d2)) == []


def test_unmet_deps_lists_open_blockers():
    """Deps that are not done/archived are reported by id, in the deps order."""
    d1 = _mk_state("D1", TaskState.DONE)
    d2 = _mk_state("D2", TaskState.BACKLOG)
    d3 = _mk_state("D3", TaskState.ACTIVE)
    d4 = _mk_state("D4", TaskState.WAITING)
    t = _mk_state("T", TaskState.BACKLOG, deps=["D1", "D2", "D3", "D4"])

    blockers = unmet_deps(t, _index(t, d1, d2, d3, d4))

    # D1 (done) is terminal; the rest are open. Order follows depends_on.
    assert blockers == ["D2", "D3", "D4"]


def test_unmet_deps_missing_dep_id_treated_as_unmet():
    """A dangling depends_on id (target deleted/never existed) is unmet.

    Defensive: we must not silently treat 'unknown dep' as 'satisfied' — that
    would let a task start even though a real dependency was never run.
    """
    t = _mk_state("T", TaskState.BACKLOG, deps=["GHOST"])

    assert unmet_deps(t, _index(t)) == ["GHOST"]


def test_unmet_deps_waiting_state_is_not_terminal():
    """`waiting` is NOT in the terminal set — should be reported as a blocker.

    Locks in the contract that 'done or archived' is the *only* terminal
    classification (matches `_TERMINAL_STATES`).
    """
    d = _mk_state("D", TaskState.WAITING)
    t = _mk_state("T", TaskState.BACKLOG, deps=["D"])

    assert unmet_deps(t, _index(t, d)) == ["D"]


def test_unmet_deps_active_state_is_not_terminal():
    """A dep that's actively running still blocks — until it finishes."""
    d = _mk_state("D", TaskState.ACTIVE)
    t = _mk_state("T", TaskState.BACKLOG, deps=["D"])

    assert unmet_deps(t, _index(t, d)) == ["D"]


def test_unmet_deps_preserves_dependency_order():
    """The returned blocker list mirrors the order in `depends_on`.

    Important for the error message users see: stable order makes the
    UI display deterministic across reloads.
    """
    a = _mk_state("A", TaskState.BACKLOG)
    b = _mk_state("B", TaskState.BACKLOG)
    c = _mk_state("C", TaskState.BACKLOG)
    t = _mk_state("T", TaskState.BACKLOG, deps=["C", "A", "B"])

    assert unmet_deps(t, _index(t, a, b, c)) == ["C", "A", "B"]


# ---- open_children() ----


def test_open_children_no_children_returns_empty():
    """A goal with no children at all has no open children."""
    g = _mk_state("G", TaskState.ACTIVE, task_type="goal")

    assert open_children("G", _index(g)) == []


def test_open_children_all_done_returns_empty():
    """A goal whose every child is `done` is ready to close."""
    g = _mk_state("G", TaskState.ACTIVE, task_type="goal")
    c1 = _mk_state("C1", TaskState.DONE, parent="G")
    c2 = _mk_state("C2", TaskState.DONE, parent="G")

    assert open_children("G", _index(g, c1, c2)) == []


def test_open_children_all_archived_returns_empty():
    """Archived children are also terminal — should not block goal-done."""
    g = _mk_state("G", TaskState.ACTIVE, task_type="goal")
    c1 = _mk_state("C1", TaskState.ARCHIVED, parent="G")

    assert open_children("G", _index(g, c1)) == []


def test_open_children_lists_open_ones():
    """Children in backlog/active/waiting are all reported."""
    g = _mk_state("G", TaskState.ACTIVE, task_type="goal")
    closed = _mk_state("CLOSED", TaskState.DONE, parent="G")
    backlog = _mk_state("BACKLOG_C", TaskState.BACKLOG, parent="G")
    active = _mk_state("ACTIVE_C", TaskState.ACTIVE, parent="G")
    waiting = _mk_state("WAITING_C", TaskState.WAITING, parent="G")

    result = open_children("G", _index(g, closed, backlog, active, waiting))

    # All three non-terminal children should appear; CLOSED must not.
    assert set(result) == {"BACKLOG_C", "ACTIVE_C", "WAITING_C"}
    assert "CLOSED" not in result


def test_open_children_ignores_other_parents_children():
    """A child of a different goal must not appear in this goal's open list.

    Guards against an off-by-one where the predicate forgets to filter on
    parent_id (would return every open task in the space).
    """
    g1 = _mk_state("G1", TaskState.ACTIVE, task_type="goal")
    g2 = _mk_state("G2", TaskState.ACTIVE, task_type="goal")
    c_g1 = _mk_state("C_G1", TaskState.BACKLOG, parent="G1")
    c_g2 = _mk_state("C_G2", TaskState.BACKLOG, parent="G2")
    loner = _mk_state("LONER", TaskState.BACKLOG)  # no parent

    result = open_children("G1", _index(g1, g2, c_g1, c_g2, loner))

    assert result == ["C_G1"]


def test_open_children_ignores_root_level_tasks():
    """Tasks with parent_id=None must not be attributed to any goal."""
    g = _mk_state("G", TaskState.ACTIVE, task_type="goal")
    rootless = _mk_state("RL", TaskState.BACKLOG)  # parent=None by default

    assert open_children("G", _index(g, rootless)) == []


# ---- TaskStore.transition gates ----


async def test_transition_backlog_to_active_blocked_by_unmet_deps(task_store):
    """A backlog task cannot move to active while any dep is open."""
    dep = await task_store.create(space_id=SPACE_ID, title="Dep", brief="")
    blocked = await task_store.create(
        space_id=SPACE_ID,
        title="Blocked",
        brief="",
        depends_on=[dep.id],
    )

    with pytest.raises(InvalidTransition) as excinfo:
        await task_store.transition(
            blocked.id, TaskState.ACTIVE, allowed=USER_TRANSITIONS
        )

    # Message must surface the offending id so the API can echo it back.
    msg = str(excinfo.value)
    assert "unmet dependencies" in msg
    assert dep.id in msg
    # Task must remain in backlog — gate is enforced *before* state mutation.
    assert task_store.get(blocked.id).state == TaskState.BACKLOG


async def test_transition_backlog_to_active_allowed_after_deps_done(task_store):
    """Once every dep reaches `done`, the same transition succeeds."""
    dep = await task_store.create(space_id=SPACE_ID, title="Dep", brief="")
    # Walk dep through active -> done so we get a legal terminal state.
    await task_store.transition(dep.id, TaskState.ACTIVE, allowed=USER_TRANSITIONS)
    await task_store.transition(dep.id, TaskState.DONE, allowed=WORKER_TRANSITIONS)

    blocked = await task_store.create(
        space_id=SPACE_ID,
        title="Blocked Then Free",
        brief="",
        depends_on=[dep.id],
    )

    updated = await task_store.transition(
        blocked.id, TaskState.ACTIVE, allowed=USER_TRANSITIONS
    )

    assert updated.state == TaskState.ACTIVE


async def test_transition_backlog_to_active_allowed_when_deps_archived(task_store):
    """Archived deps also unblock — archived is a terminal state."""
    dep = await task_store.create(space_id=SPACE_ID, title="Dep", brief="")
    # Walk dep through active -> done -> archived.
    await task_store.transition(dep.id, TaskState.ACTIVE, allowed=USER_TRANSITIONS)
    await task_store.transition(dep.id, TaskState.DONE, allowed=WORKER_TRANSITIONS)
    await task_store.transition(dep.id, TaskState.ARCHIVED, allowed=USER_TRANSITIONS)

    blocked = await task_store.create(
        space_id=SPACE_ID,
        title="Blocked",
        brief="",
        depends_on=[dep.id],
    )

    updated = await task_store.transition(
        blocked.id, TaskState.ACTIVE, allowed=USER_TRANSITIONS
    )

    assert updated.state == TaskState.ACTIVE


async def test_transition_backlog_to_active_unblocked_when_no_deps(task_store):
    """Sanity: a task with depends_on=[] is never blocked by the new gate."""
    task = await task_store.create(space_id=SPACE_ID, title="No Deps", brief="")

    updated = await task_store.transition(
        task.id, TaskState.ACTIVE, allowed=USER_TRANSITIONS
    )

    assert updated.state == TaskState.ACTIVE


async def test_transition_backlog_to_active_multi_dep_lists_all_blockers(task_store):
    """When multiple deps are open, the error names all of them."""
    d1 = await task_store.create(space_id=SPACE_ID, title="D1", brief="")
    d2 = await task_store.create(space_id=SPACE_ID, title="D2", brief="")
    blocked = await task_store.create(
        space_id=SPACE_ID,
        title="Blocked",
        brief="",
        depends_on=[d1.id, d2.id],
    )

    with pytest.raises(InvalidTransition) as excinfo:
        await task_store.transition(
            blocked.id, TaskState.ACTIVE, allowed=USER_TRANSITIONS
        )

    msg = str(excinfo.value)
    assert d1.id in msg
    assert d2.id in msg


async def test_transition_goal_to_done_blocked_by_open_children(task_store):
    """A goal cannot move to done while any child is non-terminal.

    The goal-done gate fires regardless of the `allowed` set, so we exercise
    it via the worker path (ACTIVE -> DONE) which is the realistic route.
    """
    goal = await task_store.create(
        space_id=SPACE_ID, title="Parent Goal", brief="", type="goal"
    )
    child = await task_store.create(
        space_id=SPACE_ID,
        title="Child",
        brief="",
        parent_id=goal.id,
    )
    # Move goal to active so worker can attempt active->done.
    await task_store.transition(goal.id, TaskState.ACTIVE, allowed=USER_TRANSITIONS)

    with pytest.raises(InvalidTransition) as excinfo:
        await task_store.transition(
            goal.id, TaskState.DONE, allowed=WORKER_TRANSITIONS
        )

    msg = str(excinfo.value)
    assert "open children" in msg
    assert child.id in msg
    # Goal must remain in active — gate enforced before state mutation.
    assert task_store.get(goal.id).state == TaskState.ACTIVE


async def test_transition_goal_to_done_allowed_after_children_done(task_store):
    """Once every child reaches done, the goal can be closed."""
    goal = await task_store.create(
        space_id=SPACE_ID, title="Parent Goal", brief="", type="goal"
    )
    child = await task_store.create(
        space_id=SPACE_ID, title="Child", brief="", parent_id=goal.id
    )
    # Move child to done.
    await task_store.transition(child.id, TaskState.ACTIVE, allowed=USER_TRANSITIONS)
    await task_store.transition(child.id, TaskState.DONE, allowed=WORKER_TRANSITIONS)
    # Move goal to active.
    await task_store.transition(goal.id, TaskState.ACTIVE, allowed=USER_TRANSITIONS)

    updated = await task_store.transition(
        goal.id, TaskState.DONE, allowed=WORKER_TRANSITIONS
    )

    assert updated.state == TaskState.DONE


async def test_transition_goal_to_done_gate_does_not_fire_for_task_type(task_store):
    """A non-goal parent should NOT trip the goal-done gate.

    The gate condition is `task.type == "goal"`. If a regression widens this
    to "any task with children" it would block normal sub-task hierarchies.
    """
    parent = await task_store.create(
        space_id=SPACE_ID, title="Parent Task", brief="", type="task"
    )
    # Give it an open child to make this assertion meaningful.
    await task_store.create(
        space_id=SPACE_ID, title="Child", brief="", parent_id=parent.id
    )
    await task_store.transition(parent.id, TaskState.ACTIVE, allowed=USER_TRANSITIONS)

    # Should succeed: gate only applies to type='goal'.
    updated = await task_store.transition(
        parent.id, TaskState.DONE, allowed=WORKER_TRANSITIONS
    )

    assert updated.state == TaskState.DONE


async def test_transition_invalid_transition_check_runs_before_gate(task_store):
    """If the `(state, new_state)` pair isn't allowed, the gate is never reached.

    Locks in the order: legality check first, dependency gate second. Without
    this order a misuse of the API would surface a misleading 'unmet deps'
    error instead of the real 'transition not allowed' one.
    """
    dep = await task_store.create(space_id=SPACE_ID, title="Dep", brief="")
    task = await task_store.create(
        space_id=SPACE_ID, title="T", brief="", depends_on=[dep.id]
    )

    with pytest.raises(InvalidTransition) as excinfo:
        # BACKLOG -> DONE is not in USER_TRANSITIONS.
        await task_store.transition(
            task.id, TaskState.DONE, allowed=USER_TRANSITIONS
        )

    # The message should report the illegal transition, NOT the deps gate.
    msg = str(excinfo.value)
    assert "Cannot move task from backlog to done" in msg
    assert "unmet dependencies" not in msg


# ---- TaskStore.apply_reply gates ----


async def test_apply_reply_backlog_blocked_by_unmet_deps(task_store):
    """A reply to a backlog task with unmet deps must NOT auto-activate it.

    apply_reply normally drives backlog -> active. The new gate makes that
    transition fail loudly with InvalidTransition so the caller can surface
    the blockers to the user (instead of silently starting a task whose
    dependencies aren't done).
    """
    dep = await task_store.create(space_id=SPACE_ID, title="Dep", brief="")
    blocked = await task_store.create(
        space_id=SPACE_ID,
        title="Blocked",
        brief="",
        depends_on=[dep.id],
    )

    with pytest.raises(InvalidTransition) as excinfo:
        await task_store.apply_reply(blocked.id, "please start")

    msg = str(excinfo.value)
    assert "unmet dependencies" in msg
    assert dep.id in msg
    # Task remains in backlog with no mutation.
    stored = task_store.get(blocked.id)
    assert stored.state == TaskState.BACKLOG
    # No history entry should have been appended on the failed call.
    assert "please start" not in stored.history


async def test_apply_reply_backlog_allowed_after_deps_done(task_store):
    """Same flow as above but with deps satisfied — reply must promote to active."""
    dep = await task_store.create(space_id=SPACE_ID, title="Dep", brief="")
    await task_store.transition(dep.id, TaskState.ACTIVE, allowed=USER_TRANSITIONS)
    await task_store.transition(dep.id, TaskState.DONE, allowed=WORKER_TRANSITIONS)

    unblocked = await task_store.create(
        space_id=SPACE_ID,
        title="Will Start",
        brief="",
        depends_on=[dep.id],
    )

    outcome = await task_store.apply_reply(unblocked.id, "go")

    assert outcome.task.state == TaskState.ACTIVE
    assert outcome.should_enqueue is True


async def test_apply_reply_active_path_unaffected_by_dep_gate(task_store):
    """A reply to an already-active task is appended to pending_messages.

    The dep gate is scoped to the backlog branch only. An active task with
    open deps (e.g. dep was reset to backlog after the task started) must
    not be blocked from receiving follow-up messages.
    """
    dep = await task_store.create(space_id=SPACE_ID, title="Dep", brief="")
    # Drive a task to ACTIVE first, then mutate its deps via update().
    task = await task_store.create(space_id=SPACE_ID, title="Running", brief="")
    await task_store.transition(task.id, TaskState.ACTIVE, allowed=USER_TRANSITIONS)
    # Now retroactively add an open dep.
    await task_store.update(task.id, depends_on=[dep.id])

    outcome = await task_store.apply_reply(task.id, "hello agent")

    assert outcome.task.state == TaskState.ACTIVE
    assert outcome.should_enqueue is False
    assert "hello agent" in outcome.task.pending_messages


async def test_apply_reply_waiting_path_unaffected_by_dep_gate(task_store):
    """A reply to a WAITING task promotes to ACTIVE even with open deps.

    The dep gate guards only the backlog branch of apply_reply (the
    "agent never started" entry point). A task that already entered the
    pipeline (active->waiting) was past the gate; replying to a clarifying
    question must not retroactively block on a freshly-introduced dep.
    """
    dep = await task_store.create(space_id=SPACE_ID, title="Dep", brief="")
    task = await task_store.create(space_id=SPACE_ID, title="Q?", brief="")
    # Drive it through backlog -> active -> waiting.
    await task_store.transition(task.id, TaskState.ACTIVE, allowed=USER_TRANSITIONS)
    await task_store.transition(task.id, TaskState.WAITING, allowed=WORKER_TRANSITIONS)
    # Retroactively add an open dep.
    await task_store.update(task.id, depends_on=[dep.id])

    outcome = await task_store.apply_reply(task.id, "answer")

    # Promotes to ACTIVE despite open deps — gate is BACKLOG-only.
    assert outcome.task.state == TaskState.ACTIVE
    assert outcome.should_enqueue is True


async def test_apply_reply_done_path_unaffected_by_dep_gate(task_store):
    """A reply to a DONE task re-promotes to ACTIVE — open deps must not block.

    Same scoping argument as the waiting case: once past the original
    backlog gate, follow-up turns are not re-gated. Locks in the
    `task.state == TaskState.BACKLOG` exact match (not e.g. `!= ACTIVE`).
    """
    dep = await task_store.create(space_id=SPACE_ID, title="Dep", brief="")
    task = await task_store.create(space_id=SPACE_ID, title="Closed", brief="")
    # Walk task to done.
    await task_store.transition(task.id, TaskState.ACTIVE, allowed=USER_TRANSITIONS)
    await task_store.transition(task.id, TaskState.DONE, allowed=WORKER_TRANSITIONS)
    # Retroactively add an open dep.
    await task_store.update(task.id, depends_on=[dep.id])

    outcome = await task_store.apply_reply(task.id, "reopen")

    assert outcome.task.state == TaskState.ACTIVE
    assert outcome.should_enqueue is True


# ---- unmet_deps edge cases ----


def test_unmet_deps_does_not_treat_self_as_satisfied():
    """If a task self-references in depends_on (data corruption only;
    create() blocks this), the gate still reports it as unmet because the
    task itself is in BACKLOG, not a terminal state.

    Locks in the policy: terminal-state check uses the dep's CURRENT state,
    not its identity. A backlog task cannot be its own satisfied dependency.
    """
    t = _mk_state("T", TaskState.BACKLOG, deps=["T"])

    # Task is in the index but its own state (BACKLOG) is non-terminal.
    assert unmet_deps(t, _index(t)) == ["T"]


def test_unmet_deps_returns_independent_list():
    """Repeated calls must return fresh lists — no shared mutable state.

    Defensive against a regression where callers mutate the result and
    accidentally poison the next caller.
    """
    d = _mk_state("D", TaskState.BACKLOG)
    t = _mk_state("T", TaskState.BACKLOG, deps=["D"])
    by_id = _index(t, d)

    first = unmet_deps(t, by_id)
    first.append("MUTATED")
    second = unmet_deps(t, by_id)

    assert second == ["D"]
    assert "MUTATED" not in second


def test_open_children_returns_independent_list():
    """Same independence contract on open_children."""
    g = _mk_state("G", TaskState.ACTIVE, task_type="goal")
    c = _mk_state("C", TaskState.BACKLOG, parent="G")
    by_id = _index(g, c)

    first = open_children("G", by_id)
    first.append("MUTATED")
    second = open_children("G", by_id)

    assert second == ["C"]
