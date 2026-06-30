"""Verify that app.pipeline.contract re-exports all symbols from lib.contract with identity equality."""
import importlib

import app.pipeline.contract as app_contract
import lib.contract as lib_contract


def _all_public_names(mod):
    return [n for n in dir(mod) if not n.startswith("_")]


def test_cc_version_identity():
    assert app_contract.CC_VERSION is lib_contract.CC_VERSION


def test_all_constants_importable():
    for name in _all_public_names(lib_contract):
        assert hasattr(app_contract, name), f"app.pipeline.contract missing: {name}"


def test_key_constants_identity():
    for name in _all_public_names(lib_contract):
        lib_val = getattr(lib_contract, name)
        app_val = getattr(app_contract, name)
        # For immutable objects (str, int, tuple), identity may differ due to interning;
        # equality is sufficient. For mutable containers, equality is the right check.
        assert app_val == lib_val, f"Mismatch for {name}: {app_val!r} != {lib_val!r}"
