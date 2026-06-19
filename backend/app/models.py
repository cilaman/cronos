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
AgentModel = Literal["default", "sonnet", "opus", "haiku", "opus-4-8", "fable-5"]
TaskType = Literal["task", "goal", "issue", "feature", "fix"]


class FeatureState(str, Enum):
    """Lifecycle state for feature and fix tasks.

    Distinct from TaskState — never mix the two in typed method signatures.
    """

    BACKLOG = "backlog"
    PROCESSING = "processing"
    PLANNED = "planned"
    WAITING = "waiting"
    DONE = "done"


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
    type: Literal["task", "goal", "issue", "feature", "fix"] = "task"
    parent_id: str | None = None
    depends_on: list[str] = Field(default_factory=list)
    pr_url: str | None = None
    proposed_pr_path: str | None = None
    # Feature / fix fields — all optional; populated only when type in ("feature", "fix")
    feature_state: FeatureState | None = None
    feature_key: str | None = None  # e.g. "FEAT-001" or "FIX-007"
    realizes: str | None = None  # task_id of the feature/fix this item realizes
    issue_number: int | None = None
    issue_url: str | None = None
    proposed_issue_path: str | None = None


class ChildItem(BaseModel):
    id: str
    title: str
    state: TaskState
    priority: int
    updated_at: datetime
    type: Literal["task", "goal", "issue", "feature", "fix"] = "task"
    children_progress: ChildrenProgress | None = None


class ChildrenProgress(BaseModel):
    done: int
    total: int
    waiting: int
    items: list[ChildItem] = Field(default_factory=list)


ChildItem.model_rebuild()


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
    type: Literal["task", "goal", "issue", "feature", "fix"] = "task"
    parent_id: str | None = None
    depends_on: list[str] = Field(default_factory=list)
    unmet_dependencies: list[str] = []
    pr_url: str | None = None
    proposed_pr_path: str | None = None
    children_progress: ChildrenProgress | None = None
    # Feature / fix fields — all optional; populated only when type in ("feature", "fix")
    feature_state: FeatureState | None = None
    feature_key: str | None = None  # e.g. "FEAT-001" or "FIX-007"
    realizes: str | None = None  # task_id of the feature/fix this item realizes
    issue_number: int | None = None
    issue_url: str | None = None
    proposed_issue_path: str | None = None
    # True when a worker is actively executing this task right now.
    is_running: bool = False
    # Denormalized space fields so cards can render without a separate join.
    space_name: str | None = None
    space_color: str | None = None
    space_icon: str | None = None
    space_autopilot: str | None = None
    # Count of tasks/goals that realize this feature; 0 for non-feature tasks.
    realizing_count: int = 0
    # Count of tasks/goals that realize this task (parallel field to realizing_count).
    realized_by_count: int = 0
    # feature_key of the feature/fix this task realizes (e.g. "FEAT-007"); None if not set.
    realizes_feature_key: str | None = None


class Board(BaseModel):
    """Tasks grouped by state, in the order they should appear in each lane."""

    backlog: list[TaskSummary] = []
    active: list[TaskSummary] = []
    waiting: list[TaskSummary] = []
    done: list[TaskSummary] = []


# ---------------------------------------------------------------------------
# Feature / fix request + response schemas
# ---------------------------------------------------------------------------


class CreateFeatureBody(BaseModel):
    """Request body for POST /api/features."""

    space_id: str
    title: str
    brief: str = ""
    type: Literal["feature", "fix"]
    priority: int = Field(default=3, ge=1, le=5)


class PatchFeatureBody(BaseModel):
    """Request body for PATCH /api/features/{id} (edit title/brief)."""

    title: str | None = None
    brief: str | None = None


class PatchFeatureStateBody(BaseModel):
    """Request body for PATCH /api/features/{id}/feature-state."""

    feature_state: FeatureState


class PatchRealizeBody(BaseModel):
    """Request body for PATCH /api/features/{id}/realize.

    Set ``feature_id=None`` to unlink the item from any feature.
    """

    item_id: str
    feature_id: str | None = None


class FeatureBoard(BaseModel):
    """Features/fixes grouped by FeatureState lane.

    Lane names mirror FeatureState values (lowercased) — five lanes, distinct
    from the four-lane Board used for ordinary tasks.
    """

    backlog: list[TaskSummary] = []
    processing: list[TaskSummary] = []
    planned: list[TaskSummary] = []
    waiting: list[TaskSummary] = []
    done: list[TaskSummary] = []


class FeatureRead(BaseModel):
    """Full feature/fix representation returned by GET /api/features/{id}."""

    id: str
    space_id: str
    title: str
    state: TaskState
    created_at: datetime
    updated_at: datetime
    brief: str = ""
    priority: int = 3
    manual_order: int = 0
    type: Literal["task", "goal", "issue", "feature", "fix"] = "task"
    parent_id: str | None = None
    depends_on: list[str] = Field(default_factory=list)
    pr_url: str | None = None
    proposed_pr_path: str | None = None
    feature_state: FeatureState | None = None
    feature_key: str | None = None
    realizes: str | None = None
    issue_number: int | None = None
    issue_url: str | None = None
    proposed_issue_path: str | None = None
    waiting_question: str | None = None
    # Realizing items — tasks that link to this feature via task.realizes == self.id
    realizing_items: list[TaskSummary] = Field(default_factory=list)


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
    feature_totals: dict[FeatureState, int] = Field(default_factory=dict)


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


class AdoptedToolEntry(BaseModel):
    source_url: str
    source_slug: str
    source_path: str
    source_sha: str
    adopted_at: datetime
    base_sha: str
    local_sha: str
    evolved: bool
    kind: str
    name: str
    status: Literal["pristine", "edited", "evolved"]


class SpaceToolsResponse(BaseModel):
    space_id: str
    agents: list[AiToolEntry] = []
    commands: list[AiToolEntry] = []
    skills: list[AiToolEntry] = []
    context_files: list[AiToolEntry] = []
    hooks: list[HookEntry] = []
    permissions: list[PermissionEntry] = []
    has_claude_md: bool = False
    adopted: list[AdoptedToolEntry] = []


class AiToolDetail(BaseModel):
    name: str
    path: str
    description: str | None = None
    scope: Literal["space", "global"]
    modified_at: str
    category: Literal["agent", "command", "skill", "context"]
    content: str


# ---------------------------------------------------------------------------
# Memory
# ---------------------------------------------------------------------------

class MemoryKind(str, Enum):
    FACT = "fact"
    PROCEDURE = "procedure"
    OBSERVATION = "observation"
    REFERENCE = "reference"


class MemoryItem(BaseModel):
    id: str
    scope: str  # "global" | "space:{space_id}"
    kind: MemoryKind
    title: str
    body: str = ""
    confirmed: bool = False
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    score: float = 0.0
    last_used_at: datetime
    ref_count: int = 0
    ttl_until: datetime | None = None
    sources: list[str] = Field(default_factory=list)
    links: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Plugin Management
# ---------------------------------------------------------------------------

class PluginComponent(BaseModel):
    name: str
    kind: str  # "agent" | "skill" | "command"


class PluginEntry(BaseModel):
    id: str
    name: str
    marketplace: str | None = None
    version: str | None = None
    scope: str
    enabled: bool
    components: list[PluginComponent]
    installPath: str | None = None
    installedAt: str | None = None
    lastUpdated: str | None = None


class MarketplacePluginEntry(BaseModel):
    pluginId: str
    name: str
    description: str | None = None
    marketplaceName: str | None = None
    source: str | None = None
    installCount: int


class MarketplaceEntry(BaseModel):
    name: str
    source: str


class PluginsResponse(BaseModel):
    installed: list[PluginEntry]
    available: list[MarketplacePluginEntry]
    marketplaces: list[MarketplaceEntry]
