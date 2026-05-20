from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, HTTPException, Query, Request, Response, UploadFile, status
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field

log = logging.getLogger(__name__)

from .. import git_ops
from ..agent import CRONOS_SUBDIR, space_dir_for
from ..file_service import FileEntry, list_files, list_git_changed_files, resolve_safe, save_upload
from ..models import Board, Space, Task, TaskState, TaskSummary
from ..space_storage import SpaceStore
from ..storage import (
    USER_TRANSITIONS,
    InvalidTransition,
    StorageError,
    TaskNotFound,
    TaskStore,
    UnknownSpace,
    summarize,
)
from ..worker import Worker, sse_events
from ..worker_pool import WorkerPool

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


def get_store(request: Request) -> TaskStore:
    return request.app.state.store


def get_space_store(request: Request) -> SpaceStore:
    return request.app.state.space_store


def get_pool(request: Request) -> WorkerPool:
    return request.app.state.worker_pool


def get_worker_for_task(request: Request, task_id: str) -> Worker:
    """Resolve the per-space worker that owns `task_id`.

    Raises 404 if the task is unknown, or 503 if no worker exists for its
    space (should only happen during a brief window while the space is
    being created or deleted).
    """
    pool = get_pool(request)
    task = get_store(request).get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    worker = pool.get(task.space_id)
    if worker is None:
        raise HTTPException(
            status_code=503,
            detail=f"No worker for space {task.space_id}",
        )
    return worker


class TaskRead(Task):
    """Task response with denormalized space fields for self-describing clients."""

    space_name: str | None = None
    space_color: str | None = None
    space_icon: str | None = None


class CreateTaskBody(BaseModel):
    space_id: str = Field(min_length=1, max_length=64)
    title: str = Field(min_length=1, max_length=200)
    brief: str = Field(default="", max_length=20_000)
    agent_model: Literal["default", "sonnet", "opus", "haiku"] = "default"
    agent_mode: Literal["plan", "auto", "ask"] = "auto"
    priority: int = Field(default=3, ge=1, le=5)


class UpdateTaskBody(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    brief: str | None = Field(default=None, max_length=20_000)
    agent_mode: Literal["plan", "auto", "ask"] | None = None
    agent_model: Literal["default", "sonnet", "opus", "haiku"] | None = None
    priority: int | None = Field(default=None, ge=1, le=5)


class ReorderBody(BaseModel):
    lane: TaskState
    task_ids: list[str] = Field(default_factory=list)


class TransitionBody(BaseModel):
    state: TaskState


class ReplyBody(BaseModel):
    message: str = Field(min_length=1, max_length=20_000)


class UpdateFileBody(BaseModel):
    content: str = Field(max_length=10_000_000)


def _enrich_summary(summary: TaskSummary, space: Space | None) -> TaskSummary:
    if space is None:
        return summary
    return summary.model_copy(
        update={
            "space_name": space.name,
            "space_color": space.color,
            "space_icon": space.icon,
        }
    )


def _enrich_board(board: Board, space_store: SpaceStore) -> Board:
    space_by_id = {s.id: s for s in space_store.list_all()}

    def fill(items: list[TaskSummary]) -> list[TaskSummary]:
        return [_enrich_summary(s, space_by_id.get(s.space_id)) for s in items]

    return Board(
        backlog=fill(board.backlog),
        active=fill(board.active),
        waiting=fill(board.waiting),
        done=fill(board.done),
    )


def _build_task_read(task: Task, space: Space | None) -> TaskRead:
    return TaskRead(
        **task.model_dump(),
        space_name=space.name if space else None,
        space_color=space.color if space else None,
        space_icon=space.icon if space else None,
    )


@router.get("", response_model=Board)
async def list_tasks(
    request: Request,
    space_id: str | None = Query(default=None, description="Space id, or 'all' for cross-space."),
) -> Board:
    store = get_store(request)
    space_store = get_space_store(request)
    scope = None if space_id in (None, "all", "") else space_id
    if scope is not None and not space_store.exists(scope):
        raise HTTPException(status_code=404, detail=f"Space {scope} not found")
    return _enrich_board(store.board(scope), space_store)


@router.get("/archived", response_model=list[TaskSummary])
async def list_archived_tasks(
    request: Request,
    space_id: str | None = Query(default=None, description="Space id, or 'all' for cross-space."),
) -> list[TaskSummary]:
    store = get_store(request)
    space_store = get_space_store(request)
    scope = None if space_id in (None, "all", "") else space_id
    if scope is not None and not space_store.exists(scope):
        raise HTTPException(status_code=404, detail=f"Space {scope} not found")
    space_by_id = {s.id: s for s in space_store.list_all()}
    tasks = [
        t for t in store.all()
        if t.state == TaskState.ARCHIVED and (scope is None or t.space_id == scope)
    ]
    tasks.sort(key=lambda t: t.updated_at, reverse=True)
    return [_enrich_summary(summarize(t), space_by_id.get(t.space_id)) for t in tasks]


@router.put("/reorder", status_code=status.HTTP_204_NO_CONTENT)
async def reorder_tasks(body: ReorderBody, request: Request) -> Response:
    await get_store(request).reorder(body.task_ids, body.lane)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{task_id}", response_model=TaskRead)
async def get_task(task_id: str, request: Request) -> TaskRead:
    task = get_store(request).get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    space = get_space_store(request).get(task.space_id)
    return _build_task_read(task, space)


@router.post("", response_model=TaskRead, status_code=status.HTTP_201_CREATED)
async def create_task(body: CreateTaskBody, request: Request) -> TaskRead:
    space_store = get_space_store(request)
    if not space_store.exists(body.space_id):
        raise HTTPException(status_code=404, detail=f"Space {body.space_id} not found")
    try:
        task = await get_store(request).create(
            space_id=body.space_id,
            title=body.title,
            brief=body.brief,
            agent_model=body.agent_model,
            agent_mode=body.agent_mode,
            priority=body.priority,
        )
    except UnknownSpace:
        raise HTTPException(status_code=404, detail=f"Space {body.space_id} not found") from None
    except StorageError as e:
        raise HTTPException(status_code=400, detail=str(e)) from None
    return _build_task_read(task, space_store.get(body.space_id))


@router.patch("/{task_id}", response_model=TaskRead)
async def update_task(task_id: str, body: UpdateTaskBody, request: Request) -> TaskRead:
    if (
        body.title is None
        and body.brief is None
        and body.agent_mode is None
        and body.agent_model is None
        and body.priority is None
    ):
        raise HTTPException(
            status_code=400,
            detail="Provide title, brief, agent_mode, or agent_model to update",
        )
    try:
        task = await get_store(request).update(
            task_id,
            title=body.title,
            brief=body.brief,
            agent_mode=body.agent_mode,
            agent_model=body.agent_model,
            priority=body.priority,
        )
    except TaskNotFound:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found") from None
    except StorageError as e:
        raise HTTPException(status_code=400, detail=str(e)) from None
    return _build_task_read(task, get_space_store(request).get(task.space_id))


@router.patch("/{task_id}/state", response_model=TaskRead)
async def transition_task(
    task_id: str, body: TransitionBody, request: Request
) -> TaskRead:
    try:
        updated = await get_store(request).transition(
            task_id, body.state, allowed=USER_TRANSITIONS
        )
    except TaskNotFound:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found") from None
    except InvalidTransition as e:
        raise HTTPException(status_code=409, detail=str(e)) from None
    except StorageError as e:
        raise HTTPException(status_code=400, detail=str(e)) from None
    if updated.state == TaskState.ACTIVE:
        await get_worker_for_task(request, task_id).enqueue(task_id)
    return _build_task_read(updated, get_space_store(request).get(updated.space_id))


@router.post("/{task_id}/start", response_model=TaskRead)
async def start_task(task_id: str, request: Request) -> TaskRead:
    store = get_store(request)
    task = store.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    if task.state != TaskState.BACKLOG:
        raise HTTPException(
            status_code=409,
            detail=f"Only backlog tasks can be started (current state: {task.state.value})",
        )
    updated = await store.transition(
        task_id, TaskState.ACTIVE, allowed=USER_TRANSITIONS
    )
    await get_worker_for_task(request, task_id).enqueue(task_id)
    return _build_task_read(updated, get_space_store(request).get(updated.space_id))


@router.post("/{task_id}/reply", response_model=TaskRead)
async def reply_to_task(task_id: str, body: ReplyBody, request: Request) -> TaskRead:
    store = get_store(request)
    try:
        outcome = await store.apply_reply(task_id, body.message)
    except TaskNotFound:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found") from None
    except InvalidTransition as e:
        raise HTTPException(status_code=409, detail=str(e)) from None
    except StorageError as e:
        raise HTTPException(status_code=400, detail=str(e)) from None
    if outcome.should_enqueue:
        await get_worker_for_task(request, task_id).enqueue(
            task_id, user_message=body.message
        )
    return _build_task_read(outcome.task, get_space_store(request).get(outcome.task.space_id))


@router.post("/{task_id}/stop", response_model=TaskRead)
async def stop_task(task_id: str, request: Request) -> TaskRead:
    store = get_store(request)
    task = store.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    worker = get_worker_for_task(request, task_id)
    if not worker.stop_current(task_id):
        # Nothing is actively running. If the task is stuck in active state
        # (e.g. the worker crashed mid-run without finalizing), reset it to
        # backlog so the user can un-stick it without a backend restart.
        if task.state == TaskState.ACTIVE:
            try:
                updated = await store.transition(
                    task_id, TaskState.BACKLOG, allowed=USER_TRANSITIONS
                )
                return _build_task_read(updated, get_space_store(request).get(updated.space_id))
            except (InvalidTransition, StorageError) as e:
                raise HTTPException(status_code=409, detail=str(e)) from None
        raise HTTPException(
            status_code=409,
            detail="Task is not currently running",
        )
    return _build_task_read(task, get_space_store(request).get(task.space_id))


@router.get("/{task_id}/stream")
async def stream_task(task_id: str, request: Request) -> StreamingResponse:
    worker = get_worker_for_task(request, task_id)
    return StreamingResponse(
        sse_events(task_id, worker),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


def _task_workspace(task: Task):
    return space_dir_for(task.space_id) / CRONOS_SUBDIR / "workspaces" / task.id


@router.get("/{task_id}/files", response_model=list[FileEntry])
async def list_task_files(task_id: str, request: Request) -> list[FileEntry]:
    task = get_store(request).get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    workspace = _task_workspace(task)
    if not workspace.exists():
        return []
    # For git worktrees (repo-linked spaces) show only files the agent
    # changed or created, not the entire repo checkout.
    changed = await list_git_changed_files(workspace)
    if changed is not None:
        return changed
    return list_files(workspace)


@router.get("/{task_id}/files/{file_path:path}")
async def get_task_file(
    task_id: str,
    file_path: str,
    request: Request,
    download: bool = Query(default=False),
) -> FileResponse:
    task = get_store(request).get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    workspace = _task_workspace(task)
    try:
        full = resolve_safe(workspace, file_path)
    except ValueError:
        raise HTTPException(status_code=403, detail="Access denied")
    if not full.exists() or full.is_dir():
        raise HTTPException(status_code=404, detail=f"File not found: {file_path}")
    headers = {}
    if download:
        headers["Content-Disposition"] = f'attachment; filename="{full.name}"'
    return FileResponse(str(full), headers=headers)


@router.post("/{task_id}/files", response_model=FileEntry, status_code=status.HTTP_201_CREATED)
async def upload_task_file(
    task_id: str,
    request: Request,
    file: UploadFile,
    subdir: str = Query(default=""),
) -> FileEntry:
    task = get_store(request).get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    workspace = _task_workspace(task)
    workspace.mkdir(parents=True, exist_ok=True)
    # Validate subdir is safe before passing to save_upload
    if subdir:
        try:
            resolve_safe(workspace, subdir)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid subdir path")
    try:
        return await save_upload(workspace, subdir, file)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/{task_id}/files/{file_path:path}", response_model=FileEntry)
async def update_task_file(
    task_id: str,
    file_path: str,
    body: UpdateFileBody,
    request: Request,
) -> FileEntry:
    task = get_store(request).get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    workspace = _task_workspace(task)
    try:
        full = resolve_safe(workspace, file_path)
    except ValueError:
        raise HTTPException(status_code=403, detail="Access denied")
    if not full.exists() or full.is_dir():
        raise HTTPException(status_code=404, detail=f"File not found: {file_path}")
    tmp = full.with_suffix(full.suffix + ".tmp")
    try:
        tmp.write_bytes(body.content.encode("utf-8"))
        tmp.rename(full)
    except Exception:
        tmp.unlink(missing_ok=True)
        raise
    stat = full.stat()
    rel = str(full.relative_to(workspace)).replace("\\", "/")
    mtime = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()
    return FileEntry(
        name=full.name,
        path=rel,
        size=stat.st_size,
        modified_at=mtime,
        is_dir=False,
        category=classify_file(rel, full.name),
    )


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(task_id: str, request: Request) -> Response:
    store = get_store(request)
    task = store.get(task_id)
    space = (
        get_space_store(request).get(task.space_id) if task is not None else None
    )
    try:
        await store.delete(task_id)
    except TaskNotFound:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found") from None
    # Tear down the per-task worktree (keep the branch — soft delete only).
    if task is not None and space is not None and space.git_repo_url:
        try:
            await git_ops.remove_task_worktree(space_dir_for(task.space_id), task_id)
        except git_ops.GitError:
            log.exception("Worktree cleanup failed for %s", task_id)
    # Delete traces — they live with the task (unlike stats which survive deletion).
    if task is not None:
        trace_store = getattr(request.app.state, "trace_store", None)
        if trace_store is not None:
            try:
                await trace_store.delete_task_traces(task.space_id, task_id)
            except Exception:
                log.exception("Trace cleanup failed for %s", task_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
