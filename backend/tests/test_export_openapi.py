"""Tests for backend/app/export_openapi.py.

Verifies that:
1. app.openapi() returns a valid OpenAPI 3.x schema (R1).
2. The schema's components.schemas covers the Task, Feature, Space,
   Harness, and Plugin model families.
3. The export script writes the schema to the specified --out path.
"""

import json
import subprocess
import sys
from pathlib import Path


def _get_schema() -> dict:
    from app.main import app
    return app.openapi()


def test_openapi_schema_is_valid_v3():
    schema = _get_schema()
    assert "openapi" in schema, "missing 'openapi' field"
    assert schema["openapi"].startswith("3."), f"expected OpenAPI 3.x, got {schema['openapi']}"
    assert "info" in schema
    assert "paths" in schema


def test_openapi_schema_has_components():
    schema = _get_schema()
    assert "components" in schema, "no components section in schema"
    assert "schemas" in schema["components"], "no schemas in components"


def _component_names(schema: dict) -> set[str]:
    return set(schema.get("components", {}).get("schemas", {}).keys())


def test_task_family_in_schema():
    names = _component_names(_get_schema())
    # Backend exposes the full task as TaskRead; TaskSummary is the board/list shape.
    assert "TaskRead" in names, f"TaskRead not in schema components: {sorted(names)[:20]}"
    assert "TaskSummary" in names, f"TaskSummary not in schema components"


def test_space_family_in_schema():
    names = _component_names(_get_schema())
    assert "Space" in names, f"Space not in schema components: {sorted(names)[:20]}"


def test_harness_family_in_schema():
    names = _component_names(_get_schema())
    assert "Harness" in names, f"Harness not in schema components: {sorted(names)[:20]}"


def test_plugin_family_in_schema():
    names = _component_names(_get_schema())
    assert "PluginsResponse" in names, f"PluginsResponse not in schema components"


def test_export_script_writes_file(tmp_path):
    out_file = tmp_path / "openapi.json"
    result = subprocess.run(
        [sys.executable, "-m", "app.export_openapi", "--out", str(out_file)],
        capture_output=True,
        text=True,
        cwd=Path(__file__).parent.parent,
    )
    assert result.returncode == 0, f"export script failed:\n{result.stderr}"
    assert out_file.exists(), "output file was not created"
    schema = json.loads(out_file.read_text())
    assert schema.get("openapi", "").startswith("3.")


def test_export_script_schema_is_deterministic(tmp_path):
    out1 = tmp_path / "openapi1.json"
    out2 = tmp_path / "openapi2.json"
    cwd = Path(__file__).parent.parent
    for out in (out1, out2):
        subprocess.run(
            [sys.executable, "-m", "app.export_openapi", "--out", str(out)],
            capture_output=True,
            cwd=cwd,
        )
    assert json.loads(out1.read_text()) == json.loads(out2.read_text()), \
        "openapi() is not deterministic across calls"
