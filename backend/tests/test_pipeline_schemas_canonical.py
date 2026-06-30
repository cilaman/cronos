"""Assert that schemas/ has moved to packages/delivery-workflow/lib/schemas/ (single canonical source)."""
import pathlib
import yaml

LIB_SCHEMAS = pathlib.Path("/data/spaces/cronos-development/packages/delivery-workflow/lib/schemas")
BACKEND_SCHEMAS = pathlib.Path("/data/spaces/cronos-development/backend/app/pipeline/schemas")
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
