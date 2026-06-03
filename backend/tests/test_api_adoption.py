from __future__ import annotations

"""Tests for app/api/adoption.py and the adopted-tools branch of app/api/tools.py.

Covers the adopt/unadopt REST endpoints (mocking the discovery-backed
``adopt``/``unadopt`` functions at the API-module boundary) and the
``adopted`` field of ``GET /api/spaces/{id}/tools`` (driven by real
manifest.yml round-trips in the test's tmp space dir).
"""

from datetime import UTC, datetime

import pytest

from app.api import adoption as adoption_api
from app.tools.adoption import (
    AdoptionManifest,
    AlreadyAdopted,
    ItemNotFound,
    NotAdopted,
    _write_manifest,
    recompute_local_sha,
)

from .conftest import SPACE_ID


def _make_manifest(**overrides) -> AdoptionManifest:
    """A baseline pristine manifest; base_sha == local_sha, evolved False."""
    base = {
        "source_url": "https://github.com/acme/tools",
        "source_slug": "acme-tools",
        "source_path": "agents/coder.md",
        "source_sha": "deadbeef",
        "adopted_at": datetime(2026, 6, 3, 12, 0, 0, tzinfo=UTC),
        "base_sha": "abc123",
        "local_sha": "abc123",
        "evolved": False,
        "kind": "agents",
        "name": "coder",
    }
    base.update(overrides)
    return AdoptionManifest(**base)


# ---------------------------------------------------------------------------
# POST /api/spaces/{id}/adopt
# ---------------------------------------------------------------------------


async def test_adopt_success_returns_201_and_manifest(async_client, monkeypatch):
    # Arrange: stub the discovery-backed adopt to return a pristine manifest.
    manifest = _make_manifest()

    async def fake_adopt(space_id, source_slug, kind, name):
        return manifest

    monkeypatch.setattr(adoption_api, "adopt", fake_adopt)

    # Act
    resp = await async_client.post(
        f"/api/spaces/{SPACE_ID}/adopt",
        json={"source_slug": "acme-tools", "kind": "agents", "name": "coder"},
    )

    # Assert
    assert resp.status_code == 201
    body = resp.json()
    assert body["source_slug"] == "acme-tools"
    assert body["kind"] == "agents"
    assert body["name"] == "coder"
    assert body["base_sha"] == body["local_sha"]
    assert body["evolved"] is False


async def test_adopt_unknown_space_returns_404(async_client, monkeypatch):
    # Arrange: adopt must never be reached when the space is missing.
    async def fail_adopt(*args, **kwargs):  # pragma: no cover - should not run
        raise AssertionError("adopt() called for a missing space")

    monkeypatch.setattr(adoption_api, "adopt", fail_adopt)

    # Act
    resp = await async_client.post(
        "/api/spaces/nonexistent-space/adopt",
        json={"source_slug": "acme-tools", "kind": "agents", "name": "coder"},
    )

    # Assert
    assert resp.status_code == 404


async def test_adopt_already_adopted_returns_409(async_client, monkeypatch):
    # Arrange
    async def fake_adopt(space_id, source_slug, kind, name):
        raise AlreadyAdopted(f"{kind}/{name!r} already adopted")

    monkeypatch.setattr(adoption_api, "adopt", fake_adopt)

    # Act
    resp = await async_client.post(
        f"/api/spaces/{SPACE_ID}/adopt",
        json={"source_slug": "acme-tools", "kind": "agents", "name": "coder"},
    )

    # Assert
    assert resp.status_code == 409


async def test_adopt_item_not_in_discovery_returns_404(async_client, monkeypatch):
    # Arrange
    async def fake_adopt(space_id, source_slug, kind, name):
        raise ItemNotFound(f"No discovered {kind!r} named {name!r}")

    monkeypatch.setattr(adoption_api, "adopt", fake_adopt)

    # Act
    resp = await async_client.post(
        f"/api/spaces/{SPACE_ID}/adopt",
        json={"source_slug": "acme-tools", "kind": "agents", "name": "ghost"},
    )

    # Assert
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /api/spaces/{id}/adopt/{kind}/{name}
# ---------------------------------------------------------------------------


async def test_unadopt_success_returns_204(async_client, monkeypatch):
    # Arrange: capture the args the endpoint forwards to unadopt.
    called: dict = {}

    async def fake_unadopt(space_id, kind, name):
        called["args"] = (space_id, kind, name)

    monkeypatch.setattr(adoption_api, "unadopt", fake_unadopt)

    # Act
    resp = await async_client.delete(f"/api/spaces/{SPACE_ID}/adopt/agents/coder")

    # Assert
    assert resp.status_code == 204
    assert resp.content == b""
    assert called["args"] == (SPACE_ID, "agents", "coder")


async def test_unadopt_unknown_space_returns_404(async_client, monkeypatch):
    # Arrange: unadopt must never run for a missing space.
    async def fail_unadopt(*args, **kwargs):  # pragma: no cover - should not run
        raise AssertionError("unadopt() called for a missing space")

    monkeypatch.setattr(adoption_api, "unadopt", fail_unadopt)

    # Act
    resp = await async_client.delete("/api/spaces/nonexistent-space/adopt/agents/coder")

    # Assert
    assert resp.status_code == 404


async def test_unadopt_item_not_adopted_returns_404(async_client, monkeypatch):
    # Arrange
    async def fake_unadopt(space_id, kind, name):
        raise NotAdopted(f"{kind}/{name!r} is not adopted")

    monkeypatch.setattr(adoption_api, "unadopt", fake_unadopt)

    # Act
    resp = await async_client.delete(f"/api/spaces/{SPACE_ID}/adopt/agents/missing")

    # Assert
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /api/spaces/{id}/tools — adopted field
# ---------------------------------------------------------------------------


def _adopt_dir(tmp_spaces_dir, kind: str, name: str):
    return tmp_spaces_dir / SPACE_ID / ".cronos" / "tools" / kind / name


async def test_tools_no_adopted_items_returns_empty_list(async_client, space_store):
    # Act
    resp = await async_client.get(f"/api/spaces/{SPACE_ID}/tools")

    # Assert
    assert resp.status_code == 200
    assert resp.json()["adopted"] == []


async def test_tools_after_adopt_shows_pristine(async_client, space_store, tmp_spaces_dir):
    # Arrange: vendor one file and write a pristine manifest (base_sha == local_sha).
    adir = _adopt_dir(tmp_spaces_dir, "agents", "coder")
    adir.mkdir(parents=True, exist_ok=True)
    (adir / "coder.md").write_text("# Coder\nbody\n", encoding="utf-8")
    # local_sha computed by recompute below; seed manifest then recompute to make it accurate.
    _write_manifest(adir / "manifest.yml", _make_manifest())
    m = recompute_local_sha(SPACE_ID, "agents", "coder", spaces_dir=tmp_spaces_dir)
    # Make the recorded baseline match the on-disk content so status is pristine.
    _write_manifest(
        adir / "manifest.yml",
        m.model_copy(update={"base_sha": m.local_sha, "evolved": False}),
    )

    # Act
    resp = await async_client.get(f"/api/spaces/{SPACE_ID}/tools")

    # Assert
    assert resp.status_code == 200
    adopted = resp.json()["adopted"]
    assert len(adopted) == 1
    entry = adopted[0]
    assert entry["kind"] == "agents"
    assert entry["name"] == "coder"
    assert entry["status"] == "pristine"
    assert entry["base_sha"] == entry["local_sha"]


async def test_tools_local_drift_without_evolved_shows_edited(
    async_client, space_store, tmp_spaces_dir
):
    """status='edited' requires local_sha != base_sha AND evolved is False.

    Note: ``recompute_local_sha`` couples ``evolved`` to sha drift (it sets
    ``evolved = local_sha != base_sha``), so once you recompute after an edit
    the entry reports 'evolved', not 'edited'. The 'edited' status from
    ``_derive_status`` is therefore only reachable for a manifest whose
    ``evolved`` flag is still False while the shas differ — that exact state
    is asserted here by writing the manifest directly.
    """
    # Arrange
    adir = _adopt_dir(tmp_spaces_dir, "agents", "coder")
    adir.mkdir(parents=True, exist_ok=True)
    (adir / "coder.md").write_text("# Coder\nlocally changed\n", encoding="utf-8")
    _write_manifest(
        adir / "manifest.yml",
        _make_manifest(base_sha="aaa111", local_sha="bbb222", evolved=False),
    )

    # Act
    resp = await async_client.get(f"/api/spaces/{SPACE_ID}/tools")

    # Assert
    assert resp.status_code == 200
    adopted = resp.json()["adopted"]
    assert len(adopted) == 1
    entry = adopted[0]
    assert entry["status"] == "edited"
    assert entry["local_sha"] != entry["base_sha"]
    assert entry["evolved"] is False


async def test_tools_recompute_after_edit_marks_evolved(
    async_client, space_store, tmp_spaces_dir
):
    """End-to-end drift: editing a vendored file then recomputing flips evolved.

    Documents the real coupling in ``recompute_local_sha`` — a local edit
    surfaces as status='evolved' once drift is recomputed, because the helper
    sets ``evolved = local_sha != base_sha``.
    """
    # Arrange: adopt pristine via a real sha round-trip.
    adir = _adopt_dir(tmp_spaces_dir, "agents", "coder")
    adir.mkdir(parents=True, exist_ok=True)
    (adir / "coder.md").write_text("# Coder\noriginal\n", encoding="utf-8")
    _write_manifest(adir / "manifest.yml", _make_manifest())
    pristine = recompute_local_sha(SPACE_ID, "agents", "coder", spaces_dir=tmp_spaces_dir)
    _write_manifest(
        adir / "manifest.yml",
        pristine.model_copy(update={"base_sha": pristine.local_sha, "evolved": False}),
    )

    # Act: change content on disk, then recompute drift.
    (adir / "coder.md").write_text("# Coder\nlocally changed\n", encoding="utf-8")
    updated = recompute_local_sha(SPACE_ID, "agents", "coder", spaces_dir=tmp_spaces_dir)
    assert updated.evolved is True  # helper couples evolved to drift

    resp = await async_client.get(f"/api/spaces/{SPACE_ID}/tools")

    # Assert
    assert resp.status_code == 200
    adopted = resp.json()["adopted"]
    assert len(adopted) == 1
    entry = adopted[0]
    assert entry["status"] == "evolved"
    assert entry["local_sha"] != entry["base_sha"]


async def test_tools_evolved_flag_shows_evolved(async_client, space_store, tmp_spaces_dir):
    # Arrange: a manifest with evolved=True must win over any sha comparison.
    adir = _adopt_dir(tmp_spaces_dir, "skills", "deploy")
    adir.mkdir(parents=True, exist_ok=True)
    (adir / "SKILL.md").write_text("# Deploy\n", encoding="utf-8")
    _write_manifest(
        adir / "manifest.yml",
        _make_manifest(kind="skills", name="deploy", evolved=True),
    )

    # Act
    resp = await async_client.get(f"/api/spaces/{SPACE_ID}/tools")

    # Assert
    assert resp.status_code == 200
    adopted = resp.json()["adopted"]
    assert len(adopted) == 1
    assert adopted[0]["status"] == "evolved"
    assert adopted[0]["evolved"] is True
