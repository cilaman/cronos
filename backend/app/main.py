from __future__ import annotations

import asyncio
import logging
import os
import shutil
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, Response
from watchfiles import awatch

from .api.tasks import router as tasks_router
from .storage import TaskStore
from .worker import Worker

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("cronos")

DATA_DIR = Path(os.environ.get("CRONOS_DATA_DIR", "/data"))
TASKS_DIR = DATA_DIR / "tasks"
WORKSPACES_DIR = DATA_DIR / "workspaces"


async def watch_tasks_dir(store: TaskStore, stop_event: asyncio.Event) -> None:
    log.info("Watching %s for task changes", store.tasks_dir)
    async for changes in awatch(store.tasks_dir, stop_event=stop_event):
        for _change, raw_path in changes:
            path = Path(raw_path)
            if path.suffix != ".md":
                continue
            await store.reindex_path(path)


@asynccontextmanager
async def lifespan(app: FastAPI):
    TASKS_DIR.mkdir(parents=True, exist_ok=True)
    WORKSPACES_DIR.mkdir(parents=True, exist_ok=True)

    store = TaskStore(TASKS_DIR)
    await store.reload_all()
    app.state.store = store

    worker = Worker(store)
    worker.start()
    app.state.worker = worker

    stop_event = asyncio.Event()
    watcher = asyncio.create_task(watch_tasks_dir(store, stop_event), name="watcher")

    # Recover in-flight runs: any task left in ACTIVE on startup gets
    # re-enqueued. The agent resumes via its stored claude_session_id if any.
    board = store.board()
    for summary in board.active:
        log.info("Resuming task left in active state: %s", summary.id)
        await worker.enqueue(summary.id)

    try:
        yield
    finally:
        stop_event.set()
        await worker.stop()
        try:
            await asyncio.wait_for(watcher, timeout=5.0)
        except asyncio.TimeoutError:
            watcher.cancel()


app = FastAPI(title="Cronos", version="0.0.1", lifespan=lifespan)
app.include_router(tasks_router)


@app.get("/api/health")
async def health(request: Request, response: Response) -> dict[str, object]:
    """Liveness + light readiness check.

    Returns 200 only when the dirs exist, the in-memory task index loaded,
    and the worker loop is alive. The Docker healthcheck and any external
    monitoring should treat a non-200 here as "restart me".
    """
    worker: Worker | None = getattr(request.app.state, "worker", None)
    store: TaskStore | None = getattr(request.app.state, "store", None)

    tasks_dir_ok = TASKS_DIR.is_dir()
    workspaces_dir_ok = WORKSPACES_DIR.is_dir()
    claude_on_path = shutil.which("claude") is not None
    worker_alive = worker is not None and worker.is_alive()
    index_loaded = store is not None
    tasks_indexed = store.count() if store is not None else None

    ok = tasks_dir_ok and workspaces_dir_ok and worker_alive and index_loaded
    if not ok:
        response.status_code = 503

    return {
        "ok": ok,
        "data_dir": str(DATA_DIR),
        "tasks_dir_exists": tasks_dir_ok,
        "workspaces_dir_exists": workspaces_dir_ok,
        "claude_on_path": claude_on_path,
        "index_loaded": index_loaded,
        "tasks_indexed": tasks_indexed,
        "worker_running": worker_alive,
        "current_task": worker.current() if worker else None,
    }
