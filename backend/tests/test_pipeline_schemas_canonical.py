"""Assert that schemas/ has moved to packages/delivery-workflow/lib/schemas/ (single canonical source)."""
import pathlib
import yaml

# Derive paths from the repo layout (this file is backend/tests/…) so the test
# is portable across machines/CI instead of pinned to one deployment's path.
_REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
LIB_SCHEMAS = _REPO_ROOT / "packages" / "delivery-workflow" / "lib" / "schemas"
BACKEND_SCHEMAS = _REPO_ROOT / "backend" / "app" / "pipeline" / "schemas"
EXPECTED = {
    "research", "analysis", "design", "implementation",
    "test", "review", "doc", "retro",
}


def test_lib_schemas_has_all_eight():
    found = {p.stem.replace(".schema", "") for p in LIB_SCHEMAS.glob("*.schema.yaml")}
    assert found == EXPECTED, f"lib/schemas missing: {EXPECTED - found}"


def test_backend_schemas_has_no_yaml():
    yaml_files = list(BACKEND_SCHEMAS.glob("*.yaml"))
    assert yaml_files == [], f"backend/app/pipeline/schemas/ still has .yaml: {yaml_files}"


def test_schemas_are_valid_yaml():
    for schema_file in LIB_SCHEMAS.glob("*.schema.yaml"):
        with open(schema_file) as f:
            data = yaml.safe_load(f)
        assert data is not None, f"{schema_file} parsed as None"
        assert "properties" in data or "required" in data or "type" in data, \
            f"{schema_file} does not look like a JSON schema"
