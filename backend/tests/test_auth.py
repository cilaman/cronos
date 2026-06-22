from __future__ import annotations

"""Integration tests for HTTP Basic Auth (app/auth.py).

The auth dependency reads CRONOS_BASIC_AUTH_USER / CRONOS_BASIC_AUTH_PASSWORD
from the environment at request time (no module reload needed). These tests
use monkeypatch.setenv / delenv to flip auth on and off per test, then exercise
the real FastAPI app through the shared `async_client` fixture.
"""

import bcrypt
import httpx
import pytest

from .conftest import SPACE_ID

AUTH_USER = "alice"
AUTH_PASS = "s3cret-pa$$w0rd"
# bcrypt hash of AUTH_PASS (low cost so the test suite stays fast). This mirrors
# reusing Caddy's BASIC_AUTH_HASH for the app-layer check.
AUTH_HASH = bcrypt.hashpw(AUTH_PASS.encode(), bcrypt.gensalt(rounds=4)).decode()


@pytest.fixture(autouse=True)
def _clear_auth_env(monkeypatch):
    """Clear all auth env vars per-test so the real fail-closed logic is exercised.

    conftest's _auth_disabled_by_default sets CRONOS_AUTH_DISABLED=true at
    function scope; this fixture's delenv runs in the SAME scope and wins,
    leaving all three variables unset. Individual tests opt in as needed.
    """
    monkeypatch.delenv("CRONOS_BASIC_AUTH_USER", raising=False)
    monkeypatch.delenv("CRONOS_BASIC_AUTH_PASSWORD", raising=False)
    monkeypatch.delenv("CRONOS_BASIC_AUTH_HASH", raising=False)
    monkeypatch.delenv("CRONOS_AUTH_DISABLED", raising=False)


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
# Auth ENABLED via bcrypt hash (CRONOS_BASIC_AUTH_HASH — no plaintext in env)
# ---------------------------------------------------------------------------


async def test_hash_credentials_correct_returns_200(async_client, monkeypatch):
    # Arrange — only the username + bcrypt hash are configured (no plaintext).
    monkeypatch.setenv("CRONOS_BASIC_AUTH_USER", AUTH_USER)
    monkeypatch.setenv("CRONOS_BASIC_AUTH_HASH", AUTH_HASH)

    # Act
    resp = await async_client.get("/api/spaces", auth=httpx.BasicAuth(AUTH_USER, AUTH_PASS))

    # Assert
    assert resp.status_code == 200
    assert any(s.get("id") == SPACE_ID for s in resp.json()["spaces"])


async def test_hash_credentials_wrong_password_returns_401(async_client, monkeypatch):
    # Arrange
    monkeypatch.setenv("CRONOS_BASIC_AUTH_USER", AUTH_USER)
    monkeypatch.setenv("CRONOS_BASIC_AUTH_HASH", AUTH_HASH)

    # Act
    resp = await async_client.get("/api/spaces", auth=httpx.BasicAuth(AUTH_USER, "definitely-wrong"))

    # Assert
    assert resp.status_code == 401


async def test_hash_credentials_wrong_username_returns_401(async_client, monkeypatch):
    # Arrange
    monkeypatch.setenv("CRONOS_BASIC_AUTH_USER", AUTH_USER)
    monkeypatch.setenv("CRONOS_BASIC_AUTH_HASH", AUTH_HASH)

    # Act
    resp = await async_client.get("/api/spaces", auth=httpx.BasicAuth("not-alice", AUTH_PASS))

    # Assert
    assert resp.status_code == 401


async def test_only_hash_without_user_returns_503(async_client, monkeypatch):
    # Arrange — hash set but no username is still misconfiguration.
    monkeypatch.setenv("CRONOS_BASIC_AUTH_HASH", AUTH_HASH)

    # Act
    resp = await async_client.get("/api/spaces")

    # Assert
    assert resp.status_code == 503


async def test_hash_takes_precedence_over_plaintext(async_client, monkeypatch):
    # Arrange — both set; the hash is authoritative, plaintext is ignored.
    monkeypatch.setenv("CRONOS_BASIC_AUTH_USER", AUTH_USER)
    monkeypatch.setenv("CRONOS_BASIC_AUTH_HASH", AUTH_HASH)
    monkeypatch.setenv("CRONOS_BASIC_AUTH_PASSWORD", "a-different-plaintext")

    # Act — the password matching the HASH succeeds...
    ok = await async_client.get("/api/spaces", auth=httpx.BasicAuth(AUTH_USER, AUTH_PASS))
    # ...and the password matching only the ignored plaintext fails.
    bad = await async_client.get("/api/spaces", auth=httpx.BasicAuth(AUTH_USER, "a-different-plaintext"))

    # Assert
    assert ok.status_code == 200
    assert bad.status_code == 401


async def test_malformed_hash_returns_401_not_500(async_client, monkeypatch):
    # Arrange — a garbage (non-bcrypt) hash must fail closed as a non-match,
    # not raise and surface as a 500.
    monkeypatch.setenv("CRONOS_BASIC_AUTH_USER", AUTH_USER)
    monkeypatch.setenv("CRONOS_BASIC_AUTH_HASH", "not-a-real-bcrypt-hash")

    # Act
    resp = await async_client.get("/api/spaces", auth=httpx.BasicAuth(AUTH_USER, AUTH_PASS))

    # Assert
    assert resp.status_code == 401


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
# Fail-closed: unconfigured credentials → 503
# ---------------------------------------------------------------------------


async def test_unset_credentials_returns_503(async_client):
    # Arrange — _clear_auth_env deleted all auth vars (CRONOS_AUTH_DISABLED too).

    # Act
    resp = await async_client.get("/api/spaces")

    # Assert — misconfiguration, not a credentials challenge
    assert resp.status_code == 503


async def test_only_user_env_set_returns_503(async_client, monkeypatch):
    # Arrange — partial config is still misconfigured.
    monkeypatch.setenv("CRONOS_BASIC_AUTH_USER", AUTH_USER)
    # password intentionally not set

    # Act
    resp = await async_client.get("/api/spaces")

    # Assert
    assert resp.status_code == 503


async def test_only_password_env_set_returns_503(async_client, monkeypatch):
    # Arrange — partial config is still misconfigured.
    monkeypatch.setenv("CRONOS_BASIC_AUTH_PASSWORD", AUTH_PASS)

    # Act
    resp = await async_client.get("/api/spaces")

    # Assert
    assert resp.status_code == 503


async def test_empty_user_with_password_returns_503(async_client, monkeypatch):
    # Arrange — empty string user with password is still partial/invalid config.
    monkeypatch.setenv("CRONOS_BASIC_AUTH_USER", "")
    monkeypatch.setenv("CRONOS_BASIC_AUTH_PASSWORD", AUTH_PASS)

    # Act
    resp = await async_client.get("/api/spaces")

    # Assert
    assert resp.status_code == 503


# ---------------------------------------------------------------------------
# Explicit opt-out: CRONOS_AUTH_DISABLED=true
# ---------------------------------------------------------------------------


async def test_auth_disabled_flag_allows_unauthenticated_request(async_client, monkeypatch):
    # Arrange — explicit opt-out, no credentials configured.
    monkeypatch.setenv("CRONOS_AUTH_DISABLED", "true")

    # Act
    resp = await async_client.get("/api/spaces")

    # Assert — opt-out grants access without credentials
    assert resp.status_code == 200
    assert "spaces" in resp.json()


async def test_auth_disabled_flag_wins_over_credentials(async_client, monkeypatch):
    # Arrange — both disabled flag AND credentials set; disabled takes precedence.
    monkeypatch.setenv("CRONOS_AUTH_DISABLED", "true")
    monkeypatch.setenv("CRONOS_BASIC_AUTH_USER", AUTH_USER)
    monkeypatch.setenv("CRONOS_BASIC_AUTH_PASSWORD", AUTH_PASS)

    # Act
    resp = await async_client.get("/api/spaces")

    # Assert — no credentials required when disabled
    assert resp.status_code == 200


async def test_auth_disabled_false_does_not_disable(async_client, monkeypatch):
    # Arrange — only "true" (exact string) disables auth.
    monkeypatch.setenv("CRONOS_AUTH_DISABLED", "false")
    monkeypatch.setenv("CRONOS_BASIC_AUTH_USER", AUTH_USER)
    monkeypatch.setenv("CRONOS_BASIC_AUTH_PASSWORD", AUTH_PASS)

    # Act — request without credentials
    resp = await async_client.get("/api/spaces")

    # Assert — auth still enforced (not disabled)
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Route coverage: File Browser and Plugin API are protected by require_auth (R3/R4)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "router_path",
    [
        pytest.param("/api/spaces/test-space/files", id="file-browser-route"),
        pytest.param("/api/plugins", id="plugins-route"),
    ],
)
async def test_file_browser_and_plugin_routes_require_auth(async_client, monkeypatch, router_path):
    # Arrange — credentials set so auth is enabled.
    monkeypatch.setenv("CRONOS_BASIC_AUTH_USER", AUTH_USER)
    monkeypatch.setenv("CRONOS_BASIC_AUTH_PASSWORD", AUTH_PASS)

    # Act — request without credentials
    unauth = await async_client.get(router_path)
    # Act — request with correct credentials
    authed = await async_client.get(router_path, auth=httpx.BasicAuth(AUTH_USER, AUTH_PASS))

    # Assert
    assert unauth.status_code == 401, f"{router_path} must require auth"
    assert authed.status_code != 401, f"{router_path} must accept correct credentials"


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
