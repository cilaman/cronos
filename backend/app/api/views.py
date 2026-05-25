from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response, status
from pydantic import BaseModel, Field

from ..models import TaskState, TaskType, View
from ..space_storage import (
    SpaceError,
    SpaceNotFound,
    SpaceStore,
    ViewNotFound,
)

router = APIRouter(prefix="/api/spaces", tags=["views"])


def get_space_store(request: Request) -> SpaceStore:
    return request.app.state.space_store


class CreateViewBody(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    lanes: list[TaskState] = Field(min_length=1)
    type_filter: list[TaskType] | None = None
    default: bool = False


class UpdateViewBody(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    lanes: list[TaskState] | None = Field(default=None, min_length=1)
    type_filter: list[TaskType] | None = None
    default: bool | None = None


@router.get("/{space_id}/views", response_model=list[View])
async def list_views(space_id: str, request: Request) -> list[View]:
    space = get_space_store(request).get(space_id)
    if space is None:
        raise HTTPException(status_code=404, detail=f"Space {space_id} not found")
    return space.views


@router.post(
    "/{space_id}/views",
    response_model=View,
    status_code=status.HTTP_201_CREATED,
)
async def create_view(
    space_id: str, body: CreateViewBody, request: Request
) -> View:
    try:
        return await get_space_store(request).create_view(
            space_id,
            name=body.name,
            lanes=body.lanes,
            type_filter=body.type_filter,
            default=body.default,
        )
    except SpaceNotFound:
        raise HTTPException(
            status_code=404, detail=f"Space {space_id} not found"
        ) from None
    except SpaceError as e:
        raise HTTPException(status_code=400, detail=str(e)) from None


@router.patch("/{space_id}/views/{view_id}", response_model=View)
async def update_view(
    space_id: str, view_id: str, body: UpdateViewBody, request: Request
) -> View:
    if (
        body.name is None
        and body.lanes is None
        and "type_filter" not in body.model_fields_set
        and body.default is None
    ):
        raise HTTPException(status_code=400, detail="No fields to update")
    clear_type_filter = (
        "type_filter" in body.model_fields_set and body.type_filter is None
    )
    explicit_type_filter = (
        "type_filter" in body.model_fields_set and body.type_filter is not None
    )
    try:
        return await get_space_store(request).update_view(
            space_id,
            view_id,
            name=body.name,
            lanes=body.lanes,
            type_filter=body.type_filter if explicit_type_filter else None,
            clear_type_filter=clear_type_filter,
            default=body.default,
        )
    except SpaceNotFound:
        raise HTTPException(
            status_code=404, detail=f"Space {space_id} not found"
        ) from None
    except ViewNotFound:
        raise HTTPException(
            status_code=404, detail=f"View {view_id} not found"
        ) from None
    except SpaceError as e:
        raise HTTPException(status_code=400, detail=str(e)) from None


@router.delete(
    "/{space_id}/views/{view_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_view(
    space_id: str, view_id: str, request: Request
) -> Response:
    try:
        await get_space_store(request).delete_view(space_id, view_id)
    except SpaceNotFound:
        raise HTTPException(
            status_code=404, detail=f"Space {space_id} not found"
        ) from None
    except ViewNotFound:
        raise HTTPException(
            status_code=404, detail=f"View {view_id} not found"
        ) from None
    except SpaceError as e:
        detail = str(e)
        code = 409 if "Cannot delete the last view" in detail else 400
        raise HTTPException(status_code=code, detail=detail) from None
    return Response(status_code=status.HTTP_204_NO_CONTENT)
