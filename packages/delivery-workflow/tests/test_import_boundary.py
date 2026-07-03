"""Verify that the portable delivery-workflow core never imports app.* or backend.*.

Uses AST scanning — no import-linter process needed in the test environment.
The `delivery-workflow` CI job additionally runs `lint-imports` (step "Import
boundary") against the .importlinter contract, so both enforcement paths run
on every push; this AST test is the one that also runs locally under pytest.
"""
import ast
from pathlib import Path

PACKAGE_ROOT = Path(__file__).parent.parent
# R10a src layout: importable source lives under src/delivery_workflow/.
SRC_ROOT = PACKAGE_ROOT / "src" / "delivery_workflow"
FORBIDDEN_PREFIXES = ("app", "backend")

# R10c: NO exceptions.  The Cronos adapter moved to the host
# (backend/app/delivery_adapter.py) — the package contains zero host code.
ALLOWED_PATHS: set[Path] = set()

# The fixture file deliberately contains forbidden imports; exclude it from the clean check.
FIXTURE_PATH = PACKAGE_ROOT / "tests" / "fixtures" / "forbidden_import_sample.py"

# Known deferred/CLI-only residual imports that are accepted.
# Each entry is (relative_path, line_number).  Empty since R11 deleted the dead
# CLI-only `from app.pipeline.normalize import normalize` in lib/verify.py (its
# target module was removed upstream in 758190d).
KNOWN_DEFERRED_RESIDUALS: set[tuple[str, int]] = set()


def _is_allowed(path: Path) -> bool:
    for allowed in ALLOWED_PATHS:
        try:
            path.relative_to(allowed)
            return True
        except ValueError:
            pass
    return False


def _collect_source_files():
    for p in SRC_ROOT.rglob("*.py"):
        if _is_allowed(p):
            continue
        yield p


def _scan_violations(filepath: Path, rel_path: str) -> list[str]:
    try:
        tree = ast.parse(filepath.read_text())
    except SyntaxError:
        return []
    violations = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if any(alias.name == p or alias.name.startswith(p + ".") for p in FORBIDDEN_PREFIXES):
                    if (rel_path, node.lineno) not in KNOWN_DEFERRED_RESIDUALS:
                        violations.append(f"line {node.lineno}: import {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            if any(mod == p or mod.startswith(p + ".") for p in FORBIDDEN_PREFIXES):
                if (rel_path, node.lineno) not in KNOWN_DEFERRED_RESIDUALS:
                    violations.append(f"line {node.lineno}: from {mod} import ...")
    return violations


def test_no_app_imports_in_portable_core():
    all_violations: dict[str, list[str]] = {}
    for py_file in _collect_source_files():
        rel_path = str(py_file.relative_to(SRC_ROOT))
        v = _scan_violations(py_file, rel_path)
        if v:
            all_violations[rel_path] = v
    assert not all_violations, "Forbidden app.*/backend.* imports found in portable core:\n" + str(all_violations)


def test_fixture_violations_detected():
    """The boundary checker must flag the deliberately bad fixture file."""
    violations = _scan_violations(FIXTURE_PATH, str(FIXTURE_PATH.relative_to(PACKAGE_ROOT)))
    assert violations, "Expected the fixture file to contain forbidden imports but none were detected"
    assert any("app" in v for v in violations)
