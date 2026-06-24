from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
import jsonschema

_SCHEMA_PATH = Path(__file__).parent / "schemas" / "delivery.workflow.schema.yaml"

_schema: dict[str, Any] | None = None


def _get_schema() -> dict[str, Any]:
    global _schema
    if _schema is None:
        _schema = yaml.safe_load(_SCHEMA_PATH.read_text())
    return _schema


def load_spec(path: str | Path) -> dict[str, Any]:
    """Load and validate a delivery.workflow.yaml from a file path.

    Raises ValueError with a non-empty message if the spec is invalid.
    Returns the parsed dict on success.
    """
    raw = yaml.safe_load(Path(path).read_text())
    return _validate(raw)


def loads_spec(text: str) -> dict[str, Any]:
    """Load and validate a delivery.workflow.yaml from a YAML string.

    Raises ValueError with a non-empty message if the spec is invalid.
    Returns the parsed dict on success.
    """
    raw = yaml.safe_load(text)
    return _validate(raw)


def _validate(data: Any) -> dict[str, Any]:
    """Validate *data* against the delivery/v1 schema.

    Raises ValueError with a descriptive message listing all errors found.
    """
    schema = _get_schema()
    validator = jsonschema.Draft7Validator(schema)
    errors = sorted(validator.iter_errors(data), key=lambda e: e.path)
    if errors:
        msgs = [f"{'.'.join(str(p) for p in e.absolute_path) or '<root>'}: {e.message}" for e in errors]
        raise ValueError("Invalid delivery/v1 spec:\n" + "\n".join(f"  - {m}" for m in msgs))
    return data  # type: ignore[return-value]
