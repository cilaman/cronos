"""
backend/tests/test_harness_acceptance — R14 end-to-end acceptance scenario.

Executes the analyst's R14 acceptance scenario verbatim:

  1. POST a 3-node / 2-edge harness to the API.
  2. GET it back by name.
  3. Assert field-for-field equality between POST response and GET response.
  4. Load the on-disk YAML file at {space_dir}/.cronos/harnesses/<slug>.yml.
  5. Parse the YAML and construct a Harness model from it.
  6. Assert the on-disk Harness equals the GET response.

The test uses an isolated FastAPI app (same pattern as test_api_harnesses.py) so
it does not depend on the full main.py lifespan fixture.  The SpaceStore and
HarnessStore are wired directly onto app.state.

Node types used:
  - Node 1: type=trigger  (ports: "out" for the outbound edge)
  - Node 2: type=agent    (ports: "in", "out")
  - Node 3: type=decision (ports: "in", "yes", "no")

Edges:
  - trigger → agent  (trigger.out → agent.in)
  - agent   → decision (agent.out → decision.in)
"""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest
import yaml
from fastapi import Depends, FastAPI

from app.api.harnesses import router as harnesses_router
from app.auth import require_auth
from app.harnesses import Harness, HarnessStore
from app.harnesses.store import slugify_name
from app.space_storage import SpaceStore

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SPACE_ID = "acceptance-space"
_BASE_URL = f"/api/spaces/{SPACE_ID}/harnesses"
_auth = [Depends(require_auth)]

# ---------------------------------------------------------------------------
# 3-node / 2-edge harness payload (R14 scenario)
# ---------------------------------------------------------------------------

_HARNESS_PAYLOAD = {
    "name": "Acceptance Flow",
    "description": "R14 acceptance scenario harness",
    "nodes": [
        {
            "id": "n1",
            "type": "trigger",
            "position": {"x": 0.0, "y": 100.0},
            "ports": {
                "out": {"direction": "output", "label": "trigger-out"},
            },
            "data": {"schedule": "*/5 * * * *", "enabled": True, "retries": 3},
            "label": "Entry Trigger",
        },
        {
            "id": "n2",
            "type": "agent",
            "position": {"x": 200.0, "y": 100.0},
            "ports": {
                "in": {"direction": "input"},
                "out": {"direction": "output"},
            },
            "data": {"agent_name": "pipeline-implementor", "timeout_s": 300},
            "label": "Implementor Agent",
        },
        {
            "id": "n3",
            "type": "decision",
            "position": {"x": 400.0, "y": 100.0},
            "ports": {
                "in": {"direction": "input"},
                "yes": {"direction": "output"},
                "no": {"direction": "output"},
            },
            "data": {"condition": "output.status == 'done'"},
            "label": "Outcome Decision",
        },
    ],
    "edges": [
        {
            "id": "e1",
            "source": {"node_id": "n1", "port_id": "out"},
            "target": {"node_id": "n2", "port_id": "in"},
            "condition": None,
        },
        {
            "id": "e2",
            "source": {"node_id": "n2", "port_id": "out"},
            "target": {"node_id": "n3", "port_id": "in"},
            "condition": None,
        },
    ],
    "variables": {
        "env": "production",
        "max_retries": 5,
        "debug": False,
        "threshold": 0.75,
    },
    "version": "1.0",
}

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_test_app(space_store: SpaceStore, harness_store: HarnessStore) -> FastAPI:
    """Minimal FastAPI app with only the harnesses router — mirrors test_api_harnesses.py."""
    _app = FastAPI()
    _app.include_router(harnesses_router, dependencies=_auth)
    _app.state.space_store = space_store
    _app.state.harness_store = harness_store
    return _app


@pytest.fixture
async def space_store(tmp_path: Path) -> SpaceStore:
    """SpaceStore with one pre-created space; spaces_dir = tmp_path/spaces."""
    store = SpaceStore(tmp_path / "spaces")
    await store.create(
        name="Acceptance Space",
        color="#15803D",
        space_id=SPACE_ID,
    )
    return store


@pytest.fixture
def harness_store() -> HarnessStore:
    return HarnessStore()


@pytest.fixture
async def h_client(space_store: SpaceStore, harness_store: HarnessStore):
    """AsyncClient backed by the isolated test app."""
    _app = _make_test_app(space_store, harness_store)
    transport = httpx.ASGITransport(app=_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


# ---------------------------------------------------------------------------
# Helper: resolve the space_dir the same way the API does
# ---------------------------------------------------------------------------


def _space_dir(space_store: SpaceStore) -> Path:
    """Return the space directory path that the API router will use."""
    return space_store.spaces_dir / SPACE_ID


# ---------------------------------------------------------------------------
# R14 Acceptance scenario
# ---------------------------------------------------------------------------


async def test_post_get_disk_round_trip(
    h_client: httpx.AsyncClient,
    space_store: SpaceStore,
) -> None:
    """Full R14 acceptance scenario: POST → GET → on-disk YAML round-trip.

    Steps:
      1. POST a 3-node/2-edge harness to the API.
      2. GET it back by name.
      3. Assert field-for-field equality between POST and GET responses.
      4. Load the on-disk YAML file.
      5. Construct a Harness model from the YAML.
      6. Assert on-disk Harness equals the GET response (field-for-field).
    """
    # Step 1 — POST
    post_resp = await h_client.post(_BASE_URL, json=_HARNESS_PAYLOAD)
    assert post_resp.status_code == 201, f"POST failed: {post_resp.text}"
    post_body = post_resp.json()

    # Basic shape assertions
    assert post_body["name"] == "Acceptance Flow"
    assert post_body["description"] == "R14 acceptance scenario harness"
    assert len(post_body["nodes"]) == 3
    assert len(post_body["edges"]) == 2
    assert "created_at" in post_body
    assert "updated_at" in post_body

    # Node types
    node_types = {n["id"]: n["type"] for n in post_body["nodes"]}
    assert node_types["n1"] == "trigger"
    assert node_types["n2"] == "agent"
    assert node_types["n3"] == "decision"

    # Edge topology
    edges = {e["id"]: e for e in post_body["edges"]}
    assert edges["e1"]["source"]["node_id"] == "n1"
    assert edges["e1"]["target"]["node_id"] == "n2"
    assert edges["e2"]["source"]["node_id"] == "n2"
    assert edges["e2"]["target"]["node_id"] == "n3"

    # Step 2 — GET
    get_resp = await h_client.get(f"{_BASE_URL}/Acceptance Flow")
    assert get_resp.status_code == 200, f"GET failed: {get_resp.text}"
    get_body = get_resp.json()

    # Step 3 — POST response equals GET response (field-for-field)
    assert post_body == get_body, (
        "POST response and GET response differ:\n"
        f"  POST: {post_body}\n"
        f"  GET:  {get_body}"
    )

    # Step 4 — Load on-disk YAML
    slug = slugify_name("Acceptance Flow")
    space_d = _space_dir(space_store)
    yaml_path = space_d / ".cronos" / "harnesses" / f"{slug}.yml"

    assert yaml_path.exists(), (
        f"Expected harness YAML file not found at {yaml_path}.\n"
        f"Directory listing: {list(yaml_path.parent.iterdir()) if yaml_path.parent.exists() else 'parent dir missing'}"
    )

    raw = yaml_path.read_text(encoding="utf-8")
    disk_data = yaml.safe_load(raw)
    assert isinstance(disk_data, dict), f"YAML content is not a dict: {disk_data!r}"

    # Step 5 — Construct Harness from the YAML dict
    disk_harness = Harness.model_validate(disk_data)

    # Step 6 — On-disk Harness equals the GET response (field-for-field)
    # Compare via model_dump(mode='json') to normalise datetimes and enums
    disk_dict = disk_harness.model_dump(mode="json")
    assert disk_dict == get_body, (
        "On-disk Harness and GET response differ:\n"
        f"  disk: {disk_dict}\n"
        f"  GET:  {get_body}"
    )


# ---------------------------------------------------------------------------
# Supplementary: verify slugify predicts the correct filename
# ---------------------------------------------------------------------------


async def test_slugify_produces_expected_filename(
    h_client: httpx.AsyncClient,
    space_store: SpaceStore,
) -> None:
    """Verify that slugify_name('Acceptance Flow') predicts the on-disk filename."""
    await h_client.post(_BASE_URL, json=_HARNESS_PAYLOAD)

    expected_slug = slugify_name("Acceptance Flow")
    assert expected_slug == "acceptance-flow", (
        f"slugify_name produced unexpected slug: {expected_slug!r}"
    )

    yaml_path = (
        _space_dir(space_store)
        / ".cronos"
        / "harnesses"
        / f"{expected_slug}.yml"
    )
    assert yaml_path.exists(), f"Expected file not found: {yaml_path}"


# ---------------------------------------------------------------------------
# Supplementary: YAML round-trip preserves mixed types in data / variables
# ---------------------------------------------------------------------------


async def test_yaml_round_trip_type_fidelity(
    h_client: httpx.AsyncClient,
    space_store: SpaceStore,
) -> None:
    """Verify that YAML round-trip does not coerce int/float/bool/str scalar types.

    This guards against the high-severity R8 risk identified in the design report:
    yaml.safe_dump + yaml.safe_load coercing numeric strings or altering scalars.
    """
    await h_client.post(_BASE_URL, json=_HARNESS_PAYLOAD)

    slug = slugify_name("Acceptance Flow")
    yaml_path = (
        _space_dir(space_store) / ".cronos" / "harnesses" / f"{slug}.yml"
    )
    raw = yaml_path.read_text(encoding="utf-8")
    disk_data = yaml.safe_load(raw)

    # Verify node n1 data types: int + bool + str
    n1_data = next(n["data"] for n in disk_data["nodes"] if n["id"] == "n1")
    assert isinstance(n1_data["schedule"], str), "schedule should be str"
    assert isinstance(n1_data["enabled"], bool), "enabled should be bool"
    assert isinstance(n1_data["retries"], int), "retries should be int"

    # Verify node n2 data types: str + int
    n2_data = next(n["data"] for n in disk_data["nodes"] if n["id"] == "n2")
    assert isinstance(n2_data["agent_name"], str), "agent_name should be str"
    assert isinstance(n2_data["timeout_s"], int), "timeout_s should be int"

    # Verify top-level variables types: str + int + bool + float
    variables = disk_data["variables"]
    assert isinstance(variables["env"], str), "env should be str"
    assert isinstance(variables["max_retries"], int), "max_retries should be int"
    assert isinstance(variables["debug"], bool), "debug should be bool"
    assert isinstance(variables["threshold"], float), "threshold should be float"
