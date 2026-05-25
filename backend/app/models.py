from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class TaskState(str, Enum):
    BACKLOG = "backlog"
    ACTIVE = "active"
    WAITING = "waiting"
    DONE = "done"
    ARCHIVED = "archived"


AgentMode = Literal["plan", "auto", "ask"]
AgentModel = Literal["default", "sonnet", "opus", "haiku"]
TaskType = Literal["task", "goal", "issue"]


class View(BaseModel):
    id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]*$", max_length=32)
    name: str
    lanes: list[TaskState] = Field(min_length=1)
    type_filter: list[TaskType] | None = None
    default: bool = False
    created_at: datetime
    updated_at: datetime


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
    priority: int = 3  # 1 (highest) to 5 (lowest)
    manual_order: int = 0  # lower value = higher in lane
    type: Literal["task", "goal", "issue"] = "task"
    parent_id: str | None = None
    depends_on: list[str] = Field(default_factory=list)
    pr_url: str | None = None
    proposed_pr_path: str | None = None


class ChildItem(BaseModel):
    id: str
    title: str
    state: TaskState
    priority: int
    updated_at: datetime


class ChildrenProgress(BaseModel):
    done: int
    total: int
    waiting: int
    items: list[ChildItem] = Field(default_factory=list)


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
    priority: int = 3
    manual_order: int = 0
    agent_mode: AgentMode = "auto"
    type: Literal["task", "goal", "issue"] = "task"
    parent_id: str | None = None
    depends_on: list[str] = Field(default_factory=list)
    unmet_dependencies: list[str] = []
    pr_url: str | None = None
    proposed_pr_path: str | None = None
    children_progress: ChildrenProgress | None = None
    # True when a worker is actively executing this task right now.
    is_running: bool = False
    # Denormalized space fields so cards can render without a separate join.
    space_name: str | None = None
    space_color: str | None = None
    space_icon: str | None = None
    space_autopilot: str | None = None


class Board(BaseModel):
    """Tasks grouped by state, in the order they should appear in each lane."""

    backlog: list[TaskSummary] = []
    active: list[TaskSummary] = []
    waiting: list[TaskSummary] = []
    done: list[TaskSummary] = []


class Space(BaseModel):
    """A project-like namespace that owns tasks, workspaces, and config.

    On disk the Space directory is the repo working tree (when linked); all
    Cronos state lives under `{space_dir}/.cronos/`. When `git_repo_url` is
    set the space is linked: Cronos clones the repo into the space dir on
    link, and creates a per-task git worktree for each task it spawns.
    """

    id: str
    name: str
    color: str  # validated hex, e.g. "#15803D"
    icon: str | None = None
    description: str = ""
    created_at: datetime
    updated_at: datetime
    git_repo_url: str | None = None
    git_branch: str | None = None
    # When True, `.cronos/` is NOT added to .gitignore — the repo and Cronos
    # state are versioned together so teammates can share tasks via git.
    git_share_cronos: bool = False
    agent_defaults: dict[str, str] = Field(default_factory=dict)
    autopilot: Literal["disabled", "enabled", "paused"] = "disabled"
    views: list[View] = Field(default_factory=list)

    @model_validator(mode="after")
    def _view_ids_unique(self) -> "Space":
        seen: set[str] = set()
        for v in self.views:
            if v.id in seen:
                raise ValueError(f"Duplicate view id {v.id!r}")
            seen.add(v.id)
        return self


class SpaceSummary(BaseModel):
    id: str
    name: str
    color: str
    icon: str | None = None
    task_counts: dict[TaskState, int] = Field(default_factory=dict)
    last_activity_at: datetime | None = None
    autopilot: Literal["disabled", "enabled", "paused"] = "disabled"


class SpacesResponse(BaseModel):
    spaces: list[SpaceSummary] = []
    totals: dict[TaskState, int] = Field(default_factory=dict)


class Activity(BaseModel):
    task_id: str
    space_id: str
    title: str
    state: TaskState
    updated_at: datetime


# ---------------------------------------------------------------------------
# AI Tools Inventory
# ---------------------------------------------------------------------------

class AiToolEntry(BaseModel):
    name: str
    path: str
    description: str | None = None
    scope: str  # "space" | "global"
    modified_at: str  # ISO-8601


class HookEntry(BaseModel):
    event: str
    matcher: str | None = None
    command: str
    scope: str  # "space" | "global"


class PermissionEntry(BaseModel):
    pattern: str
    allowed: bool
    scope: str  # "space" | "global"


class SpaceToolsResponse(BaseModel):
    space_id: str
    agents: list[AiToolEntry] = []
    commands: list[AiToolEntry] = []
    skills: list[AiToolEntry] = []
    context_files: list[AiToolEntry] = []
    hooks: list[HookEntry] = []
    permissions: list[PermissionEntry] = []
    has_claude_md: bool = False
