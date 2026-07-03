"""
Tests for lib/delivery_status.py — parse_delivery_status().

Covers:
  - Valid block parsed correctly from fixture file
  - All fields populated on DeliveryStatusBlock
  - Returns None when no block present
  - Returns None on malformed JSON inside the fence
  - Returns None on invalid status value
  - Handles multiple blocks (returns first)
  - open_questions defaults to empty list when absent
  - telemetry defaults to zero when fields missing
  - Coexistence with cronos_status (unrelated fence is ignored)
"""

from __future__ import annotations

import pathlib
import textwrap

import pytest

from delivery_workflow.lib.delivery_status import DeliveryStatusBlock, parse_delivery_status
from delivery_workflow.results import TelemetryData

FIXTURES_DIR = pathlib.Path(__file__).parent / "fixtures"


class TestParseFromFixture:
    def test_fixture_file_parses(self):
        text = (FIXTURES_DIR / "delivery_status_sample.md").read_text()
        block = parse_delivery_status(text)
        assert block is not None

    def test_fixture_status(self):
        text = (FIXTURES_DIR / "delivery_status_sample.md").read_text()
        block = parse_delivery_status(text)
        assert block.status == "done"

    def test_fixture_produces(self):
        text = (FIXTURES_DIR / "delivery_status_sample.md").read_text()
        block = parse_delivery_status(text)
        assert block.produces == "research"

    def test_fixture_artifact_paths(self):
        text = (FIXTURES_DIR / "delivery_status_sample.md").read_text()
        block = parse_delivery_status(text)
        assert block.artifact_paths == [
            ".cronos/pipeline/delivery-v1/scout-report-delivery-v1.md"
        ]

    def test_fixture_fields(self):
        text = (FIXTURES_DIR / "delivery_status_sample.md").read_text()
        block = parse_delivery_status(text)
        assert block.fields["memory_hits"] == 0
        assert block.fields["critical_blockers"] == ["G0.1", "G0.3", "G3.3", "G1.3"]
        assert block.fields["estimated_weeks_to_milestone"] == 4

    def test_fixture_open_questions_empty(self):
        text = (FIXTURES_DIR / "delivery_status_sample.md").read_text()
        block = parse_delivery_status(text)
        assert block.open_questions == []

    def test_fixture_telemetry(self):
        text = (FIXTURES_DIR / "delivery_status_sample.md").read_text()
        block = parse_delivery_status(text)
        assert isinstance(block.telemetry, TelemetryData)
        assert block.telemetry.tokens == 8240
        assert abs(block.telemetry.usd - 0.124) < 1e-9
        assert block.telemetry.seconds == 34.0


class TestReturnTypes:
    def test_returns_dataclass(self):
        text = textwrap.dedent("""\
            ```delivery_status
            {"status":"done","artifact_paths":[],"produces":"design","fields":{},"telemetry":{"tokens":1,"usd":0.0,"seconds":1.0}}
            ```
        """)
        block = parse_delivery_status(text)
        assert isinstance(block, DeliveryStatusBlock)
        assert isinstance(block.telemetry, TelemetryData)


class TestMissingBlock:
    def test_no_block_returns_none(self):
        assert parse_delivery_status("No fenced block here.") is None

    def test_empty_string_returns_none(self):
        assert parse_delivery_status("") is None

    def test_wrong_fence_tag_returns_none(self):
        text = "```cronos_status\n{}\n```"
        assert parse_delivery_status(text) is None

    def test_yaml_fence_not_matched(self):
        text = "```yaml\nstatus: done\n```"
        assert parse_delivery_status(text) is None


class TestMalformedBlocks:
    def test_invalid_json_returns_none(self):
        text = "```delivery_status\nnot valid json\n```"
        assert parse_delivery_status(text) is None

    def test_json_array_not_object_returns_none(self):
        text = '```delivery_status\n[1, 2, 3]\n```'
        assert parse_delivery_status(text) is None

    def test_invalid_status_value_returns_none(self):
        text = textwrap.dedent("""\
            ```delivery_status
            {"status":"DONE","artifact_paths":[],"produces":"doc","fields":{},"telemetry":{"tokens":1,"usd":0.0,"seconds":1.0}}
            ```
        """)
        assert parse_delivery_status(text) is None

    def test_unknown_status_value_returns_none(self):
        text = textwrap.dedent("""\
            ```delivery_status
            {"status":"partial","artifact_paths":[],"produces":"test","fields":{},"telemetry":{"tokens":1,"usd":0.0,"seconds":1.0}}
            ```
        """)
        assert parse_delivery_status(text) is None


class TestDefaults:
    def _block_text(self, **overrides) -> str:
        base = {
            "status": "done",
            "artifact_paths": [],
            "produces": "research",
            "fields": {},
            "telemetry": {"tokens": 10, "usd": 0.0, "seconds": 2.0},
        }
        base.update(overrides)
        import json
        return f"```delivery_status\n{json.dumps(base)}\n```"

    def test_open_questions_defaults_to_empty_list(self):
        text = self._block_text()
        block = parse_delivery_status(text)
        assert block.open_questions == []

    def test_fields_defaults_to_empty_dict(self):
        text = self._block_text()
        block = parse_delivery_status(text)
        assert block.fields == {}

    def test_telemetry_tokens_zero_when_missing(self):
        import json
        data = {
            "status": "done",
            "artifact_paths": [],
            "produces": "analysis",
            "fields": {"has_ui": False},
            "telemetry": {},
        }
        text = f"```delivery_status\n{json.dumps(data)}\n```"
        block = parse_delivery_status(text)
        assert block.telemetry.tokens == 0
        assert block.telemetry.usd == 0.0
        assert block.telemetry.seconds == 0.0

    def test_artifact_paths_defaults_to_empty_list(self):
        import json
        data = {
            "status": "blocked",
            "produces": "implementation",
            "fields": {},
            "telemetry": {"tokens": 1, "usd": 0.0, "seconds": 0.5},
        }
        text = f"```delivery_status\n{json.dumps(data)}\n```"
        block = parse_delivery_status(text)
        assert block.artifact_paths == []


class TestMultipleBlocks:
    def test_returns_first_block(self):
        import json
        first = json.dumps({
            "status": "done",
            "artifact_paths": ["first.md"],
            "produces": "research",
            "fields": {},
            "telemetry": {"tokens": 1, "usd": 0.0, "seconds": 1.0},
        })
        second = json.dumps({
            "status": "failed",
            "artifact_paths": ["second.md"],
            "produces": "design",
            "fields": {},
            "telemetry": {"tokens": 2, "usd": 0.0, "seconds": 2.0},
        })
        text = f"```delivery_status\n{first}\n```\n\nSome prose.\n\n```delivery_status\n{second}\n```"
        block = parse_delivery_status(text)
        assert block.produces == "research"
        assert block.artifact_paths == ["first.md"]


class TestAllStatusValues:
    @pytest.mark.parametrize("status", ["done", "blocked", "needs_fix", "failed"])
    def test_valid_status(self, status):
        import json
        data = {
            "status": status,
            "artifact_paths": [],
            "produces": "review",
            "fields": {"verdict": "pass"},
            "telemetry": {"tokens": 10, "usd": 0.01, "seconds": 3.0},
        }
        text = f"```delivery_status\n{json.dumps(data)}\n```"
        block = parse_delivery_status(text)
        assert block is not None
        assert block.status == status


class TestCoexistence:
    def test_cronos_status_fence_ignored(self):
        text = textwrap.dedent("""\
            Some text with a cronos_status block:

            ```cronos_status
            {"verdict": "pass"}
            ```

            And a delivery_status block:

            ```delivery_status
            {"status":"done","artifact_paths":[],"produces":"doc","fields":{},"telemetry":{"tokens":5,"usd":0.0,"seconds":1.0}}
            ```
        """)
        block = parse_delivery_status(text)
        assert block is not None
        assert block.produces == "doc"

    def test_only_cronos_status_block_returns_none(self):
        text = textwrap.dedent("""\
            ```cronos_status
            {"verdict": "pass", "status": "done"}
            ```
        """)
        assert parse_delivery_status(text) is None
