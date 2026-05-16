from __future__ import annotations

import logging
from typing import Literal

from fastapi import APIRouter, HTTPException, Query, Request, Response, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

log = logging.getLogger(__name__)

from .. import git_ops
from ..agent import space_dir_for
from ..models import Board, Space, Task, TaskState, TaskSummary
from ..space_storage import SpaceStore
from ..storage import (
    USER_TRANSITIONS,
    InvalidTransition,
    StorageError,
    TaskNotFound,
    TaskStore,
    UnknownSpace,
)
from ..worker import Worker, sse_events

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


def get_store(request: Request) -> TaskStore:
    return request.app.state.store


def get_space_store(request: Request) -> SpaceStore:
    return request.app.state.space_store


def get_worker(request: Request) -> Worker:
    return request.app.state.worker


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


class UpdateTaskBody(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    brief: str | None = Field(default=None, max_length=20_000)
    agent_mode: Literal["plan", "auto", "ask"] | None = None
    agent_model: Literal["default", "sonnet", "opus", "haiku"] | None = None


class TransitionBody(BaseModel):
    state: TaskState


class ReplyBody(BaseModel):
    message: str = Field(min_length=1, max_length=20_000)


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
        await get_worker(request).enqueue(task_id)
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
    await get_worker(request).enqueue(task_id)
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
        await get_worker(request).enqueue(task_id, user_message=body.message)
    return _build_task_read(outcome.task, get_space_store(request).get(outcome.task.space_id))


@router.post("/{task_id}/stop", response_model=TaskRead)
async def stop_task(task_id: str, request: Request) -> TaskRead:
    store = get_store(request)
    task = store.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    worker = get_worker(request)
    if not worker.stop_current(task_id):
        raise HTTPException(
            status_code=409,
            detail="Task is not currently running",
        )
    return _build_task_read(task, get_space_store(request).get(task.space_id))


@router.get("/{task_id}/stream")
async def stream_task(task_id: str, request: Request) -> StreamingResponse:
    worker = get_worker(request)
    return StreamingResponse(
        sse_events(task_id, worker),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
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
    return Response(status_code=status.HTTP_204_NO_CONTENT)
