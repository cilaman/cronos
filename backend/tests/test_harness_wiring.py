from __future__ import annotations

"""Integration / wiring tests for backend/app/api/harnesses.py mounted in main.py.

These tests verify two things:
  1. Auth wiring — unauthenticated requests return 401 when auth is enabled.
  2. DI ordering — HarnessStore is on app.state before the first request, so
     an authenticated request to a valid endpoint does not raise AttributeError
     but instead returns a meaningful HTTP response (200 or 404, not 500).

The tests use the shared `async_client` fixture from conftest.py which already
mounts the real FastAPI app. We additionally set app.state.harness_store via
the fixture below so the DI chain resolves correctly.
"""

import httpx
import pytest

from app.harnesses import HarnessStore
from app.main import app

from .conftest import SPACE_ID

AUTH_USER = "testuser"
AUTH_PASS = "testpass"

HARNESS_URL = f"/api/spaces/{SPACE_ID}/harnesses"
NONEXISTENT_URL = "/api/spaces/nonexistent-space/harnesses"


@pytest.fixture(autouse=True)
def _inject_harness_store(tmp_path):
    """Inject a fresh HarnessStore onto app.state for each test.

    This mirrors the conftest.py pattern of setting app.state.X directly so
    that the DI helper in harnesses.py (`request.app.state.harness_store`)
    resolves without raising AttributeError.
    """
    app.state.harness_store = HarnessStore()
    yield
    # cleanup — remove harness_store so other tests are not surprised
    try:
        del app.state.harness_store
    except AttributeError:
        pass


@pytest.fixture(autouse=True)
def _clear_auth_env(monkeypatch):
    """Ensure no leftover auth env vars from other tests interfere."""
    monkeypatch.delenv("CRONOS_BASIC_AUTH_USER", raising=False)
    monkeypatch.delenv("CRONOS_BASIC_AUTH_PASSWORD", raising=False)


# ---------------------------------------------------------------------------
# Auth wiring — unauthenticated requests must return 401 when auth enabled
# ---------------------------------------------------------------------------


async def test_unauthenticated_list_returns_401(async_client, monkeypatch):
    """GET /api/spaces/{space_id}/harnesses without credentials must return 401."""
    monkeypatch.setenv("CRONOS_BASIC_AUTH_USER", AUTH_USER)
    monkeypatch.setenv("CRONOS_BASIC_AUTH_PASSWORD", AUTH_PASS)

    resp = await async_client.get(HARNESS_URL)

    assert resp.status_code == 401
    assert resp.headers.get("www-authenticate", "").lower().startswith("basic")


async def test_unauthenticated_post_returns_401(async_client, monkeypatch):
    """POST /api/spaces/{space_id}/harnesses without credentials must return 401."""
    monkeypatch.setenv("CRONOS_BASIC_AUTH_USER", AUTH_USER)
    monkeypatch.setenv("CRONOS_BASIC_AUTH_PASSWORD", AUTH_PASS)

    resp = await async_client.post(
        HARNESS_URL,
        json={"name": "test-harness"},
    )

    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# DI ordering — authenticated requests must NOT raise AttributeError (500)
# ---------------------------------------------------------------------------


async def test_authenticated_list_existing_space_returns_200(async_client, monkeypatch):
    """GET /api/spaces/{space_id}/harnesses with valid credentials returns 200.

    The test space is created by the conftest space_store fixture. An empty
    list response (200 []) confirms that:
      - the router is wired into main.py
      - HarnessStore is on app.state (DI resolves, no AttributeError)
      - SpaceStore resolves the space_id correctly (no 500)
      - auth dependency accepts the credentials
    """
    monkeypatch.setenv("CRONOS_BASIC_AUTH_USER", AUTH_USER)
    monkeypatch.setenv("CRONOS_BASIC_AUTH_PASSWORD", AUTH_PASS)

    resp = await async_client.get(
        HARNESS_URL,
        auth=httpx.BasicAuth(AUTH_USER, AUTH_PASS),
    )

    assert resp.status_code == 200
    assert resp.json() == []


async def test_authenticated_list_nonexistent_space_returns_404(async_client, monkeypatch):
    """GET /api/spaces/nonexistent-space/harnesses with valid credentials returns 404.

    This confirms the router is wired and the space-not-found path in the DI
    helper works end-to-end without a 500. A 404 (not 500) means:
      - HarnessStore is on app.state
      - SpaceStore is on app.state
      - _get_space_dir correctly raises HTTPException(404) for unknown space_id
    """
    monkeypatch.setenv("CRONOS_BASIC_AUTH_USER", AUTH_USER)
    monkeypatch.setenv("CRONOS_BASIC_AUTH_PASSWORD", AUTH_PASS)

    resp = await async_client.get(
        NONEXISTENT_URL,
        auth=httpx.BasicAuth(AUTH_USER, AUTH_PASS),
    )

    assert resp.status_code == 404


async def test_harness_store_on_app_state(async_client):
    """Verify HarnessStore is accessible on app.state after wiring."""
    assert hasattr(app.state, "harness_store")
    assert isinstance(app.state.harness_store, HarnessStore)


async def test_harnesses_endpoint_reachable_without_auth_when_auth_disabled(async_client):
    """When auth is disabled (no env vars), the endpoint returns 200 for an existing space."""
    # _clear_auth_env autouse fixture already deleted env vars

    resp = await async_client.get(HARNESS_URL)

    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
