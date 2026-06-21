from __future__ import annotations

"""Tests that NO_STATUS string literal has been renamed to NO_CRONOS_STATUS in worker.py."""

import subprocess


def test_no_status_literal_absent_from_worker() -> None:
    """worker.py must not contain the old 'NO_STATUS' string literal."""
    result = subprocess.run(
        ["grep", "-c", r"\bNO_STATUS\b", "app/worker.py"],
        capture_output=True,
        text=True,
        cwd="/data/spaces/cronos-development/backend",
    )
    count = int(result.stdout.strip()) if result.stdout.strip().isdigit() else 0
    assert count == 0, (
        f"Found {count} occurrence(s) of 'NO_STATUS' in worker.py; "
        "all sites must be renamed to 'NO_CRONOS_STATUS'"
    )


def test_no_cronos_status_literal_present_in_worker() -> None:
    """worker.py must contain at least 3 occurrences of 'NO_CRONOS_STATUS'."""
    result = subprocess.run(
        ["grep", "-c", "NO_CRONOS_STATUS", "app/worker.py"],
        capture_output=True,
        text=True,
        cwd="/data/spaces/cronos-development/backend",
    )
    count = int(result.stdout.strip()) if result.stdout.strip().isdigit() else 0
    assert count >= 3, (
        f"Expected >= 3 occurrences of 'NO_CRONOS_STATUS' in worker.py, found {count}"
    )


def test_no_status_literal_absent_from_agent() -> None:
    """agent.py must not contain the old 'NO_STATUS' string literal in non-comment code."""
    result = subprocess.run(
        ["grep", "-c", r"\bNO_STATUS\b", "app/agent.py"],
        capture_output=True,
        text=True,
        cwd="/data/spaces/cronos-development/backend",
    )
    count = int(result.stdout.strip()) if result.stdout.strip().isdigit() else 0
    assert count == 0, (
        f"Found {count} occurrence(s) of 'NO_STATUS' in agent.py"
    )
