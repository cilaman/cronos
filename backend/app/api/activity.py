from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request

from ..models import Activity
from ..space_storage import SpaceStore
from ..storage import TaskStore

router = APIRouter(prefix="/api/activity", tags=["activity"])


def get_store(request: Request) -> TaskStore:
    return request.app.state.store


def get_space_store(request: Request) -> SpaceStore:
    return request.app.state.space_store


@router.get("", response_model=list[Activity])
async def list_activity(
    request: Request,
    limit: int = Query(default=50, ge=1, le=200),
    space_id: str | None = Query(default=None),
) -> list[Activity]:
    task_store = get_store(request)
    space_store = get_space_store(request)
    if space_id is not None and not space_store.exists(space_id):
        raise HTTPException(status_code=404, detail=f"Space {space_id} not found")

    tasks = task_store.all()
    if space_id is not None:
        tasks = [t for t in tasks if t.space_id == space_id]
    tasks.sort(key=lambda t: t.updated_at, reverse=True)
    out = [
        Activity(
            task_id=t.id,
            space_id=t.space_id,
            title=t.title,
            state=t.state,
            updated_at=t.updated_at,
        )
        for t in tasks[:limit]
    ]
    return out
