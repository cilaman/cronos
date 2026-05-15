from __future__ import annotations

import asyncio
import logging
import os
import re
import secrets
from datetime import UTC, datetime
from pathlib import Path

import frontmatter
from pydantic import ValidationError

from dataclasses import dataclass

from .models import AgentMode, Board, Task, TaskState, TaskSummary

VALID_AGENT_MODES: tuple[AgentMode, ...] = ("plan", "auto", "ask")


@dataclass
class ReplyOutcome:
    task: Task
    should_enqueue: bool

log = logging.getLogger(__name__)

BRIEF_PREVIEW_CHARS = 200
MAX_SLUG_LEN = 40

USER_TRANSITIONS: set[tuple[TaskState, TaskState]] = {
    (TaskState.BACKLOG, TaskState.ACTIVE),
    (TaskState.ACTIVE, TaskState.BACKLOG),
    (TaskState.WAITING, TaskState.BACKLOG),
    (TaskState.DONE, TaskState.BACKLOG),
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


def parse_file(path: Path) -> Task:
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
    try:
        return Task(
            id=meta.get("id") or path.stem,
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
        )
    except (KeyError, ValidationError) as e:
        raise ValueError(f"Invalid task file {path.name}: {e}") from e


def summarize(task: Task) -> TaskSummary:
    preview = task.brief.replace("\n", " ").strip()
    if len(preview) > BRIEF_PREVIEW_CHARS:
        preview = preview[: BRIEF_PREVIEW_CHARS - 1].rstrip() + "…"
    return TaskSummary(
        id=task.id,
        title=task.title,
        state=task.state,
        created_at=task.created_at,
        updated_at=task.updated_at,
        waiting_question=task.waiting_question,
        brief_preview=preview,
    )


# ---------- serialization ----------


def _iso(dt: datetime) -> str:
    return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def dump_task(task: Task) -> str:
    """Serialize a Task to its on-disk markdown form."""
    meta = {
        "id": task.id,
        "title": task.title,
        "state": task.state.value,
        "created_at": _iso(task.created_at),
        "updated_at": _iso(task.updated_at),
        "claude_session_id": task.claude_session_id,
        "waiting_question": task.waiting_question,
        "agent_mode": task.agent_mode,
        "pending_messages": list(task.pending_messages),
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

    Writes go through atomic tmpfile + os.replace. After every write we
    re-parse the file and update the in-memory index synchronously so the
    next API read reflects the change without waiting for the file watcher.
    The watcher then sees the same change and is a no-op.
    """

    def __init__(self, tasks_dir: Path) -> None:
        self.tasks_dir = tasks_dir
        self.trash_dir = tasks_dir / ".trash"
        self._by_id: dict[str, Task] = {}
        self._path_by_id: dict[str, Path] = {}
        self._lock = asyncio.Lock()

    # ---- index ops ----

    async def reload_all(self) -> None:
        async with self._lock:
            self._by_id.clear()
            self._path_by_id.clear()
            for path in sorted(self.tasks_dir.glob("*.md")):
                try:
                    task = parse_file(path)
                except ValueError as e:
                    log.warning("Skipping invalid task file: %s", e)
                    continue
                self._by_id[task.id] = task
                self._path_by_id[task.id] = path
            log.info("Loaded %d tasks from %s", len(self._by_id), self.tasks_dir)

    async def reindex_path(self, path: Path) -> None:
        async with self._lock:
            self._reindex_locked(path)

    def _reindex_locked(self, path: Path) -> None:
        # Ignore anything outside the top-level tasks dir (e.g. .trash/*.md).
        if path.parent != self.tasks_dir:
            return
        if not path.exists():
            stale_id = next(
                (tid for tid, p in self._path_by_id.items() if p == path), None
            )
            if stale_id:
                self._by_id.pop(stale_id, None)
                self._path_by_id.pop(stale_id, None)
                log.info("Removed task %s (file deleted)", stale_id)
            return
        try:
            task = parse_file(path)
        except ValueError as e:
            log.warning("Skipping invalid task file: %s", e)
            return
        self._by_id[task.id] = task
        self._path_by_id[task.id] = path

    def get(self, task_id: str) -> Task | None:
        return self._by_id.get(task_id)

    def count(self) -> int:
        return len(self._by_id)

    def board(self) -> Board:
        lanes: dict[TaskState, list[TaskSummary]] = {s: [] for s in TaskState}
        for task in self._by_id.values():
            lanes[task.state].append(summarize(task))
        for items in lanes.values():
            items.sort(key=lambda t: t.updated_at, reverse=True)
        return Board(
            backlog=lanes[TaskState.BACKLOG],
            active=lanes[TaskState.ACTIVE],
            waiting=lanes[TaskState.WAITING],
            done=lanes[TaskState.DONE],
        )

    # ---- mutations ----

    async def create(self, title: str, brief: str) -> Task:
        now = datetime.now(tz=UTC)
        async with self._lock:
            task_id = generate_task_id(title, now, set(self._by_id.keys()))
            task = Task(
                id=task_id,
                title=title.strip(),
                state=TaskState.BACKLOG,
                created_at=now,
                updated_at=now,
                brief=brief.strip(),
                history="",
            )
            path = self.tasks_dir / f"{task_id}.md"
            atomic_write(path, dump_task(task))
            self._reindex_locked(path)
            log.info("Created task %s", task_id)
            return self._by_id[task_id]

    async def update(
        self,
        task_id: str,
        *,
        title: str | None = None,
        brief: str | None = None,
        agent_mode: AgentMode | None = None,
    ) -> Task:
        if agent_mode is not None and agent_mode not in VALID_AGENT_MODES:
            raise StorageError(f"Invalid agent_mode: {agent_mode}")
        async with self._lock:
            task = self._by_id.get(task_id)
            if task is None:
                raise TaskNotFound(task_id)
            updated = task.model_copy(
                update={
                    "title": title.strip() if title is not None else task.title,
                    "brief": brief.strip() if brief is not None else task.brief,
                    "agent_mode": agent_mode if agent_mode is not None else task.agent_mode,
                    "updated_at": datetime.now(tz=UTC),
                }
            )
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

    async def delete(self, task_id: str) -> None:
        """Soft-delete: move the file into `.trash/` so nothing is destroyed."""
        async with self._lock:
            path = self._path_by_id.get(task_id)
            if path is None:
                raise TaskNotFound(task_id)
            self.trash_dir.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%SZ")
            dest = self.trash_dir / f"{path.stem}.{stamp}.md"
            os.replace(path, dest)
            self._by_id.pop(task_id, None)
            self._path_by_id.pop(task_id, None)
            log.info("Trashed task %s -> %s", task_id, dest.name)
