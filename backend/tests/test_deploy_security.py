"""Security regression tests for deploy-side scripts.

These tests guard against accidental reverts of security fixes in files that
live outside the `app/` package (and therefore aren't otherwise touched by the
backend test suite).
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
UPGRADE_WEBHOOK = REPO_ROOT / "deploy" / "upgrade-webhook.py"


@pytest.fixture(scope="module")
def webhook_source() -> str:
    assert UPGRADE_WEBHOOK.is_file(), (
        f"expected deploy script at {UPGRADE_WEBHOOK} — repo layout changed?"
    )
    return UPGRADE_WEBHOOK.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def webhook_ast(webhook_source: str) -> ast.Module:
    return ast.parse(webhook_source, filename=str(UPGRADE_WEBHOOK))


def test_upgrade_webhook_imports_hmac(webhook_ast: ast.Module) -> None:
    """The deploy script must import `hmac` so it can do constant-time compares."""
    imported_modules: set[str] = set()
    for node in ast.walk(webhook_ast):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported_modules.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.add(node.module)
    assert "hmac" in imported_modules, (
        "deploy/upgrade-webhook.py must `import hmac` — without it the "
        "constant-time secret compare cannot be implemented (CRIT-004 fix)"
    )


def test_upgrade_webhook_uses_compare_digest(webhook_ast: ast.Module) -> None:
    """The secret check must go through `hmac.compare_digest`, not `==`.

    Scans the AST for any call of the form `hmac.compare_digest(...)`. A
    plain `==` comparison on the secret is timing-leaky and was the original
    bug fixed by CRIT-004.
    """
    found_compare_digest = False
    for node in ast.walk(webhook_ast):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        # Match `hmac.compare_digest(...)` exactly.
        if (
            isinstance(func, ast.Attribute)
            and func.attr == "compare_digest"
            and isinstance(func.value, ast.Name)
            and func.value.id == "hmac"
        ):
            found_compare_digest = True
            break
    assert found_compare_digest, (
        "deploy/upgrade-webhook.py must call `hmac.compare_digest(...)` for "
        "the secret check (CRIT-004). A plain `==` comparison leaks timing "
        "information about the secret."
    )


def test_upgrade_webhook_no_plain_equality_on_secret(webhook_source: str) -> None:
    """Belt-and-braces grep: ensure no leftover `auth == SECRET` style compare."""
    # The original vulnerable form was `if auth != SECRET:`. After the fix,
    # neither `auth == SECRET` nor `auth != SECRET` should appear in source.
    # We allow the variable to be on either side of the operator.
    for forbidden in ("auth == SECRET", "auth != SECRET", "SECRET == auth", "SECRET != auth"):
        assert forbidden not in webhook_source, (
            f"Found `{forbidden}` in deploy/upgrade-webhook.py — this is the "
            "timing-leaky comparison that CRIT-004 fixed. Use "
            "`hmac.compare_digest(auth.encode(), SECRET.encode())` instead."
        )
