"""Verify the packages/delivery-workflow/ directory structure matches spec §2.

R10a: the package uses a src layout — importable source lives in
``src/delivery_workflow/`` and is installed as the ``delivery_workflow``
distribution; ``pyproject.toml`` / ``plugin.json`` / ``.importlinter`` /
``tests/`` stay at the package root.
"""
import json
from pathlib import Path

PACKAGE_ROOT = Path(__file__).parent.parent
SRC_ROOT = PACKAGE_ROOT / "src" / "delivery_workflow"


def test_pyproject_toml_exists():
    assert (PACKAGE_ROOT / "pyproject.toml").is_file()


def test_pyproject_name():
    import tomllib  # Python 3.11+

    data = tomllib.loads((PACKAGE_ROOT / "pyproject.toml").read_text())
    assert data["project"]["name"] == "delivery-workflow"


def test_required_directories_exist():
    required = [
        "lib/state",
        "lib/telemetry",
        "runner",
        "schemas",
        "agents",
        "skills",
    ]
    for rel in required:
        assert (SRC_ROOT / rel).is_dir(), f"Missing directory: src/delivery_workflow/{rel}"
    assert (PACKAGE_ROOT / "tests").is_dir()


def test_init_files_exist():
    inits = [
        "__init__.py",
        "lib/__init__.py",
        "lib/state/__init__.py",
        "lib/telemetry/__init__.py",
        "runner/__init__.py",
    ]
    for rel in inits:
        assert (SRC_ROOT / rel).is_file(), f"Missing __init__.py: src/delivery_workflow/{rel}"


def test_plugin_json_exists_and_valid():
    path = PACKAGE_ROOT / "plugin.json"
    assert path.is_file()
    data = json.loads(path.read_text())
    assert "name" in data
    assert "version" in data
    assert data["name"] == "delivery-workflow"


def test_importlinter_config_exists():
    assert (PACKAGE_ROOT / ".importlinter").is_file()


def test_package_importable():
    import delivery_workflow  # noqa: F401

    assert delivery_workflow is not None


def test_lib_importable():
    from delivery_workflow import lib  # noqa: F401

    assert lib is not None


def test_lib_state_importable():
    from delivery_workflow.lib import state  # noqa: F401

    assert state is not None


def test_lib_telemetry_importable():
    from delivery_workflow.lib import telemetry  # noqa: F401

    assert telemetry is not None


def test_runner_importable():
    from delivery_workflow import runner  # noqa: F401

    assert runner is not None


def test_no_adapters_tree_in_package():
    """R10c (02-package-boundary.md §2.3): host adapters live in their hosts.
    The Cronos adapter is backend/app/delivery_adapter.py; the package ships
    no adapters/ tree at all (null_runtime stays as the reference runtime)."""
    import importlib.util

    assert not (SRC_ROOT / "adapters").exists()
    assert importlib.util.find_spec("delivery_workflow.adapters") is None


def test_null_runtime_importable():
    """The reference runtime kept its top-level home after the adapters/ tree
    was deleted (R10c)."""
    from delivery_workflow import null_runtime  # noqa: F401

    assert null_runtime is not None
