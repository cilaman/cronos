"""Guard: fail the suite if any committed trace JSON contains a secret pattern."""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

from app.trace_redact import SECRET_PATTERNS

_SPACE_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_TRACES_DIR = _SPACE_ROOT / ".cronos" / "traces"


def _traces_dir() -> Path:
    override = os.environ.get("CRONOS_TRACES_DIR")
    return Path(override) if override else _DEFAULT_TRACES_DIR


def _scan_files(traces_dir: Path) -> list[Path]:
    """Return files to scan. Uses git ls-files for the default path (committed only).
    Falls back to rglob when the dir doesn't exist in a git repo, or when
    CRONOS_TRACES_DIR is set (used by the canary test via tmp_path)."""
    if os.environ.get("CRONOS_TRACES_DIR"):
        return list(traces_dir.rglob("*.json"))

    try:
        result = subprocess.run(
            ["git", "ls-files", ".cronos/traces/"],
            capture_output=True,
            text=True,
            cwd=_SPACE_ROOT,
            timeout=15,
        )
        if result.returncode == 0:
            if not result.stdout.strip():
                return []  # no tracked traces — nothing to scan
            return [
                _SPACE_ROOT / line
                for line in result.stdout.splitlines()
                if line.endswith(".json")
            ]
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    return list(traces_dir.rglob("*.json"))


def test_committed_traces_contain_no_pat():
    traces_dir = _traces_dir()
    if not traces_dir.exists():
        pytest.skip("traces dir not present — nothing to scan")

    files = _scan_files(traces_dir)
    offenders: list[str] = []
    for p in files:
        try:
            text = p.read_text(errors="replace")
        except OSError:
            continue
        for pat in SECRET_PATTERNS:
            if pat.search(text):
                try:
                    rel = p.relative_to(_SPACE_ROOT)
                except ValueError:
                    rel = p
                offenders.append(f"{rel}: {pat.pattern}")

    assert not offenders, (
        "Secret patterns found in committed trace JSONs:\n" + "\n".join(offenders)
    )


def test_no_pat_in_traces__detects_canary(tmp_path, monkeypatch):
    """Canary: verify the guard fires when a trace contains a real PAT."""
    trace_file = tmp_path / "0000.json"
    trace_file.write_text(
        json.dumps({"output_summary": "ghp_AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"}),
        encoding="utf-8",
    )
    monkeypatch.setenv("CRONOS_TRACES_DIR", str(tmp_path))

    traces_dir = _traces_dir()
    offenders: list[str] = []
    for p in _scan_files(traces_dir):
        text = p.read_text(errors="replace")
        for pat in SECRET_PATTERNS:
            if pat.search(text):
                offenders.append(f"{p}: {pat.pattern}")

    assert offenders, "Expected canary PAT to be detected but nothing was found"
    assert any("ghp_" in entry for entry in offenders)


# ---------------------------------------------------------------------------
# Assert that CRONOS_GIT_TOKEN credential forms are covered by SECRET_PATTERNS
# ---------------------------------------------------------------------------


def test_secret_patterns_catch_x_access_token_form() -> None:
    """The x-access-token form used in git HTTPS Basic Auth headers is caught.

    git_ops._auth_env() encodes the PAT as 'x-access-token:<token>' before
    base64-encoding it, so the raw 'x-access-token:TOKEN' string should never
    reach a trace.  This test asserts that SECRET_PATTERNS would catch it if
    it somehow did, closing the redaction loop.
    """
    token_in_header = "x-access-token:ghp_AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    assert any(pat.search(token_in_header) for pat in SECRET_PATTERNS), (
        "SECRET_PATTERNS must catch the 'x-access-token:TOKEN' form "
        "used by git_ops._auth_env()"
    )


def test_secret_patterns_catch_cronos_git_token_forms() -> None:
    """Common PAT formats that operators assign to CRONOS_GIT_TOKEN are caught.

    Cronos documents fine-grained PATs (github_pat_*) and classic PATs (ghp_*)
    as the two token forms for CRONOS_GIT_TOKEN.  Both must be redacted if they
    ever appear in a trace JSON.
    """
    forms = [
        "ghp_AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
        "github_pat_AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
    ]
    for form in forms:
        assert any(pat.search(form) for pat in SECRET_PATTERNS), (
            f"SECRET_PATTERNS must catch CRONOS_GIT_TOKEN form: {form!r}"
        )
