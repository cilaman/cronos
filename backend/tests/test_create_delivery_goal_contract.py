"""Contract test: create-delivery-goal/SKILL.md sentinel is byte-compatible with
DELIVERY_WORKFLOW_SENTINEL_PATTERN from backend.app.delivery_driver.

This is a pure unit test — no HTTP calls, no live backend required.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

SKILL_PATH = (
    Path(__file__).parent.parent.parent
    / ".claude"
    / "skills"
    / "create-delivery-goal"
    / "SKILL.md"
)


def _read_skill() -> str:
    return SKILL_PATH.read_text()


# ---------------------------------------------------------------------------
# Fixture: expected sentinel components
# ---------------------------------------------------------------------------

EXPECTED_NAME_FIELD = "name: create-delivery-goal"
EXPECTED_SENTINEL_SUBSTRING = "<!-- delivery-workflow:"
EXPECTED_DO_NOT_PRE_CREATE = "do not pre-create"
EXPECTED_CANONICAL_SPEC = "packages/delivery-workflow/src/delivery_workflow/delivery.workflow.yaml"


# ---------------------------------------------------------------------------
# Test 1 — SKILL.md file existence and key fields
# ---------------------------------------------------------------------------


def test_skill_file_exists():
    assert SKILL_PATH.exists(), f"SKILL.md not found at {SKILL_PATH}"


def test_frontmatter_name():
    content = _read_skill()
    assert EXPECTED_NAME_FIELD in content, (
        f"Expected '{EXPECTED_NAME_FIELD}' in frontmatter"
    )


def test_sentinel_literal_present():
    content = _read_skill()
    assert EXPECTED_SENTINEL_SUBSTRING in content, (
        "SKILL.md must document the delivery-workflow sentinel literal"
    )


def test_do_not_pre_create_rule():
    content = _read_skill()
    assert EXPECTED_DO_NOT_PRE_CREATE in content.lower(), (
        "SKILL.md must contain explicit 'do not pre-create' instruction"
    )


def test_canonical_spec_path_present():
    content = _read_skill()
    assert EXPECTED_CANONICAL_SPEC in content, (
        f"SKILL.md must document the canonical spec path '{EXPECTED_CANONICAL_SPEC}'"
    )


# ---------------------------------------------------------------------------
# Test 2 — sentinel format is byte-compatible with delivery_driver regex
# ---------------------------------------------------------------------------


def test_skill_sentinel_matches_delivery_driver_pattern():
    """The sentinel string documented in SKILL.md must be matched by
    DELIVERY_WORKFLOW_SENTINEL_PATTERN so that detect_delivery_workflow_spec()
    routes correctly when an agent follows the skill instructions.
    """
    from app.delivery_driver import (
        DELIVERY_WORKFLOW_SENTINEL_PATTERN,
        detect_delivery_workflow_spec,
    )

    content = _read_skill()

    # Extract the first sentinel example line from the skill (inside a code block)
    # Pattern: any line of the form "<!-- delivery-workflow: something -->"
    sentinel_line_re = re.compile(r"<!--\s*delivery-workflow:\s*([^\s>]+)\s*-->")
    m = sentinel_line_re.search(content)
    assert m is not None, (
        "SKILL.md must contain at least one example line matching "
        "'<!-- delivery-workflow: <spec_path> -->'"
    )
    extracted_spec_path = m.group(1)
    extracted_sentinel_line = m.group(0)

    # Verify the extracted line matches the authoritative pattern
    pattern_match = DELIVERY_WORKFLOW_SENTINEL_PATTERN.search(extracted_sentinel_line)
    assert pattern_match is not None, (
        f"The sentinel line from SKILL.md does not match "
        f"DELIVERY_WORKFLOW_SENTINEL_PATTERN.\n"
        f"  Sentinel line: {extracted_sentinel_line!r}\n"
        f"  Pattern: {DELIVERY_WORKFLOW_SENTINEL_PATTERN.pattern!r}"
    )
    assert pattern_match.group(1).strip() == extracted_spec_path, (
        "The spec_path captured by DELIVERY_WORKFLOW_SENTINEL_PATTERN differs "
        "from the one in SKILL.md"
    )


def test_detect_delivery_workflow_spec_with_skill_example():
    """detect_delivery_workflow_spec() must return a non-None spec_path when
    given a brief that contains the sentinel as documented in SKILL.md.
    """
    from app.delivery_driver import detect_delivery_workflow_spec

    content = _read_skill()

    # Extract the canonical example sentinel line
    sentinel_line_re = re.compile(r"<!--\s*delivery-workflow:\s*([^\s>]+)\s*-->")
    m = sentinel_line_re.search(content)
    assert m is not None, "SKILL.md must contain a sentinel example"

    # Build a minimal brief that mimics what an agent would create
    sentinel_line = m.group(0)
    example_brief = f"My delivery goal.\n\n## Scope\n\n- file.py\n\n{sentinel_line}"

    result = detect_delivery_workflow_spec(example_brief)
    assert result is not None, (
        f"detect_delivery_workflow_spec() returned None for brief with sentinel "
        f"'{sentinel_line}'. Check that the sentinel format in SKILL.md matches "
        f"DELIVERY_WORKFLOW_SENTINEL_PATTERN."
    )
    assert result == m.group(1).strip(), (
        f"detect_delivery_workflow_spec() returned {result!r}, expected {m.group(1).strip()!r}"
    )


def test_example_brief_in_procedure_section():
    """The Procedure section must contain an inline sentinel in the example brief."""
    content = _read_skill()

    # Find the procedure python block
    procedure_block_re = re.compile(r"```python.*?```", re.DOTALL)
    blocks = procedure_block_re.findall(content)
    assert blocks, "SKILL.md must have at least one Python code block in the Procedure section"

    # At least one code block must contain the sentinel
    sentinel_in_block = any(
        "<!-- delivery-workflow:" in block for block in blocks
    )
    assert sentinel_in_block, (
        "The Python example in SKILL.md must embed the sentinel in the brief string"
    )


def test_example_uses_urllib_not_curl():
    """Python example must use urllib.request (not curl) for auth safety."""
    from app.delivery_driver import detect_delivery_workflow_spec  # noqa: F401 (import check)

    content = _read_skill()
    procedure_block_re = re.compile(r"```python.*?```", re.DOTALL)
    blocks = procedure_block_re.findall(content)

    urllib_in_block = any("urllib.request" in block for block in blocks)
    assert urllib_in_block, (
        "SKILL.md Python example must use urllib.request (not curl) to ensure "
        "correct Bearer token auth"
    )
