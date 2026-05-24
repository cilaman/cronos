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
    dump_task,
    generate_task_id,
    parse_file,
    slugify,
    summarize,
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
