"""Coexistence regression gate for the two memory parsers (design I3).

The CRONOS_REMEMBER sentinel parser (`parse_cronos_remember_blocks`) was added
alongside the legacy MEMORY: / ```memory parser (`parse_memory_blocks`) without
touching the shared fence/line constants. This file proves the two parsers fire
*independently* on the same document: each extracts only its own block kind and
ignores the other's syntax. The legacy suite (tests/test_memory_parser.py) is
run unmodified in the same validation command as the R4 backward-compat gate.
"""
from __future__ import annotations

from app.memory_parser import (
    CronosRememberBlock,
    MemoryBlock,
    parse_cronos_remember_blocks,
    parse_memory_blocks,
)

# A document containing BOTH a legacy MEMORY: line and a CRONOS_REMEMBER fence.
MIXED = """\
Some preamble.

MEMORY: legacy single-line memory survives untouched

```cronos_remember
name: structured sentinel
type: fact
description: a structured fact
body: with a body
metadata:
  k: v
```

Trailing prose.
"""


def test_legacy_parser_ignores_cronos_remember_fence() -> None:
    blocks = parse_memory_blocks(MIXED)
    # The legacy parser sees only its MEMORY: line, not the cronos_remember fence.
    contents = [b.content for b in blocks]
    assert any("legacy single-line memory survives untouched" in c for c in contents)
    assert all("structured sentinel" not in c for c in contents)
    assert all(isinstance(b, MemoryBlock) for b in blocks)


def test_cronos_parser_ignores_legacy_memory_line() -> None:
    blocks = parse_cronos_remember_blocks(MIXED)
    assert len(blocks) == 1
    block = blocks[0]
    assert isinstance(block, CronosRememberBlock)
    assert block.name == "structured sentinel"
    assert block.type == "fact"
    assert block.description == "a structured fact"
    assert block.body == "with a body"
    assert block.metadata == {"k": "v"}


def test_both_parsers_fire_independently_on_same_text() -> None:
    legacy = parse_memory_blocks(MIXED)
    structured = parse_cronos_remember_blocks(MIXED)
    # Each parser produces exactly its own kind; neither steals the other's block.
    assert len(legacy) >= 1
    assert len(structured) == 1
    assert {type(b) for b in legacy} == {MemoryBlock}
    assert {type(b) for b in structured} == {CronosRememberBlock}


def test_cronos_parser_empty_on_legacy_only_text() -> None:
    legacy_only = "MEMORY: just a legacy line\n"
    assert parse_cronos_remember_blocks(legacy_only) == []
    assert len(parse_memory_blocks(legacy_only)) == 1


def test_legacy_parser_empty_on_cronos_only_text() -> None:
    cronos_only = (
        "```cronos_remember\n"
        "name: only structured\n"
        "type: observation\n"
        "description: nothing legacy here\n"
        "```\n"
    )
    assert parse_memory_blocks(cronos_only) == []
    assert len(parse_cronos_remember_blocks(cronos_only)) == 1
