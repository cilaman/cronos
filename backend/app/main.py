from __future__ import annotations

import asyncio
import logging
import os
import shutil
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, Response
from watchfiles import awatch

from .api.activity import router as activity_router
from .api.spaces import router as spaces_router
from .api.tasks import router as tasks_router
from .space_storage import CRONOS_SUBDIR, RESERVED_SPACE_DIRS, SpaceStore
from .storage import TaskStore
from .worker import Worker

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("cronos")

DATA_DIR = Path(os.environ.get("CRONOS_DATA_DIR", "/data"))
SPACES_DIR = DATA_DIR / "spaces"
LEGACY_TASKS_DIR = DATA_DIR / "tasks"
LEGACY_WORKSPACES_DIR = DATA_DIR / "workspaces"
ARCHIVE_AFTER_DAYS = int(os.environ.get("CRONOS_ARCHIVE_AFTER_DAYS", "7"))


def _path_is_reserved(path: Path, root: Path) -> bool:
    try:
        rel = path.relative_to(root)
    except ValueError:
        return True
    return any(part in RESERVED_SPACE_DIRS for part in rel.parts)


async def auto_archive_loop(
    task_store: TaskStore,
    days: int,
    stop_event: asyncio.Event,
) -> None:
    while not stop_event.is_set():
        try:
            n = await task_store.archive_stale_done_tasks(days)
            if n:
                log.info("Auto-archived %d stale done task(s) (threshold: %d days)", n, days)
        except Exception:
            log.exception("Error during auto-archive sweep")
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=3600.0)
        except asyncio.TimeoutError:
            pass


async def watch_spaces_dir(
    task_store: TaskStore,
    space_store: SpaceStore,
    stop_event: asyncio.Event,
) -> None:
    log.info("Watching %s for task & space changes", SPACES_DIR)
    async for changes in awatch(SPACES_DIR, stop_event=stop_event):
        for _change, raw_path in changes:
            path = Path(raw_path)
            if _path_is_reserved(path, SPACES_DIR):
                continue
            # Only react to events inside `.cronos/` — repo files are not
            # Cronos state and should not trigger reindex churn.
            try:
                rel = path.relative_to(SPACES_DIR)
            except ValueError:
                continue
            if len(rel.parts) < 2 or rel.parts[1] != CRONOS_SUBDIR:
                continue
            if path.suffix == ".md":
                await task_store.reindex_path(path)
            elif path.name == "space.yml":
                await space_store.reindex_path(path)


def _migrate_legacy_spaces() -> None:
    """Move any pre-`.cronos/` spaces aside on startup.

    Cronos now expects `{spaces_dir}/{id}/.cronos/space.yml`. Earlier
    versions stored everything at `{spaces_dir}/{id}/` directly. Per the
    upgrade plan (user chose "delete old spaces"), we soft-delete legacy
    spaces by moving them under `.trash/{id}.legacy-{stamp}/` so nothing
    is destroyed silently.
    """
    if not SPACES_DIR.exists():
        return
    trash = SPACES_DIR / ".trash"
    stamp = None
    for child in sorted(SPACES_DIR.iterdir()):
        if not child.is_dir() or child.name in RESERVED_SPACE_DIRS:
            continue
        if (child / CRONOS_SUBDIR / "space.yml").exists():
            continue
        if not (child / "space.yml").exists():
            continue  # not a legacy space, skip
        trash.mkdir(parents=True, exist_ok=True)
        from datetime import UTC, datetime
        stamp = stamp or datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%SZ")
        dest = trash / f"{child.name}.legacy-{stamp}"
        log.warning(
            "Migrating legacy-layout space %s -> %s (data preserved in .trash; "
            "create a fresh space to continue)",
            child.name, dest,
        )
        os.replace(child, dest)


@asynccontextmanager
async def lifespan(app: FastAPI):
    SPACES_DIR.mkdir(parents=True, exist_ok=True)

    if LEGACY_TASKS_DIR.exists() or LEGACY_WORKSPACES_DIR.exists():
        log.warning(
            "Legacy /data/tasks or /data/workspaces directories exist. They are "
            "ignored by Cronos now that tasks live under /data/spaces/{id}/.cronos/. "
            "Remove them once you've confirmed no data is needed."
        )

    _migrate_legacy_spaces()

    space_store = SpaceStore(SPACES_DIR)
    await space_store.reload_all()
    if space_store.count() == 0:
        await space_store.create(
            name="Personal",
            color="#15803D",
            icon=None,
            description="Default space — created automatically on first launch.",
            space_id="personal",
        )
        log.info("Bootstrapped default 'personal' space")
    app.state.space_store = space_store

    task_store = TaskStore(SPACES_DIR)
    await task_store.reload_all()
    app.state.store = task_store

    worker = Worker(task_store, space_store=space_store)
    worker.start()
    app.state.worker = worker

    stop_event = asyncio.Event()
    watcher = asyncio.create_task(
        watch_spaces_dir(task_store, space_store, stop_event),
        name="watcher",
    )
    archiver = asyncio.create_task(
        auto_archive_loop(task_store, ARCHIVE_AFTER_DAYS, stop_event),
        name="archiver",
    )

    # Recover in-flight runs: any task left in ACTIVE on startup gets
    # re-enqueued. The agent resumes via its stored claude_session_id if any.
    board = task_store.board()
    for summary in board.active:
        log.info("Resuming task left in active state: %s", summary.id)
        await worker.enqueue(summary.id)

    try:
        yield
    finally:
        stop_event.set()
        await worker.stop()
        for bg_task in (watcher, archiver):
            try:
                await asyncio.wait_for(bg_task, timeout=5.0)
            except asyncio.TimeoutError:
                bg_task.cancel()


app = FastAPI(title="Cronos", version="0.0.1", lifespan=lifespan)
app.include_router(tasks_router)
app.include_router(spaces_router)
app.include_router(activity_router)


@app.get("/api/health")
async def health(request: Request, response: Response) -> dict[str, object]:
    """Liveness + light readiness check.

    Returns 200 only when the spaces dir exists, the in-memory indexes loaded,
    and the worker loop is alive.
    """
    worker: Worker | None = getattr(request.app.state, "worker", None)
    store: TaskStore | None = getattr(request.app.state, "store", None)
    space_store: SpaceStore | None = getattr(request.app.state, "space_store", None)

    spaces_dir_ok = SPACES_DIR.is_dir()
    claude_on_path = shutil.which("claude") is not None
    worker_alive = worker is not None and worker.is_alive()
    index_loaded = store is not None and space_store is not None
    tasks_indexed = store.count() if store is not None else None
    spaces_indexed = space_store.count() if space_store is not None else None

    ok = spaces_dir_ok and worker_alive and index_loaded
    if not ok:
        response.status_code = 503

    return {
        "ok": ok,
        "data_dir": str(DATA_DIR),
        "spaces_dir_exists": spaces_dir_ok,
        "claude_on_path": claude_on_path,
        "index_loaded": index_loaded,
        "tasks_indexed": tasks_indexed,
        "spaces_indexed": spaces_indexed,
        "worker_running": worker_alive,
        "current_task": worker.current() if worker else None,
    }
