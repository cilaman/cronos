from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import secrets
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

import frontmatter
from pydantic import ValidationError

from dataclasses import dataclass

from .models import AgentMode, AgentModel, Board, FeatureState, Task, TaskState, TaskSummary
from .feature_state import FEATURE_USER_TRANSITIONS, FEATURE_WORKER_TRANSITIONS  # noqa: F401 — used by transition_feature

VALID_AGENT_MODES: tuple[AgentMode, ...] = ("plan", "auto", "ask")
VALID_AGENT_MODELS: tuple[AgentModel, ...] = ("default", "sonnet", "opus", "haiku", "opus-4-8", "fable-5")


@dataclass
class ReplyOutcome:
    task: Task
    should_enqueue: bool

log = logging.getLogger(__name__)

BRIEF_PREVIEW_CHARS = 200
MAX_SLUG_LEN = 40

# Directory names under `/data/spaces/` that aren't real spaces.
RESERVED_SPACE_DIRS: frozenset[str] = frozenset({".trash", ".imports"})

# Subdir inside each space where Cronos state lives. Kept in sync with the
# constant in space_storage.py (duplicated here to avoid a circular import).
CRONOS_SUBDIR = ".cronos"

# Ordered column list shared by _db_upsert and the reload_all bulk INSERT.
# Both call sites MUST consume this constant so column order cannot drift.
# New columns must be appended here and in the corresponding tuple builders.
_TASK_INSERT_COLS: tuple[str, ...] = (
    "id",
    "space_id",
    "state",
    "title",
    "type",
    "parent_id",
    "depends_on_json",
    "feature_state",
    "feature_key",
    "realizes",
    "issue_number",
    "issue_url",
    "proposed_issue_path",
)

USER_TRANSITIONS: set[tuple[TaskState, TaskState]] = {
    (TaskState.BACKLOG, TaskState.ACTIVE),
    (TaskState.BACKLOG, TaskState.ARCHIVED),
    (TaskState.ACTIVE, TaskState.BACKLOG),
    (TaskState.WAITING, TaskState.BACKLOG),
    (TaskState.WAITING, TaskState.DONE),
    (TaskState.DONE, TaskState.BACKLOG),
    (TaskState.DONE, TaskState.ARCHIVED),
    (TaskState.WAITING, TaskState.ARCHIVED),
    (TaskState.ARCHIVED, TaskState.BACKLOG),
    (TaskState.ARCHIVED, TaskState.DONE),
}

WORKER_TRANSITIONS: set[tuple[TaskState, TaskState]] = {
    (TaskState.ACTIVE, TaskState.WAITING),
    (TaskState.ACTIVE, TaskState.DONE),
    (TaskState.WAITING, TaskState.ACTIVE),
}


class StorageError(Exception):
    """Raised for invalid storage operations (bad transition, missing task)."""


class TaskNotFound(StorageError):
    pass


class InvalidTransition(StorageError):
    pass


class UnknownSpace(StorageError):
    pass


class CycleError(ValueError):
    """Raised when a parent_id or depends_on assignment would create a cycle or cross-space reference."""


# ---------- validators ----------


def validate_parent(
    task_id: str,
    candidate_parent_id: str | None,
    space_id: str,
    by_id: dict[str, Task],
) -> None:
    """Raise CycleError if setting task_id.parent_id = candidate_parent_id creates a cycle.

    Also raises for self-reference and cross-space parents.
    O(N) in tasks-per-space — walks the ancestor chain without re-reading files.
    """
    if candidate_parent_id is None:
        return
    if candidate_parent_id == task_id:
        raise CycleError(f"{task_id} -> {task_id}")
    candidate = by_id.get(candidate_parent_id)
    if candidate is None or candidate.space_id != space_id:
        raise CycleError(
            f"Parent {candidate_parent_id!r} not found in space {space_id!r}"
        )
    # Walk the ancestor chain of candidate_parent_id upward.
    # If we reach task_id it means task_id is already an ancestor of the candidate,
    # so making the candidate a parent of task_id would create a cycle.
    path = [task_id, candidate_parent_id]
    seen: set[str] = {task_id, candidate_parent_id}
    current_id = candidate_parent_id
    while True:
        node = by_id.get(current_id)
        if node is None:
            break
        next_id = node.parent_id
        if next_id is None:
            break
        if next_id == task_id:
            path.append(next_id)
            raise CycleError(" -> ".join(path))
        if next_id in seen:
            break
        seen.add(next_id)
        path.append(next_id)
        current_id = next_id


def _dep_cycle_path(
    target_id: str,
    start_id: str,
    by_id: dict[str, Task],
) -> list[str] | None:
    """BFS through depends_on links starting at start_id; return cycle path if target_id is found."""
    came_from: dict[str, str | None] = {start_id: None}
    queue: list[str] = [start_id]
    while queue:
        current_id = queue.pop(0)
        node = by_id.get(current_id)
        if node is None:
            continue
        for next_id in node.depends_on:
            if next_id == target_id:
                # Reconstruct: target_id -> start_id -> ... -> current_id -> target_id
                path = [target_id]
                curr: str | None = current_id
                while curr is not None:
                    path.append(curr)
                    curr = came_from.get(curr)
                path.append(target_id)
                path.reverse()
                return path
            if next_id not in came_from:
                came_from[next_id] = current_id
                queue.append(next_id)
    return None


def validate_depends_on(
    task_id: str,
    candidate_depends_on: list[str],
    space_id: str,
    by_id: dict[str, Task],
) -> None:
    """Raise CycleError if any dep in candidate_depends_on would create a cycle.

    A cycle exists when task_id is reachable from a dep via the depends_on chain.
    Also raises for self-references and cross-space deps.
    O(N) in tasks-per-space — uses BFS without re-reading files.
    """
    for dep_id in candidate_depends_on:
        if dep_id == task_id:
            raise CycleError(f"{task_id} -> {task_id}")
        dep = by_id.get(dep_id)
        if dep is None or dep.space_id != space_id:
            raise CycleError(
                f"Dependency {dep_id!r} not found in space {space_id!r}"
            )
    for dep_id in candidate_depends_on:
        path = _dep_cycle_path(task_id, dep_id, by_id)
        if path is not None:
            raise CycleError(" -> ".join(path))


def validate_realizes(
    item_id: str,
    feature_id: str | None,
    space_id: str,
    by_id: dict[str, Task],
) -> None:
    """Raise CycleError if setting item_id.realizes = feature_id is invalid.

    Validates:
    - No self-reference: item_id != feature_id
    - Target exists: feature_id must be in by_id
    - Same space: target.space_id must equal space_id
    - Target type: target.type must be "feature" or "fix"

    When feature_id is None, returns immediately (clearing is always valid).
    """
    if feature_id is None:
        return
    if feature_id == item_id:
        raise CycleError(f"{item_id} cannot realize itself")
    target = by_id.get(feature_id)
    if target is None or target.space_id != space_id:
        raise CycleError(
            f"Feature {feature_id!r} not found in space {space_id!r}"
        )
    if target.type not in ("feature", "fix"):
        raise CycleError(
            f"Target {feature_id!r} has type {target.type!r}; realizes must point to a feature or fix"
        )
    # BFS from item_id following existing realizes pointers to detect transitive cycles.
    # If feature_id is already reachable from item_id's chain, reject.
    visited: set[str] = {item_id}
    queue: list[str] = [item_id]
    hops = 0
    while queue and hops < 50:
        current_id = queue.pop(0)
        hops += 1
        current = by_id.get(current_id)
        if current is None or current.realizes is None:
            continue
        next_id = current.realizes
        if next_id == feature_id:
            raise StorageError(
                f"Circular realizes reference: {item_id} already transitively realizes {feature_id}"
            )
        if next_id not in visited:
            visited.add(next_id)
            queue.append(next_id)


_TERMINAL_STATES: frozenset[str] = frozenset({"done", "archived"})


def unmet_deps(task: Task, by_id: dict[str, Task]) -> list[str]:
    """Return ids of depends_on entries that are not yet done or archived."""
    result = []
    for dep_id in task.depends_on:
        dep = by_id.get(dep_id)
        if dep is None or dep.state.value not in _TERMINAL_STATES:
            result.append(dep_id)
    return result


def open_children(goal_id: str, by_id: dict[str, Task]) -> list[str]:
    """Return ids of child tasks of a goal that are not done or archived."""
    return [
        t.id
        for t in by_id.values()
        if t.parent_id == goal_id and t.state.value not in _TERMINAL_STATES
    ]


# ---------- parsing ----------


def split_body(body: str) -> tuple[str, str]:
    """Split a task body into (brief, history). Headings: `# Brief`, `# History`."""
    pattern = re.compile(r"(?im)^#\s+(brief|history)\s*$")
    parts: dict[str, str] = {}
    last_section: str | None = None
    last_idx = 0
    for m in pattern.finditer(body):
        if last_section is not None:
            parts[last_section] = body[last_idx : m.start()].strip("\n")
        last_section = m.group(1).lower()
        last_idx = m.end()
    if last_section is not None:
        parts[last_section] = body[last_idx:].strip("\n")
    else:
        return body.strip("\n"), ""
    return parts.get("brief", "").strip(), parts.get("history", "").strip()


def parse_file(path: Path, space_id: str) -> Task:
    """Parse a task markdown file. `space_id` is authoritative (from path)."""
    post = frontmatter.load(path)
    meta = dict(post.metadata)
    brief, history = split_body(post.content)
    raw_pending = meta.get("pending_messages") or []
    if not isinstance(raw_pending, list):
        raw_pending = []
    pending = [str(m) for m in raw_pending if isinstance(m, (str, int, float))]
    agent_mode = meta.get("agent_mode") or "auto"
    if agent_mode not in VALID_AGENT_MODES:
        agent_mode = "auto"
    agent_model = meta.get("agent_model") or "default"
    if agent_model not in VALID_AGENT_MODELS:
        agent_model = "default"
    try:
        priority = max(1, min(5, int(meta.get("priority", 3) or 3)))
    except (TypeError, ValueError):
        priority = 3
    try:
        manual_order = int(meta.get("manual_order", 0) or 0)
    except (TypeError, ValueError):
        manual_order = 0
    task_type = meta.get("type", "task")
    # "feature" and "fix" are valid types; unknown types coerce to "task" (preserve backward compat)
    if task_type not in ("task", "goal", "issue", "feature", "fix"):
        task_type = "task"
    parent_id = meta.get("parent_id") or None
    raw_depends = meta.get("depends_on") or []
    if not isinstance(raw_depends, list):
        raw_depends = []
    depends_on = [str(d) for d in raw_depends if isinstance(d, (str, int, float))]
    try:
        return Task(
            id=meta.get("id") or path.stem,
            space_id=space_id,
            title=meta["title"],
            state=meta.get("state", "backlog"),
            created_at=meta["created_at"],
            updated_at=meta["updated_at"],
            claude_session_id=meta.get("claude_session_id"),
            waiting_question=meta.get("waiting_question"),
            brief=brief,
            history=history,
            pending_messages=pending,
            agent_mode=agent_mode,
            agent_model=agent_model,
            priority=priority,
            manual_order=manual_order,
            type=task_type,
            parent_id=parent_id,
            depends_on=depends_on,
            pr_url=meta.get("pr_url") or None,
            proposed_pr_path=meta.get("proposed_pr_path") or None,
            feature_state=FeatureState(meta.get("feature_state")) if meta.get("feature_state") else None,
            feature_key=meta.get("feature_key") or None,
            realizes=meta.get("realizes") or None,
            issue_number=meta.get("issue_number") or None,
            issue_url=meta.get("issue_url") or None,
            proposed_issue_path=meta.get("proposed_issue_path") or None,
        )
    except (KeyError, ValidationError) as e:
        raise ValueError(f"Invalid task file {path.name}: {e}") from e


def summarize(task: Task) -> TaskSummary:
    """Build a TaskSummary from a Task. Space denorm fields are filled by the API layer."""
    preview = task.brief.replace("\n", " ").strip()
    if len(preview) > BRIEF_PREVIEW_CHARS:
        preview = preview[: BRIEF_PREVIEW_CHARS - 1].rstrip() + "…"
    return TaskSummary(
        id=task.id,
        space_id=task.space_id,
        title=task.title,
        state=task.state,
        created_at=task.created_at,
        updated_at=task.updated_at,
        waiting_question=task.waiting_question,
        brief_preview=preview,
        priority=task.priority,
        manual_order=task.manual_order,
        agent_mode=task.agent_mode,
        type=task.type,
        parent_id=task.parent_id,
        depends_on=list(task.depends_on),
        pr_url=task.pr_url,
        proposed_pr_path=task.proposed_pr_path,
        feature_state=task.feature_state,
        feature_key=task.feature_key,
        realizes=task.realizes,
        issue_number=task.issue_number,
        issue_url=task.issue_url,
        proposed_issue_path=task.proposed_issue_path,
    )


# ---------- serialization ----------


def _iso(dt: datetime) -> str:
    return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def dump_task(task: Task) -> str:
    """Serialize a Task to its on-disk markdown form."""
    meta = {
        "id": task.id,
        "space_id": task.space_id,
        "title": task.title,
        "state": task.state.value,
        "created_at": _iso(task.created_at),
        "updated_at": _iso(task.updated_at),
        "claude_session_id": task.claude_session_id,
        "waiting_question": task.waiting_question,
        "agent_mode": task.agent_mode,
        "agent_model": task.agent_model,
        "pending_messages": list(task.pending_messages),
        "priority": task.priority,
        "manual_order": task.manual_order,
        "type": task.type,
        "parent_id": task.parent_id,
        "depends_on": list(task.depends_on),
        "pr_url": task.pr_url,
        "proposed_pr_path": task.proposed_pr_path,
        "feature_state": task.feature_state.value if task.feature_state else None,
        "feature_key": task.feature_key,
        "realizes": task.realizes,
        "issue_number": task.issue_number,
        "issue_url": task.issue_url,
        "proposed_issue_path": task.proposed_issue_path,
    }
    body_parts = ["# Brief", "", task.brief.strip() or ""]
    if task.history.strip():
        body_parts += ["", "# History", "", task.history.strip()]
    else:
        body_parts += ["", "# History", ""]
    post = frontmatter.Post("\n".join(body_parts), **meta)
    return frontmatter.dumps(post) + "\n"


def atomic_write(path: Path, text: str) -> None:
    """Write `text` to `path` atomically via tmpfile + os.replace."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".tmp.{secrets.token_hex(4)}")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


# ---------- id / slug ----------

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def slugify(title: str) -> str:
    slug = _SLUG_RE.sub("-", title.lower()).strip("-")
    if not slug:
        slug = "untitled"
    return slug[:MAX_SLUG_LEN].rstrip("-") or "untitled"


def generate_task_id(title: str, now: datetime, taken: set[str]) -> str:
    base = f"{now.strftime('%Y-%m-%d-%H%M')}-{slugify(title)}"
    if base not in taken:
        return base
    # Collision: append a short random suffix.
    for _ in range(10):
        candidate = f"{base}-{secrets.token_hex(2)}"
        if candidate not in taken:
            return candidate
    raise StorageError("Could not generate a unique task id")


# ---------- store ----------


class TaskStore:
    """Markdown-on-disk task store with an in-memory index.

    Tasks live at `/data/spaces/{space_id}/tasks/*.md`. The directory name is
    authoritative for a task's space (the frontmatter is denormalized for
    self-describing files but is overridden by the path on reindex).

    Writes go through atomic tmpfile + os.replace. After every write we
    re-parse the file and update the in-memory index synchronously so the
    next API read reflects the change without waiting for the file watcher.
    The watcher then sees the same change and is a no-op.
    """

    def __init__(self, spaces_dir: Path) -> None:
        self.spaces_dir = spaces_dir
        self._db_path = spaces_dir.parent / "cronos-index.db"
        self._by_id: dict[str, Task] = {}
        self._path_by_id: dict[str, Path] = {}
        self._lock = asyncio.Lock()

    # ---- SQLite index ----

    def _ensure_db_schema(self) -> None:
        """Create or migrate the SQLite tasks index. Idempotent."""
        con = sqlite3.connect(self._db_path)
        try:
            con.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    id TEXT NOT NULL PRIMARY KEY,
                    space_id TEXT NOT NULL,
                    state TEXT NOT NULL,
                    title TEXT NOT NULL,
                    type TEXT NOT NULL DEFAULT 'task',
                    parent_id TEXT NULL,
                    depends_on_json TEXT NOT NULL DEFAULT '[]'
                )
            """)
            for col, defn in [
                ("type", "TEXT NOT NULL DEFAULT 'task'"),
                ("parent_id", "TEXT NULL"),
                ("depends_on_json", "TEXT NOT NULL DEFAULT '[]'"),
                # Feature / fix columns — added by featurefix-data-model I2
                ("feature_state", "TEXT NULL"),
                ("feature_key", "TEXT NULL"),
                ("realizes", "TEXT NULL"),
                ("issue_number", "INTEGER NULL"),
                ("issue_url", "TEXT NULL"),
                ("proposed_issue_path", "TEXT NULL"),
            ]:
                try:
                    con.execute(f"ALTER TABLE tasks ADD COLUMN {col} {defn}")
                except sqlite3.OperationalError:
                    pass  # column already exists
            con.execute(
                "CREATE INDEX IF NOT EXISTS idx_tasks_space_parent ON tasks(space_id, parent_id)"
            )
            con.execute(
                "CREATE INDEX IF NOT EXISTS idx_tasks_space_type ON tasks(space_id, type)"
            )
            con.execute(
                "CREATE INDEX IF NOT EXISTS idx_tasks_space_realizes ON tasks(space_id, realizes)"
            )
            con.execute("""
                CREATE TABLE IF NOT EXISTS discovered_tools (
                    source_url TEXT NOT NULL,
                    source_slug TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    name TEXT NOT NULL,
                    relative_path TEXT NOT NULL,
                    description TEXT,
                    source_sha TEXT NOT NULL,
                    last_seen TEXT NOT NULL,
                    PRIMARY KEY (source_slug, kind, name)
                )
            """)
            con.execute(
                "CREATE INDEX IF NOT EXISTS idx_discovered_tools_kind ON discovered_tools(kind)"
            )
            con.commit()
        finally:
            con.close()

    @staticmethod
    def _task_insert_row(task: Task) -> tuple:
        """Return an INSERT value tuple in the same order as _TASK_INSERT_COLS.

        Both _db_upsert and reload_all MUST call this helper so column order
        cannot drift between the two code paths (design risk R7: INSERT tuple
        drift — a drift would silently NULL-out feature columns after reload_all).

        Column positions (0-indexed, must match _TASK_INSERT_COLS exactly):
          0  id
          1  space_id
          2  state
          3  title
          4  type
          5  parent_id
          6  depends_on_json
          7  feature_state   <- feature field 1 of 6
          8  feature_key     <- feature field 2 of 6
          9  realizes        <- feature field 3 of 6
         10  issue_number    <- feature field 4 of 6
         11  issue_url       <- feature field 5 of 6
         12  proposed_issue_path  <- feature field 6 of 6

        Adding a new column requires updating both _TASK_INSERT_COLS (constant)
        and this tuple at the same position.  Never add to one without the other.
        """
        row = (
            task.id,
            task.space_id,
            task.state.value,
            task.title,
            task.type,
            task.parent_id,
            json.dumps(task.depends_on),
            task.feature_state.value if task.feature_state is not None else None,
            task.feature_key,
            task.realizes,
            task.issue_number,
            task.issue_url,
            task.proposed_issue_path,
        )
        # I9 persistence invariant: tuple length must equal column list length.
        assert len(row) == len(_TASK_INSERT_COLS), (
            f"_task_insert_row length {len(row)} != _TASK_INSERT_COLS length "
            f"{len(_TASK_INSERT_COLS)} — add new columns to both"
        )
        return row

    def _db_upsert(self, task: Task) -> None:
        cols = ", ".join(_TASK_INSERT_COLS)
        placeholders = ", ".join("?" * len(_TASK_INSERT_COLS))
        con = sqlite3.connect(self._db_path)
        try:
            con.execute(
                f"INSERT OR REPLACE INTO tasks ({cols}) VALUES ({placeholders})",
                self._task_insert_row(task),
            )
            con.commit()
        finally:
            con.close()

    def _db_delete(self, task_id: str) -> None:
        con = sqlite3.connect(self._db_path)
        try:
            con.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
            con.commit()
        finally:
            con.close()

    # ---- helpers ----

    def _space_for(self, path: Path) -> str | None:
        """Return space_id if `path` is `{spaces_dir}/{space}/.cronos/tasks/{file}.md`."""
        try:
            rel = path.relative_to(self.spaces_dir)
        except ValueError:
            return None
        if len(rel.parts) != 4:
            return None
        space_id, cronos, subdir, _name = rel.parts
        if space_id in RESERVED_SPACE_DIRS:
            return None
        if cronos != CRONOS_SUBDIR or subdir != "tasks":
            return None
        if path.suffix != ".md":
            return None
        return space_id

    def trash_dir_for(self, space_id: str) -> Path:
        return self.spaces_dir / space_id / CRONOS_SUBDIR / ".trash"

    def tasks_dir_for(self, space_id: str) -> Path:
        return self.spaces_dir / space_id / CRONOS_SUBDIR / "tasks"

    # ---- index ops ----

    async def reload_all(self) -> None:
        async with self._lock:
            self._by_id.clear()
            self._path_by_id.clear()
            if not self.spaces_dir.exists():
                log.info("Spaces dir %s does not exist yet", self.spaces_dir)
                self._ensure_db_schema()
                return
            for space_dir in sorted(self.spaces_dir.iterdir()):
                if not space_dir.is_dir() or space_dir.name in RESERVED_SPACE_DIRS:
                    continue
                tasks_dir = space_dir / CRONOS_SUBDIR / "tasks"
                if not tasks_dir.is_dir():
                    continue
                space_id = space_dir.name
                for path in sorted(tasks_dir.glob("*.md")):
                    try:
                        task = parse_file(path, space_id)
                    except ValueError as e:
                        log.warning("Skipping invalid task file: %s", e)
                        continue
                    self._by_id[task.id] = task
                    self._path_by_id[task.id] = path
            log.info("Loaded %d tasks from %s", len(self._by_id), self.spaces_dir)
            self._ensure_db_schema()
            cols = ", ".join(_TASK_INSERT_COLS)
            placeholders = ", ".join("?" * len(_TASK_INSERT_COLS))
            con = sqlite3.connect(self._db_path)
            try:
                con.execute("DELETE FROM tasks")
                for task in self._by_id.values():
                    con.execute(
                        f"INSERT INTO tasks ({cols}) VALUES ({placeholders})",
                        self._task_insert_row(task),
                    )
                con.commit()
            finally:
                con.close()

    async def reindex_path(self, path: Path) -> None:
        async with self._lock:
            self._reindex_locked(path)

    def _reindex_locked(self, path: Path) -> None:
        space_id = self._space_for(path)
        if space_id is None:
            return
        if not path.exists():
            stale_id = next(
                (tid for tid, p in self._path_by_id.items() if p == path), None
            )
            if stale_id:
                self._by_id.pop(stale_id, None)
                self._path_by_id.pop(stale_id, None)
                self._db_delete(stale_id)
                log.info("Removed task %s (file deleted)", stale_id)
            return
        try:
            task = parse_file(path, space_id)
        except ValueError as e:
            log.warning("Skipping invalid task file: %s", e)
            return
        self._by_id[task.id] = task
        self._path_by_id[task.id] = path
        self._db_upsert(task)

    def get(self, task_id: str) -> Task | None:
        return self._by_id.get(task_id)

    def all(self) -> list[Task]:
        return list(self._by_id.values())

    def count(self, space_id: str | None = None) -> int:
        if space_id is None:
            return len(self._by_id)
        return sum(1 for t in self._by_id.values() if t.space_id == space_id)

    def counts_by_space(self) -> dict[str, dict[TaskState, int]]:
        out: dict[str, dict[TaskState, int]] = {}
        for task in self._by_id.values():
            if task.type in ("feature", "fix"):
                continue
            buckets = out.setdefault(task.space_id, {s: 0 for s in TaskState})
            buckets[task.state] = buckets.get(task.state, 0) + 1
        return out

    def last_activity_by_space(self) -> dict[str, datetime]:
        out: dict[str, datetime] = {}
        for task in self._by_id.values():
            prev = out.get(task.space_id)
            if prev is None or task.updated_at > prev:
                out[task.space_id] = task.updated_at
        return out

    def board(self, space_id: str | None = None) -> Board:
        """Return tasks grouped by state. `None` or "all" ⇒ cross-space.

        Feature and fix tasks are excluded — they are surfaced via feature_board() instead.
        """
        scope = None if space_id in (None, "all", "") else space_id
        # Build realizes_feature_key lookup: task_id -> feature_key for feature/fix tasks.
        feature_key_by_id: dict[str, str] = {
            t.id: t.feature_key
            for t in self._by_id.values()
            if t.feature_key is not None and (scope is None or t.space_id == scope)
        }
        lanes: dict[TaskState, list[TaskSummary]] = {s: [] for s in TaskState}
        for task in self._by_id.values():
            if scope is not None and task.space_id != scope:
                continue
            if task.type in ("feature", "fix"):
                continue
            s = summarize(task)
            if task.realizes:
                s.realizes_feature_key = feature_key_by_id.get(task.realizes)
            blockers = unmet_deps(task, self._by_id)
            if blockers:
                s = s.model_copy(update={"unmet_dependencies": blockers})
            lanes[task.state].append(s)
        for items in lanes.values():
            items.sort(key=lambda t: (t.manual_order, -t.updated_at.timestamp()))
        return Board(
            backlog=lanes[TaskState.BACKLOG],
            active=lanes[TaskState.ACTIVE],
            waiting=lanes[TaskState.WAITING],
            done=lanes[TaskState.DONE],
        )

    async def feature_board(self, space_id: str) -> dict[FeatureState, list[TaskSummary]]:
        """Return feature and fix tasks for space_id bucketed by feature_state.

        Only includes tasks with type in ("feature", "fix").
        Tasks with feature_state=None are excluded (should not exist in practice).
        """
        async with self._lock:
            # Count realizing items per feature (tasks with realizes=feature_id in this space).
            realizing_counts: dict[str, int] = {}
            for t in self._by_id.values():
                if t.space_id == space_id and t.realizes:
                    realizing_counts[t.realizes] = realizing_counts.get(t.realizes, 0) + 1

            # Build realizes_feature_key lookup scoped to this space.
            feature_key_by_id: dict[str, str] = {
                t.id: t.feature_key
                for t in self._by_id.values()
                if t.space_id == space_id and t.feature_key is not None
            }

            buckets: dict[FeatureState, list[TaskSummary]] = {fs: [] for fs in FeatureState}
            for task in self._by_id.values():
                if task.space_id != space_id:
                    continue
                if task.type not in ("feature", "fix"):
                    continue
                if task.feature_state is None:
                    log.warning(
                        "feature_board: task %s (type=%s) has feature_state=None — skipping",
                        task.id,
                        task.type,
                    )
                    continue
                summary = summarize(task)
                count = realizing_counts.get(task.id, 0)
                summary.realizing_count = count
                summary.realized_by_count = count
                if task.realizes:
                    summary.realizes_feature_key = feature_key_by_id.get(task.realizes)
                buckets[task.feature_state].append(summary)
            # Sort each bucket by manual_order then created_at
            for fs in buckets:
                buckets[fs].sort(key=lambda s: (s.manual_order, s.created_at))
            return buckets

    # ---- feature helpers ----

    def _next_feature_key(self, space_id: str, task_type: str) -> str:
        """Return the next sequential FEAT-NNN or FIX-NNN key for the given space and type.

        Caller must hold self._lock.

        Scans self._by_id directly without acquiring any lock — the caller
        already holds self._lock when this is invoked from create().  Never
        make this async or re-acquire the lock inside this method (deadlock risk
        documented in design-report risks[]).

        Args:
            space_id: The space to scope the counter to (per-space isolation).
            task_type: ``"feature"`` produces ``FEAT-NNN``; any other value
                produces ``FIX-NNN``.

        Returns:
            A zero-padded key string such as ``"FEAT-001"`` or ``"FIX-007"``.
        """
        # I6 invariant: FEAT and FIX counters are independent — each prefix is
        # derived from task_type so "feature" tasks only increment the FEAT-NNN
        # counter and "fix" tasks only increment the FIX-NNN counter.
        prefix = "FEAT" if task_type == "feature" else "FIX"
        max_num = 0
        for task in self._by_id.values():
            # I6 invariant: counter is per-space — skip tasks in other spaces.
            if task.space_id != space_id:
                continue
            # I6 invariant: counter is per-type — skip tasks of the wrong type.
            if task.type != task_type:
                continue
            fk = task.feature_key
            if fk is None or not fk.startswith(prefix + "-"):
                continue
            suffix = fk[len(prefix) + 1:]
            try:
                num = int(suffix)
            except ValueError:
                continue
            if num > max_num:
                max_num = num
        # I6 invariant: non-feature/non-fix tasks never reach this method —
        # create() only calls _next_feature_key when type in ("feature", "fix").
        return f"{prefix}-{(max_num + 1):03d}"

    # ---- mutations ----

    async def transition_feature(
        self,
        task_id: str,
        new_feature_state: FeatureState,
        *,
        allowed: frozenset[tuple[FeatureState, FeatureState]],
    ) -> Task:
        """Transition task.feature_state to new_feature_state.

        Modelled on transition() but operates exclusively on feature_state —
        task.state is NEVER mutated by this method.  FeatureState and TaskState
        are distinct enums; do not pass a TaskState value here.

        Args:
            task_id: ID of the task to transition.
            new_feature_state: The target FeatureState (not TaskState).
            allowed: Frozenset of (current, new) FeatureState pairs that are
                permitted; typically FEATURE_USER_TRANSITIONS or
                FEATURE_WORKER_TRANSITIONS from app.feature_state.

        Returns:
            The updated Task (task.state is unchanged).

        Raises:
            TaskNotFound: task_id does not exist.
            InvalidTransition: task type is not "feature" or "fix", or the
                (current, new) pair is not in allowed, or feature_state is None.
        """
        async with self._lock:
            task = self._by_id.get(task_id)
            if task is None:
                raise TaskNotFound(task_id)
            if task.type not in ("feature", "fix"):
                raise InvalidTransition(
                    f"Task {task_id!r} has type {task.type!r}; "
                    "transition_feature requires type 'feature' or 'fix'"
                )
            if task.feature_state is None:
                raise InvalidTransition(
                    f"Task {task_id!r} has no feature_state set"
                )
            current_feature_state = task.feature_state
            if current_feature_state == new_feature_state:
                return task
            if (current_feature_state, new_feature_state) not in allowed:
                raise InvalidTransition(
                    f"Cannot move feature from {current_feature_state.value!r} "
                    f"to {new_feature_state.value!r}"
                )
            updated = task.model_copy(
                update={
                    "feature_state": new_feature_state,
                    "updated_at": datetime.now(tz=UTC),
                }
            )
            path = self._path_by_id[task_id]
            atomic_write(path, dump_task(updated))
            self._reindex_locked(path)
            return self._by_id[task_id]

    async def set_feature_waiting_question(self, task_id: str, question: str | None) -> Task:
        async with self._lock:
            task = self._by_id.get(task_id)
            if task is None:
                raise TaskNotFound(task_id)
            if task.type not in ("feature", "fix"):
                raise StorageError(f"Task {task_id} is not a feature or fix")
            updated = task.model_copy(
                update={"waiting_question": question, "updated_at": datetime.now(tz=UTC)}
            )
            path = self._path_by_id[task_id]
            atomic_write(path, dump_task(updated))
            self._reindex_locked(path)
            return self._by_id[task_id]

    async def create(
        self,
        *,
        space_id: str,
        title: str,
        brief: str,
        agent_model: AgentModel = "default",
        agent_mode: AgentMode = "auto",
        priority: int = 3,
        type: str = "task",
        parent_id: str | None = None,
        depends_on: list[str] | None = None,
    ) -> Task:
        if agent_model not in VALID_AGENT_MODELS:
            raise StorageError(f"Invalid agent_model: {agent_model}")
        if agent_mode not in VALID_AGENT_MODES:
            raise StorageError(f"Invalid agent_mode: {agent_mode}")
        if type not in ("task", "goal", "issue", "feature", "fix"):
            raise StorageError(f"Invalid type: {type}")
        tasks_dir = self.tasks_dir_for(space_id)
        if not tasks_dir.is_dir():
            raise UnknownSpace(space_id)
        now = datetime.now(tz=UTC)
        async with self._lock:
            task_id = generate_task_id(title, now, set(self._by_id.keys()))
            feature_key: str | None = None
            initial_feature_state: FeatureState | None = None
            if type in ("feature", "fix"):
                feature_key = self._next_feature_key(space_id, type)
                initial_feature_state = FeatureState.BACKLOG
            task = Task(
                id=task_id,
                space_id=space_id,
                title=title.strip(),
                state=TaskState.BACKLOG,
                created_at=now,
                updated_at=now,
                brief=brief.strip(),
                history="",
                agent_model=agent_model,
                agent_mode=agent_mode,
                priority=max(1, min(5, priority)),
                manual_order=0,
                type=type,
                parent_id=parent_id,
                depends_on=depends_on or [],
                feature_key=feature_key,
                feature_state=initial_feature_state,
            )
            path = tasks_dir / f"{task_id}.md"
            atomic_write(path, dump_task(task))
            self._reindex_locked(path)
            log.info("Created task %s in space %s", task_id, space_id)
            return self._by_id[task_id]

    async def update(
        self,
        task_id: str,
        *,
        title: str | None = None,
        brief: str | None = None,
        agent_mode: AgentMode | None = None,
        agent_model: AgentModel | None = None,
        priority: int | None = None,
        type: str | None = None,
        parent_id: str | None = None,
        depends_on: list[str] | None = None,
    ) -> Task:
        if agent_mode is not None and agent_mode not in VALID_AGENT_MODES:
            raise StorageError(f"Invalid agent_mode: {agent_mode}")
        if agent_model is not None and agent_model not in VALID_AGENT_MODELS:
            raise StorageError(f"Invalid agent_model: {agent_model}")
        if type is not None and type not in ("task", "goal", "issue", "feature", "fix"):
            raise StorageError(f"Invalid type: {type}")
        async with self._lock:
            task = self._by_id.get(task_id)
            if task is None:
                raise TaskNotFound(task_id)
            if type is not None and type in ("feature", "fix") and task.type not in ("feature", "fix"):
                raise StorageError(
                    "Cannot change task type to feature or fix via update(); create a new feature task instead"
                )
            update_dict: dict = {
                "title": title.strip() if title is not None else task.title,
                "brief": brief.strip() if brief is not None else task.brief,
                "agent_mode": agent_mode if agent_mode is not None else task.agent_mode,
                "agent_model": agent_model if agent_model is not None else task.agent_model,
                "updated_at": datetime.now(tz=UTC),
            }
            if priority is not None:
                update_dict["priority"] = max(1, min(5, priority))
            if type is not None:
                update_dict["type"] = type
            if parent_id is not None:
                update_dict["parent_id"] = parent_id
            if depends_on is not None:
                update_dict["depends_on"] = depends_on
            updated = task.model_copy(update=update_dict)
            path = self._path_by_id[task_id]
            atomic_write(path, dump_task(updated))
            self._reindex_locked(path)
            return self._by_id[task_id]

    async def transition(
        self,
        task_id: str,
        new_state: TaskState,
        *,
        allowed: set[tuple[TaskState, TaskState]],
    ) -> Task:
        async with self._lock:
            task = self._by_id.get(task_id)
            if task is None:
                raise TaskNotFound(task_id)
            if task.state == new_state:
                return task
            if (task.state, new_state) not in allowed:
                raise InvalidTransition(
                    f"Cannot move task from {task.state.value} to {new_state.value}"
                )
            if task.state == TaskState.BACKLOG and new_state == TaskState.ACTIVE:
                blockers = unmet_deps(task, self._by_id)
                if blockers:
                    raise InvalidTransition(
                        f"Cannot start task: unmet dependencies: {', '.join(blockers)}"
                    )
            if task.type == "goal" and new_state == TaskState.DONE:
                open_child_ids = open_children(task_id, self._by_id)
                if open_child_ids:
                    raise InvalidTransition(
                        f"Cannot mark goal done: open children: {', '.join(open_child_ids)}"
                    )
            updated = task.model_copy(
                update={
                    "state": new_state,
                    "updated_at": datetime.now(tz=UTC),
                }
            )
            # Leaving the waiting lane clears any pending question.
            if task.state == TaskState.WAITING and new_state != TaskState.WAITING:
                updated = updated.model_copy(update={"waiting_question": None})
            path = self._path_by_id[task_id]
            atomic_write(path, dump_task(updated))
            self._reindex_locked(path)
            return self._by_id[task_id]

    async def finalize_run(
        self,
        task_id: str,
        *,
        new_state: TaskState,
        session_id: str | None,
        waiting_question: str | None,
        history_entry: str,
    ) -> Task:
        """Atomic post-agent-run update: state, session id, question, history."""
        async with self._lock:
            task = self._by_id.get(task_id)
            if task is None:
                raise TaskNotFound(task_id)
            if new_state != task.state and (task.state, new_state) not in WORKER_TRANSITIONS:
                raise InvalidTransition(
                    f"Worker cannot move task from {task.state.value} to {new_state.value}"
                )
            history = task.history.strip()
            if history:
                history = history + "\n\n" + history_entry.strip()
            else:
                history = history_entry.strip()
            updated = task.model_copy(
                update={
                    "state": new_state,
                    "claude_session_id": session_id or task.claude_session_id,
                    "waiting_question": waiting_question,
                    "history": history,
                    "updated_at": datetime.now(tz=UTC),
                }
            )
            path = self._path_by_id[task_id]
            atomic_write(path, dump_task(updated))
            self._reindex_locked(path)
            return self._by_id[task_id]

    async def set_pr_refs(
        self,
        task_id: str,
        *,
        pr_url: str | None,
        proposed_pr_path: str | None,
    ) -> Task:
        """Persist PR URL and/or proposed PR path on a task."""
        async with self._lock:
            task = self._by_id.get(task_id)
            if task is None:
                raise TaskNotFound(task_id)
            updated = task.model_copy(
                update={
                    "pr_url": pr_url,
                    "proposed_pr_path": proposed_pr_path,
                    "updated_at": datetime.now(tz=UTC),
                }
            )
            path = self._path_by_id[task_id]
            atomic_write(path, dump_task(updated))
            self._reindex_locked(path)
            return self._by_id[task_id]

    async def set_issue_refs(
        self,
        task_id: str,
        *,
        issue_number: int | None,
        issue_url: str | None,
        proposed_issue_path: str | None,
    ) -> Task:
        """Persist issue number, URL and/or proposed issue path on a task."""
        async with self._lock:
            task = self._by_id.get(task_id)
            if task is None:
                raise TaskNotFound(task_id)
            updated = task.model_copy(
                update={
                    "issue_number": issue_number,
                    "issue_url": issue_url,
                    "proposed_issue_path": proposed_issue_path,
                    "updated_at": datetime.now(tz=UTC),
                }
            )
            path = self._path_by_id[task_id]
            atomic_write(path, dump_task(updated))
            self._reindex_locked(path)
            return self._by_id[task_id]

    async def autopilot_conflict(self, task_id: str, waiting_question: str) -> Task:
        """Move a DONE task to WAITING with a conflict message (autopilot rebase failure)."""
        async with self._lock:
            task = self._by_id.get(task_id)
            if task is None:
                raise TaskNotFound(task_id)
            updated = task.model_copy(
                update={
                    "state": TaskState.WAITING,
                    "waiting_question": waiting_question,
                    "updated_at": datetime.now(tz=UTC),
                }
            )
            path = self._path_by_id[task_id]
            atomic_write(path, dump_task(updated))
            self._reindex_locked(path)
            return self._by_id[task_id]

    async def apply_reply(self, task_id: str, message: str) -> ReplyOutcome:
        """Record a user message on the task and return an outcome.

        - backlog | waiting | done -> append `[user]` history entry, transition
          to active, clear `waiting_question`, `should_enqueue=True`.
        - active -> append `[user]` history entry AND append to
          `pending_messages` for the worker to drain on the next turn,
          `should_enqueue=False` (worker auto-enqueues after finalize).
        """
        message = message.strip()
        if not message:
            raise StorageError("Reply message is empty")
        async with self._lock:
            task = self._by_id.get(task_id)
            if task is None:
                raise TaskNotFound(task_id)
            now = datetime.now(tz=UTC)
            entry = f"```\n{_iso(now)} [user]\n{message}\n```"
            history = task.history.strip()
            history = (history + "\n\n" + entry) if history else entry

            if task.state == TaskState.ACTIVE:
                updated = task.model_copy(
                    update={
                        "history": history,
                        "pending_messages": [*task.pending_messages, message],
                        "updated_at": now,
                    }
                )
                should_enqueue = False
            else:
                if task.state == TaskState.BACKLOG:
                    blockers = unmet_deps(task, self._by_id)
                    if blockers:
                        raise InvalidTransition(
                            f"Cannot start task: unmet dependencies: {', '.join(blockers)}"
                        )
                updated = task.model_copy(
                    update={
                        "state": TaskState.ACTIVE,
                        "waiting_question": None,
                        "history": history,
                        "updated_at": now,
                    }
                )
                should_enqueue = True

            path = self._path_by_id[task_id]
            atomic_write(path, dump_task(updated))
            self._reindex_locked(path)
            return ReplyOutcome(task=self._by_id[task_id], should_enqueue=should_enqueue)

    async def resume_with_message(self, task_id: str) -> Task:
        """Force-transition any state -> ACTIVE so a queued follow-up turn can run.

        Used by the worker after `_finalize` when pending_messages were queued
        mid-run. Bypasses `WORKER_TRANSITIONS` because DONE -> ACTIVE is not
        otherwise legal.
        """
        async with self._lock:
            task = self._by_id.get(task_id)
            if task is None:
                raise TaskNotFound(task_id)
            if task.state == TaskState.ACTIVE:
                return task
            updated = task.model_copy(
                update={
                    "state": TaskState.ACTIVE,
                    "waiting_question": None,
                    "updated_at": datetime.now(tz=UTC),
                }
            )
            path = self._path_by_id[task_id]
            atomic_write(path, dump_task(updated))
            self._reindex_locked(path)
            return self._by_id[task_id]

    async def drain_pending(self, task_id: str) -> list[str]:
        """Atomically read-and-clear `pending_messages` on a task."""
        async with self._lock:
            task = self._by_id.get(task_id)
            if task is None:
                raise TaskNotFound(task_id)
            if not task.pending_messages:
                return []
            messages = list(task.pending_messages)
            updated = task.model_copy(
                update={
                    "pending_messages": [],
                    "updated_at": datetime.now(tz=UTC),
                }
            )
            path = self._path_by_id[task_id]
            atomic_write(path, dump_task(updated))
            self._reindex_locked(path)
            return messages

    async def append_pending(self, task_id: str, message: str) -> Task:
        """Append message to pending_messages without any state transition."""
        async with self._lock:
            task = self._by_id.get(task_id)
            if task is None:
                raise TaskNotFound(task_id)
            updated = task.model_copy(
                update={
                    "pending_messages": [*task.pending_messages, message],
                    "updated_at": datetime.now(tz=UTC),
                }
            )
            path = self._path_by_id[task_id]
            atomic_write(path, dump_task(updated))
            self._reindex_locked(path)
            return self._by_id[task_id]

    async def record_user_message(self, task_id: str, message: str) -> Task:
        """Append a user message to history only, with no state change or enqueue."""
        message = message.strip()
        async with self._lock:
            task = self._by_id.get(task_id)
            if task is None:
                raise TaskNotFound(task_id)
            now = datetime.now(tz=UTC)
            entry = f"```\n{_iso(now)} [user]\n{message}\n```"
            history = task.history.strip()
            history = (history + "\n\n" + entry) if history else entry
            updated = task.model_copy(
                update={"history": history, "updated_at": now}
            )
            path = self._path_by_id[task_id]
            atomic_write(path, dump_task(updated))
            self._reindex_locked(path)
            return self._by_id[task_id]

    def subtree(self, root_id: str) -> list[Task]:
        """Return root task + all descendants in BFS order. Returns [] if root not found."""
        root = self._by_id.get(root_id)
        if root is None:
            return []
        result = [root]
        queue = [root_id]
        while queue:
            current_id = queue.pop(0)
            children = sorted(
                [t for t in self._by_id.values() if t.parent_id == current_id],
                key=lambda t: (t.manual_order, t.id),
            )
            for child in children:
                result.append(child)
                queue.append(child.id)
        return result

    async def promote(self, task_id: str) -> Task:
        """Set type to 'goal'. Idempotent if already a goal."""
        async with self._lock:
            task = self._by_id.get(task_id)
            if task is None:
                raise TaskNotFound(task_id)
            if task.type == "goal":
                return task
            updated = task.model_copy(
                update={"type": "goal", "updated_at": datetime.now(tz=UTC)}
            )
            path = self._path_by_id[task_id]
            atomic_write(path, dump_task(updated))
            self._reindex_locked(path)
            return self._by_id[task_id]

    async def set_parent(self, task_id: str, parent_id: str | None) -> Task:
        """Set or clear parent_id. Calls validate_parent; raises CycleError on cycle."""
        async with self._lock:
            task = self._by_id.get(task_id)
            if task is None:
                raise TaskNotFound(task_id)
            validate_parent(task_id, parent_id, task.space_id, self._by_id)
            updated = task.model_copy(
                update={"parent_id": parent_id, "updated_at": datetime.now(tz=UTC)}
            )
            path = self._path_by_id[task_id]
            atomic_write(path, dump_task(updated))
            self._reindex_locked(path)
            return self._by_id[task_id]

    async def realizing_items(self, feature_id: str) -> list[TaskSummary]:
        """Return TaskSummary list of tasks whose realizes field equals feature_id.

        Implemented as an in-memory scan of self._by_id. The SQLite index
        idx_tasks_space_realizes exists for future query-based variants but is
        not load-bearing in S1.
        """
        async with self._lock:
            # Build feature_key lookup (unscoped — matches the method's cross-space behavior).
            feature_key_by_id: dict[str, str] = {
                t.id: t.feature_key
                for t in self._by_id.values()
                if t.feature_key is not None
            }
            result = []
            for task in self._by_id.values():
                if task.realizes == feature_id:
                    s = summarize(task)
                    s.realizes_feature_key = feature_key_by_id.get(task.realizes)
                    result.append(s)
            return result

    async def set_realizes(self, item_id: str, feature_id: str | None) -> Task:
        """Set or clear the realizes field on a task.

        When feature_id is not None, calls validate_realizes() to enforce:
        - no self-reference
        - target exists in the same space
        - target type is "feature" or "fix"

        When feature_id is None, clears the field with no validation.
        Mirrors set_parent in structure and persistence pattern.
        """
        async with self._lock:
            task = self._by_id.get(item_id)
            if task is None:
                raise TaskNotFound(item_id)
            validate_realizes(item_id, feature_id, task.space_id, self._by_id)
            updated = task.model_copy(
                update={"realizes": feature_id, "updated_at": datetime.now(tz=UTC)}
            )
            path = self._path_by_id[item_id]
            atomic_write(path, dump_task(updated))
            self._reindex_locked(path)
            return self._by_id[item_id]

    async def set_depends_on(self, task_id: str, depends_on: list[str]) -> Task:
        """Set depends_on list. Calls validate_depends_on; raises CycleError on cycle."""
        async with self._lock:
            task = self._by_id.get(task_id)
            if task is None:
                raise TaskNotFound(task_id)
            validate_depends_on(task_id, depends_on, task.space_id, self._by_id)
            updated = task.model_copy(
                update={"depends_on": depends_on, "updated_at": datetime.now(tz=UTC)}
            )
            path = self._path_by_id[task_id]
            atomic_write(path, dump_task(updated))
            self._reindex_locked(path)
            return self._by_id[task_id]

    async def delete(self, task_id: str) -> list[str]:
        """Soft-delete the task and all its descendants into the per-space `.trash/`.

        Returns the list of all deleted task IDs (root first, BFS order).
        """
        async with self._lock:
            if task_id not in self._by_id:
                raise TaskNotFound(task_id)
            to_delete = self.subtree(task_id)
            space_id = to_delete[0].space_id
            trash = self.trash_dir_for(space_id)
            trash.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%SZ")
            deleted_ids: list[str] = []
            for t in to_delete:
                path = self._path_by_id.get(t.id)
                if path is None:
                    continue
                dest = trash / f"{path.stem}.{stamp}.md"
                os.replace(path, dest)
                self._by_id.pop(t.id, None)
                self._path_by_id.pop(t.id, None)
                self._db_delete(t.id)
                deleted_ids.append(t.id)
                log.info("Trashed task %s -> %s", t.id, dest.name)
            return deleted_ids

    async def reorder(self, task_ids: list[str], lane: TaskState) -> None:
        """Set manual_order for tasks in a lane based on their position in task_ids."""
        async with self._lock:
            for index, task_id in enumerate(task_ids):
                task = self._by_id.get(task_id)
                if task is None or task.state != lane:
                    continue
                if task.manual_order == index:
                    continue
                updated = task.model_copy(update={"manual_order": index})
                path = self._path_by_id[task_id]
                atomic_write(path, dump_task(updated))
                self._reindex_locked(path)

    async def archive_stale_done_tasks(self, threshold_days: int) -> int:
        """Transition DONE tasks older than threshold_days to ARCHIVED. Returns count."""
        cutoff = datetime.now(tz=UTC) - timedelta(days=threshold_days)
        async with self._lock:
            to_archive = [
                task.id
                for task in self._by_id.values()
                if task.state == TaskState.DONE and task.updated_at < cutoff
            ]
        count = 0
        for task_id in to_archive:
            try:
                await self.transition(task_id, TaskState.ARCHIVED, allowed=USER_TRANSITIONS)
                count += 1
            except (TaskNotFound, InvalidTransition) as e:
                log.warning("Failed to auto-archive task %s: %s", task_id, e)
        return count

    async def drop_space(self, space_id: str) -> None:
        """Drop all in-memory entries for a space (used after the space is trashed)."""
        async with self._lock:
            to_drop = [tid for tid, t in self._by_id.items() if t.space_id == space_id]
            for tid in to_drop:
                self._by_id.pop(tid, None)
                self._path_by_id.pop(tid, None)
            if to_drop:
                log.info("Dropped %d tasks from in-memory index for space %s", len(to_drop), space_id)
