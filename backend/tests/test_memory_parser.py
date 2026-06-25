from __future__ import annotations

import pytest

from app.memory_parser import MemoryBlock, parse_delivery_status_block, parse_memory_blocks


# ---------------------------------------------------------------------------
# inline MEMORY: markers
# ---------------------------------------------------------------------------


def test_empty_text_returns_empty() -> None:
    assert parse_memory_blocks("") == []


def test_no_markers_returns_empty() -> None:
    assert parse_memory_blocks("Just some text\nwith no markers\nSTATUS: DONE") == []


def test_single_inline_no_kind() -> None:
    text = "Some output\nMEMORY: the repo uses poetry for dependency management\nSTATUS: DONE"
    blocks = parse_memory_blocks(text)
    assert len(blocks) == 1
    assert blocks[0].content == "the repo uses poetry for dependency management"
    assert blocks[0].kind_hint is None


def test_inline_with_valid_kind() -> None:
    text = "MEMORY[fact]: tests live under backend/tests/\nSTATUS: DONE"
    blocks = parse_memory_blocks(text)
    assert len(blocks) == 1
    assert blocks[0].kind_hint == "fact"
    assert blocks[0].content == "tests live under backend/tests/"


def test_all_valid_kind_hints() -> None:
    text = (
        "MEMORY[fact]: fact here\n"
        "MEMORY[procedure]: procedure here\n"
        "MEMORY[observation]: observation here\n"
        "MEMORY[reference]: reference here\n"
    )
    blocks = parse_memory_blocks(text)
    assert len(blocks) == 4
    kinds = [b.kind_hint for b in blocks]
    assert kinds == ["fact", "procedure", "observation", "reference"]


def test_invalid_kind_hint_treated_as_none() -> None:
    text = "MEMORY[bogus]: some content"
    blocks = parse_memory_blocks(text)
    assert len(blocks) == 1
    assert blocks[0].kind_hint is None
    assert blocks[0].content == "some content"


def test_multiple_inline_markers() -> None:
    text = (
        "MEMORY: first fact\n"
        "MEMORY[procedure]: run pytest to test\n"
        "MEMORY: second fact\n"
    )
    blocks = parse_memory_blocks(text)
    assert len(blocks) == 3
    assert blocks[0].content == "first fact"
    assert blocks[1].content == "run pytest to test"
    assert blocks[2].content == "second fact"


def test_inline_marker_case_insensitive() -> None:
    text = "memory: lowercase works too"
    blocks = parse_memory_blocks(text)
    assert len(blocks) == 1
    assert blocks[0].content == "lowercase works too"


def test_inline_leading_whitespace_ignored() -> None:
    text = "   MEMORY: indented marker"
    blocks = parse_memory_blocks(text)
    assert len(blocks) == 1
    assert blocks[0].content == "indented marker"


# ---------------------------------------------------------------------------
# fenced ```memory blocks
# ---------------------------------------------------------------------------


def test_fenced_block_no_kind() -> None:
    text = "prefix\n```memory\nline one\nline two\n```\nsuffix"
    blocks = parse_memory_blocks(text)
    assert len(blocks) == 1
    assert blocks[0].content == "line one\nline two"
    assert blocks[0].kind_hint is None


def test_fenced_block_with_kind() -> None:
    text = "```memory procedure\nstep 1\nstep 2\n```"
    blocks = parse_memory_blocks(text)
    assert len(blocks) == 1
    assert blocks[0].kind_hint == "procedure"
    assert blocks[0].content == "step 1\nstep 2"


def test_fenced_block_invalid_kind_treated_as_none() -> None:
    text = "```memory unknown\ncontent\n```"
    blocks = parse_memory_blocks(text)
    assert len(blocks) == 1
    assert blocks[0].kind_hint is None


def test_fenced_block_empty_content_skipped() -> None:
    text = "```memory\n\n```"
    blocks = parse_memory_blocks(text)
    assert len(blocks) == 0


def test_inline_inside_fence_not_double_counted() -> None:
    text = "```memory\nMEMORY: this is inside the fence\n```"
    blocks = parse_memory_blocks(text)
    assert len(blocks) == 1
    assert blocks[0].content == "MEMORY: this is inside the fence"


# ---------------------------------------------------------------------------
# mixed inline + fenced
# ---------------------------------------------------------------------------


def test_mixed_inline_and_fenced() -> None:
    text = (
        "MEMORY[fact]: inline fact\n"
        "```memory observation\n"
        "multi-line\nobservation\n"
        "```\n"
        "MEMORY: another inline\n"
    )
    blocks = parse_memory_blocks(text)
    assert len(blocks) == 3
    assert blocks[0].kind_hint == "fact"
    assert blocks[1].kind_hint == "observation"
    assert blocks[1].content == "multi-line\nobservation"
    assert blocks[2].content == "another inline"


def test_real_agent_output() -> None:
    text = """\
I've completed the refactor.

MEMORY[fact]: The main entry point is backend/app/main.py
MEMORY[procedure]: Run `pytest backend/tests/` to execute backend tests

```memory observation
The project uses frontmatter for all markdown-with-metadata files,
including task files and memory items.
```

STATUS: DONE"""
    blocks = parse_memory_blocks(text)
    assert len(blocks) == 3
    assert blocks[0].kind_hint == "fact"
    assert "main.py" in blocks[0].content
    assert blocks[1].kind_hint == "procedure"
    assert blocks[2].kind_hint == "observation"
    assert "frontmatter" in blocks[2].content


# ---------------------------------------------------------------------------
# parse_delivery_status_block (I1 / R14)
# ---------------------------------------------------------------------------


def test_delivery_status_none_on_empty() -> None:
    assert parse_delivery_status_block("") is None
    assert parse_delivery_status_block(None) is None  # type: ignore[arg-type]


def test_delivery_status_none_when_absent() -> None:
    text = "Some output\nSTATUS: DONE"
    assert parse_delivery_status_block(text) is None


def test_delivery_status_basic_parse() -> None:
    text = '```delivery_status\n{"status": "done", "summary": "all good"}\n```'
    result = parse_delivery_status_block(text)
    assert result is not None
    assert result["status"] == "done"
    assert result["summary"] == "all good"


def test_delivery_status_normalises_status_to_lowercase() -> None:
    text = '```delivery_status\n{"status": "DONE"}\n```'
    result = parse_delivery_status_block(text)
    assert result is not None
    assert result["status"] == "done"


def test_delivery_status_accepts_lowercase_status() -> None:
    text = '```delivery_status\n{"status": "wait"}\n```'
    result = parse_delivery_status_block(text)
    assert result is not None
    assert result["status"] == "wait"


def test_delivery_status_does_not_validate_status_value() -> None:
    text = '```delivery_status\n{"status": "custom_value", "fields": {}}\n```'
    result = parse_delivery_status_block(text)
    assert result is not None
    assert result["status"] == "custom_value"


def test_delivery_status_with_fields() -> None:
    text = (
        '```delivery_status\n'
        '{"status": "done", "fields": {"verdict": "pass", "finding_count": "3"}}\n'
        '```'
    )
    result = parse_delivery_status_block(text)
    assert result is not None
    assert result["fields"]["verdict"] == "pass"
    assert result["fields"]["finding_count"] == "3"


def test_delivery_status_missing_optional_fields() -> None:
    text = '```delivery_status\n{"status": "done"}\n```'
    result = parse_delivery_status_block(text)
    assert result is not None
    assert result.get("fields") is None


def test_delivery_status_malformed_json_returns_none() -> None:
    text = '```delivery_status\n{not valid json\n```'
    assert parse_delivery_status_block(text) is None


def test_delivery_status_unclosed_fence_returns_none() -> None:
    text = '```delivery_status\n{"status": "done"}'
    assert parse_delivery_status_block(text) is None


def test_delivery_status_non_dict_returns_none() -> None:
    text = '```delivery_status\n["not", "a", "dict"]\n```'
    assert parse_delivery_status_block(text) is None


def test_delivery_status_first_block_wins() -> None:
    text = (
        '```delivery_status\n{"status": "done", "summary": "first"}\n```\n'
        '```delivery_status\n{"status": "wait", "summary": "second"}\n```'
    )
    result = parse_delivery_status_block(text)
    assert result is not None
    assert result["summary"] == "first"


def test_delivery_status_case_insensitive_fence() -> None:
    text = '```DELIVERY_STATUS\n{"status": "done"}\n```'
    result = parse_delivery_status_block(text)
    assert result is not None
    assert result["status"] == "done"


def test_delivery_status_with_finding_ids() -> None:
    text = (
        '```delivery_status\n'
        '{"status": "done", "fields": {"finding_ids": ["f1", "f2"]}}\n'
        '```'
    )
    result = parse_delivery_status_block(text)
    assert result is not None
    assert result["fields"]["finding_ids"] == ["f1", "f2"]


def test_delivery_status_embedded_in_longer_output() -> None:
    text = (
        "The agent completed the review.\n\n"
        "```delivery_status\n"
        '{"status": "done", "fields": {"verdict": "pass"}}\n'
        "```\n\n"
        "STATUS: DONE"
    )
    result = parse_delivery_status_block(text)
    assert result is not None
    assert result["fields"]["verdict"] == "pass"
