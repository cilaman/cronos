"""Arc 5 end-to-end test: 5a (discovery) → 5b (adoption) → 5c (evolve).

Four scenarios exercised in a single module, fully mocked — no real network
or git calls are made.

  Step 1  Config source → refresh → discovered_tools rows appear in SQLite
  Step 2  Adopt agent → manifest.yml written with correct hashes
  Step 3  Task run with adopted tool → ToolCallTrace.adopted_tool_id set
  Step 4  Low-success telemetry → create_evolve_task → mocked agent emits
          EVOLVE: → vendored file updated, local_sha changes, evolved=True,
          mocked commit_fn returns a PR URL
"""
from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
import yaml

from app.stats import AdoptedToolRunStats, RunStats, TaskStats
from app.tools.adoption import (
    _compute_sha,
    _read_manifest,
    adopt,
    recompute_local_sha,
)
from app.tools.discovery import DiscoveredItem
from app.tools.evolve import (
    EVOLVE_TITLE,
    EvolveProposal,
    create_evolve_task,
    open_evolve_prs,
    parse_evolve_blocks,
)
from app.tools.index import adopted_index_for_space, list_discovered, upsert_discovered
from app.trace_parser import ToolCallTrace, extract_run_trace

# ---------------------------------------------------------------------------
# Shared constants
# ---------------------------------------------------------------------------

SPACE_ID = "test-space"
SOURCE_URL = "https://github.com/example/tools"
SOURCE_SLUG = "github-com-example-tools"
SOURCE_SHA = "deadbeef1234"

AGENT_NAME = "reviewer"
AGENT_KIND = "agent"
AGENT_BODY = "# Reviewer\nReviews code changes.\n"
AGENT_REVISED = "# Reviewer (revised)\nMore thorough review instructions.\n"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _create_db(db_path: Path) -> None:
    """Create discovered_tools schema in a fresh SQLite file."""
    con = sqlite3.connect(db_path)
    con.execute(
        """CREATE TABLE IF NOT EXISTS discovered_tools (
            source_url TEXT NOT NULL, source_slug TEXT NOT NULL, kind TEXT NOT NULL,
            name TEXT NOT NULL, relative_path TEXT NOT NULL, description TEXT,
            source_sha TEXT NOT NULL, last_seen TEXT NOT NULL,
            PRIMARY KEY (source_slug, kind, name))"""
    )
    con.commit()
    con.close()


def _make_discovered_item() -> DiscoveredItem:
    return DiscoveredItem(
        source_url=SOURCE_URL,
        source_slug=SOURCE_SLUG,
        kind=AGENT_KIND,
        name=AGENT_NAME,
        relative_path=f".claude/agents/{AGENT_NAME}.md",
        description="Reviews code changes.",
        source_sha=SOURCE_SHA,
    )


def _write_clone(disc_base: Path) -> None:
    """Write a fake clone with one agent file."""
    agent_dir = disc_base / SOURCE_SLUG / ".claude" / "agents"
    agent_dir.mkdir(parents=True)
    (agent_dir / f"{AGENT_NAME}.md").write_text(AGENT_BODY, encoding="utf-8")


def _write_manifest_raw(adopt_dir: Path, *, base_sha: str, local_sha: str, evolved: bool = False) -> None:
    adopt_dir.mkdir(parents=True, exist_ok=True)
    data = {
        "source_url": SOURCE_URL,
        "source_slug": SOURCE_SLUG,
        "source_path": f".claude/agents/{AGENT_NAME}.md",
        "source_sha": SOURCE_SHA,
        "adopted_at": "2026-01-01T00:00:00Z",
        "base_sha": base_sha,
        "local_sha": local_sha,
        "evolved": evolved,
        "kind": AGENT_KIND,
        "name": AGENT_NAME,
    }
    (adopt_dir / "manifest.yml").write_text(yaml.dump(data), encoding="utf-8")


def _adopt_dir(spaces_dir: Path) -> Path:
    return spaces_dir / SPACE_ID / ".cronos" / "tools" / AGENT_KIND / AGENT_NAME


def _make_run_stats(*, calls: int, errors: int, human_rescue: bool) -> RunStats:
    entry = AdoptedToolRunStats(calls=calls, errors=errors, kind=AGENT_KIND, human_rescue=human_rescue)
    now = datetime.now(tz=UTC)
    return RunStats(
        run_index=0,
        started_at=now,
        ended_at=now,
        duration_seconds=10.0,
        model="default",
        real_model=None,
        mode="auto",
        exit_reason="WAIT" if human_rescue else "DONE",
        tool_uses={},
        adopted_tool_uses={AGENT_NAME: entry},
    )


def _fake_stream_events(tool_name: str, tool_input: dict) -> list[dict]:
    """Minimal Claude stream-json events with one Skill/Agent tool use."""
    return [
        {
            "type": "assistant",
            "message": {
                "content": [
                    {
                        "type": "tool_use",
                        "id": "toolu_e2e_01",
                        "name": tool_name,
                        "input": tool_input,
                    }
                ]
            },
        },
        {
            "type": "user",
            "message": {
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "toolu_e2e_01",
                        "content": "Skill executed successfully.",
                    }
                ]
            },
        },
        {"type": "result", "subtype": "success", "session_id": "sess-e2e"},
    ]


def _evolve_agent_output() -> str:
    # Must not have leading whitespace — _EVOLVE_BLOCK_RE matches literal "EVOLVE:\n".
    return (
        "Running analysis on adopted tools...\n\n"
        "EVOLVE:\n"
        f"kind: {AGENT_KIND}\n"
        f"name: {AGENT_NAME}\n"
        "rationale: Success rate is only 33%. Review instructions are too vague.\n"
        "revised_content: |\n"
        "  # Reviewer (revised)\n"
        "  More thorough review instructions.\n"
        "END_EVOLVE\n\n"
        "Done.\n"
    )


# ---------------------------------------------------------------------------
# Step 1: Config source → refresh → discovered_tools rows in SQLite
# ---------------------------------------------------------------------------


def test_step1_discovery_refresh_populates_db(tmp_path: Path) -> None:
    """upsert_discovered() writes rows; list_discovered() returns them."""
    db_path = tmp_path / "index.db"
    _create_db(db_path)

    item = _make_discovered_item()
    upsert_discovered(db_path, [item])

    rows = list_discovered(db_path)
    assert len(rows) == 1

    row = rows[0]
    assert row.source_url == SOURCE_URL
    assert row.source_slug == SOURCE_SLUG
    assert row.kind == AGENT_KIND
    assert row.name == AGENT_NAME
    assert row.source_sha == SOURCE_SHA
    assert row.relative_path == f".claude/agents/{AGENT_NAME}.md"


def test_step1_upsert_is_idempotent(tmp_path: Path) -> None:
    """Upserting the same item twice does not create duplicates."""
    db_path = tmp_path / "index.db"
    _create_db(db_path)

    item = _make_discovered_item()
    upsert_discovered(db_path, [item])
    upsert_discovered(db_path, [item])

    rows = list_discovered(db_path)
    assert len(rows) == 1


# ---------------------------------------------------------------------------
# Step 2: Adopt agent → manifest.yml written with correct hashes
# ---------------------------------------------------------------------------


async def test_step2_adopt_writes_manifest(tmp_path: Path) -> None:
    """adopt() copies the agent file and writes manifest.yml with matching hashes."""
    spaces_dir = tmp_path / "spaces"
    disc_base = tmp_path / "disc"
    db_path = tmp_path / "index.db"

    spaces_dir.mkdir()
    disc_base.mkdir()
    _create_db(db_path)

    item = _make_discovered_item()
    upsert_discovered(db_path, [item])
    _write_clone(disc_base)

    manifest = await adopt(
        SPACE_ID, SOURCE_SLUG, AGENT_KIND, AGENT_NAME,
        spaces_dir=spaces_dir,
        discovery_base=disc_base,
        db_path=db_path,
    )

    # Manifest fields
    assert manifest.kind == AGENT_KIND
    assert manifest.name == AGENT_NAME
    assert manifest.source_url == SOURCE_URL
    assert manifest.source_slug == SOURCE_SLUG
    assert manifest.source_sha == SOURCE_SHA
    assert manifest.evolved is False
    assert manifest.base_sha == manifest.local_sha

    # Files on disk
    dest = _adopt_dir(spaces_dir)
    assert (dest / "manifest.yml").exists()
    assert (dest / f"{AGENT_NAME}.md").read_text(encoding="utf-8") == AGENT_BODY

    # Manifest round-trips correctly
    on_disk = yaml.safe_load((dest / "manifest.yml").read_text(encoding="utf-8"))
    assert on_disk["evolved"] is False
    assert on_disk["base_sha"] == on_disk["local_sha"]
    assert on_disk["source_sha"] == SOURCE_SHA

    # sha matches independently-computed value
    expected_sha = _compute_sha(dest)
    assert manifest.local_sha == expected_sha


# ---------------------------------------------------------------------------
# Step 3: Task run with adopted tool → ToolCallTrace.adopted_tool_id set
# ---------------------------------------------------------------------------


def test_step3_trace_tagging_adopted_tool_id(tmp_path: Path) -> None:
    """extract_run_trace() sets adopted_tool_id on Skill calls matching an adopted tool."""
    spaces_dir = tmp_path / "spaces"
    adopt_dir = _adopt_dir(spaces_dir)
    sha = "aaaa1111"
    _write_manifest_raw(adopt_dir, base_sha=sha, local_sha=sha)

    # adopted_index_for_space reads the manifests on disk
    index = adopted_index_for_space(SPACE_ID, spaces_dir=spaces_dir)
    assert AGENT_NAME in index
    assert index[AGENT_NAME] == (AGENT_NAME, AGENT_KIND)

    # Simulate a run where the agent invoked the adopted skill via Skill tool
    events = _fake_stream_events("Skill", {"skill": AGENT_NAME})
    now = datetime.now(tz=UTC)
    trace = extract_run_trace(
        events,
        task_id="task-e2e-1",
        space_id=SPACE_ID,
        run_index=0,
        model="default",
        mode="auto",
        started_at=now,
        ended_at=now,
        exit_reason="DONE",
        session_id=None,
        had_crash=False,
        adopted_index=index,
    )

    # Exactly one tool call was recorded
    assert len(trace.tool_calls) == 1
    tc: ToolCallTrace = trace.tool_calls[0]

    assert tc.name == "Skill"
    assert tc.adopted_tool_id == AGENT_NAME
    assert tc.adopted_tool_kind == AGENT_KIND


def test_step3_non_adopted_skill_not_tagged(tmp_path: Path) -> None:
    """Skill calls for tools not in the adopted index leave adopted_tool_id as None."""
    spaces_dir = tmp_path / "spaces"

    # No tools adopted → empty index
    index = adopted_index_for_space(SPACE_ID, spaces_dir=spaces_dir)

    events = _fake_stream_events("Skill", {"skill": "some-other-skill"})
    now = datetime.now(tz=UTC)
    trace = extract_run_trace(
        events,
        task_id="task-e2e-2",
        space_id=SPACE_ID,
        run_index=0,
        model="default",
        mode="auto",
        started_at=now,
        ended_at=now,
        exit_reason="DONE",
        session_id=None,
        had_crash=False,
        adopted_index=index,
    )

    tc = trace.tool_calls[0]
    assert tc.adopted_tool_id is None
    assert tc.adopted_tool_kind is None


# ---------------------------------------------------------------------------
# Step 4: Low-success telemetry → create_evolve_task → EVOLVE: → PR
# ---------------------------------------------------------------------------


async def test_step4_evolve_flow_pr_and_local_sha(tmp_spaces_dir: Path, task_store) -> None:
    """Full evolve flow: low telemetry → task created → EVOLVE parsed →
    open_evolve_prs updates file, sets evolved=True, returns PR URL."""

    # ---- Setup: adopt a tool so open_evolve_prs has something to update ----
    adopt_dir = _adopt_dir(tmp_spaces_dir)
    adopt_dir.mkdir(parents=True, exist_ok=True)
    agent_file = adopt_dir / f"{AGENT_NAME}.md"
    agent_file.write_text(AGENT_BODY, encoding="utf-8")

    # Compute the initial sha from the file (matches _compute_sha logic)
    initial_sha = _compute_sha(adopt_dir)
    _write_manifest_raw(adopt_dir, base_sha=initial_sha, local_sha=initial_sha)

    # ---- Fake stats: 12 calls, 8 errors → success_rate ≈ 33%, human_rescue ----
    run_stats = _make_run_stats(calls=12, errors=8, human_rescue=True)
    task_stats = TaskStats(task_id="task-dummy", space_id=SPACE_ID, title="dummy", runs=[run_stats])

    stats_store = MagicMock()
    stats_store.list_space = AsyncMock(return_value=[task_stats])

    # ---- Step 4a: create_evolve_task ----
    evolve_task = await create_evolve_task(
        SPACE_ID,
        task_store=task_store,
        spaces_dir=tmp_spaces_dir,
        stats_store=stats_store,
    )

    assert evolve_task.title == EVOLVE_TITLE
    assert evolve_task.agent_mode == "plan"
    assert AGENT_NAME in evolve_task.brief
    assert "calls" in evolve_task.brief.lower()

    # ---- Step 4b: parse mock agent output ----
    agent_output = _evolve_agent_output()
    proposals = parse_evolve_blocks(agent_output)

    assert len(proposals) == 1
    proposal = proposals[0]
    assert proposal.kind == AGENT_KIND
    assert proposal.name == AGENT_NAME
    assert "33%" in proposal.rationale or "vague" in proposal.rationale

    # ---- Step 4c: open_evolve_prs with mocked commit_fn ----
    pr_calls: list[tuple] = []

    async def mock_commit_fn(worktree: Path, branch: str, title: str, body: str) -> str:
        pr_calls.append((worktree, branch, title, body))
        return "https://github.com/example/tools/pull/42"

    pr_urls = await open_evolve_prs(
        SPACE_ID,
        proposals,
        spaces_dir=tmp_spaces_dir,
        _commit_fn=mock_commit_fn,
    )

    # ---- Assertions ----

    # PR URL returned
    assert pr_urls == ["https://github.com/example/tools/pull/42"]

    # commit_fn called with correct branch naming and title
    assert len(pr_calls) == 1
    _, branch, title, body = pr_calls[0]
    assert branch.startswith(f"cronos/evolve/{AGENT_KIND}-{AGENT_NAME}-")
    assert title == f"evolve: {AGENT_KIND}/{AGENT_NAME}"

    # Vendored file updated with revised content (strip trailing whitespace for yaml block scalar)
    written = agent_file.read_text(encoding="utf-8")
    assert "Reviewer (revised)" in written
    assert "More thorough review instructions" in written
    assert AGENT_BODY.strip() not in written

    # manifest.yml: local_sha changed, evolved=True
    manifest = _read_manifest(adopt_dir / "manifest.yml")
    assert manifest.evolved is True
    assert manifest.local_sha != initial_sha
    assert manifest.base_sha == initial_sha  # base unchanged; only local advanced


async def test_step4_evolve_no_tools_still_creates_task(tmp_spaces_dir: Path, task_store) -> None:
    """create_evolve_task works even when no tools are adopted."""
    task = await create_evolve_task(
        SPACE_ID,
        task_store=task_store,
        spaces_dir=tmp_spaces_dir,
    )
    assert task.title == EVOLVE_TITLE
    assert "|---" in task.brief  # table header present even when empty
