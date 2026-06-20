from __future__ import annotations

# Import both modules at collection time to catch any circular import immediately
from app.memory_parser import parse_cronos_status_block, parse_cronos_remember_blocks
from app.agent import parse_status, Status, STATUS_CONTRACT


# ---------------------------------------------------------------------------
# I1: TestParseCronosStatusBlock — parse_cronos_status_block() unit tests
# ---------------------------------------------------------------------------


class TestParseCronosStatusBlock:
    """Tests for parse_cronos_status_block() in memory_parser.py."""

    def test_empty_text_returns_none(self) -> None:
        assert parse_cronos_status_block("") == (None, None)

    def test_no_block_returns_none(self) -> None:
        text = "Some text\nSTATUS: DONE\nMore text"
        assert parse_cronos_status_block(text) == (None, None)

    def test_done_block(self) -> None:
        text = '```cronos_status\n{"status": "DONE", "summary": "Implemented the feature."}\n```'
        status, summary = parse_cronos_status_block(text)
        assert status == "DONE"
        assert summary == "Implemented the feature."

    def test_wait_block(self) -> None:
        text = '```cronos_status\n{"status": "WAIT", "summary": "Need your approval."}\n```'
        status, summary = parse_cronos_status_block(text)
        assert status == "WAIT"
        assert summary == "Need your approval."

    def test_blocked_block(self) -> None:
        text = '```cronos_status\n{"status": "BLOCKED", "summary": "Cannot access DB."}\n```'
        status, summary = parse_cronos_status_block(text)
        assert status == "BLOCKED"
        assert summary == "Cannot access DB."

    def test_with_artifacts_list(self) -> None:
        text = '```cronos_status\n{"status": "DONE", "summary": "Done.", "artifacts": ["a.py", "b.py"]}\n```'
        status, summary = parse_cronos_status_block(text)
        assert status == "DONE"
        assert summary == "Done."

    def test_artifacts_non_list_lenient(self) -> None:
        """Non-list artifacts field is accepted (lenient) — not rejected."""
        text = '```cronos_status\n{"status": "DONE", "summary": "Done.", "artifacts": "not-a-list"}\n```'
        status, summary = parse_cronos_status_block(text)
        assert status == "DONE"

    def test_summary_missing_returns_none_context(self) -> None:
        text = '```cronos_status\n{"status": "DONE"}\n```'
        status, summary = parse_cronos_status_block(text)
        assert status == "DONE"
        assert summary is None

    def test_missing_status_field_skipped(self) -> None:
        text = '```cronos_status\n{"summary": "Something happened."}\n```'
        assert parse_cronos_status_block(text) == (None, None)

    def test_invalid_status_value_skipped(self) -> None:
        text = '```cronos_status\n{"status": "FINISHED", "summary": "Done."}\n```'
        assert parse_cronos_status_block(text) == (None, None)

    def test_malformed_json_skipped(self) -> None:
        text = '```cronos_status\nnot valid json {{{\n```'
        assert parse_cronos_status_block(text) == (None, None)

    def test_non_object_json_skipped(self) -> None:
        text = '```cronos_status\n["DONE", "summary"]\n```'
        assert parse_cronos_status_block(text) == (None, None)

    def test_unclosed_fence_discarded(self) -> None:
        text = '```cronos_status\n{"status": "DONE", "summary": "Done."}\nNo closing fence'
        assert parse_cronos_status_block(text) == (None, None)

    def test_fence_case_insensitive(self) -> None:
        text = '```CRONOS_STATUS\n{"status": "DONE", "summary": "Done."}\n```'
        status, _ = parse_cronos_status_block(text)
        assert status == "DONE"

    def test_status_value_case_sensitive_uppercase_only(self) -> None:
        """status value must be uppercase DONE/WAIT/BLOCKED."""
        text = '```cronos_status\n{"status": "done", "summary": "Done."}\n```'
        assert parse_cronos_status_block(text) == (None, None)

    def test_first_block_wins(self) -> None:
        """When multiple blocks exist, the first valid one is returned."""
        text = (
            '```cronos_status\n{"status": "DONE", "summary": "First."}\n```\n'
            'Some text.\n'
            '```cronos_status\n{"status": "WAIT", "summary": "Second."}\n```'
        )
        status, summary = parse_cronos_status_block(text)
        assert status == "DONE"
        assert summary == "First."

    def test_cronos_remember_ignored_by_cronos_status_parser(self) -> None:
        """cronos_status parser ignores cronos_remember blocks."""
        text = (
            '```cronos_remember\nname: test\ntype: fact\ndescription: a fact\n```\n'
            '```cronos_status\n{"status": "DONE", "summary": "Done."}\n```'
        )
        status, _ = parse_cronos_status_block(text)
        assert status == "DONE"

    def test_cronos_remember_parser_ignores_cronos_status(self) -> None:
        """cronos_remember parser ignores cronos_status blocks."""
        text = (
            '```cronos_status\n{"status": "DONE", "summary": "Done."}\n```\n'
            '```cronos_remember\nname: test\ntype: fact\ndescription: some fact\n```'
        )
        blocks = parse_cronos_remember_blocks(text)
        assert len(blocks) == 1
        assert blocks[0].name == "test"

    def test_both_fences_coexist_cross_isolation(self) -> None:
        """Both fences can appear in the same text; each parser sees only its own."""
        text = (
            '```cronos_remember\nname: a fact\ntype: fact\ndescription: fact description\n```\n'
            'Some prose here.\n'
            '```cronos_status\n{"status": "BLOCKED", "summary": "Needs review first."}\n```'
        )
        status, summary = parse_cronos_status_block(text)
        assert status == "BLOCKED"

        remember_blocks = parse_cronos_remember_blocks(text)
        assert len(remember_blocks) == 1
        assert remember_blocks[0].name == "a fact"

    def test_returns_raw_string_not_enum(self) -> None:
        """parse_cronos_status_block must return str, not Status enum (import-direction contract)."""
        text = '```cronos_status\n{"status": "DONE", "summary": "Done."}\n```'
        status, _ = parse_cronos_status_block(text)
        assert isinstance(status, str)
        assert type(status) is str  # NOT a subclass (i.e. not Status enum)

    def test_summary_non_string_treated_as_none(self) -> None:
        """Non-string summary is coerced to None (lenient)."""
        text = '```cronos_status\n{"status": "DONE", "summary": 42}\n```'
        status, summary = parse_cronos_status_block(text)
        assert status == "DONE"
        assert summary is None

    def test_multiline_prose_before_block(self) -> None:
        """Block can appear anywhere in a large agent output."""
        text = (
            "I've completed the implementation.\n\n"
            "Here is what was done:\n- Changed file A\n- Changed file B\n\n"
            '```cronos_status\n{"status": "DONE", "summary": "Implemented parser."}\n```\n'
        )
        status, summary = parse_cronos_status_block(text)
        assert status == "DONE"
        assert summary == "Implemented parser."


# ---------------------------------------------------------------------------
# I2: TestParseStatusStructuredBlock — parse_status() integration tests
# ---------------------------------------------------------------------------


class TestParseStatusStructuredBlock:
    """Integration tests for parse_status() with the structured block channel."""

    def test_structured_done_block_parsed(self) -> None:
        text = '```cronos_status\n{"status": "DONE", "summary": "All work done."}\n```'
        status, context = parse_status(text)
        assert status == Status.DONE
        assert context == "All work done."

    def test_structured_wait_block_parsed(self) -> None:
        text = '```cronos_status\n{"status": "WAIT", "summary": "Need input."}\n```'
        status, context = parse_status(text)
        assert status == Status.WAIT
        assert context == "Need input."

    def test_structured_blocked_block_parsed(self) -> None:
        text = '```cronos_status\n{"status": "BLOCKED", "summary": "Cannot proceed."}\n```'
        status, context = parse_status(text)
        assert status == Status.BLOCKED
        assert context == "Cannot proceed."

    def test_structured_block_takes_precedence_over_free_text(self) -> None:
        """Structured block must win even when free-text STATUS: WAIT is also present."""
        text = '```cronos_status\n{"status": "DONE", "summary": "Done."}\n```\nSTATUS: WAIT'
        status, context = parse_status(text)
        assert status == Status.DONE
        assert context == "Done."

    def test_missing_block_falls_back_to_free_text(self) -> None:
        """No structured block → fall back to existing free-text scanner."""
        text = "Work is complete.\nSTATUS: DONE"
        status, context = parse_status(text)
        assert status == Status.DONE
        assert context == "Work is complete."

    def test_free_text_wait_fallback(self) -> None:
        text = "What is your preference?\n\nSTATUS: WAIT"
        status, context = parse_status(text)
        assert status == Status.WAIT
        assert context == "What is your preference?"

    def test_free_text_blocked_fallback(self) -> None:
        text = "Cannot proceed without creds.\n\nSTATUS: BLOCKED"
        status, context = parse_status(text)
        assert status == Status.BLOCKED
        assert context == "Cannot proceed without creds."

    def test_missing_both_returns_none(self) -> None:
        """No block and no free-text STATUS → (None, None)."""
        status, context = parse_status("I finished everything.")
        assert status is None
        assert context is None

    def test_empty_string_returns_none(self) -> None:
        status, context = parse_status("")
        assert status is None
        assert context is None

    # STATUS_CONTRACT content checks (I4 transitively verified here)

    def test_status_contract_contains_cronos_status_fence(self) -> None:
        """STATUS_CONTRACT must reference the cronos_status block format."""
        assert "cronos_status" in STATUS_CONTRACT

    def test_status_contract_contains_deprecated_marker(self) -> None:
        """STATUS_CONTRACT must note free-text fallback as deprecated."""
        contract_lower = STATUS_CONTRACT.lower()
        assert "deprecated" in contract_lower

    def test_status_contract_shows_done_example(self) -> None:
        assert '"status": "DONE"' in STATUS_CONTRACT

    def test_status_contract_shows_wait_example(self) -> None:
        assert '"status": "WAIT"' in STATUS_CONTRACT

    def test_status_contract_shows_blocked_example(self) -> None:
        assert '"status": "BLOCKED"' in STATUS_CONTRACT

    def test_status_contract_examples_are_parseable(self) -> None:
        """The inline block examples in STATUS_CONTRACT must parse correctly."""
        done_text = '```cronos_status\n{"status": "DONE", "summary": "Task complete."}\n```'
        assert parse_cronos_status_block(done_text) == ("DONE", "Task complete.")

        wait_text = '```cronos_status\n{"status": "WAIT", "summary": "Need approval."}\n```'
        assert parse_cronos_status_block(wait_text) == ("WAIT", "Need approval.")

        blocked_text = '```cronos_status\n{"status": "BLOCKED", "summary": "Cannot continue."}\n```'
        assert parse_cronos_status_block(blocked_text) == ("BLOCKED", "Cannot continue.")
