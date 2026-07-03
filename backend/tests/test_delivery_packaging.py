"""Guards the delivery/v2 deployment packaging.

The delivery-workflow runner lives outside the backend tree as a real
installable package (src layout, R10a). The container ships the source tree
and pip-installs it editable; local dev installs it into the backend venv the
same way. There is NO sys.path/PYTHONPATH shim anywhere — `import
delivery_workflow` must simply work. These tests pin that wiring.
"""
from __future__ import annotations

from pathlib import Path

import yaml

_REPO = Path(__file__).resolve().parents[2]


def test_dockerfile_ships_and_pip_installs_package():
    dockerfile = (_REPO / "backend" / "Dockerfile").read_text()
    assert "COPY packages/delivery-workflow" in dockerfile, (
        "backend image must ship the portable delivery-workflow package"
    )
    assert "pip install -e ./packages/delivery-workflow" in dockerfile, (
        "backend image must pip-install the delivery-workflow package (R10a)"
    )
    assert "PYTHONPATH" not in dockerfile, (
        "R10a: the PYTHONPATH shim is gone — the package is pip-installed"
    )
    # Repo-root-relative COPY sources (context is the repo root, not ./backend).
    assert "COPY backend/pyproject.toml" in dockerfile
    assert "COPY backend/app ./app" in dockerfile


def test_compose_backend_builds_from_repo_root():
    compose = yaml.safe_load((_REPO / "docker-compose.yml").read_text())
    build = compose["services"]["backend"]["build"]
    assert build["context"] == "."
    assert build["dockerfile"] == "backend/Dockerfile"


def _dep_names(dep_list):
    """Extract PyPI package names (lowercased) from a PEP 508 dependency list."""
    import re
    names = set()
    for spec in dep_list:
        m = re.match(r"^\s*([A-Za-z0-9._-]+)", spec)
        if m:
            names.add(m.group(1).lower().replace("_", "-"))
    return names


def test_backend_deps_cover_delivery_workflow_runtime_deps():
    """The delivery-workflow runtime deps must stay covered by the backend's own
    dependencies — the backend imports delivery_workflow.* directly, so a dep the
    package grows must be visible to the backend install too."""
    backend = yaml_or_toml_deps(_REPO / "backend" / "pyproject.toml")
    pkg = yaml_or_toml_deps(_REPO / "packages" / "delivery-workflow" / "pyproject.toml")
    missing = _dep_names(pkg) - _dep_names(backend)
    assert not missing, (
        f"backend/pyproject.toml must list delivery-workflow runtime deps; missing: {missing}"
    )


def yaml_or_toml_deps(pyproject_path: Path):
    """Return [project].dependencies from a pyproject.toml."""
    try:
        import tomllib  # py3.11+
    except ModuleNotFoundError:  # pragma: no cover
        import tomli as tomllib  # type: ignore
    data = tomllib.loads(pyproject_path.read_text())
    return data.get("project", {}).get("dependencies", [])


def test_jsonschema_importable():
    import jsonschema  # noqa: F401


def test_package_is_installed_not_shimmed():
    """`import delivery_workflow` resolves as an installed package — no sys.path
    bootstrap runs anywhere in app.* (R10a acceptance)."""
    import sys

    import delivery_workflow  # noqa: F401
    import app.delivery_driver  # noqa: F401

    pkg_root = _REPO / "packages" / "delivery-workflow"
    assert str(pkg_root) not in sys.path, (
        "the flat package root must NOT be on sys.path — the sys.path shims are deleted"
    )
    # The modules the runner/driver need must resolve as delivery_workflow.*.
    import delivery_workflow.compiler_a  # noqa: F401
    import delivery_workflow.spec_loader  # noqa: F401
    import delivery_workflow.runner  # noqa: F401
    import delivery_workflow.lib.contract  # noqa: F401


def test_cronos_adapter_lives_in_the_host_not_the_package():
    """R10c (02-package-boundary.md §2.3): the Cronos adapter is host code
    (app.delivery_adapter); the package ships NO adapters/ tree and zero
    Cronos knowledge."""
    import importlib.util

    import delivery_workflow

    # The host adapter module imports and exposes both port implementations.
    from app.delivery_adapter import CronosAdapter, CronosStateOps  # noqa: F401
    from delivery_workflow.lib.state.ops import StateStoreOps

    # No logic duplication: the host StateOps IS the package-native one.
    assert CronosStateOps is StateStoreOps

    # The package has no delivery_workflow.adapters subpackage at all.
    assert importlib.util.find_spec("delivery_workflow.adapters") is None, (
        "delivery_workflow.adapters must not exist — the Cronos adapter moved "
        "to backend/app/delivery_adapter.py (R10c)"
    )
    # And no adapters/ directory ships in the installed source tree.
    pkg_dir = Path(delivery_workflow.__file__).parent
    assert not (pkg_dir / "adapters").exists()


def test_no_syspath_bootstrap_in_app_source():
    """No app module may re-introduce a sys.path shim for the package."""
    app_dir = _REPO / "backend" / "app"
    offenders = []
    for py in app_dir.rglob("*.py"):
        text = py.read_text()
        if "sys.path.insert" in text and "delivery" in text:
            offenders.append(str(py.relative_to(_REPO)))
    assert not offenders, f"sys.path bootstrap re-introduced in: {offenders}"
