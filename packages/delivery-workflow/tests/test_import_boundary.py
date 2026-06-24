"""Verify that the portable delivery-workflow core never imports app.* or backend.*.

Uses AST scanning — no import-linter process needed in the test environment.
The CI step runs `lint-imports` separately against the .importlinter contract.
"""
import ast
from pathlib import Path

PACKAGE_ROOT = Path(__file__).parent.parent
FORBIDDEN_PREFIXES = ("app", "backend")

# adapters/cronos is the portability seam — it IS allowed to import app.*.
ALLOWED_PATHS = {PACKAGE_ROOT / "adapters" / "cronos"}

# The fixture file deliberately contains forbidden imports; exclude it from the clean check.
FIXTURE_PATH = PACKAGE_ROOT / "tests" / "fixtures" / "forbidden_import_sample.py"


def _is_allowed(path: Path) -> bool:
    for allowed in ALLOWED_PATHS:
        try:
            path.relative_to(allowed)
            return True
        except ValueError:
            pass
    return False


def _collect_source_files():
    for p in PACKAGE_ROOT.rglob("*.py"):
        parts = p.relative_to(PACKAGE_ROOT).parts
        if "tests" in parts:
            continue
        if _is_allowed(p):
            continue
        yield p


def _scan_violations(filepath: Path) -> list[str]:
    try:
        tree = ast.parse(filepath.read_text())
    except SyntaxError:
        return []
    violations = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if any(alias.name == p or alias.name.startswith(p + ".") for p in FORBIDDEN_PREFIXES):
                    violations.append(f"line {node.lineno}: import {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            if any(mod == p or mod.startswith(p + ".") for p in FORBIDDEN_PREFIXES):
                violations.append(f"line {node.lineno}: from {mod} import ...")
    return violations


def test_no_app_imports_in_portable_core():
    all_violations: dict[str, list[str]] = {}
    for py_file in _collect_source_files():
        v = _scan_violations(py_file)
        if v:
            all_violations[str(py_file.relative_to(PACKAGE_ROOT))] = v
    assert not all_violations, "Forbidden app.*/backend.* imports found in portable core:\n" + str(all_violations)


def test_fixture_violations_detected():
    """The boundary checker must flag the deliberately bad fixture file."""
    violations = _scan_violations(FIXTURE_PATH)
    assert violations, "Expected the fixture file to contain forbidden imports but none were detected"
    assert any("app" in v for v in violations)
