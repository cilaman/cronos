"""Tests for the unified status-envelope parser + agent-fence drift guard."""

from __future__ import annotations

import re
from pathlib import Path

from delivery_workflow.lib.status_envelope import parse_status_envelope

_NODE = """Review complete.

```node_status
{"status": "done", "produces": "review",
 "fields": {"verdict": "needs_fix", "finding_class": "local"}}
```
"""

_DELIVERY = """Done.

```delivery_status
{"status": "done", "produces": "impl", "artifact_paths": [], "fields": {},
 "open_questions": [], "telemetry": {"tokens": 0, "usd": 0.0, "seconds": 0.0}}
```
"""


def test_parses_node_status_and_exposes_verdict() -> None:
    block = parse_status_envelope(_NODE)
    assert block is not None
    assert block.status == "done"
    assert block.fields.get("verdict") == "needs_fix"
    assert block.fields.get("finding_class") == "local"


def test_parses_delivery_status_backcompat() -> None:
    block = parse_status_envelope(_DELIVERY)
    assert block is not None and block.status == "done"


def test_returns_none_when_no_fence() -> None:
    assert parse_status_envelope("no fence here") is None


_SUPPORTED = {"node_status", "delivery_status"}
_FENCE_RE = re.compile(r"```(node_status|delivery_status)\b")


def test_every_agent_emitted_fence_is_parseable() -> None:
    """Every fence keyword any delivery agent emits must be one the adapter can
    parse. Fails loudly if an agent starts emitting a fence the delivery path is
    blind to (the regression this whole fix addresses)."""
    agents_dir = Path(__file__).resolve().parent.parent / "agents"
    offenders = {}
    for md in agents_dir.glob("*.md"):
        unsupported = set(_FENCE_RE.findall(md.read_text(encoding="utf-8"))) - _SUPPORTED
        if unsupported:
            offenders[md.name] = unsupported
    assert not offenders, f"Agents emit unparseable fence(s): {offenders}"
