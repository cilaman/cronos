from __future__ import annotations

import logging
from typing import NoReturn

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..models import PluginsResponse
from ..tools.plugins import (
    PluginCliError,
    add_marketplace,
    disable,
    enable,
    install,
    list_plugins,
    remove_marketplace,
    uninstall,
)

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/plugins", tags=["plugins"])


# ---------------------------------------------------------------------------
# Request bodies
# ---------------------------------------------------------------------------


class InstallRequest(BaseModel):
    plugin_id: str
    scope: str = "user"


class PluginIdRequest(BaseModel):
    plugin_id: str


class MarketplaceRequest(BaseModel):
    source: str


# ---------------------------------------------------------------------------
# Error helpers
# ---------------------------------------------------------------------------


def _raise_cli_error(exc: PluginCliError) -> NoReturn:
    raise HTTPException(
        status_code=502,
        detail={"detail": str(exc), "stderr": exc.stderr},
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("", response_model=PluginsResponse)
async def get_plugins() -> PluginsResponse:
    """Return installed plugins (with components), available plugins, and marketplaces."""
    try:
        return await list_plugins()
    except PluginCliError as exc:
        _raise_cli_error(exc)


@router.post("/install", response_model=PluginsResponse)
async def install_plugin(body: InstallRequest) -> PluginsResponse:
    """Install a plugin by id; returns refreshed PluginsResponse."""
    try:
        return await install(body.plugin_id, body.scope)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except PluginCliError as exc:
        _raise_cli_error(exc)


@router.post("/uninstall", response_model=PluginsResponse)
async def uninstall_plugin(body: PluginIdRequest) -> PluginsResponse:
    """Uninstall a plugin by id; returns refreshed PluginsResponse."""
    try:
        return await uninstall(body.plugin_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except PluginCliError as exc:
        _raise_cli_error(exc)


@router.post("/enable", response_model=PluginsResponse)
async def enable_plugin(body: PluginIdRequest) -> PluginsResponse:
    """Enable a disabled plugin; returns refreshed PluginsResponse."""
    try:
        return await enable(body.plugin_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except PluginCliError as exc:
        _raise_cli_error(exc)


@router.post("/disable", response_model=PluginsResponse)
async def disable_plugin(body: PluginIdRequest) -> PluginsResponse:
    """Disable an enabled plugin; returns refreshed PluginsResponse."""
    try:
        return await disable(body.plugin_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except PluginCliError as exc:
        _raise_cli_error(exc)


@router.post("/marketplaces", response_model=PluginsResponse)
async def add_marketplace_endpoint(body: MarketplaceRequest) -> PluginsResponse:
    """Add a marketplace by URL; returns refreshed PluginsResponse."""
    try:
        await add_marketplace(body.source)
        return await list_plugins()
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except PluginCliError as exc:
        _raise_cli_error(exc)


@router.delete("/marketplaces/{name}", response_model=PluginsResponse)
async def remove_marketplace_endpoint(name: str) -> PluginsResponse:
    """Remove a marketplace by name; returns refreshed PluginsResponse."""
    try:
        await remove_marketplace(name)
        return await list_plugins()
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except PluginCliError as exc:
        _raise_cli_error(exc)
