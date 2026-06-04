"""
Tests for the POST /api/spaces/{space_id}/harnesses/{name}/webhook endpoint.

Covers:
  - Valid webhook call with correct token → 202 with run_ids
  - Missing Authorization header → 401
  - Wrong token → 401
  - Harness not found → 404
  - No webhook trigger node in harness → 404
  - Token shorter than 16 chars logs a warning (once-per-process)
  - Identical payloads within debounce window return empty run_ids (dedup)

The test app is isolated from main.py: we mount only the harnesses router,
wire the required app.state attributes, and mock fan_out_to_harnesses to
control run_ids without touching the real enqueue pipeline.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from fastapi import Depends, FastAPI

from app.api.harnesses import router as harnesses_router
from app.auth import require_auth
from app.harnesses import HarnessStore
from app.harnesses.model import HarnessNode, NodeType, Position
from app.space_storage import SpaceStore
from app.storage import TaskStore

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SPACE_ID = "test-space"
HARNESS_NAME = "My Webhook Flow"
_BASE_URL = f"/api/spaces/{SPACE_ID}/harnesses"
_WEBHOOK_URL = f"{_BASE_URL}/{HARNESS_NAME}/webhook"

VALID_TOKEN = "super-secret-token-32chars-long!!"
SHORT_TOKEN = "short"


# ---------------------------------------------------------------------------
# Helper — build the minimal harness payload with a webhook trigger node
# ---------------------------------------------------------------------------


def _webhook_node(auth_token: str = VALID_TOKEN, webhook_path: str = "my-hook") -> dict:
    """Return a trigger node dict for a webhook trigger."""
    return {
        "id": "trig-1",
        "type": "trigger",
        "position": {"x": 0.0, "y": 0.0},
        "ports": {},
        "label": "Webhook trigger",
        "data": {
            "kind": "webhook",
            "auth_token": auth_token,
            "webhook_path": webhook_path,
        },
    }


def _harness_payload(auth_token: str = VALID_TOKEN) -> dict:
    """Return a minimal harness CREATE body with one webhook trigger node."""
    return {
        "name": HARNESS_NAME,
        "description": "Webhook-triggered flow",
        "nodes": [_webhook_node(auth_token=auth_token)],
        "edges": [],
    }


def _harness_payload_no_trigger() -> dict:
    """Return a harness CREATE body with NO trigger node."""
    return {
        "name": HARNESS_NAME,
        "description": "No trigger",
        "nodes": [
            {
                "id": "agent-1",
                "type": "agent",
                "position": {"x": 0.0, "y": 0.0},
                "ports": {},
                "label": "Agent",
            }
        ],
        "edges": [],
    }


# ---------------------------------------------------------------------------
# Isolated test app factory
# ---------------------------------------------------------------------------


def _make_app(
    space_store: SpaceStore,
    harness_store: HarnessStore,
    task_store: object | None = None,
    worker_pool: object | None = None,
) -> FastAPI:
    """Create a minimal FastAPI app with only the harnesses router."""
    _app = FastAPI()
    _app.include_router(harnesses_router)
    _app.state.space_store = space_store
    _app.state.harness_store = harness_store
    _app.state.store = task_store or MagicMock()
    _app.state.worker_pool = worker_pool or MagicMock()
    return _app


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def space_store(tmp_path: Path) -> SpaceStore:
    store = SpaceStore(tmp_path / "spaces")
    await store.create(
        name="Test Space",
        color="#15803D",
        space_id=SPACE_ID,
    )
    return store


@pytest.fixture
def harness_store() -> HarnessStore:
    return HarnessStore()


@pytest.fixture
def mock_task_store() -> MagicMock:
    """Minimal TaskStore mock that supports task creation and transition."""
    ts = MagicMock()
    fake_task = MagicMock()
    fake_task.id = "run-task-001"
    ts.create = AsyncMock(return_value=fake_task)
    ts.transition = AsyncMock(return_value=fake_task)
    return ts


@pytest.fixture
def mock_worker_pool() -> MagicMock:
    """Minimal WorkerPool mock."""
    mock_worker = MagicMock()
    mock_worker.register_run = MagicMock()
    mock_worker.enqueue = AsyncMock()
    mock_worker.lookup_space_id = MagicMock(return_value=None)

    pool = MagicMock()
    pool.get = MagicMock(return_value=mock_worker)
    return pool


@pytest.fixture
async def client_with_harness(
    space_store: SpaceStore,
    harness_store: HarnessStore,
    mock_task_store: MagicMock,
    mock_worker_pool: MagicMock,
) -> httpx.AsyncClient:
    """AsyncClient with a test app that already has the webhook harness created."""
    _app = _make_app(space_store, harness_store, mock_task_store, mock_worker_pool)
    transport = httpx.ASGITransport(app=_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        # Create the harness
        resp = await c.post(_BASE_URL, json=_harness_payload())
        assert resp.status_code == 201, f"Setup failed: {resp.text}"
        yield c


@pytest.fixture
async def client_no_trigger(
    space_store: SpaceStore,
    harness_store: HarnessStore,
    mock_task_store: MagicMock,
    mock_worker_pool: MagicMock,
) -> httpx.AsyncClient:
    """AsyncClient with a test app that has a harness with NO trigger node."""
    _app = _make_app(space_store, harness_store, mock_task_store, mock_worker_pool)
    transport = httpx.ASGITransport(app=_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.post(_BASE_URL, json=_harness_payload_no_trigger())
        assert resp.status_code == 201, f"Setup failed: {resp.text}"
        yield c


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _bearer(token: str = VALID_TOKEN) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ===========================================================================
# Tests: authentication
# ===========================================================================


async def test_missing_auth_header_returns_401(client_with_harness: httpx.AsyncClient) -> None:
    """No Authorization header → 401."""
    resp = await client_with_harness.post(_WEBHOOK_URL, content=b"{}")
    assert resp.status_code == 401


async def test_wrong_token_returns_401(client_with_harness: httpx.AsyncClient) -> None:
    """Wrong Bearer token → 401."""
    resp = await client_with_harness.post(
        _WEBHOOK_URL,
        headers={"Authorization": "Bearer wrong-token"},
        content=b"{}",
    )
    assert resp.status_code == 401


async def test_malformed_auth_scheme_returns_401(client_with_harness: httpx.AsyncClient) -> None:
    """Basic auth (not Bearer) → 401."""
    resp = await client_with_harness.post(
        _WEBHOOK_URL,
        headers={"Authorization": "Basic dXNlcjpwYXNz"},
        content=b"{}",
    )
    assert resp.status_code == 401


# ===========================================================================
# Tests: harness / trigger lookup
# ===========================================================================


async def test_harness_not_found_returns_404(
    space_store: SpaceStore,
    harness_store: HarnessStore,
    mock_task_store: MagicMock,
    mock_worker_pool: MagicMock,
) -> None:
    """POST to a webhook for a non-existent harness → 404."""
    _app = _make_app(space_store, harness_store, mock_task_store, mock_worker_pool)
    transport = httpx.ASGITransport(app=_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.post(
            f"{_BASE_URL}/nonexistent-harness/webhook",
            headers=_bearer(),
            content=b"{}",
        )
    assert resp.status_code == 404


async def test_no_webhook_trigger_node_returns_404(client_no_trigger: httpx.AsyncClient) -> None:
    """Harness exists but has no webhook trigger node → 404."""
    resp = await client_no_trigger.post(
        _WEBHOOK_URL,
        headers=_bearer(),
        content=b"{}",
    )
    assert resp.status_code == 404


# ===========================================================================
# Tests: successful fan-out
# ===========================================================================


async def test_valid_webhook_returns_202_with_run_ids(
    client_with_harness: httpx.AsyncClient,
) -> None:
    """Correct token + existing harness → 202 with run_ids list."""
    with patch(
        "app.api.harnesses.fan_out_to_harnesses",
        new_callable=AsyncMock,
        return_value=["run-001"],
    ):
        resp = await client_with_harness.post(
            _WEBHOOK_URL,
            headers=_bearer(),
            content=b'{"hello": "world"}',
        )
    assert resp.status_code == 202
    body = resp.json()
    assert "run_ids" in body
    assert body["run_ids"] == ["run-001"]


async def test_valid_webhook_empty_body_accepted(
    client_with_harness: httpx.AsyncClient,
) -> None:
    """Empty body is valid; payload is accepted as empty dict."""
    with patch(
        "app.api.harnesses.fan_out_to_harnesses",
        new_callable=AsyncMock,
        return_value=["run-002"],
    ):
        resp = await client_with_harness.post(
            _WEBHOOK_URL,
            headers=_bearer(),
            content=b"",
        )
    assert resp.status_code == 202
    assert resp.json()["run_ids"] == ["run-002"]


async def test_valid_webhook_non_json_body_accepted(
    client_with_harness: httpx.AsyncClient,
) -> None:
    """Non-JSON body is accepted and stored as raw string in payload."""
    with patch(
        "app.api.harnesses.fan_out_to_harnesses",
        new_callable=AsyncMock,
        return_value=[],
    ) as mock_fan_out:
        resp = await client_with_harness.post(
            _WEBHOOK_URL,
            headers=_bearer(),
            content=b"not-json",
        )
    assert resp.status_code == 202
    # fan_out_to_harnesses should have been called with payload containing raw key
    call_args = mock_fan_out.call_args
    event = call_args.args[0]
    assert "raw" in event.payload


# ===========================================================================
# Tests: deduplication (identical payloads within debounce window)
# ===========================================================================


async def test_identical_payload_deduplicated_returns_empty_run_ids(
    client_with_harness: httpx.AsyncClient,
) -> None:
    """Identical payloads within debounce window → empty run_ids on second call."""
    # Patch fan_out_to_harnesses to simulate dedup: first call returns run_ids,
    # second call returns [] (debouncer suppressed it).
    call_count = 0

    async def _fan_out_side_effect(event, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return ["run-dedup-001"]
        return []  # deduplicated

    with patch("app.api.harnesses.fan_out_to_harnesses", side_effect=_fan_out_side_effect):
        body = b'{"event": "push", "ref": "refs/heads/main"}'
        resp1 = await client_with_harness.post(
            _WEBHOOK_URL, headers=_bearer(), content=body
        )
        resp2 = await client_with_harness.post(
            _WEBHOOK_URL, headers=_bearer(), content=body
        )

    assert resp1.status_code == 202
    assert resp1.json()["run_ids"] == ["run-dedup-001"]

    assert resp2.status_code == 202
    assert resp2.json()["run_ids"] == []  # deduplicated


async def test_different_payloads_not_deduplicated(
    client_with_harness: httpx.AsyncClient,
) -> None:
    """Different payloads produce different event_ids → both enqueued."""
    with patch(
        "app.api.harnesses.fan_out_to_harnesses",
        new_callable=AsyncMock,
        return_value=["run-x"],
    ) as mock_fan_out:
        body1 = b'{"event": "push"}'
        body2 = b'{"event": "pull_request"}'
        resp1 = await client_with_harness.post(
            _WEBHOOK_URL, headers=_bearer(), content=body1
        )
        resp2 = await client_with_harness.post(
            _WEBHOOK_URL, headers=_bearer(), content=body2
        )

    assert resp1.status_code == 202
    assert resp2.status_code == 202
    # fan_out_to_harnesses called twice with different event_ids
    assert mock_fan_out.call_count == 2
    event1 = mock_fan_out.call_args_list[0].args[0]
    event2 = mock_fan_out.call_args_list[1].args[0]
    assert event1.event_id != event2.event_id


# ===========================================================================
# Tests: event_id construction
# ===========================================================================


async def test_event_id_includes_space_and_harness_hash(
    client_with_harness: httpx.AsyncClient,
) -> None:
    """event_id must be webhook:{space_id}:{webhook_path}:{body_hash[:16]}."""
    import hashlib

    captured_event = None

    async def _capture(event, **kwargs):
        nonlocal captured_event
        captured_event = event
        return ["run-ev-001"]

    body = b'{"action": "test"}'
    expected_hash = hashlib.sha256(body).hexdigest()[:16]

    with patch("app.api.harnesses.fan_out_to_harnesses", side_effect=_capture):
        resp = await client_with_harness.post(
            _WEBHOOK_URL, headers=_bearer(), content=body
        )

    assert resp.status_code == 202
    assert captured_event is not None
    assert captured_event.kind == "webhook"
    assert captured_event.space_id == SPACE_ID
    # event_id format: webhook:{space_id}:{webhook_path}:{hash[:16]}
    assert captured_event.event_id == f"webhook:{SPACE_ID}:my-hook:{expected_hash}"


# ===========================================================================
# Tests: short-token warning (once per process)
# ===========================================================================


async def test_short_token_emits_warning_once(
    space_store: SpaceStore,
    harness_store: HarnessStore,
    mock_task_store: MagicMock,
    mock_worker_pool: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A webhook trigger with an auth_token shorter than 16 chars triggers log.warning once."""
    # Reset the per-process warning guard for this test
    import app.api.harnesses as harnesses_mod
    short_warn_key = f"{SPACE_ID}:{HARNESS_NAME}"
    harnesses_mod._SHORT_TOKEN_WARNED.discard(short_warn_key)

    _app = _make_app(space_store, harness_store, mock_task_store, mock_worker_pool)
    transport = httpx.ASGITransport(app=_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        # Create harness with a short token
        resp = await c.post(_BASE_URL, json=_harness_payload(auth_token=SHORT_TOKEN))
        assert resp.status_code == 201

        with patch(
            "app.api.harnesses.fan_out_to_harnesses",
            new_callable=AsyncMock,
            return_value=["run-short-001"],
        ):
            with caplog.at_level(logging.WARNING, logger="app.api.harnesses"):
                # First call — should log warning
                resp1 = await c.post(
                    _WEBHOOK_URL,
                    headers={"Authorization": f"Bearer {SHORT_TOKEN}"},
                    content=b"{}",
                )
                # Second call — warning should NOT be re-emitted
                resp2 = await c.post(
                    _WEBHOOK_URL,
                    headers={"Authorization": f"Bearer {SHORT_TOKEN}"},
                    content=b"{}",
                )

    assert resp1.status_code == 202
    assert resp2.status_code == 202

    warning_records = [
        r for r in caplog.records
        if r.levelname == "WARNING" and "shorter than 16" in r.message
    ]
    assert len(warning_records) == 1, (
        f"Expected exactly 1 short-token warning, got {len(warning_records)}: "
        f"{[r.message for r in warning_records]}"
    )


async def test_long_token_no_warning(
    client_with_harness: httpx.AsyncClient,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A webhook trigger with a token >= 16 chars does NOT emit a warning."""
    with patch(
        "app.api.harnesses.fan_out_to_harnesses",
        new_callable=AsyncMock,
        return_value=["run-long-001"],
    ):
        with caplog.at_level(logging.WARNING, logger="app.api.harnesses"):
            resp = await client_with_harness.post(
                _WEBHOOK_URL,
                headers=_bearer(VALID_TOKEN),
                content=b"{}",
            )

    assert resp.status_code == 202
    warning_records = [
        r for r in caplog.records if "shorter than 16" in r.message
    ]
    assert len(warning_records) == 0


# ===========================================================================
# Tests: response structure
# ===========================================================================


async def test_response_contains_only_run_ids_key(
    client_with_harness: httpx.AsyncClient,
) -> None:
    """The 202 response body must have exactly the 'run_ids' key."""
    with patch(
        "app.api.harnesses.fan_out_to_harnesses",
        new_callable=AsyncMock,
        return_value=["run-struct-001", "run-struct-002"],
    ):
        resp = await client_with_harness.post(
            _WEBHOOK_URL,
            headers=_bearer(),
            content=b'{"key": "value"}',
        )

    assert resp.status_code == 202
    body = resp.json()
    assert set(body.keys()) == {"run_ids"}
    assert isinstance(body["run_ids"], list)
    assert len(body["run_ids"]) == 2


async def test_run_ids_empty_when_fan_out_returns_empty(
    client_with_harness: httpx.AsyncClient,
) -> None:
    """When fan_out_to_harnesses returns [], run_ids is an empty list."""
    with patch(
        "app.api.harnesses.fan_out_to_harnesses",
        new_callable=AsyncMock,
        return_value=[],
    ):
        resp = await client_with_harness.post(
            _WEBHOOK_URL,
            headers=_bearer(),
            content=b"{}",
        )

    assert resp.status_code == 202
    assert resp.json()["run_ids"] == []


# ===========================================================================
# Tests: unknown space
# ===========================================================================


async def test_unknown_space_returns_404(
    space_store: SpaceStore,
    harness_store: HarnessStore,
) -> None:
    """Webhook to a non-existent space_id → 404 before token check."""
    _app = _make_app(space_store, harness_store)
    transport = httpx.ASGITransport(app=_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.post(
            f"/api/spaces/no-such-space/harnesses/{HARNESS_NAME}/webhook",
            headers=_bearer(),
            content=b"{}",
        )
    assert resp.status_code == 404
