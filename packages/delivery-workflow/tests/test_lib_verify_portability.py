"""
Portability test: lib.verify and lib.contract must be importable WITHOUT loading any app.* module.

This test validates R6 (importlinter compliance) by using sys.modules introspection.
The test runs in a subprocess to get a pristine Python environment.
"""
import subprocess
import sys


def test_lib_verify_importable_without_app():
    """lib.verify must import cleanly without pulling in any app.* module."""
    code = """
import sys
# Save pristine state
before = set(sys.modules.keys())
import lib.verify
after = set(sys.modules.keys())
new_modules = after - before
app_modules = [m for m in new_modules if m == 'app' or m.startswith('app.')]
if app_modules:
    print(f"FAIL: importing lib.verify loaded app modules: {app_modules}", file=sys.stderr)
    sys.exit(1)
print(f"OK: lib.verify imported cleanly; {len(new_modules)} new modules, none from app.*")
"""
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        cwd="/data/spaces/cronos-development/backend",  # ensures lib is on sys.path
    )
    assert result.returncode == 0, (
        f"lib.verify import pulled in app modules:\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )


def test_lib_contract_importable_without_app():
    """lib.contract must import cleanly without pulling in any app.* module."""
    code = """
import sys
before = set(sys.modules.keys())
import lib.contract
after = set(sys.modules.keys())
new_modules = after - before
app_modules = [m for m in new_modules if m == 'app' or m.startswith('app.')]
if app_modules:
    print(f"FAIL: importing lib.contract loaded app modules: {app_modules}", file=sys.stderr)
    sys.exit(1)
print(f"OK: lib.contract imported cleanly")
"""
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        cwd="/data/spaces/cronos-development/backend",
    )
    assert result.returncode == 0, (
        f"lib.contract import pulled in app modules:\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )


def test_lib_verify_schemas_dir_resolves():
    """SCHEMAS_DIR in lib.verify must resolve to packages/delivery-workflow/lib/schemas/."""
    code = """
import lib.verify, pathlib, sys
schemas_dir = pathlib.Path(lib.verify.SCHEMAS_DIR)
assert schemas_dir.exists(), f"SCHEMAS_DIR does not exist: {schemas_dir}"
yaml_count = len(list(schemas_dir.glob("*.yaml")))
assert yaml_count == 8, f"Expected 8 YAML files in lib/schemas/, got {yaml_count}"
assert "delivery-workflow" in str(schemas_dir), f"SCHEMAS_DIR not under delivery-workflow: {schemas_dir}"
print(f"OK: SCHEMAS_DIR={schemas_dir}, {yaml_count} yaml files")
"""
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        cwd="/data/spaces/cronos-development/backend",
    )
    assert result.returncode == 0, f"SCHEMAS_DIR check failed:\n{result.stdout}\n{result.stderr}"
