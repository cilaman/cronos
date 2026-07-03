"""
Portability test: delivery_workflow.lib.verify and delivery_workflow.lib.contract
must be importable WITHOUT loading any app.* module.

This test validates R6 (importlinter compliance) by using sys.modules introspection.
The test runs in a subprocess to get a pristine Python environment. The package is
an installed (editable) distribution, so the subprocess needs no cwd/sys.path setup.
"""
import subprocess
import sys


def test_lib_verify_importable_without_app():
    """delivery_workflow.lib.verify must import cleanly without pulling in any app.* module."""
    code = """
import sys
# Save pristine state
before = set(sys.modules.keys())
import delivery_workflow.lib.verify
after = set(sys.modules.keys())
new_modules = after - before
app_modules = [m for m in new_modules if m == 'app' or m.startswith('app.')]
if app_modules:
    print(f"FAIL: importing delivery_workflow.lib.verify loaded app modules: {app_modules}", file=sys.stderr)
    sys.exit(1)
print(f"OK: delivery_workflow.lib.verify imported cleanly; {len(new_modules)} new modules, none from app.*")
"""
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"delivery_workflow.lib.verify import pulled in app modules:\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )


def test_lib_contract_importable_without_app():
    """delivery_workflow.lib.contract must import cleanly without pulling in any app.* module."""
    code = """
import sys
before = set(sys.modules.keys())
import delivery_workflow.lib.contract
after = set(sys.modules.keys())
new_modules = after - before
app_modules = [m for m in new_modules if m == 'app' or m.startswith('app.')]
if app_modules:
    print(f"FAIL: importing delivery_workflow.lib.contract loaded app modules: {app_modules}", file=sys.stderr)
    sys.exit(1)
print(f"OK: delivery_workflow.lib.contract imported cleanly")
"""
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"delivery_workflow.lib.contract import pulled in app modules:\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )


def test_lib_verify_schemas_dir_resolves():
    """SCHEMAS_DIR in delivery_workflow.lib.verify must resolve to the packaged lib/schemas/."""
    code = """
import delivery_workflow.lib.verify as verify, pathlib, sys
schemas_dir = pathlib.Path(verify.SCHEMAS_DIR)
assert schemas_dir.exists(), f"SCHEMAS_DIR does not exist: {schemas_dir}"
yaml_count = len(list(schemas_dir.glob("*.yaml")))
assert yaml_count == 8, f"Expected 8 YAML files in lib/schemas/, got {yaml_count}"
assert "delivery_workflow" in str(schemas_dir), f"SCHEMAS_DIR not under delivery_workflow: {schemas_dir}"
print(f"OK: SCHEMAS_DIR={schemas_dir}, {yaml_count} yaml files")
"""
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"SCHEMAS_DIR check failed:\n{result.stdout}\n{result.stderr}"
