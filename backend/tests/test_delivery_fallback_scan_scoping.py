"""B2 — `_fallback_delivery_status` scopes its scan to the goal's slug subtree
and orders by mtime.

Regression tests for the delivery-runner defect where the fallback report scan
globbed the *entire* ``.cronos/delivery/`` tree (newest by lexicographic path)
and could bridge a *sibling goal's* report into this node — see
docs/delivery-pipeline/delivery-v2/runner-stuck-waiting-fix-plan.md (B2).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Make the delivery-workflow package importable.
_BUNDLE = Path(__file__).parent.parent.parent / "packages" / "delivery-workflow"
if str(_BUNDLE) not in sys.path:
    sys.path.insert(0, str(_BUNDLE))

from adapters.cronos.adapter import _fallback_delivery_status  # noqa: E402


def _report(produces: str) -> str:
    return (
        "# scout report\n\n"
        "```node_status\n"
        "{\n"
        '  "status": "done",\n'
        f'  "artifact_paths": ["{produces}.md"],\n'
        f'  "produces": "{produces}",\n'
        '  "fields": {},\n'
        '  "open_questions": []\n'
        "}\n"
        "```\n"
    )


def _write(path: Path, text: str, mtime: float) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    os.utime(path, (mtime, mtime))


def _layout(tmp_path: Path) -> Path:
    """Return run_dir == <space>/.cronos/delivery-runs/<goal_id>."""
    run_dir = tmp_path / ".cronos" / "delivery-runs" / "2026-07-01-1131-my-goal"
    run_dir.mkdir(parents=True)
    return run_dir


def test_scoped_scan_ignores_newer_sibling_goal_report(tmp_path: Path) -> None:
    run_dir = _layout(tmp_path)
    delivery = tmp_path / ".cronos" / "delivery"

    # Our goal's report — older.
    _write(delivery / "my-goal" / "scout-report.md", _report("research"), mtime=1000.0)
    # A DIFFERENT goal's report — newer mtime; must NOT be picked.
    _write(delivery / "other-goal" / "scout-report.md", _report("design"), mtime=9000.0)

    ds = _fallback_delivery_status(run_dir, slug="my-goal")
    assert ds is not None
    assert ds.produces == "research"  # ours, not the newer sibling's "design"


def test_unscoped_scan_would_pick_the_wrong_report(tmp_path: Path) -> None:
    """Without a slug the scan spans the whole tree — documents the old behaviour
    the scoping fixes (newest by mtime across all goals)."""
    run_dir = _layout(tmp_path)
    delivery = tmp_path / ".cronos" / "delivery"
    _write(delivery / "my-goal" / "scout-report.md", _report("research"), mtime=1000.0)
    _write(delivery / "other-goal" / "scout-report.md", _report("design"), mtime=9000.0)

    ds = _fallback_delivery_status(run_dir, slug=None)
    assert ds is not None
    assert ds.produces == "design"  # newest by mtime, unscoped


def test_orders_by_mtime_within_scope(tmp_path: Path) -> None:
    run_dir = _layout(tmp_path)
    delivery = tmp_path / ".cronos" / "delivery"
    # Two reports for our goal; the newer one must win even though its path
    # sorts earlier lexicographically ("aaa" < "zzz").
    _write(delivery / "my-goal" / "zzz-scout-report.md", _report("research"), mtime=5000.0)
    _write(delivery / "my-goal" / "aaa-scout-report.md", _report("design"), mtime=1000.0)

    ds = _fallback_delivery_status(run_dir, slug="my-goal")
    assert ds is not None
    assert ds.produces == "research"  # newest by mtime, not lexicographic


def test_falls_back_to_whole_tree_when_scoped_dir_absent(tmp_path: Path) -> None:
    """If the agent wrote under a different slug, the scoped dir won't exist —
    scan the whole tree rather than returning nothing."""
    run_dir = _layout(tmp_path)
    delivery = tmp_path / ".cronos" / "delivery"
    _write(delivery / "some-other-slug" / "scout-report.md", _report("research"), mtime=1000.0)

    ds = _fallback_delivery_status(run_dir, slug="my-goal")
    assert ds is not None
    assert ds.produces == "research"


def test_returns_none_when_no_reports(tmp_path: Path) -> None:
    run_dir = _layout(tmp_path)
    assert _fallback_delivery_status(run_dir, slug="my-goal") is None
