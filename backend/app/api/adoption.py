from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request, Response, status
from pydantic import BaseModel

from ..space_storage import SpaceStore
from ..tools.adoption import (
    AdoptionManifest,
    AlreadyAdopted,
    ItemNotFound,
    NotAdopted,
    adopt,
    unadopt,
)

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/spaces", tags=["adoption"])


def _get_space_store(request: Request) -> SpaceStore:
    return request.app.state.space_store


class AdoptRequest(BaseModel):
    source_slug: str
    kind: str
    name: str


@router.post("/{space_id}/adopt", status_code=201, response_model=AdoptionManifest)
async def adopt_tool(
    space_id: str,
    body: AdoptRequest,
    request: Request,
) -> AdoptionManifest:
    space_store = _get_space_store(request)
    if space_store.get(space_id) is None:
        raise HTTPException(status_code=404, detail=f"Space {space_id!r} not found")

    try:
        return await adopt(
            space_id,
            body.source_slug,
            body.kind,
            body.name,
        )
    except AlreadyAdopted as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ItemNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/{space_id}/adopt/{kind}/{name}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def unadopt_tool(
    space_id: str,
    kind: str,
    name: str,
    request: Request,
) -> Response:
    space_store = _get_space_store(request)
    if space_store.get(space_id) is None:
        raise HTTPException(status_code=404, detail=f"Space {space_id!r} not found")

    try:
        await unadopt(space_id, kind, name)
    except NotAdopted as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return Response(status_code=status.HTTP_204_NO_CONTENT)
