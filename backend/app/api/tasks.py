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
from ..models import Board, Space, Task, TaskState, TaskSummary, View
from ..space_storage import SpaceStore
from ..storage import (
    USER_TRANSITIONS,
    CycleError,
    InvalidTransition,
    StorageError,
    TaskNotFound,
    TaskStore,
    UnknownSpace,
    summarize,
    unmet_deps,
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
    unmet_dependencies: list[str] = []


class CreateTaskBody(BaseModel):
    space_id: str = Field(min_length=1, max_length=64)
    title: str = Field(min_length=1, max_length=200)
    brief: str = Field(default="", max_length=20_000)
    agent_model: Literal["default", "sonnet", "opus", "haiku"] = "default"
    agent_mode: Literal["plan", "auto", "ask"] = "auto"
    priority: int = Field(default=3, ge=1, le=5)
    type: Literal["task", "goal", "issue"] = "task"
    parent_id: str | None = None
    depends_on: list[str] = Field(default_factory=list)


class UpdateTaskBody(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    brief: str | None = Field(default=None, max_length=20_000)
    agent_mode: Literal["plan", "auto", "ask"] | None = None
    agent_model: Literal["default", "sonnet", "opus", "haiku"] | None = None
    priority: int | None = Field(default=None, ge=1, le=5)
    type: Literal["task", "goal", "issue"] | None = None
    parent_id: str | None = None
    depends_on: list[str] | None = None


class ReorderBody(BaseModel):
    lane: TaskState
    task_ids: list[str] = Field(default_factory=list)


class TransitionBody(BaseModel):
    state: TaskState


class ReplyBody(BaseModel):
    message: str = Field(min_length=1, max_length=20_000)


class UpdateFileBody(BaseModel):
    content: str = Field(max_length=10_000_000)


class ParentBody(BaseModel):
    parent_id: str | None


class DependsOnBody(BaseModel):
    depends_on: list[str] = Field(default_factory=list)


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


def _apply_view_filter(board: Board, view: View) -> Board:
    lane_set = {state.value for state in view.lanes}

    def filter_lane(items: list[TaskSummary], lane_name: str) -> list[TaskSummary]:
        if lane_name not in lane_set:
            return []
        if view.type_filter is None:
            return items
        return [t for t in items if t.type in view.type_filter]

    return Board(
        backlog=filter_lane(board.backlog, "backlog"),
        active=filter_lane(board.active, "active"),
        waiting=filter_lane(board.waiting, "waiting"),
        done=filter_lane(board.done, "done"),
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


def _build_task_read(task: Task, space: Space | None, store: TaskStore | None = None) -> TaskRead:
    unmet: list[str] = unmet_deps(task, store._by_id) if store is not None else []
    return TaskRead(
        **task.model_dump(),
        space_name=space.name if space else None,
        space_color=space.color if space else None,
        space_icon=space.icon if space else None,
        unmet_dependencies=unmet,
    )


@router.get("", response_model=Board)
async def list_tasks(
    request: Request,
    space_id: str | None = Query(default=None, description="Space id, or 'all' for cross-space."),
    view: str | None = Query(default=None, description="View id or 'default'. Requires space_id."),
) -> Board:
    store = get_store(request)
    space_store = get_space_store(request)
    scope = None if space_id in (None, "all", "") else space_id
    if scope is not None and not space_store.exists(scope):
        raise HTTPException(status_code=404, detail=f"Space {scope} not found")
    board = _enrich_board(store.board(scope), space_store)
    if view is not None:
        if scope is None:
            raise HTTPException(
                status_code=400,
                detail="?view requires a specific space_id",
            )
        space = space_store.get(scope)
        assert space is not None  # already checked above
        if view == "default":
            resolved = next((v for v in space.views if v.default), None)
            if resolved is None:
                raise HTTPException(status_code=404, detail="No default view found")
        else:
            resolved = next((v for v in space.views if v.id == view), None)
            if resolved is None:
                raise HTTPException(status_code=404, detail=f"View {view!r} not found")
        board = _apply_view_filter(board, resolved)
    return board


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
    return [
        _enrich_summary(
            summarize(t).model_copy(update={"unmet_dependencies": unmet_deps(t, store._by_id)}),
            space_by_id.get(t.space_id),
        )
        for t in tasks
    ]


@router.put("/reorder", status_code=status.HTTP_204_NO_CONTENT)
async def reorder_tasks(body: ReorderBody, request: Request) -> Response:
    await get_store(request).reorder(body.task_ids, body.lane)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{task_id}", response_model=TaskRead)
async def get_task(task_id: str, request: Request) -> TaskRead:
    store = get_store(request)
    task = store.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    space = get_space_store(request).get(task.space_id)
    return _build_task_read(task, space, store)


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
            type=body.type,
            parent_id=body.parent_id,
            depends_on=body.depends_on,
        )
    except UnknownSpace:
        raise HTTPException(status_code=404, detail=f"Space {body.space_id} not found") from None
    except StorageError as e:
        raise HTTPException(status_code=400, detail=str(e)) from None
    store = get_store(request)
    return _build_task_read(task, space_store.get(body.space_id), store)


@router.patch("/{task_id}", response_model=TaskRead)
async def update_task(task_id: str, body: UpdateTaskBody, request: Request) -> TaskRead:
    if (
        body.title is None
        and body.brief is None
        and body.agent_mode is None
        and body.agent_model is None
        and body.priority is None
        and body.type is None
        and body.parent_id is None
        and body.depends_on is None
    ):
        raise HTTPException(
            status_code=400,
            detail="Provide title, brief, agent_mode, agent_model, type, parent_id, or depends_on to update",
        )
    try:
        task = await get_store(request).update(
            task_id,
            title=body.title,
            brief=body.brief,
            agent_mode=body.agent_mode,
            agent_model=body.agent_model,
            priority=body.priority,
            type=body.type,
            parent_id=body.parent_id,
            depends_on=body.depends_on,
        )
    except TaskNotFound:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found") from None
    except StorageError as e:
        raise HTTPException(status_code=400, detail=str(e)) from None
    store = get_store(request)
    return _build_task_read(task, get_space_store(request).get(task.space_id), store)


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
    return _build_task_read(updated, get_space_store(request).get(updated.space_id), get_store(request))


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
    try:
        updated = await store.transition(
            task_id, TaskState.ACTIVE, allowed=USER_TRANSITIONS
        )
    except InvalidTransition as e:
        raise HTTPException(status_code=409, detail=str(e)) from None
    await get_worker_for_task(request, task_id).enqueue(task_id)
    return _build_task_read(updated, get_space_store(request).get(updated.space_id), store)


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
    return _build_task_read(outcome.task, get_space_store(request).get(outcome.task.space_id), store)


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
                return _build_task_read(updated, get_space_store(request).get(updated.space_id), store)
            except (InvalidTransition, StorageError) as e:
                raise HTTPException(status_code=409, detail=str(e)) from None
        raise HTTPException(
            status_code=409,
            detail="Task is not currently running",
        )
    return _build_task_read(task, get_space_store(request).get(task.space_id), store)


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


@router.get("/{task_id}/tree", response_model=list[TaskRead])
async def get_task_tree(task_id: str, request: Request) -> list[TaskRead]:
    store = get_store(request)
    task = store.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    space_store = get_space_store(request)
    space_by_id = {s.id: s for s in space_store.list_all()}
    tasks = store.subtree(task_id)
    return [_build_task_read(t, space_by_id.get(t.space_id), store) for t in tasks]


@router.post("/{task_id}/promote", response_model=TaskRead)
async def promote_task(task_id: str, request: Request) -> TaskRead:
    store = get_store(request)
    try:
        task = await store.promote(task_id)
    except TaskNotFound:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found") from None
    return _build_task_read(task, get_space_store(request).get(task.space_id), store)


@router.patch("/{task_id}/parent", response_model=TaskRead)
async def set_task_parent(task_id: str, body: ParentBody, request: Request) -> TaskRead:
    store = get_store(request)
    try:
        task = await store.set_parent(task_id, body.parent_id)
    except TaskNotFound:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found") from None
    except CycleError as e:
        raise HTTPException(status_code=409, detail=str(e)) from None
    return _build_task_read(task, get_space_store(request).get(task.space_id), store)


@router.patch("/{task_id}/depends_on", response_model=TaskRead)
async def set_task_depends_on(task_id: str, body: DependsOnBody, request: Request) -> TaskRead:
    store = get_store(request)
    try:
        task = await store.set_depends_on(task_id, body.depends_on)
    except TaskNotFound:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found") from None
    except CycleError as e:
        raise HTTPException(status_code=409, detail=str(e)) from None
    return _build_task_read(task, get_space_store(request).get(task.space_id), store)


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
