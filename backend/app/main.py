from __future__ import annotations

import asyncio
import logging
import os
import shutil
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Request, Response
from watchfiles import awatch

from .api.activity import router as activity_router
from .api.adoption import router as adoption_router
from .api.discovery import router as discovery_router
from .api.memory import router as memory_router
from .api.spaces import router as spaces_router
from .api.stats import router as stats_router
from .api.tasks import router as tasks_router
from .api.test_reports import router as test_reports_router
from .api.tools import router as tools_router
from .api.traces import router as traces_router
from .api.views import router as views_router
from .auth import require_auth
from .memory_store import MemoryStore
from .space_storage import CRONOS_SUBDIR, RESERVED_SPACE_DIRS, SpaceStore
from .stats_store import StatsStore
from .storage import TaskStore
from .test_report_store import TestReportStore
from .trace_store import TraceStore
from .worker_pool import WorkerPool

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
MEMORY_PRUNE_INTERVAL = int(os.environ.get("CRONOS_MEMORY_PRUNE_INTERVAL", "3600"))
DISCOVERY_INTERVAL_HOURS = float(os.environ.get("CRONOS_DISCOVERY_INTERVAL_HOURS", "6"))
DISCOVERY_DB_PATH = DATA_DIR / "cronos-index.db"
DISCOVERY_SOURCES_PATH = DATA_DIR / "tool_sources.yml"


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


async def memory_prune_loop(
    memory_store: MemoryStore,
    space_store: SpaceStore,
    stop_event: asyncio.Event,
) -> None:
    while not stop_event.is_set():
        try:
            scopes = ["global"] + [f"space:{s.id}" for s in space_store.list_all()]
            total = sum([await memory_store.prune_stale(scope) for scope in scopes])
            if total:
                log.info("Memory prune: archived %d stale item(s)", total)
        except Exception:
            log.exception("Error during memory prune sweep")
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=float(MEMORY_PRUNE_INTERVAL))
        except asyncio.TimeoutError:
            pass


async def discovery_refresh_loop(
    db_path: Path,
    sources_path: Path,
    interval_hours: float,
    stop_event: asyncio.Event,
    *,
    task_store: "TaskStore | None" = None,
    spaces_dir: "Path | None" = None,
) -> None:
    from .api.discovery import run_refresh_if_unlocked

    while not stop_event.is_set():
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=interval_hours * 3600)
        except asyncio.TimeoutError:
            pass
        if stop_event.is_set():
            break
        try:
            result = await run_refresh_if_unlocked(
                db_path,
                sources_path,
                task_store=task_store,
                spaces_dir=spaces_dir,
            )
            if result is not None:
                log.info(
                    "Periodic discovery refresh: %d source(s), %d item(s)",
                    result["refreshed"],
                    len(result["items"]),
                )
            else:
                log.debug("Periodic discovery refresh: skipped (locked or recent)")
        except Exception:
            log.exception("Error during periodic discovery refresh; will retry next cycle")


async def watch_spaces_dir(
    task_store: TaskStore,
    space_store: SpaceStore,
    stop_event: asyncio.Event,
) -> None:
    import time
    from .tools.adoption import NotAdopted, recompute_local_sha

    log.info("Watching %s for task & space changes", SPACES_DIR)
    _sha_throttle: dict[tuple[str, str, str], float] = {}
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
            if (
                len(rel.parts) >= 6
                and rel.parts[2] == "tools"
                and path.name != "manifest.yml"
            ):
                space_id = rel.parts[0]
                kind = rel.parts[3]
                name = rel.parts[4]
                key = (space_id, kind, name)
                now = time.monotonic()
                if now - _sha_throttle.get(key, 0.0) >= 1.0:
                    _sha_throttle[key] = now
                    try:
                        recompute_local_sha(space_id, kind, name)
                    except NotAdopted:
                        pass
                    except Exception:
                        log.exception(
                            "Error recomputing local_sha for %s/%s in space %s",
                            kind, name, space_id,
                        )
            elif path.suffix == ".md":
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

    stats_store = StatsStore(SPACES_DIR)
    app.state.stats_store = stats_store

    trace_store = TraceStore(SPACES_DIR)
    app.state.trace_store = trace_store

    test_report_store = TestReportStore(SPACES_DIR)
    app.state.test_report_store = test_report_store

    memory_store = MemoryStore(DATA_DIR, SPACES_DIR)
    app.state.memory_store = memory_store

    app.state.discovery_db_path = DISCOVERY_DB_PATH
    app.state.discovery_sources_path = DISCOVERY_SOURCES_PATH

    worker_pool = WorkerPool(task_store, space_store, stats_store=stats_store, trace_store=trace_store, memory_store=memory_store)
    for space in space_store.list_all():
        await worker_pool.start_for_space(space.id)
    app.state.worker_pool = worker_pool

    stop_event = asyncio.Event()
    watcher = asyncio.create_task(
        watch_spaces_dir(task_store, space_store, stop_event),
        name="watcher",
    )
    archiver = asyncio.create_task(
        auto_archive_loop(task_store, ARCHIVE_AFTER_DAYS, stop_event),
        name="archiver",
    )
    memory_pruner = asyncio.create_task(
        memory_prune_loop(memory_store, space_store, stop_event),
        name="memory_pruner",
    )
    discoverer = asyncio.create_task(
        discovery_refresh_loop(
            DISCOVERY_DB_PATH,
            DISCOVERY_SOURCES_PATH,
            DISCOVERY_INTERVAL_HOURS,
            stop_event,
            task_store=task_store,
            spaces_dir=SPACES_DIR,
        ),
        name="discoverer",
    )

    # Recover in-flight runs: any task left in ACTIVE on startup gets
    # re-enqueued on its space's worker. The agent resumes via its stored
    # claude_session_id if any.
    board = task_store.board()
    for summary in board.active:
        worker = worker_pool.get(summary.space_id)
        if worker is None:
            log.warning(
                "Skipping resume of task %s: no worker for space %s",
                summary.id, summary.space_id,
            )
            continue
        log.info("Resuming task left in active state: %s", summary.id)
        await worker.enqueue(summary.id)

    try:
        yield
    finally:
        stop_event.set()
        await worker_pool.stop_all()
        for bg_task in (watcher, archiver, memory_pruner, discoverer):
            try:
                await asyncio.wait_for(bg_task, timeout=5.0)
            except asyncio.TimeoutError:
                bg_task.cancel()


_auth = [Depends(require_auth)]

app = FastAPI(title="Cronos", version="0.0.1", lifespan=lifespan)
app.include_router(tasks_router, dependencies=_auth)
app.include_router(spaces_router, dependencies=_auth)
app.include_router(views_router, dependencies=_auth)
app.include_router(activity_router, dependencies=_auth)
app.include_router(tools_router, dependencies=_auth)
app.include_router(adoption_router, dependencies=_auth)
app.include_router(stats_router, dependencies=_auth)
app.include_router(traces_router, dependencies=_auth)
app.include_router(test_reports_router, dependencies=_auth)
app.include_router(memory_router, dependencies=_auth)
app.include_router(discovery_router, dependencies=_auth)


@app.get("/api/info")
async def info() -> dict[str, object]:
    """Return build metadata baked into the container image.

    All three fields are ``None`` in local dev and CI where the ``BUILD_*``
    environment variables are not set.  ``os.environ.get`` (not
    ``os.environ[...]``) is used deliberately so missing vars never raise.

    NOTE: this endpoint is protected by HTTP Basic Auth via Caddy like all
    other ``/api/*`` routes; do not relax the auth in front of it — the
    commit SHA could be used to fingerprint deployed versions against a
    public GitHub repository.
    """
    return {
        "commit_sha": os.environ.get("BUILD_COMMIT"),
        "build_time": os.environ.get("BUILD_TIME"),
        "repo_url": os.environ.get("BUILD_REPO_URL"),
    }


@app.get("/api/health")
async def health(request: Request, response: Response) -> dict[str, object]:
    """Liveness + light readiness check.

    Returns 200 only when the spaces dir exists, the in-memory indexes loaded,
    and every per-space worker loop is alive.
    """
    pool: WorkerPool | None = getattr(request.app.state, "worker_pool", None)
    store: TaskStore | None = getattr(request.app.state, "store", None)
    space_store: SpaceStore | None = getattr(request.app.state, "space_store", None)

    spaces_dir_ok = SPACES_DIR.is_dir()
    claude_on_path = shutil.which("claude") is not None
    workers_info: list[dict[str, object]] = []
    all_alive = True
    if pool is not None:
        for space_id, worker in pool.items():
            alive = worker.is_alive()
            all_alive = all_alive and alive
            workers_info.append({
                "space_id": space_id,
                "alive": alive,
                "current_task": worker.current(),
            })
    workers_running = pool is not None and all_alive
    index_loaded = store is not None and space_store is not None
    tasks_indexed = store.count() if store is not None else None
    spaces_indexed = space_store.count() if space_store is not None else None

    ok = spaces_dir_ok and workers_running and index_loaded
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
        "workers_running": workers_running,
        "workers": workers_info,
    }
