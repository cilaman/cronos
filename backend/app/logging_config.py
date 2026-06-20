"""Structured JSON logging configuration for Cronos.

Provides:
- JsonFormatter: stdlib logging.Formatter emitting JSON lines with timestamp,
  level, logger, message, plus any contextvars fields bound via bind_run_context.
- bind_run_context(run_id, task_id): context manager that binds run_id / task_id
  into contextvars for the duration of a block, then resets on exit (token-safe).
- configure_logging(): reads CRONOS_LOG_LEVEL, installs JsonFormatter on the root
  logger (replacing any existing handlers), so every module-named logger inherits it.
"""

from __future__ import annotations

import contextvars
import json
import logging
import os
import sys
import time

_run_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "run_id", default=None
)
_task_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "task_id", default=None
)


class JsonFormatter(logging.Formatter):
    """Emit each log record as a single-line JSON object."""

    def format(self, record: logging.LogRecord) -> str:
        obj: dict = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        run_id = _run_id_var.get()
        if run_id is not None:
            obj["run_id"] = run_id
        task_id = _task_id_var.get()
        if task_id is not None:
            obj["task_id"] = task_id
        if record.exc_info:
            obj["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(obj)


class bind_run_context:
    """Context manager that binds run_id and task_id into contextvars.

    Uses token-based reset so bindings never leak into sibling or parent
    coroutines — safe for concurrent asyncio tasks.

    Usage::

        async with bind_run_context(run_id="abc", task_id="t1"):
            log.info("this has run_id and task_id fields")
    """

    def __init__(self, run_id: str | None, task_id: str | None = None) -> None:
        self._run_id = run_id
        self._task_id = task_id
        self._tokens: list = []

    def __enter__(self) -> "bind_run_context":
        self._tokens.append(_run_id_var.set(self._run_id))
        self._tokens.append(_task_id_var.set(self._task_id))
        return self

    def __exit__(self, *_: object) -> None:
        for token in reversed(self._tokens):
            try:
                token.var.reset(token)
            except Exception:
                pass
        self._tokens.clear()

    async def __aenter__(self) -> "bind_run_context":
        return self.__enter__()

    async def __aexit__(self, *args: object) -> None:
        self.__exit__(*args)


_VALID_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}


def configure_logging() -> None:
    """Install JsonFormatter on the root logger.

    Reads CRONOS_LOG_LEVEL (default INFO). Invalid values are logged at WARNING
    level and INFO is used as a fallback.
    """
    level_name = os.environ.get("CRONOS_LOG_LEVEL", "INFO").upper()
    if level_name not in _VALID_LEVELS:
        level = logging.INFO
        # Cannot use structured logger yet — format manually.
        sys.stderr.write(
            json.dumps({
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "level": "WARNING",
                "logger": "cronos.logging_config",
                "message": f"Invalid CRONOS_LOG_LEVEL={level_name!r}; falling back to INFO",
            }) + "\n"
        )
    else:
        level = getattr(logging, level_name)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)
