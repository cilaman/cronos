"""
Tests for the 8 delivery/v1 artifact-class delivery_status schemas.

Each schema validates the delivery_status block (structured return)
for a specific produces class. Tests cover:
  - Valid blocks pass validation
  - Missing required fields fail validation
  - Wrong produces constant fails validation
  - Invalid status values fail validation
"""

from __future__ import annotations

import pathlib

import jsonschema
import pytest
import yaml

SCHEMAS_DIR = pathlib.Path(__file__).parent.parent / "schemas"

ARTIFACT_CLASSES = [
    "research",
    "analysis",
    "design",
    "frontend",
    "implementation",
    "review",
    "test",
    "doc",
]


def load_schema(class_name: str) -> dict:
    path = SCHEMAS_DIR / f"{class_name}.schema.yaml"
    return yaml.safe_load(path.read_text())


def validate(instance: dict, schema: dict) -> None:
    """Validate instance against schema using draft-07."""
    validator_cls = jsonschema.Draft7Validator
    validator = validator_cls(schema)
    errors = list(validator.iter_errors(instance))
    if errors:
        messages = [e.message for e in errors]
        raise jsonschema.ValidationError("\n".join(messages))


# --- Fixtures: minimal valid blocks per class ---

def _base_block(produces: str, **extra_fields) -> dict:
    return {
        "status": "done",
        "artifact_paths": [f".cronos/pipeline/example/{produces}-report.md"],
        "produces": produces,
        "fields": extra_fields or {},
        "open_questions": [],
        "telemetry": {"tokens": 100, "usd": 0.01, "seconds": 5.0},
    }


VALID_BLOCKS = {
    "research": _base_block(
        "research",
        memory_hits=3,
        critical_blockers=["G0.1", "G0.3"],
        implementation_status="60% complete",
    ),
    "analysis": _base_block(
        "analysis",
        has_ui=False,
        scope="Backend-only change",
        req_ids=["REQ-001", "REQ-002"],
    ),
    "design": _base_block(
        "design",
        iterations_planned=5,
        risks_count=2,
        has_ui=False,
    ),
    "frontend": _base_block(
        "frontend",
        component_names=["TaskCard", "BoardPage"],
        pages=["/board"],
        responsive=True,
    ),
    "implementation": _base_block(
        "implementation",
        iteration_id="I4",
        files_changed=["packages/delivery-workflow/lib/delivery_status.py"],
        validation_command_passed=True,
        diff_lines_added=80,
        diff_lines_removed=0,
    ),
    "review": _base_block(
        "review",
        verdict="pass",
        findings_count=0,
        attempt=1,
    ),
    "test": _base_block(
        "test",
        passed=True,
        coverage_pct=83.5,
        tests_run=142,
        tests_failed=0,
    ),
    "doc": _base_block(
        "doc",
        docs_updated=["docs/delivery-pipeline/README.md"],
        intentionally_not_updated=[],
        modules_documented=3,
    ),
}


# --- Schema loading ---

class TestSchemaFiles:
    @pytest.mark.parametrize("class_name", ARTIFACT_CLASSES)
    def test_schema_file_exists(self, class_name):
        path = SCHEMAS_DIR / f"{class_name}.schema.yaml"
        assert path.exists(), f"Missing schema: {path}"

    @pytest.mark.parametrize("class_name", ARTIFACT_CLASSES)
    def test_schema_is_valid_yaml(self, class_name):
        schema = load_schema(class_name)
        assert isinstance(schema, dict)
        assert "$schema" in schema

    @pytest.mark.parametrize("class_name", ARTIFACT_CLASSES)
    def test_schema_has_produces_const(self, class_name):
        schema = load_schema(class_name)
        produces_prop = schema["properties"]["produces"]
        assert produces_prop.get("const") == class_name, (
            f"{class_name}.schema.yaml: produces const should be '{class_name}'"
        )


# --- Valid block acceptance ---

class TestValidBlocks:
    @pytest.mark.parametrize("class_name", ARTIFACT_CLASSES)
    def test_valid_block_passes(self, class_name):
        schema = load_schema(class_name)
        validate(VALID_BLOCKS[class_name], schema)

    @pytest.mark.parametrize("class_name", ARTIFACT_CLASSES)
    def test_status_blocked_is_valid(self, class_name):
        schema = load_schema(class_name)
        block = dict(VALID_BLOCKS[class_name])
        block["status"] = "blocked"
        validate(block, schema)

    @pytest.mark.parametrize("class_name", ARTIFACT_CLASSES)
    def test_status_needs_fix_is_valid(self, class_name):
        schema = load_schema(class_name)
        block = dict(VALID_BLOCKS[class_name])
        block["status"] = "needs_fix"
        validate(block, schema)

    @pytest.mark.parametrize("class_name", ARTIFACT_CLASSES)
    def test_open_questions_optional(self, class_name):
        schema = load_schema(class_name)
        block = {k: v for k, v in VALID_BLOCKS[class_name].items() if k != "open_questions"}
        validate(block, schema)

    @pytest.mark.parametrize("class_name", ARTIFACT_CLASSES)
    def test_extra_fields_allowed_in_fields(self, class_name):
        schema = load_schema(class_name)
        block = dict(VALID_BLOCKS[class_name])
        block["fields"] = dict(block["fields"])
        block["fields"]["custom_routing_key"] = "some_value"
        # analysis requires has_ui; make sure it's still present
        if class_name == "analysis":
            block["fields"]["has_ui"] = False
        if class_name == "review":
            block["fields"]["verdict"] = "pass"
        validate(block, schema)


# --- Invalid block rejection ---

class TestInvalidBlocks:
    @pytest.mark.parametrize("class_name", ARTIFACT_CLASSES)
    def test_wrong_produces_rejected(self, class_name):
        schema = load_schema(class_name)
        block = dict(VALID_BLOCKS[class_name])
        block["produces"] = "wrong_class"
        with pytest.raises(jsonschema.ValidationError):
            validate(block, schema)

    @pytest.mark.parametrize("class_name", ARTIFACT_CLASSES)
    def test_invalid_status_rejected(self, class_name):
        schema = load_schema(class_name)
        block = dict(VALID_BLOCKS[class_name])
        block["status"] = "DONE"  # uppercase — delivery/v1 uses lowercase
        with pytest.raises(jsonschema.ValidationError):
            validate(block, schema)

    @pytest.mark.parametrize("class_name", ARTIFACT_CLASSES)
    def test_missing_status_rejected(self, class_name):
        schema = load_schema(class_name)
        block = {k: v for k, v in VALID_BLOCKS[class_name].items() if k != "status"}
        with pytest.raises(jsonschema.ValidationError):
            validate(block, schema)

    @pytest.mark.parametrize("class_name", ARTIFACT_CLASSES)
    def test_missing_telemetry_rejected(self, class_name):
        schema = load_schema(class_name)
        block = {k: v for k, v in VALID_BLOCKS[class_name].items() if k != "telemetry"}
        with pytest.raises(jsonschema.ValidationError):
            validate(block, schema)

    @pytest.mark.parametrize("class_name", ARTIFACT_CLASSES)
    def test_partial_telemetry_rejected(self, class_name):
        schema = load_schema(class_name)
        block = dict(VALID_BLOCKS[class_name])
        block["telemetry"] = {"tokens": 100}  # missing usd and seconds
        with pytest.raises(jsonschema.ValidationError):
            validate(block, schema)

    def test_analysis_missing_has_ui_rejected(self):
        schema = load_schema("analysis")
        block = _base_block("analysis", scope="some scope")
        with pytest.raises(jsonschema.ValidationError):
            validate(block, schema)

    def test_review_missing_verdict_rejected(self):
        schema = load_schema("review")
        block = _base_block("review", findings_count=0)
        with pytest.raises(jsonschema.ValidationError):
            validate(block, schema)

    def test_review_invalid_verdict_rejected(self):
        schema = load_schema("review")
        block = _base_block("review", verdict="partial")
        with pytest.raises(jsonschema.ValidationError):
            validate(block, schema)

    def test_review_invalid_finding_class_rejected(self):
        schema = load_schema("review")
        block = _base_block("review", verdict="needs_fix", finding_class="unknown")
        with pytest.raises(jsonschema.ValidationError):
            validate(block, schema)

    def test_implementation_invalid_iteration_id_rejected(self):
        schema = load_schema("implementation")
        block = _base_block("implementation", iteration_id="i4")  # lowercase — invalid
        with pytest.raises(jsonschema.ValidationError):
            validate(block, schema)
