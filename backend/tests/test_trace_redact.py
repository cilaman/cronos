from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.trace_redact import _redact_secrets, redact_trace_dict
from app.trace_parser import RunTrace, ToolCallTrace
from app.trace_store import TraceStore


# ---------------------------------------------------------------------------
# _redact_secrets — per-pattern positive and negative cases
# ---------------------------------------------------------------------------

class TestRedactSecrets:
    def test_ghp_token_is_redacted(self):
        assert _redact_secrets("ghp_AAAAAAAAAAAAAAAAAAAAA") == "REDACTED-GHP"

    def test_ghp_too_short_not_redacted(self):
        # fewer than 20 chars after prefix → no match
        assert _redact_secrets("ghp_short") == "ghp_short"

    def test_github_pat_token_is_redacted(self):
        result = _redact_secrets("github_pat_AAAAAAAAAAAAAAAAAAAAA")
        assert result == "REDACTED-GITHUB-PAT"

    def test_github_pat_too_short_not_redacted(self):
        assert _redact_secrets("github_pat_tiny") == "github_pat_tiny"

    def test_gho_token_is_redacted(self):
        assert _redact_secrets("gho_AAAAAAAAAAAAAAAAAAAAA") == "REDACTED-GHO"

    def test_gho_too_short_not_redacted(self):
        assert _redact_secrets("gho_short") == "gho_short"

    def test_ghs_token_is_redacted(self):
        assert _redact_secrets("ghs_AAAAAAAAAAAAAAAAAAAAA") == "REDACTED-GHS"

    def test_ghs_too_short_not_redacted(self):
        assert _redact_secrets("ghs_short") == "ghs_short"

    def test_ghr_token_is_redacted(self):
        assert _redact_secrets("ghr_AAAAAAAAAAAAAAAAAAAAA") == "REDACTED-GHR"

    def test_ghr_too_short_not_redacted(self):
        assert _redact_secrets("ghr_short") == "ghr_short"

    def test_https_token_at_github_is_redacted(self):
        result = _redact_secrets("https://ghp_AAAAAAAAAAAAAAAAAAAAA@github.com/org/repo.git")
        # The ghp_ pattern fires first; URL pattern then has no token-prefixed credential to match.
        assert "ghp_" not in result
        assert "REDACTED" in result

    def test_https_no_credentials_not_redacted(self):
        url = "https://github.com/org/repo.git"
        assert _redact_secrets(url) == url

    def test_x_access_token_is_redacted(self):
        result = _redact_secrets("x-access-token:AAAAAAAAAAAAAAAAAAAAA")
        assert result == "x-access-token:REDACTED"

    def test_x_access_token_too_short_not_redacted(self):
        assert _redact_secrets("x-access-token:short") == "x-access-token:short"

    def test_unrelated_text_unchanged(self):
        text = "no secrets here, just plain text"
        assert _redact_secrets(text) == text

    def test_multiple_distinct_pats_all_redacted(self):
        text = (
            "token1=ghp_AAAAAAAAAAAAAAAAAAAA1 "
            "token2=ghs_BBBBBBBBBBBBBBBBBBBBB "
            "token3=github_pat_CCCCCCCCCCCCCCCCCCCCC"
        )
        result = _redact_secrets(text)
        assert "ghp_" not in result
        assert "ghs_" not in result
        assert "github_pat_" not in result
        assert "REDACTED-GHP" in result
        assert "REDACTED-GHS" in result
        assert "REDACTED-GITHUB-PAT" in result

    def test_pat_embedded_in_larger_string(self):
        text = "running: git push https://ghp_AAAAAAAAAAAAAAAAAAAAA@github.com/org/repo.git main"
        result = _redact_secrets(text)
        assert "ghp_" not in result
        assert "REDACTED" in result


# ---------------------------------------------------------------------------
# redact_trace_dict — structural recursion
# ---------------------------------------------------------------------------

class TestRedactTraceDict:
    def test_plain_string(self):
        assert redact_trace_dict("ghp_AAAAAAAAAAAAAAAAAAAAA") == "REDACTED-GHP"

    def test_non_secret_string_unchanged(self):
        assert redact_trace_dict("hello world") == "hello world"

    def test_integer_unchanged(self):
        assert redact_trace_dict(42) == 42

    def test_none_unchanged(self):
        assert redact_trace_dict(None) is None

    def test_flat_dict_string_values_redacted(self):
        d = {"output": "ghp_AAAAAAAAAAAAAAAAAAAAA", "other": "clean"}
        result = redact_trace_dict(d)
        assert result["output"] == "REDACTED-GHP"
        assert result["other"] == "clean"

    def test_flat_dict_keys_not_redacted(self):
        # Keys themselves should not be altered
        d = {"ghp_AAAAAAAAAAAAAAAAAAAAA": "value"}
        result = redact_trace_dict(d)
        assert "ghp_AAAAAAAAAAAAAAAAAAAAA" in result

    def test_nested_dict_redacts_deep_strings(self):
        d = {
            "level1": {
                "level2": {
                    "secret": "ghs_AAAAAAAAAAAAAAAAAAAAA",
                    "safe": "no-secret",
                }
            }
        }
        result = redact_trace_dict(d)
        assert result["level1"]["level2"]["secret"] == "REDACTED-GHS"
        assert result["level1"]["level2"]["safe"] == "no-secret"

    def test_list_of_strings_redacted(self):
        lst = ["ghp_AAAAAAAAAAAAAAAAAAAAA", "clean", "gho_BBBBBBBBBBBBBBBBBBBBB"]
        result = redact_trace_dict(lst)
        assert result == ["REDACTED-GHP", "clean", "REDACTED-GHO"]

    def test_mixed_nested_structure(self):
        obj = {
            "tool_calls": [
                {
                    "input_summary": "git push https://ghp_AAAAAAAAAAAAAAAAAAAAA@github.com/org/repo.git",
                    "output_summary": "remote: error",
                    "count": 3,
                }
            ]
        }
        result = redact_trace_dict(obj)
        tc = result["tool_calls"][0]
        assert "ghp_" not in tc["input_summary"]
        assert "REDACTED" in tc["input_summary"]
        assert tc["output_summary"] == "remote: error"
        assert tc["count"] == 3


# ---------------------------------------------------------------------------
# TraceStore.save_run — redaction at write layer
# ---------------------------------------------------------------------------

def _make_trace_with_pat(run_index: int = 0) -> RunTrace:
    now = datetime.now(tz=timezone.utc)
    tc = ToolCallTrace(
        tool_call_index=0,
        tool_use_id="tu-001",
        name="Bash",
        input_summary='{"command": "git push https://ghp_AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA@github.com/org/repo.git"}',
        output_summary="ghp_AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA leaked in output",
        turn_index=0,
    )
    return RunTrace(
        task_id="task-secret",
        space_id="space-1",
        run_index=run_index,
        session_id="sess-secret",
        model="sonnet",
        mode="auto",
        started_at=now,
        ended_at=now,
        duration_seconds=1.0,
        exit_reason="done",
        tool_calls=[tc],
    )


@pytest.fixture
def store(tmp_path: Path) -> TraceStore:
    return TraceStore(tmp_path / "spaces")


async def test_save_run_redacts_pat_in_output_summary(store: TraceStore, tmp_path: Path):
    trace = _make_trace_with_pat(run_index=0)
    await store.save_run("space-1", "task-secret", trace)

    trace_file = (
        tmp_path / "spaces" / "space-1" / ".cronos" / "traces" / "task-secret" / "0000.json"
    )
    assert trace_file.exists()
    contents = trace_file.read_text(encoding="utf-8")
    assert "ghp_AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA" not in contents
    assert "REDACTED-GHP" in contents


async def test_save_run_redacts_pat_in_input_summary(store: TraceStore, tmp_path: Path):
    trace = _make_trace_with_pat(run_index=1)
    await store.save_run("space-1", "task-secret", trace)

    trace_file = (
        tmp_path / "spaces" / "space-1" / ".cronos" / "traces" / "task-secret" / "0001.json"
    )
    contents = trace_file.read_text(encoding="utf-8")
    # The ghp token embedded in the URL inside input_summary must be gone
    assert "ghp_AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA" not in contents


async def test_save_run_clean_trace_unchanged(store: TraceStore):
    now = datetime.now(tz=timezone.utc)
    trace = RunTrace(
        task_id="task-clean",
        space_id="space-1",
        run_index=0,
        session_id="sess-clean",
        model="sonnet",
        mode="auto",
        started_at=now,
        ended_at=now,
        duration_seconds=0.5,
        exit_reason="done",
    )
    await store.save_run("space-1", "task-clean", trace)
    loaded = await store.load_run("space-1", "task-clean", 0)
    assert loaded is not None
    assert loaded.exit_reason == "done"
    assert loaded.session_id == "sess-clean"
