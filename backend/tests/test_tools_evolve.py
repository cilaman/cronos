"""Tests for backend/app/tools/evolve.py — create_evolve_task, parse_evolve_blocks,
open_evolve_prs — plus _schedule_evolve_tasks in api/discovery.py."""
from __future__ import annotations

import textwrap
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import yaml

from app.tools.evolve import (
    EVOLVE_TITLE,
    EvolveProposal,
    _build_evolve_brief,
    _compute_tool_telemetry,
    _scan_adopted_tools,
    create_evolve_task,
    open_evolve_prs,
    parse_evolve_blocks,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_manifest(adopt_dir: Path, kind: str, name: str) -> None:
    """Write a minimal manifest.yml for a fake adopted tool."""
    adopt_dir.mkdir(parents=True, exist_ok=True)
    data = {
        "source_url": "https://github.com/test/repo",
        "source_slug": "github-com-test-repo",
        "source_path": f".claude/{kind}s/{name}.md",
        "source_sha": "abc123",
        "adopted_at": "2026-01-01T00:00:00Z",
        "base_sha": "sha_base",
        "local_sha": "sha_base",
        "evolved": False,
        "kind": kind,
        "name": name,
    }
    (adopt_dir / "manifest.yml").write_text(yaml.dump(data), encoding="utf-8")


def _write_tool_file(adopt_dir: Path, kind: str, name: str, content: str = "# original") -> None:
    filename = "SKILL.md" if kind == "skill" else f"{name}.md"
    (adopt_dir / filename).write_text(content, encoding="utf-8")


class _FakeRunStats:
    """Minimal RunStats stand-in."""

    def __init__(self, adopted_tool_uses: dict, *, days_ago: int = 0) -> None:
        self.adopted_tool_uses = adopted_tool_uses
        d = datetime.now(tz=UTC) - timedelta(days=days_ago)
        self.started_at = d


class _FakeTaskStats:
    def __init__(self, runs: list[_FakeRunStats]) -> None:
        self.runs = runs


class _FakeAdoptedEntry:
    def __init__(self, calls: int, errors: int, kind: str, human_rescue: bool = False) -> None:
        self.calls = calls
        self.errors = errors
        self.kind = kind
        self.human_rescue = human_rescue


# ---------------------------------------------------------------------------
# parse_evolve_blocks
# ---------------------------------------------------------------------------


def test_parse_evolve_blocks_empty():
    assert parse_evolve_blocks("no blocks here") == []


def test_parse_evolve_blocks_single():
    text = textwrap.dedent("""\
        Here is the proposal:
        EVOLVE:
        kind: agent
        name: my-agent
        rationale: It breaks a lot.
        revised_content: |
          # Revised
          Better content.
        END_EVOLVE
        Done.
    """)
    proposals = parse_evolve_blocks(text)
    assert len(proposals) == 1
    p = proposals[0]
    assert p.kind == "agent"
    assert p.name == "my-agent"
    assert "breaks" in p.rationale
    assert "Revised" in p.revised_content


def test_parse_evolve_blocks_multiple():
    text = textwrap.dedent("""\
        EVOLVE:
        kind: agent
        name: agent-a
        rationale: First.
        revised_content: |
          Content A.
        END_EVOLVE
        Some text in between.
        EVOLVE:
        kind: skill
        name: skill-b
        rationale: Second.
        revised_content: |
          Content B.
        END_EVOLVE
    """)
    proposals = parse_evolve_blocks(text)
    assert len(proposals) == 2
    assert proposals[0].name == "agent-a"
    assert proposals[1].name == "skill-b"


def test_parse_evolve_blocks_malformed_skipped():
    # Block contains invalid YAML.
    text = "EVOLVE:\n: : : invalid yaml\nEND_EVOLVE\n"
    proposals = parse_evolve_blocks(text)
    assert proposals == []


def test_parse_evolve_blocks_missing_required_field():
    # Block is valid YAML but missing required fields → validation error, skipped.
    text = textwrap.dedent("""\
        EVOLVE:
        kind: agent
        rationale: Missing name field.
        revised_content: |
          content
        END_EVOLVE
    """)
    proposals = parse_evolve_blocks(text)
    assert proposals == []


# ---------------------------------------------------------------------------
# _compute_tool_telemetry
# ---------------------------------------------------------------------------


def test_compute_tool_telemetry_no_stats():
    result = _compute_tool_telemetry("my-tool", "agent", [], window_days=30)
    assert result["calls"] == 0
    assert result["avg_success_rate"] == 0.0
    assert result["human_rescue_count"] == 0


def test_compute_tool_telemetry_within_window():
    entry = _FakeAdoptedEntry(calls=10, errors=4, kind="agent")
    run = _FakeRunStats({"my-tool": entry}, days_ago=5)
    ts = _FakeTaskStats([run])
    result = _compute_tool_telemetry("my-tool", "agent", [ts], window_days=30)
    assert result["calls"] == 10
    assert result["errors"] == 4
    assert abs(result["avg_success_rate"] - 0.6) < 0.001


def test_compute_tool_telemetry_outside_window_excluded():
    entry = _FakeAdoptedEntry(calls=10, errors=4, kind="agent")
    run = _FakeRunStats({"my-tool": entry}, days_ago=40)
    ts = _FakeTaskStats([run])
    result = _compute_tool_telemetry("my-tool", "agent", [ts], window_days=30)
    assert result["calls"] == 0


def test_compute_tool_telemetry_kind_mismatch_excluded():
    entry = _FakeAdoptedEntry(calls=5, errors=1, kind="skill")  # kind mismatch
    run = _FakeRunStats({"my-tool": entry})
    ts = _FakeTaskStats([run])
    result = _compute_tool_telemetry("my-tool", "agent", [ts])  # looking for "agent"
    assert result["calls"] == 0


def test_compute_tool_telemetry_human_rescue_counted():
    entry = _FakeAdoptedEntry(calls=5, errors=1, kind="agent", human_rescue=True)
    run = _FakeRunStats({"my-tool": entry})
    ts = _FakeTaskStats([run])
    result = _compute_tool_telemetry("my-tool", "agent", [ts])
    assert result["human_rescue_count"] == 1


# ---------------------------------------------------------------------------
# create_evolve_task
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_evolve_task_basic(tmp_spaces_dir, task_store):
    """create_evolve_task creates a task with correct title and agent_mode."""
    space_id = "test-space"

    task = await create_evolve_task(
        space_id,
        task_store=task_store,
        spaces_dir=tmp_spaces_dir,
    )

    assert task.title == EVOLVE_TITLE
    assert task.agent_mode == "plan"
    assert task.type == "task"
    assert task.space_id == space_id


@pytest.mark.asyncio
async def test_create_evolve_task_brief_contains_telemetry(tmp_spaces_dir, task_store):
    """create_evolve_task brief contains telemetry table when tools are adopted."""
    space_id = "test-space"
    adopt_dir = tmp_spaces_dir / space_id / ".cronos" / "tools" / "agent" / "my-agent"
    _write_manifest(adopt_dir, "agent", "my-agent")
    _write_tool_file(adopt_dir, "agent", "my-agent")

    # Build a fake stats_store
    entry = _FakeAdoptedEntry(calls=12, errors=7, kind="agent", human_rescue=True)
    run = _FakeRunStats({"my-agent": entry})
    ts_obj = _FakeTaskStats([run])
    stats_store = MagicMock()
    stats_store.list_space = AsyncMock(return_value=[ts_obj])

    task = await create_evolve_task(
        space_id,
        task_store=task_store,
        spaces_dir=tmp_spaces_dir,
        stats_store=stats_store,
    )

    assert "my-agent" in task.brief
    assert "calls" in task.brief.lower()
    assert EVOLVE_TITLE in task.title


@pytest.mark.asyncio
async def test_create_evolve_task_no_tools(tmp_spaces_dir, task_store):
    """create_evolve_task with no adopted tools still creates the task."""
    space_id = "test-space"

    task = await create_evolve_task(
        space_id,
        task_store=task_store,
        spaces_dir=tmp_spaces_dir,
    )
    assert task.title == EVOLVE_TITLE
    # Brief table has header row even with no tools.
    assert "|---" in task.brief


# ---------------------------------------------------------------------------
# open_evolve_prs
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_open_evolve_prs_writes_file_and_bumps_sha(tmp_path):
    """open_evolve_prs writes the revised content and calls recompute_local_sha."""
    spaces_dir = tmp_path / "spaces"
    space_id = "s1"
    adopt_dir = spaces_dir / space_id / ".cronos" / "tools" / "agent" / "my-agent"
    _write_manifest(adopt_dir, "agent", "my-agent")
    _write_tool_file(adopt_dir, "agent", "my-agent", "# original")

    proposal = EvolveProposal(
        kind="agent",
        name="my-agent",
        rationale="Low success rate.",
        revised_content="# revised content",
    )

    commit_calls: list[tuple] = []

    async def mock_commit_fn(worktree, branch, title, body):
        commit_calls.append((worktree, branch, title, body))
        return "https://github.com/test/pr/1"

    results = await open_evolve_prs(
        space_id,
        [proposal],
        spaces_dir=spaces_dir,
        _commit_fn=mock_commit_fn,
    )

    # File written
    tool_file = adopt_dir / "my-agent.md"
    assert tool_file.read_text() == "# revised content"

    # commit_fn called
    assert len(commit_calls) == 1
    _, branch, title, body = commit_calls[0]
    assert branch.startswith("cronos/evolve/agent-my-agent-")
    assert title == "evolve: agent/my-agent"
    assert "my-agent" in body

    # PR URL returned
    assert results == ["https://github.com/test/pr/1"]


@pytest.mark.asyncio
async def test_open_evolve_prs_sets_evolved_true(tmp_path):
    """open_evolve_prs bumps local_sha and sets evolved=True on content change."""
    spaces_dir = tmp_path / "spaces"
    space_id = "s1"
    adopt_dir = spaces_dir / space_id / ".cronos" / "tools" / "skill" / "my-skill"
    _write_manifest(adopt_dir, "skill", "my-skill")
    _write_tool_file(adopt_dir, "skill", "my-skill", "# original skill")

    proposal = EvolveProposal(
        kind="skill",
        name="my-skill",
        rationale="Too many rescues.",
        revised_content="# improved skill content",
    )

    async def noop_commit_fn(worktree, branch, title, body):
        return "https://github.com/pr/99"

    await open_evolve_prs(
        space_id, [proposal], spaces_dir=spaces_dir, _commit_fn=noop_commit_fn,
    )

    # Read updated manifest
    import yaml as _yaml
    manifest_path = adopt_dir / "manifest.yml"
    data = _yaml.safe_load(manifest_path.read_text())
    assert data["evolved"] is True
    assert data["local_sha"] != data["base_sha"]


@pytest.mark.asyncio
async def test_open_evolve_prs_missing_tool_skipped(tmp_path):
    """Proposals for tools not adopted in the space are skipped gracefully."""
    spaces_dir = tmp_path / "spaces"
    space_id = "s1"
    (spaces_dir / space_id / ".cronos").mkdir(parents=True)

    proposal = EvolveProposal(
        kind="agent",
        name="nonexistent",
        rationale="Doesn't exist.",
        revised_content="# content",
    )

    commit_calls: list = []

    async def mock_commit_fn(worktree, branch, title, body):
        commit_calls.append(branch)
        return "https://pr/1"

    results = await open_evolve_prs(
        space_id, [proposal], spaces_dir=spaces_dir, _commit_fn=mock_commit_fn,
    )

    assert results == []
    assert commit_calls == []


@pytest.mark.asyncio
async def test_open_evolve_prs_multiple_proposals(tmp_path):
    """Multiple proposals result in separate commits with unique branches."""
    spaces_dir = tmp_path / "spaces"
    space_id = "s1"

    for kind, name in [("agent", "agent-a"), ("skill", "skill-b")]:
        adopt_dir = spaces_dir / space_id / ".cronos" / "tools" / kind / name
        _write_manifest(adopt_dir, kind, name)
        _write_tool_file(adopt_dir, kind, name)

    proposals = [
        EvolveProposal(kind="agent", name="agent-a", rationale="r1", revised_content="# a"),
        EvolveProposal(kind="skill", name="skill-b", rationale="r2", revised_content="# b"),
    ]

    branches: list[str] = []

    async def mock_commit_fn(worktree, branch, title, body):
        branches.append(branch)
        return f"https://pr/{len(branches)}"

    results = await open_evolve_prs(
        space_id, proposals, spaces_dir=spaces_dir, _commit_fn=mock_commit_fn,
    )

    assert len(results) == 2
    # Both branches have the same timestamp suffix — check unique kind+name prefix
    assert any("agent-agent-a" in b for b in branches)
    assert any("skill-skill-b" in b for b in branches)


# ---------------------------------------------------------------------------
# _schedule_evolve_tasks (in api/discovery.py)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_schedule_evolve_tasks_no_spaces(tmp_path, task_store):
    from app.api.discovery import _schedule_evolve_tasks

    spaces_dir = tmp_path / "no-spaces"
    spaces_dir.mkdir()
    n = await _schedule_evolve_tasks(task_store, spaces_dir)
    assert n == 0


@pytest.mark.asyncio
async def test_schedule_evolve_tasks_autopilot_gate(tmp_spaces_dir, task_store, space_store):
    """Only autopilot-enabled spaces get a task scheduled."""
    from app.api.discovery import _schedule_evolve_tasks

    space_id = "test-space"

    # Create an adopted tool so the tool gate passes.
    adopt_dir = tmp_spaces_dir / space_id / ".cronos" / "tools" / "agent" / "my-agent"
    _write_manifest(adopt_dir, "agent", "my-agent")
    _write_tool_file(adopt_dir, "agent", "my-agent")

    # space_store fixture has test-space, autopilot defaults to "disabled"
    # => should NOT schedule a task
    n = await _schedule_evolve_tasks(task_store, tmp_spaces_dir, space_store=space_store)
    assert n == 0

    # Enable autopilot on the space.
    await space_store.set_autopilot("test-space", "enabled")

    n = await _schedule_evolve_tasks(task_store, tmp_spaces_dir, space_store=space_store)
    assert n == 1


@pytest.mark.asyncio
async def test_schedule_evolve_tasks_run_count_gate(tmp_spaces_dir, task_store, space_store):
    """Only spaces with >10 runs for at least one tool are scheduled."""
    from app.api.discovery import _schedule_evolve_tasks

    space_id = "test-space"
    adopt_dir = tmp_spaces_dir / space_id / ".cronos" / "tools" / "agent" / "my-agent"
    _write_manifest(adopt_dir, "agent", "my-agent")
    _write_tool_file(adopt_dir, "agent", "my-agent")

    await space_store.set_autopilot(space_id, "enabled")

    # Build stats_store with only 5 calls (below the 10-run gate).
    entry = _FakeAdoptedEntry(calls=5, errors=1, kind="agent")
    run = _FakeRunStats({"my-agent": entry})
    ts_obj = _FakeTaskStats([run])
    stats_store = MagicMock()
    stats_store.list_space = AsyncMock(return_value=[ts_obj])

    n = await _schedule_evolve_tasks(
        task_store, tmp_spaces_dir, space_store=space_store, stats_store=stats_store, min_runs=10,
    )
    assert n == 0

    # Now bump to 15 calls.
    entry2 = _FakeAdoptedEntry(calls=15, errors=2, kind="agent")
    run2 = _FakeRunStats({"my-agent": entry2})
    ts_obj2 = _FakeTaskStats([run2])
    stats_store.list_space = AsyncMock(return_value=[ts_obj2])

    n = await _schedule_evolve_tasks(
        task_store, tmp_spaces_dir, space_store=space_store, stats_store=stats_store, min_runs=10,
    )
    assert n == 1


@pytest.mark.asyncio
async def test_schedule_evolve_tasks_deduplication(tmp_spaces_dir, task_store, space_store):
    """A second call does not create a duplicate when a pending task exists."""
    from app.api.discovery import _schedule_evolve_tasks

    space_id = "test-space"
    adopt_dir = tmp_spaces_dir / space_id / ".cronos" / "tools" / "agent" / "my-agent"
    _write_manifest(adopt_dir, "agent", "my-agent")
    _write_tool_file(adopt_dir, "agent", "my-agent")

    await space_store.set_autopilot(space_id, "enabled")

    n1 = await _schedule_evolve_tasks(task_store, tmp_spaces_dir, space_store=space_store)
    assert n1 == 1

    n2 = await _schedule_evolve_tasks(task_store, tmp_spaces_dir, space_store=space_store)
    assert n2 == 0  # deduped
