from __future__ import annotations

import io
import logging
import os
import secrets
import shutil
import zipfile
from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, Request, Response, UploadFile, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from ..models import (
    Space,
    SpaceSummary,
    SpacesResponse,
    TaskState,
)
from ..space_storage import (
    SpaceError,
    SpaceExists,
    SpaceNotFound,
    SpaceRepoConflict,
    SpaceStore,
    dump_space,
    parse_space_yaml,
    validate_color,
    validate_space_id,
)
from ..storage import TaskStore, slugify
from ..worker_pool import WorkerPool

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/spaces", tags=["spaces"])

# 200 MB cap on uncompressed import size to guard against zip-bombs.
MAX_IMPORT_UNCOMPRESSED_BYTES = 200 * 1024 * 1024


def get_space_store(request: Request) -> SpaceStore:
    return request.app.state.space_store


def get_task_store(request: Request) -> TaskStore:
    return request.app.state.store


def get_pool(request: Request) -> WorkerPool:
    return request.app.state.worker_pool


class CreateSpaceBody(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    color: str = Field(min_length=7, max_length=7)
    icon: str | None = Field(default=None, max_length=8)
    description: str = Field(default="", max_length=2000)
    space_id: str | None = Field(default=None, max_length=64)
    # Optional repo binding on creation. If `repo_url` is set, `branch` is
    # required; Cronos clones the repo into the new space dir.
    repo_url: str | None = Field(default=None, max_length=2048)
    branch: str | None = Field(default=None, max_length=200)
    share_cronos: bool = False


class UpdateSpaceBody(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    color: str | None = Field(default=None, min_length=7, max_length=7)
    icon: str | None = Field(default=None, max_length=8)
    clear_icon: bool = False
    description: str | None = Field(default=None, max_length=2000)


class LinkRepoBody(BaseModel):
    repo_url: str = Field(min_length=1, max_length=2048)
    branch: str = Field(min_length=1, max_length=200)
    share_cronos: bool = False


def _summarize_space(
    space: Space,
    counts: dict[TaskState, int] | None,
    last_activity: datetime | None,
) -> SpaceSummary:
    bucket = counts or {s: 0 for s in TaskState}
    # Ensure all TaskState keys are present even if no tasks exist yet.
    for s in TaskState:
        bucket.setdefault(s, 0)
    return SpaceSummary(
        id=space.id,
        name=space.name,
        color=space.color,
        icon=space.icon,
        task_counts=bucket,
        last_activity_at=last_activity,
    )


@router.get("", response_model=SpacesResponse)
async def list_spaces(request: Request) -> SpacesResponse:
    space_store = get_space_store(request)
    task_store = get_task_store(request)
    counts = task_store.counts_by_space()
    last_activity = task_store.last_activity_by_space()
    summaries = [
        _summarize_space(s, counts.get(s.id), last_activity.get(s.id))
        for s in space_store.list_all()
    ]
    totals: dict[TaskState, int] = {s: 0 for s in TaskState}
    for task in task_store.all():
        totals[task.state] = totals.get(task.state, 0) + 1
    return SpacesResponse(spaces=summaries, totals=totals)


@router.get("/{space_id}", response_model=Space)
async def get_space(space_id: str, request: Request) -> Space:
    space = get_space_store(request).get(space_id)
    if space is None:
        raise HTTPException(status_code=404, detail=f"Space {space_id} not found")
    return space


@router.post("", response_model=Space, status_code=status.HTTP_201_CREATED)
async def create_space(body: CreateSpaceBody, request: Request) -> Space:
    if body.repo_url and not body.branch:
        raise HTTPException(
            status_code=400,
            detail="branch is required when repo_url is provided",
        )
    try:
        space = await get_space_store(request).create(
            name=body.name,
            color=body.color,
            icon=body.icon,
            description=body.description,
            space_id=body.space_id,
            repo_url=body.repo_url,
            branch=body.branch,
            share_cronos=body.share_cronos,
        )
    except SpaceExists as e:
        raise HTTPException(status_code=409, detail=f"Space {e} already exists") from None
    except SpaceRepoConflict as e:
        raise HTTPException(status_code=409, detail=str(e)) from None
    except SpaceError as e:
        raise HTTPException(status_code=400, detail=str(e)) from None
    await get_pool(request).start_for_space(space.id)
    return space


@router.post("/{space_id}/link", response_model=Space)
async def link_space_repo(
    space_id: str, body: LinkRepoBody, request: Request
) -> Space:
    try:
        return await get_space_store(request).link_repo(
            space_id,
            repo_url=body.repo_url,
            branch=body.branch,
            share_cronos=body.share_cronos,
        )
    except SpaceNotFound:
        raise HTTPException(status_code=404, detail=f"Space {space_id} not found") from None
    except SpaceRepoConflict as e:
        raise HTTPException(status_code=409, detail=str(e)) from None
    except SpaceError as e:
        raise HTTPException(status_code=400, detail=str(e)) from None


@router.post("/{space_id}/unlink", response_model=Space)
async def unlink_space_repo(space_id: str, request: Request) -> Space:
    try:
        return await get_space_store(request).unlink_repo(space_id)
    except SpaceNotFound:
        raise HTTPException(status_code=404, detail=f"Space {space_id} not found") from None
    except SpaceError as e:
        raise HTTPException(status_code=400, detail=str(e)) from None


@router.patch("/{space_id}", response_model=Space)
async def update_space(space_id: str, body: UpdateSpaceBody, request: Request) -> Space:
    if (
        body.name is None
        and body.color is None
        and body.icon is None
        and not body.clear_icon
        and body.description is None
    ):
        raise HTTPException(status_code=400, detail="No fields to update")
    try:
        return await get_space_store(request).update(
            space_id,
            name=body.name,
            color=body.color,
            icon=body.icon,
            description=body.description,
            clear_icon=body.clear_icon,
        )
    except SpaceNotFound:
        raise HTTPException(status_code=404, detail=f"Space {space_id} not found") from None
    except SpaceError as e:
        raise HTTPException(status_code=400, detail=str(e)) from None


@router.delete("/{space_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_space(
    space_id: str,
    request: Request,
    cascade: bool = Query(default=False, description="Delete even when tasks exist."),
) -> Response:
    space_store = get_space_store(request)
    task_store = get_task_store(request)
    pool = get_pool(request)
    if space_store.get(space_id) is None:
        raise HTTPException(status_code=404, detail=f"Space {space_id} not found")
    if task_store.count(space_id) > 0 and not cascade:
        raise HTTPException(
            status_code=409,
            detail="Space has tasks; pass ?cascade=true to delete anyway",
        )
    # Stop the worker BEFORE removing on-disk state so an in-flight task
    # can't write into a directory we're about to move to .trash/.
    await pool.stop_for_space(space_id)
    try:
        await space_store.delete(space_id)
    except SpaceNotFound:
        raise HTTPException(status_code=404, detail=f"Space {space_id} not found") from None
    await task_store.drop_space(space_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------- export ----------


@router.get("/{space_id}/export")
async def export_space(space_id: str, request: Request) -> StreamingResponse:
    space_store = get_space_store(request)
    space = space_store.get(space_id)
    if space is None:
        raise HTTPException(status_code=404, detail=f"Space {space_id} not found")

    space_dir = space_store.space_dir(space_id)
    cronos_dir = space_store.cronos_dir(space_id)

    def gen() -> bytes:
        # Only the `.cronos/` subtree is portable. Repo files & `.git/` are
        # reconstituted on the destination by re-linking the repo, and
        # per-task worktrees are recreated lazily — so skip both. We also
        # skip `.cronos/workspaces/` (worktrees) and `.cronos/.trash/`.
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
            for root, dirs, files in os.walk(cronos_dir):
                root_path = Path(root)
                # Skip workspaces (per-task worktrees) and per-space trash.
                rel_root = root_path.relative_to(cronos_dir)
                if rel_root.parts and rel_root.parts[0] in ("workspaces", ".trash"):
                    dirs.clear()
                    continue
                for name in files:
                    file_path = root_path / name
                    arcname = (
                        Path(space_dir.name) / ".cronos" / file_path.relative_to(cronos_dir)
                    )
                    zf.write(file_path, arcname.as_posix())
        return buf.getvalue()

    data = gen()
    return StreamingResponse(
        iter([data]),
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{space_id}.zip"',
            "Content-Length": str(len(data)),
        },
    )


# ---------- import ----------


def _safe_extract(zf: zipfile.ZipFile, dest_root: Path) -> str:
    """Validate the ZIP, extract into `dest_root/{incoming_id}/`, return incoming_id."""
    # First pass: validate, detect single top-level dir, enforce size cap.
    total = 0
    top_level: set[str] = set()
    entries = []
    for info in zf.infolist():
        name = info.filename
        if "\\" in name or name.startswith("/") or ".." in Path(name).parts:
            raise SpaceError(f"Unsafe entry in ZIP: {name!r}")
        normalized = os.path.normpath(name).replace(os.sep, "/")
        if normalized.startswith("..") or normalized.startswith("/"):
            raise SpaceError(f"Unsafe entry in ZIP: {name!r}")
        if normalized in ("", ".") or info.is_dir():
            continue
        total += info.file_size
        if total > MAX_IMPORT_UNCOMPRESSED_BYTES:
            raise SpaceError("Uncompressed size exceeds 200 MB cap")
        parts = Path(normalized).parts
        if not parts:
            raise SpaceError(f"Empty entry path in ZIP")
        top_level.add(parts[0])
        entries.append((info, normalized))

    if len(top_level) != 1:
        raise SpaceError(
            f"ZIP must contain exactly one top-level directory; found {sorted(top_level)}"
        )
    incoming_id = next(iter(top_level))

    has_space_yml = any(p == f"{incoming_id}/.cronos/space.yml" for _, p in entries)
    if not has_space_yml:
        raise SpaceError(f"ZIP is missing {incoming_id}/.cronos/space.yml")

    # Validate allowed subtrees: only `.cronos/{space.yml,tasks/}`. Repo
    # files and worktrees are not portable across hosts.
    for _info, normalized in entries:
        rel = normalized[len(incoming_id) + 1 :] if normalized != incoming_id else ""
        if rel == "":
            continue
        first = rel.split("/", 1)[0]
        if first != ".cronos":
            raise SpaceError(f"Disallowed path inside ZIP: {normalized!r}")
        # `.cronos/{space.yml,tasks/...}` only.
        sub = rel[len(".cronos/") :] if rel.startswith(".cronos/") else ""
        if not sub:
            continue
        sub_first = sub.split("/", 1)[0]
        if sub_first not in ("space.yml", "tasks"):
            raise SpaceError(f"Disallowed path inside ZIP: {normalized!r}")

    # Extract.
    out_dir = dest_root / incoming_id
    if out_dir.exists():
        shutil.rmtree(out_dir)
    for info, normalized in entries:
        target = dest_root / normalized
        target.parent.mkdir(parents=True, exist_ok=True)
        with zf.open(info) as src, open(target, "wb") as dst:
            shutil.copyfileobj(src, dst)

    return incoming_id


@router.post("/import", response_model=Space, status_code=status.HTTP_201_CREATED)
async def import_space(
    request: Request,
    file: UploadFile,
    rename_to: str | None = Query(default=None, max_length=64),
) -> Space:
    space_store = get_space_store(request)
    task_store = get_task_store(request)
    space_store.ensure_dirs()
    imports = space_store.free_imports_dir()

    # Stream upload to disk.
    upload_path = imports / f"upload-{secrets.token_hex(4)}.zip"
    try:
        with open(upload_path, "wb") as fh:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                fh.write(chunk)

        staging = imports / f"staging-{secrets.token_hex(4)}"
        staging.mkdir(parents=True, exist_ok=True)
        try:
            with zipfile.ZipFile(upload_path, "r") as zf:
                try:
                    incoming_id = _safe_extract(zf, staging)
                except SpaceError as e:
                    raise HTTPException(status_code=400, detail=str(e)) from None

            staged_dir = staging / incoming_id
            final_id = rename_to or incoming_id
            try:
                validate_space_id(final_id)
            except SpaceError as e:
                raise HTTPException(status_code=400, detail=str(e)) from None

            # Validate space.yml parses with the final id.
            yml = staged_dir / ".cronos" / "space.yml"
            try:
                # parse_space_yaml derives id from parent dir name, so use a temp
                # rename to validate; we'll rewrite the file post-rename below.
                temp_id_for_parse = staged_dir.name
                _ = parse_space_yaml(yml)  # validates without renaming
                del temp_id_for_parse
            except SpaceError as e:
                raise HTTPException(status_code=400, detail=str(e)) from None

            final_dir = space_store.spaces_dir / final_id
            if final_dir.exists() or space_store.exists(final_id):
                suggested = f"{final_id}-{secrets.token_hex(2)}"
                raise HTTPException(
                    status_code=409,
                    detail={
                        "message": f"Space {final_id} already exists",
                        "suggested_id": suggested,
                    },
                )

            # If renamed, rewrite space.yml with the new id and bump updated_at.
            if final_id != incoming_id:
                parsed = parse_space_yaml(yml)
                rewritten = parsed.model_copy(
                    update={"id": final_id, "updated_at": datetime.now(tz=UTC)}
                )
                yml.write_text(dump_space(rewritten), encoding="utf-8")
                renamed = staging / final_id
                os.replace(staged_dir, renamed)
                staged_dir = renamed

            # Move into place atomically.
            os.replace(staged_dir, final_dir)
        finally:
            if staging.exists():
                shutil.rmtree(staging, ignore_errors=True)
    finally:
        if upload_path.exists():
            try:
                upload_path.unlink()
            except OSError:
                pass

    # Refresh in-memory indexes (don't rely on watcher).
    await space_store.reload_all()
    await task_store.reload_all()

    imported = space_store.get(final_id)
    if imported is None:
        raise HTTPException(status_code=500, detail="Import succeeded on disk but space did not load")
    await get_pool(request).start_for_space(imported.id)
    return imported
