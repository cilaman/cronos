"""Guards the delivery/v2 deployment packaging.

The delivery-workflow runner (adapters/runner/compiler_a/spec_loader/lib) lives
outside the backend tree. It is NOT pip-installed, so the container must ship the
source tree and put it on PYTHONPATH — otherwise delivery goals fail at runtime
with "No module named 'adapters'". These tests pin the wiring that makes that so,
plus the self-contained sys.path bootstrap used in local dev.
"""
from __future__ import annotations

from pathlib import Path

import yaml

_REPO = Path(__file__).resolve().parents[2]


def test_dockerfile_ships_package_and_sets_pythonpath():
    dockerfile = (_REPO / "backend" / "Dockerfile").read_text()
    assert "COPY packages/delivery-workflow" in dockerfile, (
        "backend image must ship the portable delivery-workflow package"
    )
    assert "packages/delivery-workflow" in dockerfile and "PYTHONPATH" in dockerfile, (
        "backend image must add packages/delivery-workflow to PYTHONPATH"
    )
    # Repo-root-relative COPY sources (context is the repo root, not ./backend).
    assert "COPY backend/pyproject.toml" in dockerfile
    assert "COPY backend/app ./app" in dockerfile


def test_compose_backend_builds_from_repo_root():
    compose = yaml.safe_load((_REPO / "docker-compose.yml").read_text())
    build = compose["services"]["backend"]["build"]
    assert build["context"] == "."
    assert build["dockerfile"] == "backend/Dockerfile"


def test_delivery_driver_bootstraps_package_onto_syspath():
    import sys
    import app.delivery_driver  # noqa: F401 — import runs the bootstrap

    pkg = _REPO / "packages" / "delivery-workflow"
    assert str(pkg) in sys.path, (
        "importing app.delivery_driver must put the delivery-workflow package on sys.path"
    )
    # The modules the runner/driver import must resolve.
    import adapters.cronos.adapter  # noqa: F401
    import compiler_a  # noqa: F401
    import spec_loader  # noqa: F401
    import runner  # noqa: F401
    import lib.contract  # noqa: F401
