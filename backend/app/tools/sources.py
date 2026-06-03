from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel, field_validator

from app.git_ops import GitError, validate_repo_url


class ToolSourceError(Exception):
    """Raised when a tool source entry is invalid."""


class ToolSource(BaseModel):
    url: str
    branch: Optional[str] = None
    enabled: bool = True
    label: Optional[str] = None

    @field_validator("url")
    @classmethod
    def _validate_url(cls, v: str) -> str:
        try:
            validate_repo_url(v)
        except GitError as exc:
            raise ToolSourceError(str(exc)) from exc
        return v


def load_sources(path: Path) -> list[ToolSource]:
    """Load ToolSource entries from a YAML file.

    Checks CRONOS_TOOL_SOURCES_PATH env var first; falls back to ``path``.
    Returns an empty list if the resolved file does not exist.
    Raises ToolSourceError if any entry has an invalid URL.
    """
    override = os.environ.get("CRONOS_TOOL_SOURCES_PATH")
    resolved = Path(override) if override else path

    if not resolved.exists():
        return []

    raw = yaml.safe_load(resolved.read_text(encoding="utf-8")) or {}
    entries = raw.get("sources") or []

    sources: list[ToolSource] = []
    for entry in entries:
        try:
            sources.append(ToolSource.model_validate(entry))
        except ToolSourceError:
            raise
        except Exception as exc:
            raise ToolSourceError(f"Invalid tool source entry {entry!r}: {exc}") from exc
    return sources
