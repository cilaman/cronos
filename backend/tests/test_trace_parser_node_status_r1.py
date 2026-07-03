"""R1 regression — RunTrace.node_status parsed from the FULL final text (D6).

Pre-R1, the node_status fence had to survive inside ``final_text_snippet``
(head-truncation to 2,000 chars); any final message over ~2k chars of prose
lost the fence and a successful child was classified failed.  R1 parses the
envelope at trace-extraction time from the untruncated final assistant text
and stores it as the structured ``RunTrace.node_status`` field.

Also covers the adjacent latent bug fixed with it: ``final_text = full_text``
used to overwrite the final text with EMPTY when the last assistant turn was
tool-only, contradicting its own "last non-empty wins" comment.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime

from app.trace_parser import (
    extract_run_trace,
    final_assistant_text,
    parse_node_status_fence,
)

_NOW = datetime(2026, 7, 1, 12, 0, 0, tzinfo=UTC)
_LATER = datetime(2026, 7, 1, 12, 1, 0, tzinfo=UTC)


def _kwargs() -> dict:
    return dict(
        task_id="t1",
        space_id="sp1",
        run_index=0,
        model="default",
        mode="auto",
        started_at=_NOW,
        ended_at=_LATER,
        exit_reason="DONE",
        session_id=None,
        had_crash=False,
    )


def _assistant(text: str = "", tool_use: bool = False) -> dict:
    content: list[dict] = []
    if text:
        content.append({"type": "text", "text": text})
    if tool_use:
        content.append(
            {"type": "tool_use", "id": "tu1", "name": "Bash", "input": {"command": "ls"}}
        )
    return {"type": "assistant", "message": {"usage": {}, "content": content}}


_ENVELOPE = {
    "status": "done",
    "artifact_paths": ["reports/scout.md"],
    "produces": "research",
    "fields": {"has_ui": True},
    "open_questions": [],
}
_FENCE = f"```node_status\n{json.dumps(_ENVELOPE)}\n```"


# ---------------------------------------------------------------------------
# The acceptance case: 10k chars of prose + fence at the end → parsed.
# ---------------------------------------------------------------------------


def test_fence_after_10k_prose_is_parsed():
    prose = "Summary of the extensive work performed. " * 250  # >10k chars
    assert len(prose) > 10_000
    events = [_assistant(text=prose + _FENCE)]

    trace = extract_run_trace(events, **_kwargs())

    # The envelope is structured and complete — no truncation sensitivity.
    assert trace.node_status == _ENVELOPE
    # The snippet is still a UI nicety (2,000-char head) and the fence is NOT
    # in it — proving classification no longer depends on the snippet.
    assert len(trace.final_text_snippet) <= 2001
    assert "node_status" not in trace.final_text_snippet


def test_no_fence_yields_none():
    trace = extract_run_trace([_assistant(text="just prose")], **_kwargs())
    assert trace.node_status is None


def test_delivery_status_fence_name_accepted():
    fence = f"```delivery_status\n{json.dumps(_ENVELOPE)}\n```"
    trace = extract_run_trace([_assistant(text=f"done.\n{fence}")], **_kwargs())
    assert trace.node_status == _ENVELOPE


def test_last_complete_fence_wins():
    first = f"```node_status\n{json.dumps({'status': 'failed'})}\n```"
    last = f"```node_status\n{json.dumps({'status': 'done'})}\n```"
    trace = extract_run_trace(
        [_assistant(text=f"{first}\nrevised:\n{last}")], **_kwargs()
    )
    assert trace.node_status == {"status": "done"}


def test_malformed_json_yields_none():
    trace = extract_run_trace(
        [_assistant(text="```node_status\n{not json}\n```")], **_kwargs()
    )
    assert trace.node_status is None


def test_non_object_json_yields_none():
    trace = extract_run_trace(
        [_assistant(text='```node_status\n["a", "b"]\n```')], **_kwargs()
    )
    assert trace.node_status is None


# ---------------------------------------------------------------------------
# Latent bug (trace_parser ~L255): tool-only last turn must not clobber the
# final text ("last non-empty wins").
# ---------------------------------------------------------------------------


def test_tool_only_last_turn_does_not_clobber_final_text():
    events = [
        _assistant(text=f"All done.\n{_FENCE}"),
        _assistant(tool_use=True),  # tool-only turn, no text
    ]
    trace = extract_run_trace(events, **_kwargs())
    assert trace.node_status == _ENVELOPE
    assert "All done." in trace.final_text_snippet


def test_whitespace_only_last_turn_does_not_clobber_final_text():
    events = [
        _assistant(text=f"All done.\n{_FENCE}"),
        _assistant(text="   \n  "),
    ]
    trace = extract_run_trace(events, **_kwargs())
    assert trace.node_status == _ENVELOPE


def test_later_non_empty_turn_wins():
    events = [
        _assistant(text=f"first attempt\n{_FENCE}"),
        _assistant(text="final answer without fence"),
    ]
    trace = extract_run_trace(events, **_kwargs())
    # Last non-empty turn has no fence → no envelope, honestly.
    assert trace.node_status is None
    assert "final answer" in trace.final_text_snippet


# ---------------------------------------------------------------------------
# Conformance: the helper pair used by run_delivery_child (D13) selects the
# exact same envelope extract_run_trace stores.
# ---------------------------------------------------------------------------


def test_final_assistant_text_conforms_to_extract_run_trace():
    scenarios = [
        [_assistant(text=f"prose\n{_FENCE}")],
        [_assistant(text=f"prose\n{_FENCE}"), _assistant(tool_use=True)],
        [_assistant(text="no fence at all")],
        [_assistant(text=f"stale\n{_FENCE}"), _assistant(text="fresh, fenceless")],
        [],
    ]
    for events in scenarios:
        trace = extract_run_trace(events, **_kwargs())
        assert (
            parse_node_status_fence(final_assistant_text(events))
            == trace.node_status
        )


def test_parse_node_status_fence_handles_none_and_empty():
    assert parse_node_status_fence("") is None
    assert parse_node_status_fence(None) is None  # type: ignore[arg-type]
