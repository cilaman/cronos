from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class TaskState(str, Enum):
    BACKLOG = "backlog"
    ACTIVE = "active"
    WAITING = "waiting"
    DONE = "done"


class Task(BaseModel):
    """Full task as parsed from a markdown file."""

    id: str
    title: str
    state: TaskState
    created_at: datetime
    updated_at: datetime
    claude_session_id: str | None = None
    waiting_question: str | None = None
    brief: str = ""
    history: str = ""


class TaskSummary(BaseModel):
    """Lightweight task representation for board listings."""

    id: str
    title: str
    state: TaskState
    created_at: datetime
    updated_at: datetime
    waiting_question: str | None = None
    brief_preview: str = Field(
        default="",
        description="First ~200 chars of the brief, for card display.",
    )


class Board(BaseModel):
    """Tasks grouped by state, in the order they should appear in each lane."""

    backlog: list[TaskSummary] = []
    active: list[TaskSummary] = []
    waiting: list[TaskSummary] = []
    done: list[TaskSummary] = []
