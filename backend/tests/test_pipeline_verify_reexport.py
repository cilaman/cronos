"""Verify that app.pipeline.verify re-exports all symbols from lib.verify with identity equality."""
import importlib
import pathlib

import lib.verify as lib_verify

# Use importlib to load the verify submodule directly, bypassing the package
# __init__.py which shadows the 'verify' attribute with the function of the
# same name imported from the submodule.
app_verify = importlib.import_module("app.pipeline.verify")


def test_all_symbols_importable():
    symbols = [
        "CLASS_CONFIG", "EXIT_PROCEED", "EXIT_FAIL", "EXIT_ESCALATE", "EXIT_RETRY",
        "VerifyResult", "canonical_artifact_relpath", "verify", "split_frontmatter",
        "PER_CLASS_REQUIRED_SECTIONS", "main", "SCHEMAS_DIR",
    ]
    for sym in symbols:
        assert hasattr(app_verify, sym), f"app.pipeline.verify missing: {sym}"
        assert hasattr(lib_verify, sym), f"lib.verify missing: {sym}"


def test_schemas_dir_is_under_lib():
    lib_schemas = pathlib.Path(lib_verify.SCHEMAS_DIR)
    assert "delivery-workflow" in str(lib_schemas), (
        f"SCHEMAS_DIR should be under packages/delivery-workflow, got: {lib_schemas}"
    )
    assert lib_schemas.exists(), f"SCHEMAS_DIR does not exist: {lib_schemas}"
    yaml_files = list(lib_schemas.glob("*.yaml"))
    assert len(yaml_files) == 8, f"Expected 8 schema YAML files, got {len(yaml_files)}"


def test_schemas_dir_consistency():
    assert app_verify.SCHEMAS_DIR == lib_verify.SCHEMAS_DIR


def test_exit_code_identity():
    assert app_verify.EXIT_PROCEED is lib_verify.EXIT_PROCEED
    assert app_verify.EXIT_FAIL is lib_verify.EXIT_FAIL
    assert app_verify.EXIT_ESCALATE is lib_verify.EXIT_ESCALATE
    assert app_verify.EXIT_RETRY is lib_verify.EXIT_RETRY


def test_verify_function_identity():
    assert app_verify.verify is lib_verify.verify
    assert app_verify.split_frontmatter is lib_verify.split_frontmatter
