from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class TaskState(str, Enum):
    BACKLOG = "backlog"
    ACTIVE = "active"
    WAITING = "waiting"
    DONE = "done"


AgentMode = Literal["plan", "auto", "ask"]
AgentModel = Literal["default", "sonnet", "opus", "haiku"]


class Task(BaseModel):
    """Full task as parsed from a markdown file."""

    id: str
    space_id: str
    title: str
    state: TaskState
    created_at: datetime
    updated_at: datetime
    claude_session_id: str | None = None
    waiting_question: str | None = None
    brief: str = ""
    history: str = ""
    pending_messages: list[str] = Field(default_factory=list)
    agent_mode: AgentMode = "auto"
    agent_model: AgentModel = "default"


class TaskSummary(BaseModel):
    """Lightweight task representation for board listings."""

    id: str
    space_id: str
    title: str
    state: TaskState
    created_at: datetime
    updated_at: datetime
    waiting_question: str | None = None
    brief_preview: str = Field(
        default="",
        description="First ~200 chars of the brief, for card display.",
    )
    # Denormalized space fields so cards can render without a separate join.
    space_name: str | None = None
    space_color: str | None = None
    space_icon: str | None = None


class Board(BaseModel):
    """Tasks grouped by state, in the order they should appear in each lane."""

    backlog: list[TaskSummary] = []
    active: list[TaskSummary] = []
    waiting: list[TaskSummary] = []
    done: list[TaskSummary] = []


class Space(BaseModel):
    """A project-like namespace that owns tasks, workspaces, and config."""

    id: str
    name: str
    color: str  # validated hex, e.g. "#15803D"
    icon: str | None = None
    description: str = ""
    created_at: datetime
    updated_at: datetime
    # Reserved for future binding (declared but unused in v1).
    git_repo_url: str | None = None
    git_branch: str | None = None
    agent_defaults: dict[str, str] = Field(default_factory=dict)


class SpaceSummary(BaseModel):
    id: str
    name: str
    color: str
    icon: str | None = None
    task_counts: dict[TaskState, int] = Field(default_factory=dict)
    last_activity_at: datetime | None = None


class SpacesResponse(BaseModel):
    spaces: list[SpaceSummary] = []
    totals: dict[TaskState, int] = Field(default_factory=dict)


class Activity(BaseModel):
    task_id: str
    space_id: str
    title: str
    state: TaskState
    updated_at: datetime
