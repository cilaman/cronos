"""Tests for Plugin Management Pydantic models (I1)."""
import pytest
from app.models import (
    PluginComponent,
    PluginEntry,
    MarketplacePluginEntry,
    MarketplaceEntry,
    PluginsResponse,
)


class TestPluginComponent:
    def test_valid_agent_kind(self):
        c = PluginComponent(name="my-agent", kind="agent")
        assert c.name == "my-agent"
        assert c.kind == "agent"

    def test_valid_skill_kind(self):
        c = PluginComponent(name="my-skill", kind="skill")
        assert c.kind == "skill"

    def test_valid_command_kind(self):
        c = PluginComponent(name="my-command", kind="command")
        assert c.kind == "command"

    def test_invalid_kind_raises(self):
        with pytest.raises(Exception):
            PluginComponent(name="x", kind="invalid")

    def test_name_required(self):
        with pytest.raises(Exception):
            PluginComponent(kind="agent")


class TestPluginEntry:
    def test_minimal(self):
        p = PluginEntry(id="myplugin@default", name="myplugin")
        assert p.id == "myplugin@default"
        assert p.name == "myplugin"
        assert p.scope == "user"
        assert p.enabled is True
        assert p.components == []
        assert p.marketplace is None
        assert p.version is None
        assert p.installPath is None
        assert p.installedAt is None
        assert p.lastUpdated is None

    def test_with_components(self):
        comp = PluginComponent(name="agent1", kind="agent")
        p = PluginEntry(
            id="myplugin@default",
            name="myplugin",
            components=[comp],
            enabled=False,
            scope="project",
        )
        assert len(p.components) == 1
        assert p.components[0].kind == "agent"
        assert p.enabled is False
        assert p.scope == "project"

    def test_full_fields(self):
        p = PluginEntry(
            id="myplugin@mymarket",
            name="myplugin",
            marketplace="mymarket",
            version="1.2.3",
            scope="user",
            enabled=True,
            installPath="/home/user/.claude/plugins/myplugin",
            installedAt="2024-01-01T00:00:00Z",
            lastUpdated="2024-06-01T00:00:00Z",
        )
        assert p.marketplace == "mymarket"
        assert p.version == "1.2.3"
        assert p.installPath == "/home/user/.claude/plugins/myplugin"

    def test_id_required(self):
        with pytest.raises(Exception):
            PluginEntry(name="myplugin")

    def test_name_required(self):
        with pytest.raises(Exception):
            PluginEntry(id="myplugin@default")


class TestMarketplacePluginEntry:
    def test_minimal(self):
        e = MarketplacePluginEntry(pluginId="myplugin", name="My Plugin")
        assert e.pluginId == "myplugin"
        assert e.name == "My Plugin"
        assert e.description is None
        assert e.marketplaceName is None
        assert e.source is None
        assert e.installCount == 0

    def test_full_fields(self):
        e = MarketplacePluginEntry(
            pluginId="myplugin",
            name="My Plugin",
            description="A great plugin",
            marketplaceName="official",
            source="https://example.com/plugins",
            installCount=42,
        )
        assert e.description == "A great plugin"
        assert e.installCount == 42

    def test_plugin_id_required(self):
        with pytest.raises(Exception):
            MarketplacePluginEntry(name="My Plugin")

    def test_name_required(self):
        with pytest.raises(Exception):
            MarketplacePluginEntry(pluginId="myplugin")


class TestMarketplaceEntry:
    def test_valid(self):
        m = MarketplaceEntry(name="official", source="https://example.com/plugins")
        assert m.name == "official"
        assert m.source == "https://example.com/plugins"

    def test_name_required(self):
        with pytest.raises(Exception):
            MarketplaceEntry(source="https://example.com")

    def test_source_required(self):
        with pytest.raises(Exception):
            MarketplaceEntry(name="official")


class TestPluginsResponse:
    def test_empty_defaults(self):
        r = PluginsResponse()
        assert r.installed == []
        assert r.available == []
        assert r.marketplaces == []

    def test_with_data(self):
        plugin = PluginEntry(id="p@m", name="p")
        avail = MarketplacePluginEntry(pluginId="p", name="p")
        market = MarketplaceEntry(name="m", source="https://m.example.com")
        r = PluginsResponse(installed=[plugin], available=[avail], marketplaces=[market])
        assert len(r.installed) == 1
        assert len(r.available) == 1
        assert len(r.marketplaces) == 1

    def test_serialization_roundtrip(self):
        r = PluginsResponse(
            installed=[PluginEntry(id="x@y", name="x", enabled=True)],
            available=[MarketplacePluginEntry(pluginId="x", name="x", installCount=5)],
            marketplaces=[MarketplaceEntry(name="y", source="https://y.com")],
        )
        data = r.model_dump()
        r2 = PluginsResponse(**data)
        assert r2.installed[0].id == "x@y"
        assert r2.available[0].installCount == 5
        assert r2.marketplaces[0].name == "y"
