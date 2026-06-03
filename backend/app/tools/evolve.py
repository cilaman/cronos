"""Evolve-tools: helpers for the weekly tool-improvement agent and PR flow."""
from __future__ import annotations

import logging
import re
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Awaitable, Callable

import yaml
from pydantic import BaseModel

if TYPE_CHECKING:
    from ..stats_store import StatsStore
    from ..storage import TaskStore

log = logging.getLogger(__name__)

EVOLVE_TITLE = "Evolve adopted tools"

# Matches EVOLVE:\n<yaml>\nEND_EVOLVE blocks (non-greedy, DOTALL).
_EVOLVE_BLOCK_RE = re.compile(r"EVOLVE:\n(.*?)\nEND_EVOLVE", re.DOTALL)


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


class EvolveProposal(BaseModel):
    kind: str
    name: str
    rationale: str
    revised_content: str


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------


def parse_evolve_blocks(final_text: str) -> list[EvolveProposal]:
    """Extract structured EVOLVE: … END_EVOLVE blocks from agent output."""
    proposals: list[EvolveProposal] = []
    for m in _EVOLVE_BLOCK_RE.finditer(final_text):
        block = m.group(1)
        try:
            data = yaml.safe_load(block)
            if not isinstance(data, dict):
                log.warning("parse_evolve_blocks: block is not a dict, skipping")
                continue
            proposals.append(EvolveProposal.model_validate(data))
        except Exception:
            log.warning("parse_evolve_blocks: failed to parse block (first 200 chars): %s", block[:200])
    return proposals


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _scan_adopted_tools(space_id: str, *, spaces_dir: Path) -> list[dict]:
    """List adopted tools for a space with their kind / name / manifest."""
    from ..tools.adoption import _read_manifest

    tools_dir = spaces_dir / space_id / ".cronos" / "tools"
    if not tools_dir.is_dir():
        return []
    results: list[dict] = []
    for manifest_path in tools_dir.rglob("manifest.yml"):
        try:
            parts = manifest_path.relative_to(tools_dir).parts
        except ValueError:
            continue
        if len(parts) != 3:
            continue
        kind, name = parts[0], parts[1]
        if kind.startswith("."):
            continue
        try:
            m = _read_manifest(manifest_path)
            results.append({"kind": kind, "name": name, "manifest": m})
        except Exception:
            log.warning("_scan_adopted_tools: failed to read manifest %s", manifest_path)
    return results


def _compute_tool_telemetry(
    name: str,
    kind: str,
    all_stats: list,
    *,
    window_days: int = 30,
) -> dict:
    """Compute telemetry for one tool from a list of TaskStats."""
    from_dt = datetime.now(tz=timezone.utc) - timedelta(days=window_days)
    total_calls = 0
    total_errors = 0
    rescue_count = 0
    for ts in all_stats:
        for run in ts.runs:
            run_dt = run.started_at
            if run_dt.tzinfo is None:
                run_dt = run_dt.replace(tzinfo=timezone.utc)
            if run_dt < from_dt:
                continue
            entry = run.adopted_tool_uses.get(name)
            if entry is None or entry.kind != kind:
                continue
            total_calls += entry.calls
            total_errors += entry.errors
            if entry.human_rescue:
                rescue_count += 1
    avg_success = round(1 - total_errors / total_calls, 4) if total_calls > 0 else 0.0
    return {
        "calls": total_calls,
        "errors": total_errors,
        "avg_success_rate": avg_success,
        "human_rescue_count": rescue_count,
    }


def _build_evolve_brief(
    space_id: str,
    tool_entries: list[dict],
    *,
    window_days: int = 30,
) -> str:
    """Build the brief for the 'Evolve adopted tools' task."""
    lines = [
        f"## Evolve adopted tools in space `{space_id}`",
        "",
        f"Read per-tool telemetry (window: {window_days}d) for every adopted tool in this space.",
        "Identify tools with `avg_success_rate < 0.6` OR `human_rescue_count >= 3`.",
        "Output one structured `EVOLVE:` block per underperforming tool.",
        "",
        "### Telemetry snapshot",
        "",
        "| kind | name | calls | avg_success_rate | human_rescue_count |",
        "|------|------|-------|-----------------|-------------------|",
    ]
    for e in tool_entries:
        t = e.get("telemetry", {})
        lines.append(
            f"| {e['kind']} | {e['name']} "
            f"| {t.get('calls', 0)} "
            f"| {t.get('avg_success_rate', 0.0):.2%} "
            f"| {t.get('human_rescue_count', 0)} |"
        )
    lines += [
        "",
        "### EVOLVE block format",
        "",
        "For each underperforming tool output a block with this exact format:",
        "",
        "```",
        "EVOLVE:",
        "kind: <agent|skill|command>",
        "name: <tool-name>",
        "rationale: >",
        "  One paragraph explaining the failure pattern and the proposed improvement.",
        "revised_content: |",
        "  # Full revised content of the main tool file (agent.md / SKILL.md)",
        "  ...",
        "END_EVOLVE",
        "```",
        "",
        f"Use `GET /api/spaces/{space_id}/tools/{{kind}}/{{name}}/telemetry?window={window_days}d`"
        " for detailed stats.",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def create_evolve_task(
    space_id: str,
    *,
    task_store: "TaskStore",
    spaces_dir: "Path | None" = None,
    stats_store: "StatsStore | None" = None,
    window_days: int = 30,
):
    """Create an 'Evolve adopted tools' task with a per-tool telemetry brief.

    Returns the created Task object.
    """
    from ..tools.adoption import SPACES_DIR as _DEFAULT_SPACES_DIR

    _spaces = spaces_dir or _DEFAULT_SPACES_DIR

    adopted = _scan_adopted_tools(space_id, spaces_dir=_spaces)

    if stats_store is not None and adopted:
        all_stats = await stats_store.list_space(space_id)
        for entry in adopted:
            entry["telemetry"] = _compute_tool_telemetry(
                entry["name"],
                entry["kind"],
                all_stats,
                window_days=window_days,
            )

    brief = _build_evolve_brief(space_id, adopted, window_days=window_days)

    task = await task_store.create(
        space_id=space_id,
        title=EVOLVE_TITLE,
        brief=brief,
        type="task",
        agent_mode="plan",
    )
    log.info("create_evolve_task: created %s for space %s", task.id, space_id)
    return task


async def open_evolve_prs(
    space_id: str,
    proposals: list[EvolveProposal],
    *,
    spaces_dir: "Path | None" = None,
    _commit_fn: "Callable[[Path, str, str, str], Awaitable[str | None]] | None" = None,
) -> list[str]:
    """Write revised tool files, bump local_sha, open PRs.

    For each proposal:
    1. Writes ``revised_content`` to the vendored tool file.
    2. Calls ``recompute_local_sha`` (sets ``evolved=True``).
    3. Calls ``_commit_fn(space_dir, branch, title, body)`` to commit and open a PR.

    ``_commit_fn`` signature: ``(worktree, branch, title, body) -> Awaitable[str | None]``
    Returns the PR URL (or proposed-PR path) on success, None on failure.

    Returns a list of PR URLs / paths for successfully opened PRs.
    """
    from ..tools.adoption import SPACES_DIR as _DEFAULT_SPACES_DIR, _adopt_dir, recompute_local_sha

    _spaces = spaces_dir or _DEFAULT_SPACES_DIR
    space_dir = _spaces / space_id

    if _commit_fn is None:
        from ..autopilot_pr import commit_and_open_pr

        async def _default_commit_fn(
            worktree: Path, branch: str, title: str, body: str
        ) -> str | None:
            result = await commit_and_open_pr(
                worktree, branch, title, body, space_dir=space_dir
            )
            return result.pr_url or result.proposed_pr_path

        _commit_fn = _default_commit_fn

    results: list[str] = []
    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")

    for proposal in proposals:
        kind, name = proposal.kind, proposal.name
        adopt_dir = _adopt_dir(space_id, kind, name, spaces_dir=_spaces)
        if not adopt_dir.exists():
            log.warning(
                "open_evolve_prs: %s/%s not adopted in space %s — skipping",
                kind, name, space_id,
            )
            continue

        # Write revised content to the main tool file.
        target = adopt_dir / ("SKILL.md" if kind == "skill" else f"{name}.md")
        try:
            target.write_text(proposal.revised_content, encoding="utf-8")
        except Exception:
            log.exception("open_evolve_prs: write failed for %s/%s", kind, name)
            continue

        # Recompute local_sha → marks evolved=True when content changed.
        try:
            recompute_local_sha(space_id, kind, name, spaces_dir=_spaces)
        except Exception:
            log.exception("open_evolve_prs: sha recompute failed for %s/%s", kind, name)

        # Open PR via the commit callable.
        branch = f"cronos/evolve/{kind}-{name}-{ts}"
        title = f"evolve: {kind}/{name}"
        body = f"## evolve: {kind}/{name}\n\n{proposal.rationale}\n"

        try:
            pr_url = await _commit_fn(space_dir, branch, title, body)
            if pr_url:
                results.append(pr_url)
                log.info("open_evolve_prs: PR opened for %s/%s → %s", kind, name, pr_url)
        except Exception:
            log.exception("open_evolve_prs: commit_fn failed for %s/%s", kind, name)

    return results
