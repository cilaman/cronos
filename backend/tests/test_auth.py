from __future__ import annotations

"""Integration tests for HTTP Basic Auth (app/auth.py).

The auth dependency reads CRONOS_BASIC_AUTH_USER / CRONOS_BASIC_AUTH_PASSWORD
from the environment at request time (no module reload needed). These tests
use monkeypatch.setenv / delenv to flip auth on and off per test, then exercise
the real FastAPI app through the shared `async_client` fixture.
"""

import httpx
import pytest

from .conftest import SPACE_ID

AUTH_USER = "alice"
AUTH_PASS = "s3cret-pa$$w0rd"


@pytest.fixture(autouse=True)
def _clear_auth_env(monkeypatch):
    """Ensure no leftover auth env vars from other tests interfere.

    Individual tests opt in to auth by calling monkeypatch.setenv themselves.
    """
    monkeypatch.delenv("CRONOS_BASIC_AUTH_USER", raising=False)
    monkeypatch.delenv("CRONOS_BASIC_AUTH_PASSWORD", raising=False)


# ---------------------------------------------------------------------------
# Auth ENABLED (both env vars set)
# ---------------------------------------------------------------------------


async def test_protected_endpoint_without_credentials_returns_401(async_client, monkeypatch):
    # Arrange
    monkeypatch.setenv("CRONOS_BASIC_AUTH_USER", AUTH_USER)
    monkeypatch.setenv("CRONOS_BASIC_AUTH_PASSWORD", AUTH_PASS)

    # Act
    resp = await async_client.get("/api/spaces")

    # Assert
    assert resp.status_code == 401
    # FastAPI's HTTPException with WWW-Authenticate header should be advertised
    assert resp.headers.get("www-authenticate", "").lower().startswith("basic")


async def test_protected_endpoint_with_wrong_password_returns_401(async_client, monkeypatch):
    # Arrange
    monkeypatch.setenv("CRONOS_BASIC_AUTH_USER", AUTH_USER)
    monkeypatch.setenv("CRONOS_BASIC_AUTH_PASSWORD", AUTH_PASS)

    # Act
    resp = await async_client.get(
        "/api/spaces",
        auth=httpx.BasicAuth(AUTH_USER, "definitely-wrong"),
    )

    # Assert
    assert resp.status_code == 401
    assert resp.headers.get("www-authenticate", "").lower().startswith("basic")


async def test_protected_endpoint_with_wrong_username_returns_401(async_client, monkeypatch):
    # Arrange
    monkeypatch.setenv("CRONOS_BASIC_AUTH_USER", AUTH_USER)
    monkeypatch.setenv("CRONOS_BASIC_AUTH_PASSWORD", AUTH_PASS)

    # Act
    resp = await async_client.get(
        "/api/spaces",
        auth=httpx.BasicAuth("not-alice", AUTH_PASS),
    )

    # Assert
    assert resp.status_code == 401


async def test_protected_endpoint_with_correct_credentials_returns_200(async_client, monkeypatch):
    # Arrange
    monkeypatch.setenv("CRONOS_BASIC_AUTH_USER", AUTH_USER)
    monkeypatch.setenv("CRONOS_BASIC_AUTH_PASSWORD", AUTH_PASS)

    # Act
    resp = await async_client.get(
        "/api/spaces",
        auth=httpx.BasicAuth(AUTH_USER, AUTH_PASS),
    )

    # Assert
    assert resp.status_code == 200
    # /api/spaces returns {"spaces": [...], "totals": {...}}; conftest seeds one test space
    payload = resp.json()
    assert "spaces" in payload
    assert any(s.get("id") == SPACE_ID for s in payload["spaces"])


@pytest.mark.parametrize(
    "router_path",
    [
        pytest.param("/api/tasks", id="tasks-router"),
        pytest.param("/api/spaces", id="spaces-router"),
        pytest.param("/api/activity", id="activity-router"),
        pytest.param("/api/stats", id="stats-router"),
    ],
)
async def test_all_routers_require_auth_when_enabled(async_client, monkeypatch, router_path):
    # Arrange
    monkeypatch.setenv("CRONOS_BASIC_AUTH_USER", AUTH_USER)
    monkeypatch.setenv("CRONOS_BASIC_AUTH_PASSWORD", AUTH_PASS)

    # Act
    unauth = await async_client.get(router_path)
    authed = await async_client.get(router_path, auth=httpx.BasicAuth(AUTH_USER, AUTH_PASS))

    # Assert
    assert unauth.status_code == 401, f"{router_path} should require auth"
    # Authed should not be 401 (may be 200, 404, etc. depending on endpoint state)
    assert authed.status_code != 401, f"{router_path} should accept correct credentials"


# ---------------------------------------------------------------------------
# /api/health is always public
# ---------------------------------------------------------------------------


async def test_health_endpoint_public_when_auth_enabled(async_client, monkeypatch):
    # Arrange — auth is configured...
    monkeypatch.setenv("CRONOS_BASIC_AUTH_USER", AUTH_USER)
    monkeypatch.setenv("CRONOS_BASIC_AUTH_PASSWORD", AUTH_PASS)

    # Act — ...but health requests carry no credentials.
    resp = await async_client.get("/api/health")

    # Assert
    assert resp.status_code == 200
    body = resp.json()
    assert "ok" in body
    assert "spaces_dir_exists" in body


async def test_health_endpoint_public_when_auth_disabled(async_client):
    # Arrange — _clear_auth_env autouse fixture already deleted env vars.

    # Act
    resp = await async_client.get("/api/health")

    # Assert
    assert resp.status_code == 200
    assert "ok" in resp.json()


# ---------------------------------------------------------------------------
# Auth DISABLED (env vars unset or empty)
# ---------------------------------------------------------------------------


async def test_protected_endpoint_returns_200_when_auth_disabled(async_client):
    # Arrange — _clear_auth_env autouse fixture deleted env vars.

    # Act
    resp = await async_client.get("/api/spaces")

    # Assert
    assert resp.status_code == 200
    payload = resp.json()
    assert "spaces" in payload


async def test_auth_disabled_when_only_user_env_set(async_client, monkeypatch):
    # Arrange — partial config should also disable auth (per auth.py: needs BOTH).
    monkeypatch.setenv("CRONOS_BASIC_AUTH_USER", AUTH_USER)
    # password intentionally not set

    # Act
    resp = await async_client.get("/api/spaces")

    # Assert — auth treated as disabled
    assert resp.status_code == 200


async def test_auth_disabled_when_only_password_env_set(async_client, monkeypatch):
    # Arrange
    monkeypatch.setenv("CRONOS_BASIC_AUTH_PASSWORD", AUTH_PASS)

    # Act
    resp = await async_client.get("/api/spaces")

    # Assert
    assert resp.status_code == 200


async def test_auth_disabled_when_user_env_empty_string(async_client, monkeypatch):
    # Arrange — empty string is falsy per `if not user or not password` check
    monkeypatch.setenv("CRONOS_BASIC_AUTH_USER", "")
    monkeypatch.setenv("CRONOS_BASIC_AUTH_PASSWORD", AUTH_PASS)

    # Act
    resp = await async_client.get("/api/spaces")

    # Assert
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Edge cases — credentials with special characters
# ---------------------------------------------------------------------------


async def test_credentials_with_special_ascii_chars_succeed(async_client, monkeypatch):
    # Arrange — password with shell-special and base64-boundary chars
    tricky_pass = "p@ss:w0rd/with+special=chars&more"
    monkeypatch.setenv("CRONOS_BASIC_AUTH_USER", AUTH_USER)
    monkeypatch.setenv("CRONOS_BASIC_AUTH_PASSWORD", tricky_pass)

    # Act
    resp = await async_client.get(
        "/api/spaces",
        auth=httpx.BasicAuth(AUTH_USER, tricky_pass),
    )

    # Assert
    assert resp.status_code == 200


async def test_credentials_with_colon_in_password_succeed(async_client, monkeypatch):
    # Arrange — colon is the Basic-Auth delimiter between user and pass.
    # RFC 7617: only the first colon separates them, so colons in the password
    # are legal. Verify the server reassembles correctly.
    pass_with_colon = "abc:def:ghi"
    monkeypatch.setenv("CRONOS_BASIC_AUTH_USER", AUTH_USER)
    monkeypatch.setenv("CRONOS_BASIC_AUTH_PASSWORD", pass_with_colon)

    # Act
    resp = await async_client.get(
        "/api/spaces",
        auth=httpx.BasicAuth(AUTH_USER, pass_with_colon),
    )

    # Assert
    assert resp.status_code == 200


async def test_credentials_byte_length_mismatch_rejected(async_client, monkeypatch):
    # Arrange — verify a shorter wrong password still 401s (compare_digest is
    # constant-time but still returns False for mismatched bytes).
    monkeypatch.setenv("CRONOS_BASIC_AUTH_USER", AUTH_USER)
    monkeypatch.setenv("CRONOS_BASIC_AUTH_PASSWORD", AUTH_PASS)

    # Act
    resp = await async_client.get(
        "/api/spaces",
        auth=httpx.BasicAuth(AUTH_USER, "x"),
    )

    # Assert
    assert resp.status_code == 401
