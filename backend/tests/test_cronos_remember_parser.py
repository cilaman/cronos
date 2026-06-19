from __future__ import annotations

from app.memory_parser import CronosRememberBlock, parse_cronos_remember_blocks


# ---------------------------------------------------------------------------
# basic / empty cases
# ---------------------------------------------------------------------------


def test_empty_text_returns_empty() -> None:
    assert parse_cronos_remember_blocks("") == []


def test_no_cronos_blocks_returns_empty() -> None:
    text = "Just some text\nMEMORY: a fact\nSTATUS: DONE"
    assert parse_cronos_remember_blocks(text) == []


# ---------------------------------------------------------------------------
# valid blocks
# ---------------------------------------------------------------------------


def test_minimal_valid_block() -> None:
    text = """\
```cronos_remember
name: key insight
type: fact
description: The repo uses Python 3.12.
```"""
    blocks = parse_cronos_remember_blocks(text)
    assert len(blocks) == 1
    b = blocks[0]
    assert b.name == "key insight"
    assert b.type == "fact"
    assert b.description == "The repo uses Python 3.12."
    assert b.body == ""
    assert b.metadata == {}


def test_full_block_with_body_and_metadata() -> None:
    text = """\
```cronos_remember
name: auth middleware insight
type: observation
description: Auth middleware checks every request.
body: |
  It validates the Bearer token against the session store.
  Short-circuit on OPTIONS requests.
metadata:
  confidence: high
  source: code-review
```"""
    blocks = parse_cronos_remember_blocks(text)
    assert len(blocks) == 1
    b = blocks[0]
    assert b.name == "auth middleware insight"
    assert b.type == "observation"
    assert b.description == "Auth middleware checks every request."
    assert "Bearer token" in b.body
    assert b.metadata == {"confidence": "high", "source": "code-review"}


def test_all_valid_types() -> None:
    text = """\
```cronos_remember
name: a fact
type: fact
description: fact desc
```
```cronos_remember
name: a procedure
type: procedure
description: procedure desc
```
```cronos_remember
name: an observation
type: observation
description: observation desc
```
```cronos_remember
name: a reference
type: reference
description: reference desc
```"""
    blocks = parse_cronos_remember_blocks(text)
    assert len(blocks) == 4
    assert [b.type for b in blocks] == ["fact", "procedure", "observation", "reference"]


def test_type_case_insensitive() -> None:
    text = """\
```cronos_remember
name: a fact
type: FACT
description: desc here
```"""
    blocks = parse_cronos_remember_blocks(text)
    assert len(blocks) == 1
    assert blocks[0].type == "fact"


def test_fence_case_insensitive() -> None:
    text = """\
```CRONOS_REMEMBER
name: upper fence
type: fact
description: works with uppercase fence
```"""
    blocks = parse_cronos_remember_blocks(text)
    assert len(blocks) == 1
    assert blocks[0].name == "upper fence"


def test_multiple_blocks_document_order() -> None:
    text = """\
```cronos_remember
name: first
type: fact
description: first desc
```
some text between
```cronos_remember
name: second
type: procedure
description: second desc
```"""
    blocks = parse_cronos_remember_blocks(text)
    assert len(blocks) == 2
    assert blocks[0].name == "first"
    assert blocks[1].name == "second"


def test_name_capped_at_120_chars() -> None:
    long_name = "x" * 200
    text = f"""\
```cronos_remember
name: {long_name}
type: fact
description: desc
```"""
    blocks = parse_cronos_remember_blocks(text)
    assert len(blocks) == 1
    assert len(blocks[0].name) == 120


# ---------------------------------------------------------------------------
# silent-skip cases
# ---------------------------------------------------------------------------


def test_missing_name_skipped() -> None:
    text = """\
```cronos_remember
type: fact
description: desc
```"""
    assert parse_cronos_remember_blocks(text) == []


def test_missing_type_skipped() -> None:
    text = """\
```cronos_remember
name: my name
description: desc
```"""
    assert parse_cronos_remember_blocks(text) == []


def test_missing_description_skipped() -> None:
    text = """\
```cronos_remember
name: my name
type: fact
```"""
    assert parse_cronos_remember_blocks(text) == []


def test_unknown_type_skipped() -> None:
    text = """\
```cronos_remember
name: my name
type: note
description: desc
```"""
    assert parse_cronos_remember_blocks(text) == []


def test_malformed_yaml_skipped() -> None:
    text = """\
```cronos_remember
: this is invalid yaml [[[
```"""
    assert parse_cronos_remember_blocks(text) == []


def test_yaml_non_mapping_skipped() -> None:
    text = """\
```cronos_remember
- item one
- item two
```"""
    assert parse_cronos_remember_blocks(text) == []


def test_unclosed_fence_discarded() -> None:
    text = """\
```cronos_remember
name: unclosed
type: fact
description: no closing fence
STATUS: DONE"""
    assert parse_cronos_remember_blocks(text) == []


def test_empty_name_skipped() -> None:
    text = """\
```cronos_remember
name: "   "
type: fact
description: desc
```"""
    assert parse_cronos_remember_blocks(text) == []


def test_empty_description_skipped() -> None:
    text = """\
```cronos_remember
name: my name
type: fact
description: "   "
```"""
    assert parse_cronos_remember_blocks(text) == []


def test_metadata_non_dict_defaults_empty() -> None:
    text = """\
```cronos_remember
name: test
type: fact
description: desc
metadata: not-a-mapping
```"""
    blocks = parse_cronos_remember_blocks(text)
    assert len(blocks) == 1
    assert blocks[0].metadata == {}


def test_body_non_str_defaults_empty() -> None:
    text = """\
```cronos_remember
name: test
type: fact
description: desc
body: 42
```"""
    blocks = parse_cronos_remember_blocks(text)
    assert len(blocks) == 1
    assert blocks[0].body == ""


# ---------------------------------------------------------------------------
# coexistence with MEMORY: markers
# ---------------------------------------------------------------------------


def test_coexists_with_memory_markers() -> None:
    text = """\
MEMORY[fact]: inline memory fact
```cronos_remember
name: structured fact
type: fact
description: structured description
```
MEMORY: another memory"""
    blocks = parse_cronos_remember_blocks(text)
    assert len(blocks) == 1
    assert blocks[0].name == "structured fact"


def test_real_agent_output() -> None:
    text = """\
I've completed the implementation.

```cronos_remember
name: auth-middleware-placement
type: observation
description: Auth middleware is applied before all routes except /api/health.
body: |
  Verified in main.py lines 87-102. The health check route bypasses auth
  via an explicit exclude list, not middleware ordering.
metadata:
  file: backend/app/main.py
  lines: "87-102"
```

STATUS: DONE"""
    blocks = parse_cronos_remember_blocks(text)
    assert len(blocks) == 1
    b = blocks[0]
    assert b.name == "auth-middleware-placement"
    assert b.type == "observation"
    assert "health check" in b.body
    assert b.metadata == {"file": "backend/app/main.py", "lines": "87-102"}


# ---------------------------------------------------------------------------
# dataclass interface
# ---------------------------------------------------------------------------


def test_cronos_remember_block_dataclass_interface() -> None:
    b = CronosRememberBlock(name="n", type="fact", description="d")
    assert b.name == "n"
    assert b.type == "fact"
    assert b.description == "d"
    assert b.body == ""
    assert b.metadata == {}


def test_cronos_remember_block_full_constructor() -> None:
    b = CronosRememberBlock(
        name="n",
        type="procedure",
        description="d",
        body="body text",
        metadata={"k": "v"},
    )
    assert b.body == "body text"
    assert b.metadata == {"k": "v"}
