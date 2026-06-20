from __future__ import annotations

"""Tests for the upgrade webhook's mandatory-secret behavior.

The script lives outside the importable app package and has a hyphen in its
filename, so we load it via importlib rather than a normal import.
"""

import importlib.util
import sys
import os
from pathlib import Path

import pytest

WEBHOOK_SCRIPT = Path(__file__).resolve().parents[2] / "deploy" / "upgrade-webhook.py"


def _load_module(monkeypatch, secret: str):
    """Load upgrade-webhook.py with WEBHOOK_SECRET set to `secret`."""
    monkeypatch.setenv("WEBHOOK_SECRET", secret)
    spec = importlib.util.spec_from_file_location("upgrade_webhook", WEBHOOK_SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    # Suppress the top-level print side-effect during import
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# authorized() pure-function tests
# ---------------------------------------------------------------------------


def test_authorized_returns_false_when_secret_unset(monkeypatch):
    monkeypatch.delenv("WEBHOOK_SECRET", raising=False)
    # Import with WEBHOOK_SECRET absent — module sets SECRET=""
    spec = importlib.util.spec_from_file_location("upgrade_webhook_empty", WEBHOOK_SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod.authorized("anything") is False
    assert mod.authorized("") is False


def test_authorized_returns_false_when_secret_empty_string(monkeypatch):
    mod = _load_module(monkeypatch, "")
    assert mod.authorized("") is False
    assert mod.authorized("anything") is False


def test_authorized_returns_true_when_header_matches_secret(monkeypatch):
    mod = _load_module(monkeypatch, "supersecret")
    assert mod.authorized("supersecret") is True


def test_authorized_returns_false_when_header_mismatches_secret(monkeypatch):
    mod = _load_module(monkeypatch, "supersecret")
    assert mod.authorized("wrongsecret") is False
    assert mod.authorized("") is False
    assert mod.authorized("supersecretx") is False


def test_authorized_is_case_sensitive(monkeypatch):
    mod = _load_module(monkeypatch, "MySecret")
    assert mod.authorized("mysecret") is False
    assert mod.authorized("MYSECRET") is False
    assert mod.authorized("MySecret") is True
