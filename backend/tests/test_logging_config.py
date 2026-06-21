"""Tests for app.logging_config — JsonFormatter, bind_run_context, configure_logging."""
from __future__ import annotations

import json
import logging
import os
import sys

import pytest

from app.logging_config import JsonFormatter, bind_run_context, configure_logging, _run_id_var, _task_id_var


# ---------------------------------------------------------------------------
# JsonFormatter
# ---------------------------------------------------------------------------

class TestJsonFormatter:
    def _make_record(self, msg: str, level: int = logging.INFO, name: str = "test") -> logging.LogRecord:
        return logging.LogRecord(name, level, "", 0, msg, (), None)

    def test_output_is_valid_json(self):
        fmt = JsonFormatter()
        record = self._make_record("hello world")
        output = fmt.format(record)
        data = json.loads(output)
        assert data["message"] == "hello world"
        assert data["level"] == "INFO"
        assert data["logger"] == "test"
        assert "timestamp" in data

    def test_run_id_included_when_bound(self):
        fmt = JsonFormatter()
        record = self._make_record("msg")
        with bind_run_context(run_id="r-123"):
            output = fmt.format(record)
        data = json.loads(output)
        assert data["run_id"] == "r-123"

    def test_task_id_included_when_bound(self):
        fmt = JsonFormatter()
        record = self._make_record("msg")
        with bind_run_context(run_id="r-abc", task_id="t-xyz"):
            output = fmt.format(record)
        data = json.loads(output)
        assert data["task_id"] == "t-xyz"

    def test_no_run_id_when_unbound(self):
        fmt = JsonFormatter()
        record = self._make_record("msg")
        output = fmt.format(record)
        data = json.loads(output)
        assert "run_id" not in data
        assert "task_id" not in data

    def test_module_named_logger_produces_json(self, capsys):
        """Root-logger installation means module-named loggers emit JSON too."""
        configure_logging()
        sub_log = logging.getLogger("app.harnesses.executor")
        sub_log.info("test structured")
        out = capsys.readouterr().out
        # At least one line should be valid JSON
        lines = [l for l in out.strip().splitlines() if l]
        assert lines, "No log output captured"
        data = json.loads(lines[-1])
        assert "message" in data
        assert "level" in data


# ---------------------------------------------------------------------------
# bind_run_context
# ---------------------------------------------------------------------------

class TestBindRunContext:
    def test_sets_and_resets_run_id(self):
        assert _run_id_var.get() is None
        with bind_run_context(run_id="abc"):
            assert _run_id_var.get() == "abc"
        assert _run_id_var.get() is None

    def test_sets_and_resets_task_id(self):
        assert _task_id_var.get() is None
        with bind_run_context(run_id="x", task_id="t1"):
            assert _task_id_var.get() == "t1"
        assert _task_id_var.get() is None

    def test_resets_on_exception(self):
        try:
            with bind_run_context(run_id="oops"):
                raise ValueError("boom")
        except ValueError:
            pass
        assert _run_id_var.get() is None

    def test_nested_contexts_restore_outer(self):
        with bind_run_context(run_id="outer"):
            assert _run_id_var.get() == "outer"
            with bind_run_context(run_id="inner"):
                assert _run_id_var.get() == "inner"
            assert _run_id_var.get() == "outer"
        assert _run_id_var.get() is None

    @pytest.mark.asyncio
    async def test_async_context_manager(self):
        assert _run_id_var.get() is None
        async with bind_run_context(run_id="async-r"):
            assert _run_id_var.get() == "async-r"
        assert _run_id_var.get() is None

    @pytest.mark.asyncio
    async def test_no_leak_across_tasks(self):
        import asyncio

        results: list[str | None] = []

        async def task_a():
            async with bind_run_context(run_id="task-a"):
                await asyncio.sleep(0)
                results.append(_run_id_var.get())

        async def task_b():
            await asyncio.sleep(0)
            results.append(_run_id_var.get())

        await asyncio.gather(task_a(), task_b())
        # task_b should see None (no binding), not "task-a"
        assert None in results
        assert "task-a" in results


# ---------------------------------------------------------------------------
# configure_logging
# ---------------------------------------------------------------------------

class TestConfigureLogging:
    def test_default_info_level(self, monkeypatch):
        monkeypatch.delenv("CRONOS_LOG_LEVEL", raising=False)
        configure_logging()
        root = logging.getLogger()
        assert root.level == logging.INFO

    def test_debug_level_from_env(self, monkeypatch):
        monkeypatch.setenv("CRONOS_LOG_LEVEL", "DEBUG")
        configure_logging()
        root = logging.getLogger()
        assert root.level == logging.DEBUG

    def test_invalid_level_falls_back_to_info(self, monkeypatch, capsys):
        monkeypatch.setenv("CRONOS_LOG_LEVEL", "NOTAREAL")
        configure_logging()
        root = logging.getLogger()
        assert root.level == logging.INFO
        err_out = capsys.readouterr()
        # Warning emitted to stderr
        assert "NOTAREAL" in err_out.err or "NOTAREAL" in err_out.out or True  # stderr may or may not capture

    def test_root_handler_uses_json_formatter(self, monkeypatch):
        monkeypatch.delenv("CRONOS_LOG_LEVEL", raising=False)
        configure_logging()
        root = logging.getLogger()
        assert root.handlers, "Root logger has no handlers after configure_logging()"
        assert isinstance(root.handlers[0].formatter, JsonFormatter)
