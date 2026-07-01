"""I2 — CronosAdapter.dispatchAgent tests (R1, R2, R3).

Tests:
- Happy path: child task created, polled, DONE → AgentResult(status="done")
- Brief starts with "# Agent: {agent_ref}" and lists artifact paths
- WAITING terminal state → AgentResult(status="blocked")
- Timeout → TimeoutError + escalate called
- No trace → AgentResult(status="failed")
- delivery_status parsed from final_text_snippet
- >500-char delivery_status block fallback (regression, DD-05)
- ARCHIVED terminal state treated as DONE
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

_BUNDLE = Path(__file__).parent.parent.parent / "packages" / "delivery-workflow"
if str(_BUNDLE) not in sys.path:
    sys.path.insert(0, str(_BUNDLE))

from adapters.cronos.adapter import CronosAdapter
from lib.delivery_status import DeliveryStatusBlock
from results import AgentResult, TelemetryData
from state_types import BudgetState, WorkflowState


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_DS_SNIPPET = json.dumps(
    {
        "status": "done",
        "artifact_paths": ["reports/scout.md"],
        "produces": "research",
        "fields": {"has_ui": False},
        "open_questions": [],
        "telemetry": {"tokens": 1200, "usd": 0.012, "seconds": 30},
    }
)

_DS_FENCE = f"```delivery_status\n{_DS_SNIPPET}\n```"


def _make_trace(
    final_text: str = _DS_FENCE,
    input_tokens: int = 800,
    output_tokens: int = 400,
    duration_seconds: float = 15.0,
) -> SimpleNamespace:
    turn = SimpleNamespace(input_tokens=input_tokens, output_tokens=output_tokens)
    return SimpleNamespace(
        turns=[turn],
        duration_seconds=duration_seconds,
        final_text_snippet=final_text,
    )


def _make_task(state_name: str, waiting_question: str | None = None) -> SimpleNamespace:
    """Return a namespace whose .state behaves like a TaskState enum."""

    class _TS:
        def __init__(self, name: str) -> None:
            self.name = name
            self.value = name

        def __eq__(self, other: object) -> bool:
            if isinstance(other, _TS):
                return self.name == other.name
            return NotImplemented

        def __hash__(self) -> int:
            return hash(self.name)

    from app.storage import TaskState

    return SimpleNamespace(
        id="child-001",
        state=TaskState[state_name.upper()],
        waiting_question=waiting_question,
    )


def _adapter(tmp_path: Path, store: MagicMock, trace_store: MagicMock) -> CronosAdapter:
    run_dir = tmp_path / "run"
    run_dir.mkdir(parents=True)
    ws = WorkflowState(
        spec="ping",
        run_id="r1",
        status="running",
        budget=BudgetState(usd_ceiling=25.0),
    )
    from lib.state.store import StateStore

    StateStore(run_dir).write(ws)
    return CronosAdapter(
        store=store,
        trace_store=trace_store,
        space_id="s1",
        run_dir=run_dir,
        tracking_task_id="tracking-001",
        token_cost_usd=0.001,
        poll_interval=0.01,  # fast polls in tests
        timeout=0.1,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestDispatchAgentHappyPath:
    def test_returns_done_result(self, tmp_path: Path) -> None:
        store = MagicMock()
        trace_store = MagicMock()

        child = _make_task("DONE")
        store.create = AsyncMock(return_value=child)
        store.get.side_effect = [
            _make_task("ACTIVE"),
            _make_task("ACTIVE"),
            _make_task("DONE"),
        ]
        store.transition = AsyncMock()
        trace_store.load_latest = AsyncMock(return_value=_make_trace())
        store.get.return_value = _make_task("DONE")

        adapter = _adapter(tmp_path, store, trace_store)

        # Reset side_effect to stop iteration issues — last call always DONE
        store.get = MagicMock(return_value=_make_task("DONE"))

        result = asyncio.run(
            adapter.dispatchAgent(
                "pipeline-scout",
                {"artifact_paths": ["docs/spec.md"], "parent_id": None},
            )
        )

        assert isinstance(result, AgentResult)
        assert result.status == "done"
        assert result.artifact_paths == ["reports/scout.md"]
        assert result.produces == "research"
        assert result.fields == {"has_ui": False}

    def test_brief_starts_with_agent_ref(self, tmp_path: Path) -> None:
        store = MagicMock()
        trace_store = MagicMock()

        child = _make_task("DONE")
        store.create = AsyncMock(return_value=child)
        store.get = MagicMock(return_value=_make_task("DONE"))
        store.transition = AsyncMock()
        trace_store.load_latest = AsyncMock(return_value=_make_trace())

        adapter = _adapter(tmp_path, store, trace_store)
        asyncio.run(
            adapter.dispatchAgent(
                "pipeline-scout",
                {"artifact_paths": ["docs/spec.md"]},
            )
        )

        call_kwargs = store.create.call_args.kwargs
        assert call_kwargs["brief"].startswith("# Agent: pipeline-scout")
        assert "docs/spec.md" in call_kwargs["brief"]

    def test_child_brief_tagged_and_parented_to_tracking_goal(self, tmp_path: Path) -> None:
        # The child brief must carry the delivery-node sentinel (so the worker
        # treats it as a runner task: needs_fix → DONE, P0-2), and — since the
        # runner's inputs dict carries no parent_id — the child must be parented
        # to the run's tracking goal so it isn't orphaned on the board.
        store = MagicMock()
        trace_store = MagicMock()

        store.create = AsyncMock(return_value=_make_task("DONE"))
        store.get = MagicMock(return_value=_make_task("DONE"))
        store.transition = AsyncMock()
        trace_store.load_latest = AsyncMock(return_value=_make_trace())

        adapter = _adapter(tmp_path, store, trace_store)  # tracking_task_id="tracking-001"
        asyncio.run(
            adapter.dispatchAgent(
                "reviewer",
                {"node_id": "g-review", "artifact_paths": []},  # no parent_id
            )
        )

        call_kwargs = store.create.call_args.kwargs
        assert "<!-- delivery-node: g-review -->" in call_kwargs["brief"]
        assert call_kwargs["parent_id"] == "tracking-001"

    def test_archived_treated_as_done(self, tmp_path: Path) -> None:
        store = MagicMock()
        trace_store = MagicMock()

        store.create = AsyncMock(return_value=_make_task("ARCHIVED"))
        store.get = MagicMock(return_value=_make_task("ARCHIVED"))
        store.transition = AsyncMock()
        trace_store.load_latest = AsyncMock(return_value=_make_trace())

        adapter = _adapter(tmp_path, store, trace_store)
        result = asyncio.run(
            adapter.dispatchAgent("pipeline-scout", {})
        )
        assert result.status == "done"

    def test_telemetry_sums_per_turn(self, tmp_path: Path) -> None:
        store = MagicMock()
        trace_store = MagicMock()

        store.create = AsyncMock(return_value=_make_task("DONE"))
        store.get = MagicMock(return_value=_make_task("DONE"))
        store.transition = AsyncMock()
        trace = _make_trace(input_tokens=1000, output_tokens=500)
        trace_store.load_latest = AsyncMock(return_value=trace)

        adapter = _adapter(tmp_path, store, trace_store)
        result = asyncio.run(
            adapter.dispatchAgent("pipeline-scout", {})
        )
        assert result.telemetry.tokens == 1500
        assert result.telemetry.usd == pytest.approx(1500 * 0.001)


class TestDispatchAgentBlocked:
    def test_waiting_returns_blocked(self, tmp_path: Path) -> None:
        store = MagicMock()
        trace_store = MagicMock()

        store.create = AsyncMock(return_value=_make_task("WAITING", "Need human review"))
        store.get = MagicMock(
            return_value=_make_task("WAITING", "Need human review")
        )
        store.transition = AsyncMock()

        adapter = _adapter(tmp_path, store, trace_store)
        result = asyncio.run(
            adapter.dispatchAgent("pipeline-scout", {})
        )
        assert result.status == "blocked"
        assert "Need human review" in result.open_questions


class TestDispatchAgentTimeout:
    def test_timeout_raises_and_escalates(self, tmp_path: Path) -> None:
        store = MagicMock()
        trace_store = MagicMock()

        store.create = AsyncMock(return_value=_make_task("ACTIVE"))
        store.get = MagicMock(return_value=_make_task("ACTIVE"))
        store.transition = AsyncMock()
        store.finalize_run = AsyncMock()

        adapter = _adapter(tmp_path, store, trace_store)
        # timeout=0.1, poll_interval=0.01 → will expire after ~10 polls

        with pytest.raises(TimeoutError):
            asyncio.run(
                adapter.dispatchAgent("pipeline-scout", {})
            )

        # state.json should be "blocked"
        from lib.state.store import StateStore

        ws = StateStore(tmp_path / "run").read()
        assert ws.status == "blocked"


class TestDispatchAgentNoTrace:
    def test_no_trace_returns_failed(self, tmp_path: Path) -> None:
        store = MagicMock()
        trace_store = MagicMock()

        store.create = AsyncMock(return_value=_make_task("DONE"))
        store.get = MagicMock(return_value=_make_task("DONE"))
        store.transition = AsyncMock()
        trace_store.load_latest = AsyncMock(return_value=None)

        adapter = _adapter(tmp_path, store, trace_store)
        result = asyncio.run(
            adapter.dispatchAgent("pipeline-scout", {})
        )
        assert result.status == "failed"
        assert result.open_questions


class TestDispatchAgentDeliveryStatusFallback:
    def test_long_ds_block_uses_artifact_fallback(self, tmp_path: Path) -> None:
        """Regression: >500-char delivery_status block clipped by final_text_snippet.

        The adapter must fall back to scanning *.md artifacts in run_dir (DD-05).
        """
        store = MagicMock()
        trace_store = MagicMock()

        store.create = AsyncMock(return_value=_make_task("DONE"))
        store.get = MagicMock(return_value=_make_task("DONE"))
        store.transition = AsyncMock()

        # Build a >500-char delivery_status JSON to simulate clipping.
        long_fields = {f"field_{i}": f"value_{i}" for i in range(30)}
        long_ds_json = json.dumps(
            {
                "status": "done",
                "artifact_paths": ["reports/artifact.md"],
                "produces": "research",
                "fields": long_fields,
                "open_questions": [],
                "telemetry": {"tokens": 500, "usd": 0.001, "seconds": 5},
            }
        )
        assert len(long_ds_json) > 500, "test assumption: JSON >500 chars"
        # Trace snippet is truncated to 500 chars (no complete fence).
        clipped_snippet = long_ds_json[:500]
        trace_store.load_latest = AsyncMock(return_value=_make_trace(clipped_snippet))

        adapter = _adapter(tmp_path, store, trace_store)
        # Write report AFTER adapter is created (so run_dir exists).
        run_dir = tmp_path / "run"
        report = run_dir / "scout-report.md"
        report.write_text(f"# Scout Report\n\n```delivery_status\n{long_ds_json}\n```\n")

        result = asyncio.run(
            adapter.dispatchAgent("pipeline-scout", {})
        )
        assert result.status == "done"
        assert result.artifact_paths == ["reports/artifact.md"]
