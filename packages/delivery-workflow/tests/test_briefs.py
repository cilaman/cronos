"""Shared brief-composition helpers (``delivery_workflow.briefs``).

The bundled role definitions must load (frontmatter stripped, traversal refs
refused), the return contract must carry the full closed status vocabulary
plus the blocked/open_questions guidance, and ``local_executor.compose_brief``
must still assemble a whole brief FROM these helpers — one source, two
composers, zero drift.

Zero app.*/backend imports anywhere in this suite (package CI installs only
this package).
"""
from __future__ import annotations

import json
import re

import pytest
import yaml

from delivery_workflow.briefs import (
    AGENTS_DIR,
    _strip_frontmatter,
    load_agent_definition,
    return_contract,
    upstream_scope_section,
)
from delivery_workflow.lib.node_status import parse_node_status
from delivery_workflow.local_executor import compose_brief
from delivery_workflow.results import AGENT_STATUS_VOCAB


class TestLoadAgentDefinition:
    def test_every_bundled_role_definition_loads(self):
        refs = sorted(
            p.stem
            for p in AGENTS_DIR.glob("*.md")
            if re.fullmatch(r"[a-z0-9][a-z0-9_-]*", p.stem)
        )
        assert refs, f"no role definitions found in {AGENTS_DIR}"
        for ref in refs:
            body = load_agent_definition(ref)
            assert body, f"{ref}.md did not load"
            assert not body.startswith("---"), f"{ref}.md kept its frontmatter"

    def test_analyst_carries_the_return_contract(self):
        body = load_agent_definition("analyst")
        assert body is not None
        assert "node_status" in body

    def test_unknown_ref_is_none(self):
        assert load_agent_definition("no-such-agent") is None

    @pytest.mark.parametrize("ref", ["../analyst", "a/b", "A.Nalyst"])
    def test_traversal_refs_are_none(self, ref):
        assert load_agent_definition(ref) is None

    def test_every_workflow_agent_ref_has_a_role_definition(self):
        """A yaml agent ref with no ``agents/<ref>.md`` would silently run
        its child with no role definition (load_agent_definition → None)."""
        spec = yaml.safe_load(
            (AGENTS_DIR.parent / "delivery.workflow.yaml").read_text(
                encoding="utf-8"
            )
        )
        refs = sorted(
            node["agent"]
            for node in spec["nodes"]
            if node.get("kind") == "agent"
        )
        assert refs, "workflow spec declares no agent nodes"
        missing = [ref for ref in refs if load_agent_definition(ref) is None]
        assert missing == []


class TestStripFrontmatter:
    def test_strips_only_the_first_block(self):
        text = "---\nname: x\n---\nbody\n\n---\n\nrule survives"
        assert _strip_frontmatter(text) == "body\n\n---\n\nrule survives"

    def test_no_frontmatter_is_returned_unchanged(self):
        text = "# heading\n\nbody\n---\ntail"
        assert _strip_frontmatter(text) == text

    def test_unterminated_frontmatter_keeps_the_whole_text(self):
        text = "---\nname: x\nbody with no closing fence"
        assert _strip_frontmatter(text) == text

    def test_empty_text_is_returned_unchanged(self):
        assert _strip_frontmatter("") == ""


class TestReturnContract:
    def test_contract_carries_fence_produces_and_vocab(self):
        text = return_contract("analysis")
        assert "```node_status" in text
        assert '"produces": "analysis"' in text
        for status in sorted(AGENT_STATUS_VOCAB):
            assert status in text

    def test_contract_carries_blocked_guidance(self):
        text = return_contract("analysis")
        assert (
            'use status "blocked" and put the question in open_questions'
            in text
        )

    def test_contract_demands_fence_in_reply_text_after_housekeeping(self):
        """The reply text is the classified surface — a fence only at the
        tail of a written artifact must not read as satisfying the contract,
        and housekeeping turns must not displace it."""
        text = return_contract("analysis")
        assert "REPLY" in text and "chat message" in text
        assert "only inside an artifact file" in text
        assert "does NOT count" in text
        assert "AFTER all other steps" in text
        assert "memory writes and housekeeping" in text

    def test_contract_example_fence_is_deliberately_unparseable(self):
        """Echo-safety: agents restate the contract verbatim in planning
        turns, and turn-tolerant transports scan every turn — the shipped
        example must never parse as a genuine envelope."""
        text = return_contract("analysis")
        assert "```node_status" in text
        assert parse_node_status(text) is None


class TestUpstreamScopeSection:
    def test_empty_scope_is_empty_string(self):
        assert upstream_scope_section({}) == ""
        assert upstream_scope_section(None) == ""

    def test_scope_renders_as_indented_sorted_json(self):
        section = upstream_scope_section({"a.fields.x": 1})
        assert "## Upstream scope (outputs of completed workflow nodes)" in section
        assert json.dumps({"a.fields.x": 1}, indent=2, sort_keys=True) in section


class TestComposeBriefUsesHelpers:
    def test_refactor_kept_compose_brief_whole(self):
        brief = compose_brief(
            "analyst",
            {
                "node_id": "analyze",
                "attempt": 2,
                "produces": {"class": "analysis"},
                "scope": {"scout.fields.k": "v"},
            },
        )
        assert (
            "You are agent 'analyst' executing workflow node 'analyze'"
            " (attempt 2)." in brief
        )
        assert '"scout.fields.k": "v"' in brief
        assert return_contract("analysis") in brief
        assert upstream_scope_section({"scout.fields.k": "v"}) in brief

    def test_compose_brief_carries_the_role_definition(self):
        """The role definition holds the routing-critical fields protocol
        (analyst's has_ui) — a standalone child that never hears it cannot
        satisfy the signoff-scope edges."""
        brief = compose_brief("analyst", {"node_id": "analyze"})
        role = load_agent_definition("analyst")
        assert role is not None
        assert role in brief
        assert "has_ui" in brief
        assert brief.index(role) < brief.index("## Return contract")

    def test_compose_brief_unknown_ref_keeps_the_contract(self):
        brief = compose_brief("custom-thing", {"node_id": "custom-thing"})
        assert "## Return contract" in brief
        assert "```node_status" in brief
