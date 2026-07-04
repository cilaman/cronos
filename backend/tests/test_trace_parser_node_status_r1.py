"""R1 regression — RunTrace.node_status parsed from the FULL final text (D6).

Pre-R1, the node_status fence had to survive inside ``final_text_snippet``
(head-truncation to 2,000 chars); any final message over ~2k chars of prose
lost the fence and a successful child was classified failed.  R1 parses the
envelope at trace-extraction time from the untruncated final assistant text
and stores it as the structured ``RunTrace.node_status`` field.

Also covers the adjacent latent bug fixed with it: ``final_text = full_text``
used to overwrite the final text with EMPTY when the last assistant turn was
tool-only, contradicting its own "last non-empty wins" comment.

Turn-tolerant transport (post-R1 production failure): the envelope selection
is ``parse_node_status_from_events`` — the fence may appear in an earlier
main-thread assistant turn (trailing housekeeping turns no longer erase it),
and as a fallback at the trailing edge of agent-Written artifact content
that names itself in ``artifact_paths``.  Tolerance is guarded: sidechain
(Task-subagent) events are skipped, and earlier-turn fences must END the
turn and be node_status-named, so quoted contract examples and fences cited
from other runs' output stay as inert as they were under final-turn-only
selection.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime

from app.trace_parser import (
    extract_run_trace,
    final_assistant_text,
    parse_node_status_fence,
    parse_node_status_from_events,
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


def _write(content: str, file_path: str = "reports/scout.md", name: str = "Write") -> dict:
    return {
        "type": "assistant",
        "message": {
            "usage": {},
            "content": [
                {
                    "type": "tool_use",
                    "id": "tu-w",
                    "name": name,
                    "input": {"file_path": file_path, "content": content},
                }
            ],
        },
    }


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


def test_fence_in_earlier_turn_survives_later_fenceless_turn():
    """Turn-tolerance: the fence is honored even when a later turn (memory
    compaction, housekeeping) closes the run with fenceless prose."""
    events = [
        _assistant(text=f"first attempt\n{_FENCE}"),
        _assistant(text="final answer without fence"),
    ]
    trace = extract_run_trace(events, **_kwargs())
    assert trace.node_status == _ENVELOPE
    # The UI snippet still tracks the last non-empty turn.
    assert "final answer" in trace.final_text_snippet


# ---------------------------------------------------------------------------
# Conformance: the selector used by run_delivery_child (D13) selects the
# exact same envelope extract_run_trace stores.
# ---------------------------------------------------------------------------


def test_parse_node_status_from_events_conforms_to_extract_run_trace():
    scenarios = [
        [_assistant(text=f"prose\n{_FENCE}")],
        [_assistant(text=f"prose\n{_FENCE}"), _assistant(tool_use=True)],
        [_assistant(text="no fence at all")],
        [_assistant(text=f"earlier\n{_FENCE}"), _assistant(text="fresh, fenceless")],
        [_write(f"# Report\n\n{_FENCE}\n"), _assistant(text="prose summary")],
        [],
    ]
    for events in scenarios:
        trace = extract_run_trace(events, **_kwargs())
        assert parse_node_status_from_events(events)[0] == trace.node_status


def test_parse_node_status_fence_handles_none_and_empty():
    assert parse_node_status_fence("") is None
    assert parse_node_status_fence(None) is None  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# parse_node_status_from_events — turn-tolerant transport selection.
# Channel 1: any assistant text turn, last fence wins ('assistant_text').
# Channel 2 fallback: trailing fence in Write tool content
# ('written_artifact').
# ---------------------------------------------------------------------------


def test_fence_in_final_message_transport_assistant_text():
    """Regression pin: fence in the final message → identical envelope to the
    old final-text selection."""
    events = [_assistant(text=f"prose\n{_FENCE}")]
    envelope, transport = parse_node_status_from_events(events)
    assert envelope == _ENVELOPE
    assert transport == "assistant_text"
    assert envelope == parse_node_status_fence(final_assistant_text(events))


def test_fence_in_earlier_turn_final_prose():
    """The production shape: housekeeping turns after the fence."""
    events = [
        _assistant(text=f"work done\n{_FENCE}"),
        _assistant(tool_use=True),
        _assistant(text="wrapped up housekeeping, no fence here"),
    ]
    envelope, transport = parse_node_status_from_events(events)
    assert envelope == _ENVELOPE
    assert transport == "assistant_text"


def test_two_fences_in_different_turns_later_wins():
    first = f"```node_status\n{json.dumps({'status': 'failed'})}\n```"
    last = f"```node_status\n{json.dumps({'status': 'done'})}\n```"
    events = [_assistant(text=first), _assistant(text=last)]
    envelope, transport = parse_node_status_from_events(events)
    assert envelope == {"status": "done"}
    assert transport == "assistant_text"


def test_chat_fence_beats_written_artifact_fence():
    """Channel precedence: any assistant-text fence outranks a Write tail."""
    chat = f"```node_status\n{json.dumps({'status': 'blocked'})}\n```"
    events = [
        _write(f"# Report\n\n{_FENCE}\n"),
        _assistant(text=f"summary\n{chat}"),
    ]
    envelope, transport = parse_node_status_from_events(events)
    assert envelope == {"status": "blocked"}
    assert transport == "assistant_text"


def test_no_chat_fence_trailing_write_fence_credited():
    events = [
        _assistant(text="working on the artifact", tool_use=True),
        _write(f"# Report\n\nfindings...\n\n{_FENCE}\n"),
        _assistant(text="prose summary, no fence"),
    ]
    envelope, transport = parse_node_status_from_events(events)
    assert envelope == _ENVELOPE
    assert transport == "written_artifact"


def test_later_fenceless_write_does_not_erase_earlier_candidate():
    """Last CANDIDATE wins, not last Write — memory files written after the
    artifact must not un-credit it."""
    events = [
        _write(f"# Report\n\n{_FENCE}\n"),
        _write("# MEMORY note\n\nplain housekeeping content\n", file_path="memory/note.md"),
        _assistant(text="prose summary"),
    ]
    envelope, transport = parse_node_status_from_events(events)
    assert envelope == _ENVELOPE
    assert transport == "written_artifact"


def test_mid_content_write_fence_not_credited():
    """A fence quoted mid-document (e.g. a MEMORY.md citing the contract
    example) is not a trailing fence and must not classify the run."""
    events = [
        _write(f"# Notes\n\nexample:\n{_FENCE}\n\nmore prose after the fence\n"),
        _assistant(text="prose summary"),
    ]
    assert parse_node_status_from_events(events) == (None, None)


def test_edit_tool_inputs_never_considered():
    events = [
        _write(f"partial\n{_FENCE}\n", name="Edit"),
        _assistant(text="prose summary"),
    ]
    assert parse_node_status_from_events(events) == (None, None)


def test_malformed_trailing_write_fence_not_credited():
    events = [_write("# Report\n\n```node_status\n{not json}\n```\n")]
    assert parse_node_status_from_events(events) == (None, None)


def test_no_fence_anywhere_returns_none_none():
    events = [
        _assistant(text="just prose"),
        _write("# Report\n\nno fence here\n"),
        _assistant(text="more prose"),
    ]
    assert parse_node_status_from_events(events) == (None, None)
    assert parse_node_status_from_events([]) == (None, None)


def test_production_shaped_run_classifies_done():
    """The observed 67-turn production failure: perfect fence at the END of
    the Written artifact, memory-compaction housekeeping turns after it, and
    a fenceless prose final message → status done, not 'no fence'."""
    done_env = {
        "status": "done",
        "artifact_paths": [".cronos/delivery/goal/frontend-report.md"],
        "produces": "review",
        "fields": {},
        "open_questions": [],
    }
    done_fence = f"```node_status\n{json.dumps(done_env)}\n```"
    events = [
        _assistant(text="Starting the frontend review.", tool_use=True),
        _assistant(tool_use=True),
        _write(
            f"# Frontend report\n\nlong findings...\n\n{done_fence}\n",
            file_path=".cronos/delivery/goal/frontend-report.md",
        ),
        # Memory-compaction hook forces trailing housekeeping turns.
        _write("housekeeping memory content\n", file_path="memory/frontend.md"),
        _assistant(text="Summary of the work performed. " * 100),
    ]
    envelope, transport = parse_node_status_from_events(events)
    assert envelope is not None
    assert envelope["status"] == "done"
    assert transport == "written_artifact"
    trace = extract_run_trace(events, **_kwargs())
    assert trace.node_status == envelope


# ---------------------------------------------------------------------------
# Guards on the tolerance surfaces: quoted contract examples, sidechain
# (Task-subagent) events, legacy fence names, artifact self-reference.
# Everything here was inert under final-turn-only selection and must stay
# inert under turn tolerance.
# ---------------------------------------------------------------------------

# The (pre-hardening) contract example: regex-exact, valid JSON, status done.
_EXAMPLE_ECHO = (
    "Per the return contract I will end with:\n"
    "```node_status\n"
    '{"status": "done", "artifact_paths": [], "produces": "research", '
    '"fields": {}, "open_questions": []}\n'
    "```"
)


def test_quoted_example_in_early_turn_not_credited():
    """A planning turn restating the contract example mid-text must not
    classify the run (tail anchor on earlier turns)."""
    events = [
        _assistant(text=f"{_EXAMPLE_ECHO}\nThen I'll get to work."),
        _assistant(text="I hit an unrecoverable error — how should I proceed?"),
    ]
    assert parse_node_status_from_events(events) == (None, None)


def test_quoted_example_in_4backtick_block_not_credited():
    """The echo inside a 4-backtick quote block ENDING the turn — the outer
    closing backticks sit after the inner fence and break the tail anchor."""
    events = [
        _assistant(text=f"Restating my instructions:\n````\n{_EXAMPLE_ECHO}\n````"),
        _assistant(text="fenceless apology prose"),
    ]
    assert parse_node_status_from_events(events) == (None, None)


def test_bare_trailing_echo_of_shipped_example_not_credited():
    """A bare echo TRAILING an early turn is transport-indistinguishable from
    a genuine fence — defense in depth: the example the brief actually ships
    is deliberately invalid JSON (unquoted <status> placeholder)."""
    echo = (
        "I will finish with:\n```node_status\n"
        '{"status": <status>, "artifact_paths": [], "produces": "research", '
        '"fields": {}, "open_questions": []}\n```'
    )
    events = [_assistant(text=echo), _assistant(text="fenceless ending")]
    assert parse_node_status_from_events(events) == (None, None)


def test_early_turn_fence_must_end_the_turn():
    """Tail anchor: even a genuine-looking fence mid-turn with prose after
    does not classify from an earlier turn."""
    events = [
        _assistant(text=f"{_FENCE}\nNow let me write the memory file."),
        _assistant(text="housekeeping done, no fence"),
    ]
    assert parse_node_status_from_events(events) == (None, None)


def test_fence_then_prose_in_final_turn_still_credited():
    """Old-surface compatibility: the final turn keeps anywhere-in-turn
    matching, so a fence followed by a short closing line still counts."""
    events = [_assistant(text=f"{_FENCE}\nThat is my final status.")]
    envelope, transport = parse_node_status_from_events(events)
    assert envelope == _ENVELOPE
    assert transport == "assistant_text"


def test_sidechain_fence_never_classifies_parent_run():
    """Task-tool subagent events (parent_tool_use_id set) are interleaved
    into stream-json; their fences and Writes belong to the subagent, not
    the delivery node."""
    side_text = dict(
        _assistant(text=f"subagent done\n{_FENCE}"), parent_tool_use_id="tu-task"
    )
    side_write = dict(
        _write(f"# Report\n\n{_FENCE}\n"), parent_tool_use_id="tu-task"
    )
    events = [side_text, side_write, _assistant(text="main agent question, no fence")]
    assert parse_node_status_from_events(events) == (None, None)


def test_quoted_legacy_fence_in_earlier_turn_not_credited():
    """Cross-run misattribution guard: a retro node quoting ANOTHER run's
    legacy delivery_status fence (even turn-trailing), then a malformed own
    fence in the final turn, must classify honestly as no-envelope."""
    quoted = (
        "the previous run ended with:\n"
        f"```delivery_status\n{json.dumps(_ENVELOPE)}\n```"
    )
    events = [
        _assistant(text=quoted),
        _assistant(text="my own status:\n```node_status\n{not json}\n```"),
    ]
    assert parse_node_status_from_events(events) == (None, None)


def test_memory_write_quoting_example_at_tail_not_credited():
    """A memory note ENDING with the quoted contract example (empty
    artifact_paths → not self-referencing) must not classify the run."""
    quoted_example = (
        "delivery nodes must end with:\n```node_status\n"
        '{"status": "done", "artifact_paths": [], "produces": "review", '
        '"fields": {}, "open_questions": []}\n```\n'
    )
    events = [
        _write(
            f"# Fence compliance\n\n{quoted_example}",
            file_path="memory/fence-compliance.md",
        ),
        _assistant(text="fenceless failure prose"),
    ]
    assert parse_node_status_from_events(events) == (None, None)


def test_write_fence_must_name_the_written_file():
    """Self-reference guard: a trailing Write fence whose artifact_paths does
    not name the written file is a quote, not an artifact tail."""
    env = dict(_ENVELOPE, artifact_paths=["some/other.md"])
    events = [
        _write(f"# Report\n\n```node_status\n{json.dumps(env)}\n```\n"),
        _assistant(text="prose summary"),
    ]
    assert parse_node_status_from_events(events) == (None, None)


def test_write_fence_absolute_path_matches_relative_artifact_path():
    """Agents Write with absolute paths but list workspace-relative
    artifact_paths — segment-suffix matching credits the genuine tail."""
    env = dict(_ENVELOPE, artifact_paths=[".cronos/delivery/goal/frontend-report.md"])
    events = [
        _write(
            f"# Report\n\n```node_status\n{json.dumps(env)}\n```\n",
            file_path="/data/spaces/x/.cronos/delivery/goal/frontend-report.md",
        ),
        _assistant(text="prose summary"),
    ]
    envelope, transport = parse_node_status_from_events(events)
    assert envelope == env
    assert transport == "written_artifact"


def test_later_quoted_example_write_does_not_override_genuine_blocked_tail():
    """A genuine blocked fence at the report tail, then a memory note ending
    with the quoted done example — the quote (not self-referencing) must not
    flip blocked into done and swallow the human question."""
    blocked = {
        "status": "blocked",
        "artifact_paths": ["reports/scout.md"],
        "produces": "research",
        "fields": {},
        "open_questions": ["need credentials"],
    }
    quoted_done = (
        "the contract example:\n```node_status\n"
        '{"status": "done", "artifact_paths": [], "produces": "research", '
        '"fields": {}, "open_questions": []}\n```\n'
    )
    events = [
        _write(f"# Report\n\n```node_status\n{json.dumps(blocked)}\n```\n"),
        _write(f"# Note\n\n{quoted_done}", file_path="memory/note.md"),
        _assistant(text="prose summary"),
    ]
    envelope, transport = parse_node_status_from_events(events)
    assert envelope == blocked
    assert transport == "written_artifact"
