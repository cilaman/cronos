"""
Tests for lib/node_status.py — parse_node_status().

Covers:
  - Valid block parsed correctly from fixture file
  - All fields populated on NodeStatusBlock
  - Returns None when no block present
  - Returns None on malformed JSON inside the fence
  - Returns None on empty status value
  - Handles multiple blocks (returns first)
  - open_questions defaults to empty list when absent
  - fields defaults to empty dict when absent
  - Coexistence with delivery_status (unrelated fence is ignored)
  - Open vocabulary: any non-empty string is accepted as status
  - Case-insensitive: status is lowercased on parse
  - No telemetry attribute on NodeStatusBlock (intentional omission)
"""

from __future__ import annotations

import json
import pathlib
import textwrap

import pytest

from lib.node_status import NodeStatusBlock, parse_node_status

FIXTURES_DIR = pathlib.Path(__file__).parent / "fixtures"


class TestParseFromFixture:
    def test_fixture_file_parses(self):
        text = (FIXTURES_DIR / "node_status_sample.md").read_text()
        block = parse_node_status(text)
        assert block is not None

    def test_fixture_status(self):
        text = (FIXTURES_DIR / "node_status_sample.md").read_text()
        block = parse_node_status(text)
        assert block.status == "done"

    def test_fixture_produces(self):
        text = (FIXTURES_DIR / "node_status_sample.md").read_text()
        block = parse_node_status(text)
        assert block.produces == "research"

    def test_fixture_artifact_paths(self):
        text = (FIXTURES_DIR / "node_status_sample.md").read_text()
        block = parse_node_status(text)
        assert block.artifact_paths == [
            ".cronos/pipeline/sg2-node-status-general-sentinel/scout-report-sg2-node-status-general-sentinel.md"
        ]

    def test_fixture_fields(self):
        text = (FIXTURES_DIR / "node_status_sample.md").read_text()
        block = parse_node_status(text)
        assert block.fields["memory_hits"] == 2
        assert block.fields["critical_blockers"] == []
        assert block.fields["scope_files_count"] == 6

    def test_fixture_open_questions_empty(self):
        text = (FIXTURES_DIR / "node_status_sample.md").read_text()
        block = parse_node_status(text)
        assert block.open_questions == []


class TestReturnTypes:
    def test_returns_dataclass(self):
        text = textwrap.dedent("""\
            ```node_status
            {"status":"done","artifact_paths":[],"produces":"design","fields":{}}
            ```
        """)
        block = parse_node_status(text)
        assert isinstance(block, NodeStatusBlock)

    def test_no_telemetry_attribute(self):
        """R7: NodeStatusBlock intentionally omits telemetry (it is a general envelope)."""
        block = NodeStatusBlock(
            status="done",
            artifact_paths=[],
            produces="research",
            fields={},
            open_questions=[],
        )
        assert not hasattr(block, "telemetry")


class TestMissingBlock:
    def test_no_block_returns_none(self):
        assert parse_node_status("No fenced block here.") is None

    def test_empty_string_returns_none(self):
        assert parse_node_status("") is None

    def test_wrong_fence_tag_returns_none(self):
        text = "```delivery_status\n{}\n```"
        assert parse_node_status(text) is None

    def test_cronos_status_fence_not_matched(self):
        text = "```cronos_status\n{\"status\": \"DONE\"}\n```"
        assert parse_node_status(text) is None

    def test_yaml_fence_not_matched(self):
        text = "```yaml\nstatus: done\n```"
        assert parse_node_status(text) is None


class TestMalformedBlocks:
    def test_invalid_json_returns_none(self):
        text = "```node_status\nnot valid json\n```"
        assert parse_node_status(text) is None

    def test_json_array_not_object_returns_none(self):
        text = "```node_status\n[1, 2, 3]\n```"
        assert parse_node_status(text) is None

    def test_empty_status_value_returns_none(self):
        text = '```node_status\n{"status": ""}\n```'
        assert parse_node_status(text) is None

    def test_missing_status_field_returns_none(self):
        text = '```node_status\n{"produces": "research"}\n```'
        assert parse_node_status(text) is None

    def test_null_status_returns_none(self):
        text = '```node_status\n{"status": null}\n```'
        assert parse_node_status(text) is None


class TestOpenVocabulary:
    """Status field accepts any non-empty string — the vocab is open."""

    @pytest.mark.parametrize("status", ["done", "wait", "blocked", "needs_fix", "failed"])
    def test_delivery_vocab_accepted(self, status: str):
        text = f'```node_status\n{{"status": "{status}"}}\n```'
        block = parse_node_status(text)
        assert block is not None
        assert block.status == status

    @pytest.mark.parametrize("status", ["custom_status", "phase_complete", "pending_review"])
    def test_custom_vocab_accepted(self, status: str):
        text = f'```node_status\n{{"status": "{status}"}}\n```'
        block = parse_node_status(text)
        assert block is not None
        assert block.status == status


class TestCaseInsensitive:
    def test_uppercase_status_lowercased(self):
        text = '```node_status\n{"status": "DONE"}\n```'
        block = parse_node_status(text)
        assert block is not None
        assert block.status == "done"

    def test_mixed_case_status_lowercased(self):
        text = '```node_status\n{"status": "Needs_Fix"}\n```'
        block = parse_node_status(text)
        assert block is not None
        assert block.status == "needs_fix"


class TestDefaults:
    def _block_text(self, **overrides) -> str:
        base: dict = {"status": "done"}
        base.update(overrides)
        return f"```node_status\n{json.dumps(base)}\n```"

    def test_open_questions_defaults_to_empty_list(self):
        text = self._block_text()
        block = parse_node_status(text)
        assert block is not None
        assert block.open_questions == []

    def test_fields_defaults_to_empty_dict(self):
        text = self._block_text()
        block = parse_node_status(text)
        assert block is not None
        assert block.fields == {}

    def test_artifact_paths_defaults_to_empty_list(self):
        text = self._block_text(produces="implementation")
        block = parse_node_status(text)
        assert block is not None
        assert block.artifact_paths == []

    def test_produces_defaults_to_empty_string(self):
        text = self._block_text()
        block = parse_node_status(text)
        assert block is not None
        assert block.produces == ""


class TestMultipleBlocks:
    def test_returns_first_block(self):
        first = json.dumps({"status": "done", "artifact_paths": ["first.md"], "produces": "research"})
        second = json.dumps({"status": "failed", "artifact_paths": ["second.md"], "produces": "design"})
        text = f"```node_status\n{first}\n```\n\nSome prose.\n\n```node_status\n{second}\n```"
        block = parse_node_status(text)
        assert block is not None
        assert block.produces == "research"
        assert block.artifact_paths == ["first.md"]


class TestCoexistence:
    def test_delivery_status_fence_ignored(self):
        text = textwrap.dedent("""\
            ```delivery_status
            {"status": "done", "artifact_paths": [], "produces": "doc", "fields": {}, "telemetry": {}}
            ```

            ```node_status
            {"status": "done", "produces": "research", "artifact_paths": ["report.md"]}
            ```
        """)
        block = parse_node_status(text)
        assert block is not None
        assert block.produces == "research"
        assert block.artifact_paths == ["report.md"]

    def test_only_delivery_status_block_returns_none(self):
        text = textwrap.dedent("""\
            ```delivery_status
            {"status": "done", "artifact_paths": [], "produces": "doc", "fields": {}, "telemetry": {}}
            ```
        """)
        assert parse_node_status(text) is None

    def test_cronos_status_fence_ignored(self):
        text = textwrap.dedent("""\
            ```cronos_status
            {"status": "DONE"}
            ```

            ```node_status
            {"status": "done", "produces": "test"}
            ```
        """)
        block = parse_node_status(text)
        assert block is not None
        assert block.produces == "test"
