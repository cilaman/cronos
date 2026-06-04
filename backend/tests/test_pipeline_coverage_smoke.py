"""
Pipeline coverage smoke test — I12.

Ensures that the two new S2 modules (api/features.py and feature_hooks.py)
are imported during the test run so they register for coverage measurement.
The per-iteration tests (I1–I11) exercise the real behaviour; this file
exists solely so pytest --cov=app sees the modules.
"""


def test_coverage_smoke_imports() -> None:
    """Trivial import smoke test to register new S2 modules for coverage."""
    import app.api.features  # noqa: F401
    import app.feature_hooks  # noqa: F401
