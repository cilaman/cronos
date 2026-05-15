from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from ..models import Board, Task, TaskState
from ..storage import (
    USER_TRANSITIONS,
    InvalidTransition,
    StorageError,
    TaskNotFound,
    TaskStore,
)
from ..worker import Worker, sse_events

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


def get_store(request: Request) -> TaskStore:
    return request.app.state.store


def get_worker(request: Request) -> Worker:
    return request.app.state.worker


class CreateTaskBody(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    brief: str = Field(default="", max_length=20_000)


class UpdateTaskBody(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    brief: str | None = Field(default=None, max_length=20_000)


class TransitionBody(BaseModel):
    state: TaskState


class ReplyBody(BaseModel):
    message: str = Field(min_length=1, max_length=20_000)


@router.get("", response_model=Board)
async def list_tasks(request: Request) -> Board:
    return get_store(request).board()


@router.get("/{task_id}", response_model=Task)
async def get_task(task_id: str, request: Request) -> Task:
    task = get_store(request).get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    return task


@router.post("", response_model=Task, status_code=status.HTTP_201_CREATED)
async def create_task(body: CreateTaskBody, request: Request) -> Task:
    return await get_store(request).create(title=body.title, brief=body.brief)


@router.patch("/{task_id}", response_model=Task)
async def update_task(task_id: str, body: UpdateTaskBody, request: Request) -> Task:
    if body.title is None and body.brief is None:
        raise HTTPException(status_code=400, detail="Provide title or brief to update")
    try:
        return await get_store(request).update(
            task_id, title=body.title, brief=body.brief
        )
    except TaskNotFound:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found") from None


@router.patch("/{task_id}/state", response_model=Task)
async def transition_task(
    task_id: str, body: TransitionBody, request: Request
) -> Task:
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
    return updated


@router.post("/{task_id}/start", response_model=Task)
async def start_task(task_id: str, request: Request) -> Task:
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
    return updated


@router.post("/{task_id}/reply", response_model=Task)
async def reply_to_task(task_id: str, body: ReplyBody, request: Request) -> Task:
    store = get_store(request)
    try:
        updated = await store.apply_reply(task_id, body.message)
    except TaskNotFound:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found") from None
    except InvalidTransition as e:
        raise HTTPException(status_code=409, detail=str(e)) from None
    except StorageError as e:
        raise HTTPException(status_code=400, detail=str(e)) from None
    await get_worker(request).enqueue(task_id, user_message=body.message)
    return updated


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
    try:
        await get_store(request).delete(task_id)
    except TaskNotFound:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found") from None
    return Response(status_code=status.HTTP_204_NO_CONTENT)
