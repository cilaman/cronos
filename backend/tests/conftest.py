from __future__ import annotations

import pytest
import httpx

from app.main import app
from app.space_storage import SpaceStore
from app.stats_store import StatsStore
from app.storage import TaskStore
from app.test_report_store import TestReportStore
from app.trace_store import TraceStore

SPACE_ID = "test-space"


@pytest.fixture
def tmp_spaces_dir(tmp_path):
    return tmp_path / "spaces"


@pytest.fixture
async def space_store(tmp_spaces_dir):
    store = SpaceStore(tmp_spaces_dir)
    await store.create(
        name="Test Space",
        color="#15803D",
        icon=None,
        description="Test space for pytest",
        space_id=SPACE_ID,
    )
    return store


@pytest.fixture
async def task_store(tmp_spaces_dir, space_store):
    store = TaskStore(tmp_spaces_dir)
    await store.reload_all()
    return store


class _MockWorker:
    async def enqueue(self, task_id: str, **kwargs) -> None:
        pass

    def stop_current(self, task_id: str) -> bool:
        return False

    def is_alive(self) -> bool:
        return True

    def current(self) -> str | None:
        return None


class _MockWorkerPool:
    def get(self, space_id: str) -> _MockWorker:
        return _MockWorker()

    async def start_for_space(self, space_id: str) -> _MockWorker:
        return _MockWorker()

    async def stop_for_space(self, space_id: str) -> None:
        pass

    def items(self) -> list:
        return []


@pytest.fixture
async def async_client(task_store, space_store, tmp_spaces_dir):
    app.state.store = task_store
    app.state.space_store = space_store
    app.state.stats_store = StatsStore(tmp_spaces_dir)
    app.state.trace_store = TraceStore(tmp_spaces_dir)
    app.state.test_report_store = TestReportStore(tmp_spaces_dir)
    app.state.worker_pool = _MockWorkerPool()

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
