from __future__ import annotations

"""Integration tests for /api/plugins endpoints."""

import pytest

from app.tools.plugins import PluginCliError

from .conftest import SPACE_ID  # noqa: F401 — space fixture depends on it


# ---------------------------------------------------------------------------
# Helpers — minimal fixture data
# ---------------------------------------------------------------------------

_EMPTY_RESPONSE = {"installed": [], "available": [], "marketplaces": []}

_INSTALLED_RESPONSE = {
    "installed": [
        {
            "id": "my-plugin",
            "name": "my-plugin",
            "enabled": True,
            "components": [],
        }
    ],
    "available": [],
    "marketplaces": [],
}


def _make_plugins_response(**kwargs):
    base = dict(_EMPTY_RESPONSE)
    base.update(kwargs)
    return base


# ---------------------------------------------------------------------------
# GET /api/plugins
# ---------------------------------------------------------------------------


async def test_get_plugins_happy(async_client, monkeypatch):
    from app.tools import plugins as plugins_mod

    async def _fake_list_plugins():
        from app.models import PluginsResponse
        return PluginsResponse()

    monkeypatch.setattr(plugins_mod, "list_plugins", _fake_list_plugins)
    # Also patch the router's reference
    import app.api.plugins as api_mod
    monkeypatch.setattr(api_mod, "list_plugins", _fake_list_plugins)

    resp = await async_client.get("/api/plugins")
    assert resp.status_code == 200
    data = resp.json()
    assert data == _EMPTY_RESPONSE


async def test_get_plugins_cli_error(async_client, monkeypatch):
    import app.api.plugins as api_mod

    async def _fail():
        raise PluginCliError(["claude", "plugin", "list"], 1, "no claude binary")

    monkeypatch.setattr(api_mod, "list_plugins", _fail)

    resp = await async_client.get("/api/plugins")
    assert resp.status_code == 502
    body = resp.json()
    assert "detail" in body["detail"]
    assert "stderr" in body["detail"]


# ---------------------------------------------------------------------------
# POST /api/plugins/install
# ---------------------------------------------------------------------------


async def test_install_plugin_happy(async_client, monkeypatch):
    import app.api.plugins as api_mod

    async def _fake_install(plugin_id, scope="user"):
        from app.models import PluginsResponse
        return PluginsResponse()

    monkeypatch.setattr(api_mod, "install", _fake_install)

    resp = await async_client.post("/api/plugins/install", json={"plugin_id": "my-plugin"})
    assert resp.status_code == 200
    assert resp.json() == _EMPTY_RESPONSE


async def test_install_plugin_invalid_id(async_client, monkeypatch):
    import app.api.plugins as api_mod

    # No subprocess should be called — ValueError is raised before CLI invocation
    called = []

    async def _fake_install(plugin_id, scope="user"):
        called.append(plugin_id)
        raise ValueError(f"Invalid plugin_id: {plugin_id!r}")

    monkeypatch.setattr(api_mod, "install", _fake_install)

    resp = await async_client.post("/api/plugins/install", json={"plugin_id": "invalid!@#"})
    assert resp.status_code == 422


async def test_install_plugin_cli_error(async_client, monkeypatch):
    import app.api.plugins as api_mod

    async def _fail(plugin_id, scope="user"):
        raise PluginCliError(["claude", "plugin", "install", plugin_id], 1, "not found")

    monkeypatch.setattr(api_mod, "install", _fail)

    resp = await async_client.post("/api/plugins/install", json={"plugin_id": "missing-plugin"})
    assert resp.status_code == 502
    body = resp.json()
    assert "stderr" in body["detail"]


# ---------------------------------------------------------------------------
# POST /api/plugins/uninstall
# ---------------------------------------------------------------------------


async def test_uninstall_plugin_happy(async_client, monkeypatch):
    import app.api.plugins as api_mod

    async def _fake_uninstall(plugin_id):
        from app.models import PluginsResponse
        return PluginsResponse()

    monkeypatch.setattr(api_mod, "uninstall", _fake_uninstall)

    resp = await async_client.post("/api/plugins/uninstall", json={"plugin_id": "my-plugin"})
    assert resp.status_code == 200
    assert resp.json() == _EMPTY_RESPONSE


async def test_uninstall_plugin_invalid_id(async_client, monkeypatch):
    import app.api.plugins as api_mod

    async def _fail(plugin_id):
        raise ValueError(f"Invalid plugin_id: {plugin_id!r}")

    monkeypatch.setattr(api_mod, "uninstall", _fail)

    resp = await async_client.post("/api/plugins/uninstall", json={"plugin_id": "bad id!"})
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# POST /api/plugins/enable
# ---------------------------------------------------------------------------


async def test_enable_plugin_happy(async_client, monkeypatch):
    import app.api.plugins as api_mod

    async def _fake_enable(plugin_id):
        from app.models import PluginsResponse
        return PluginsResponse()

    monkeypatch.setattr(api_mod, "enable", _fake_enable)

    resp = await async_client.post("/api/plugins/enable", json={"plugin_id": "my-plugin"})
    assert resp.status_code == 200
    assert resp.json() == _EMPTY_RESPONSE


async def test_enable_plugin_invalid_id(async_client, monkeypatch):
    import app.api.plugins as api_mod

    async def _fail(plugin_id):
        raise ValueError(f"Invalid plugin_id: {plugin_id!r}")

    monkeypatch.setattr(api_mod, "enable", _fail)

    resp = await async_client.post("/api/plugins/enable", json={"plugin_id": "bad!"})
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# POST /api/plugins/disable
# ---------------------------------------------------------------------------


async def test_disable_plugin_happy(async_client, monkeypatch):
    import app.api.plugins as api_mod

    async def _fake_disable(plugin_id):
        from app.models import PluginsResponse
        return PluginsResponse()

    monkeypatch.setattr(api_mod, "disable", _fake_disable)

    resp = await async_client.post("/api/plugins/disable", json={"plugin_id": "my-plugin"})
    assert resp.status_code == 200
    assert resp.json() == _EMPTY_RESPONSE


async def test_disable_plugin_invalid_id(async_client, monkeypatch):
    import app.api.plugins as api_mod

    async def _fail(plugin_id):
        raise ValueError(f"Invalid plugin_id: {plugin_id!r}")

    monkeypatch.setattr(api_mod, "disable", _fail)

    resp = await async_client.post("/api/plugins/disable", json={"plugin_id": "bad!"})
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# POST /api/plugins/marketplaces
# ---------------------------------------------------------------------------


async def test_add_marketplace_happy(async_client, monkeypatch):
    import app.api.plugins as api_mod

    async def _fake_add_marketplace(source):
        from app.models import MarketplaceEntry
        return [MarketplaceEntry(name="my-market", source=source)]

    async def _fake_list_plugins():
        from app.models import PluginsResponse, MarketplaceEntry
        return PluginsResponse(
            marketplaces=[MarketplaceEntry(name="my-market", source="https://example.com")]
        )

    monkeypatch.setattr(api_mod, "add_marketplace", _fake_add_marketplace)
    monkeypatch.setattr(api_mod, "list_plugins", _fake_list_plugins)

    resp = await async_client.post(
        "/api/plugins/marketplaces", json={"source": "https://example.com"}
    )
    assert resp.status_code == 200
    data = resp.json()
    # Response must be PluginsResponse shape (not a bare list)
    assert "installed" in data
    assert "available" in data
    assert "marketplaces" in data
    assert data["marketplaces"][0]["name"] == "my-market"


async def test_add_marketplace_invalid_source(async_client, monkeypatch):
    import app.api.plugins as api_mod

    called = []

    async def _fail(source):
        called.append(source)
        raise ValueError(f"Invalid marketplace source: {source!r}")

    monkeypatch.setattr(api_mod, "add_marketplace", _fail)

    resp = await async_client.post(
        "/api/plugins/marketplaces", json={"source": "not-a-url"}
    )
    assert resp.status_code == 422
    # ValueError raised before list_plugins — no subprocess mock invoked
    assert called == ["not-a-url"]


async def test_add_marketplace_cli_error(async_client, monkeypatch):
    import app.api.plugins as api_mod

    async def _fail(source):
        raise PluginCliError(["claude", "plugin", "marketplace", "add", source], 1, "failed")

    monkeypatch.setattr(api_mod, "add_marketplace", _fail)

    resp = await async_client.post(
        "/api/plugins/marketplaces", json={"source": "https://example.com"}
    )
    assert resp.status_code == 502
    body = resp.json()
    assert "stderr" in body["detail"]


# ---------------------------------------------------------------------------
# DELETE /api/plugins/marketplaces/{name}
# ---------------------------------------------------------------------------


async def test_remove_marketplace_happy(async_client, monkeypatch):
    import app.api.plugins as api_mod

    async def _fake_remove_marketplace(name):
        return []

    async def _fake_list_plugins():
        from app.models import PluginsResponse
        return PluginsResponse()

    monkeypatch.setattr(api_mod, "remove_marketplace", _fake_remove_marketplace)
    monkeypatch.setattr(api_mod, "list_plugins", _fake_list_plugins)

    resp = await async_client.delete("/api/plugins/marketplaces/my-market")
    assert resp.status_code == 200
    data = resp.json()
    # Must return PluginsResponse shape
    assert "installed" in data
    assert "available" in data
    assert "marketplaces" in data


async def test_remove_marketplace_invalid_name(async_client, monkeypatch):
    import app.api.plugins as api_mod

    called = []

    async def _fail(name):
        called.append(name)
        raise ValueError(f"Invalid marketplace name: {name!r}")

    monkeypatch.setattr(api_mod, "remove_marketplace", _fail)

    resp = await async_client.delete("/api/plugins/marketplaces/bad!name")
    assert resp.status_code == 422
    assert called == ["bad!name"]


async def test_remove_marketplace_cli_error(async_client, monkeypatch):
    import app.api.plugins as api_mod

    async def _fail(name):
        raise PluginCliError(
            ["claude", "plugin", "marketplace", "remove", name], 1, "not found"
        )

    monkeypatch.setattr(api_mod, "remove_marketplace", _fail)

    resp = await async_client.delete("/api/plugins/marketplaces/missing")
    assert resp.status_code == 502
    body = resp.json()
    assert "stderr" in body["detail"]
