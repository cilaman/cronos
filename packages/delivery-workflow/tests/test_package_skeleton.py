"""Verify the packages/delivery-workflow/ directory structure matches spec §2."""
import json
import importlib
from pathlib import Path

PACKAGE_ROOT = Path(__file__).parent.parent


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
        "adapters/cronos",
        "hooks",
        "schemas",
        "agents",
        "skills",
        "tests",
    ]
    for rel in required:
        assert (PACKAGE_ROOT / rel).is_dir(), f"Missing directory: {rel}"


def test_init_files_exist():
    inits = [
        "__init__.py",
        "lib/__init__.py",
        "lib/state/__init__.py",
        "lib/telemetry/__init__.py",
        "runner/__init__.py",
        "adapters/__init__.py",
        "adapters/cronos/__init__.py",
    ]
    for rel in inits:
        assert (PACKAGE_ROOT / rel).is_file(), f"Missing __init__.py: {rel}"


def test_plugin_json_exists_and_valid():
    path = PACKAGE_ROOT / "plugin.json"
    assert path.is_file()
    data = json.loads(path.read_text())
    assert "name" in data
    assert "version" in data
    assert data["name"] == "delivery-workflow"


def test_importlinter_config_exists():
    assert (PACKAGE_ROOT / ".importlinter").is_file()


def test_lib_importable():
    import lib  # noqa: F401

    assert lib is not None


def test_lib_state_importable():
    import lib.state  # noqa: F401

    assert lib.state is not None


def test_lib_telemetry_importable():
    import lib.telemetry  # noqa: F401

    assert lib.telemetry is not None


def test_runner_importable():
    import runner  # noqa: F401

    assert runner is not None


def test_adapters_importable():
    import adapters  # noqa: F401

    assert adapters is not None


def test_adapters_cronos_importable():
    import adapters.cronos  # noqa: F401

    assert adapters.cronos is not None
