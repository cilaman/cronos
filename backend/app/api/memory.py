from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

from ..memory_store import MemoryNotFound, MemoryStore
from ..models import MemoryItem, MemoryKind

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/memory", tags=["memory"])


def get_store(request: Request) -> MemoryStore:
    return request.app.state.memory_store


# ---- request/response bodies ----


class CreateMemoryBody(BaseModel):
    kind: MemoryKind
    title: str = Field(min_length=1, max_length=500)
    body: str = ""
    confirmed: bool = False
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    score: float = 0.0
    last_used_at: datetime | None = None
    ref_count: int = 0
    ttl_until: datetime | None = None
    sources: list[str] = Field(default_factory=list)
    links: list[str] = Field(default_factory=list)


class UpdateMemoryBody(BaseModel):
    title: str | None = None
    body: str | None = None
    kind: MemoryKind | None = None
    confirmed: bool | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    score: float | None = None
    last_used_at: datetime | None = None
    ref_count: int | None = None
    ttl_until: datetime | None = None
    sources: list[str] | None = None
    links: list[str] | None = None


# ---- endpoints ----


@router.get("/{scope}", response_model=list[MemoryItem])
async def list_items(scope: str, request: Request) -> list[MemoryItem]:
    store = get_store(request)
    return await store.list_scope(scope)


@router.post("/{scope}", response_model=MemoryItem, status_code=201)
async def create_item(scope: str, body: CreateMemoryBody, request: Request) -> MemoryItem:
    store = get_store(request)
    return await store.create(
        scope=scope,
        kind=body.kind,
        title=body.title,
        body=body.body,
        confirmed=body.confirmed,
        confidence=body.confidence,
        score=body.score,
        last_used_at=body.last_used_at,
        ref_count=body.ref_count,
        ttl_until=body.ttl_until,
        sources=body.sources,
        links=body.links,
    )


@router.get("/{scope}/index.md", response_class=PlainTextResponse)
async def get_index(scope: str, request: Request) -> str:
    store = get_store(request)
    content = await store.read_index(scope)
    if content is None:
        raise HTTPException(status_code=404, detail=f"No index found for scope {scope!r}")
    return content


@router.get("/{scope}/{item_id}", response_model=MemoryItem)
async def get_item(scope: str, item_id: str, request: Request) -> MemoryItem:
    store = get_store(request)
    item = await store.get(scope, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail=f"Memory item {item_id!r} not found in scope {scope!r}")
    return item


@router.patch("/{scope}/{item_id}", response_model=MemoryItem)
async def update_item(scope: str, item_id: str, body: UpdateMemoryBody, request: Request) -> MemoryItem:
    store = get_store(request)
    try:
        return await store.update(
            scope,
            item_id,
            title=body.title,
            body=body.body,
            kind=body.kind,
            confirmed=body.confirmed,
            confidence=body.confidence,
            score=body.score,
            last_used_at=body.last_used_at,
            ref_count=body.ref_count,
            ttl_until=body.ttl_until,
            sources=body.sources,
            links=body.links,
        )
    except MemoryNotFound:
        raise HTTPException(status_code=404, detail=f"Memory item {item_id!r} not found in scope {scope!r}")


@router.post("/{scope}/{item_id}/confirm", response_model=MemoryItem)
async def confirm_item(scope: str, item_id: str, request: Request) -> MemoryItem:
    store = get_store(request)
    try:
        return await store.update(scope, item_id, confirmed=True)
    except MemoryNotFound:
        raise HTTPException(status_code=404, detail=f"Memory item {item_id!r} not found in scope {scope!r}")


@router.post("/{scope}/{item_id}/reject", response_model=MemoryItem)
async def reject_item(scope: str, item_id: str, request: Request) -> MemoryItem:
    store = get_store(request)
    try:
        return await store.update(scope, item_id, confirmed=False)
    except MemoryNotFound:
        raise HTTPException(status_code=404, detail=f"Memory item {item_id!r} not found in scope {scope!r}")


@router.delete("/{scope}/{item_id}", status_code=204)
async def delete_item(scope: str, item_id: str, request: Request) -> None:
    store = get_store(request)
    try:
        await store.delete(scope, item_id)
    except MemoryNotFound:
        raise HTTPException(status_code=404, detail=f"Memory item {item_id!r} not found in scope {scope!r}")
