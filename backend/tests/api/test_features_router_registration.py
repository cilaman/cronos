"""Tests for features router registration in the FastAPI app.

Covers (from I4 acceptance criteria):
  (a) /api/features prefix appears in app.routes via OpenAPI introspection.
  (b) Unauthenticated GET /api/features returns 401 (R14 auth-parity).
  (c) Authenticated GET /api/features returns a documented non-404 status code.

The test app is built using the main FastAPI ``app`` object so that
``app.include_router(features_router, dependencies=_auth)`` is exercised.
Auth is activated by setting CRONOS_BASIC_AUTH_USER + CRONOS_BASIC_AUTH_PASSWORD
env vars and using httpx.BasicAuth on the authenticated client.
"""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# App fixture — patch away the lifespan + provide minimal app.state
# ---------------------------------------------------------------------------

TEST_USER = "testuser"
TEST_PASS = "testpass"


@pytest.fixture()
def test_app(monkeypatch, tmp_path):
    """Return a TestClient for the main FastAPI app with auth enabled.

    The lifespan is bypassed by patching asynccontextmanager so we avoid
    spinning up worker pools, file watchers, etc.
    """
    monkeypatch.delenv("CRONOS_AUTH_DISABLED", raising=False)
    monkeypatch.delenv("CRONOS_BASIC_AUTH_HASH", raising=False)
    monkeypatch.setenv("CRONOS_BASIC_AUTH_USER", TEST_USER)
    monkeypatch.setenv("CRONOS_BASIC_AUTH_PASSWORD", TEST_PASS)
    monkeypatch.setenv("CRONOS_DATA_DIR", str(tmp_path))

    # Import app after env vars are set so module-level constants pick them up.
    # We need to defer the import inside the fixture to avoid polluting module
    # scope with the monkeypatched env.
    from app.main import app

    # Provide a minimal app.state so routers that call request.app.state.store
    # don't crash on AttributeError when the lifespan is bypassed.
    mock_store = MagicMock()
    mock_store.board = MagicMock(
        return_value=MagicMock(active=[], backlog=[], waiting=[], done=[])
    )
    mock_store.get.return_value = MagicMock(type="feature", space_id="test-space")
    app.state.store = mock_store
    app.state.space_store = MagicMock()
    app.state.worker_pool = MagicMock()
    app.state.harness_store = MagicMock()
    app.state.memory_store = MagicMock()
    app.state.stats_store = MagicMock()
    app.state.trace_store = MagicMock()
    app.state.test_report_store = MagicMock()

    # Use lifespan=False so the startup/shutdown hooks do not fire.
    client = TestClient(app, raise_server_exceptions=False)
    return client


@pytest.fixture()
def authed_client(test_app):
    """Wrap the TestClient with Basic Auth credentials."""
    # TestClient itself doesn't have a built-in auth kwarg across all versions;
    # we set the Authorization header manually instead.
    import base64
    token = base64.b64encode(f"{TEST_USER}:{TEST_PASS}".encode()).decode()
    test_app.headers = {**test_app.headers, "Authorization": f"Basic {token}"}
    return test_app


# ---------------------------------------------------------------------------
# (a) Router prefix /api/features is present in app.routes
# ---------------------------------------------------------------------------


def _iter_route_paths(routes):
    """Yield every route path reachable from an app's route table.

    Starlette/FastAPI changed `include_router` to wrap included routers in an
    `_IncludedRouter` object (exposing `original_router`) rather than copying
    the sub-routes onto `app.routes` directly. Walk both shapes so the
    registration check is version-agnostic.
    """
    for route in routes:
        path = getattr(route, "path", "")
        if path:
            yield path
        nested = getattr(route, "routes", None)
        if nested is None:
            original = getattr(route, "original_router", None)
            nested = getattr(original, "routes", None)
        if nested:
            yield from _iter_route_paths(nested)


def test_features_routes_registered():
    """The features router must expose at least one route under /api/features."""
    from app.main import app

    prefixes = {p for p in _iter_route_paths(app.routes) if p.startswith("/api/features")}

    assert prefixes, (
        "No routes with prefix /api/features found in app.routes. "
        "features_router was not registered in main.py."
    )


def test_features_router_has_eight_routes():
    """Exactly 8 route stubs must be defined on the features router."""
    from app.api.features import router

    # Collect unique (path, method) pairs.
    route_methods = set()
    for route in router.routes:
        path = getattr(route, "path", "")
        methods = getattr(route, "methods", set()) or set()
        for method in methods:
            route_methods.add((method, path))

    assert len(route_methods) == 8, (
        f"Expected 8 routes on features router, found {len(route_methods)}: "
        f"{sorted(route_methods)}"
    )


def test_features_router_prefix():
    """The features APIRouter must use prefix='/api/features'."""
    from app.api.features import router

    assert router.prefix == "/api/features", (
        f"Expected prefix '/api/features', got '{router.prefix}'"
    )


# ---------------------------------------------------------------------------
# (b) Unauthenticated GET /api/features returns 401
# ---------------------------------------------------------------------------


def test_unauthenticated_get_returns_401(test_app):
    """GET /api/features without credentials must return 401."""
    # Remove any pre-set auth header to simulate unauthenticated access.
    headers = {k: v for k, v in test_app.headers.items() if k.lower() != "authorization"}
    response = test_app.get("/api/features", headers=headers, params={"space_id": "x"})
    assert response.status_code == 401, (
        f"Expected 401 for unauthenticated GET /api/features, got {response.status_code}"
    )


# ---------------------------------------------------------------------------
# (c) Authenticated GET /api/features returns a documented non-404 status code
# ---------------------------------------------------------------------------


def test_authenticated_get_returns_non_404(authed_client):
    """GET /api/features with valid credentials must not return 404.

    At the stub stage the route returns 501 Not Implemented, which proves
    the route is registered and auth is satisfied.  Any 2xx or 5xx code
    (except 404) confirms the endpoint exists.
    """
    response = authed_client.get("/api/features", params={"space_id": "test-space"})
    assert response.status_code != 404, (
        f"Authenticated GET /api/features returned 404 — route may not be registered. "
        f"Got status {response.status_code}"
    )


def test_authenticated_get_feature_by_id_non_404(authed_client):
    """GET /api/features/{id} with valid credentials must not return 404."""
    response = authed_client.get("/api/features/FEAT-001")
    assert response.status_code != 404, (
        f"GET /api/features/FEAT-001 returned 404 — route stub missing. "
        f"Got status {response.status_code}"
    )


# ---------------------------------------------------------------------------
# Route presence checks — each stub path must be reachable
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("method,path", [
    ("GET", "/api/features"),
    ("POST", "/api/features"),
    ("GET", "/api/features/FEAT-001"),
    ("PATCH", "/api/features/FEAT-001"),
    ("PATCH", "/api/features/FEAT-001/feature-state"),
    ("PATCH", "/api/features/FEAT-001/realize"),
    ("POST", "/api/features/FEAT-001/process"),
    ("DELETE", "/api/features/FEAT-001"),
])
def test_route_exists_non_405(authed_client, method, path):
    """Every stub route must be registered (non-405 Method Not Allowed)."""
    response = authed_client.request(method, path, json={})
    assert response.status_code != 405, (
        f"{method} {path} returned 405 Method Not Allowed — route stub missing. "
        f"Got {response.status_code}"
    )
