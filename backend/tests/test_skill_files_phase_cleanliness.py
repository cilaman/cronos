"""Regression guard: create-task/SKILL.md and .claude/agents/*.md must not
contain CC-v1 phase-pre-creation patterns or disallowed invocation strings.

This test runs in CI to catch future drift — no implementation changes needed,
just grep assertions.
"""
from __future__ import annotations

import re
from pathlib import Path

SPACE_ROOT = Path(__file__).parent.parent.parent

CREATE_TASK_SKILL = SPACE_ROOT / ".claude" / "skills" / "create-task" / "SKILL.md"
AGENTS_DIR = SPACE_ROOT / ".claude" / "agents"

# Patterns that must NOT appear in create-task/SKILL.md
# These signal phase pre-creation logic bleeding into the simple task-creation helper.
CREATE_TASK_BANNED_PATTERNS = [
    "pipeline",
    "CC-v1",
    "analyst",
    "architect",
    "impl phase",
    "review phase",
    "doc phase",
]

# Narrow invocation patterns that must NOT appear in any agent file.
# These are the actual antipatterns (invoking old skills) — NOT agent names or phase names,
# which legitimately appear in agent description files.
AGENTS_BANNED_PATTERNS = [
    "pipeline-scaffold",
    "/create-goal",
]


def test_create_task_skill_clean():
    """create-task/SKILL.md must not contain CC-v1 phase-pre-creation patterns."""
    assert CREATE_TASK_SKILL.exists(), f"create-task/SKILL.md not found at {CREATE_TASK_SKILL}"
    content = CREATE_TASK_SKILL.read_text()

    found = [p for p in CREATE_TASK_BANNED_PATTERNS if p in content]
    assert not found, (
        f"create-task/SKILL.md contains banned CC-v1 phase patterns: {found!r}\n"
        f"These patterns indicate phase-pre-creation logic that belongs in the "
        f"delivery runner, not in a simple task-creation skill."
    )


def test_agents_no_pipeline_scaffold_invocation():
    """No agent file must invoke /pipeline-scaffold."""
    assert AGENTS_DIR.exists(), f"Agents directory not found at {AGENTS_DIR}"
    agent_files = list(AGENTS_DIR.glob("*.md"))
    assert agent_files, "No agent .md files found — directory may be misconfigured"

    violations: list[tuple[str, int, str]] = []
    for agent_file in sorted(agent_files):
        for lineno, line in enumerate(agent_file.read_text().splitlines(), 1):
            if "pipeline-scaffold" in line:
                violations.append((agent_file.name, lineno, line.strip()))

    assert not violations, (
        "Agent files must not invoke pipeline-scaffold (use /create-delivery-goal):\n"
        + "\n".join(f"  {f}:{n}: {l}" for f, n, l in violations)
    )


def test_agents_no_create_goal_invocation():
    """No agent file must invoke /create-goal (use /create-delivery-goal for delivery goals)."""
    assert AGENTS_DIR.exists(), f"Agents directory not found at {AGENTS_DIR}"
    agent_files = list(AGENTS_DIR.glob("*.md"))
    assert agent_files, "No agent .md files found — directory may be misconfigured"

    violations: list[tuple[str, int, str]] = []
    for agent_file in sorted(agent_files):
        for lineno, line in enumerate(agent_file.read_text().splitlines(), 1):
            if "/create-goal" in line:
                violations.append((agent_file.name, lineno, line.strip()))

    assert not violations, (
        "Agent files must not invoke /create-goal — use /create-delivery-goal instead:\n"
        + "\n".join(f"  {f}:{n}: {l}" for f, n, l in violations)
    )


def test_create_delivery_goal_skill_exists():
    """create-delivery-goal/SKILL.md must exist (regression guard for accidental deletion)."""
    skill_path = SPACE_ROOT / ".claude" / "skills" / "create-delivery-goal" / "SKILL.md"
    assert skill_path.exists(), (
        f"create-delivery-goal/SKILL.md not found at {skill_path}. "
        f"This skill was introduced in SG6; its absence means it was accidentally deleted."
    )


def test_create_delivery_goal_no_phase_tasks_in_procedure():
    """create-delivery-goal/SKILL.md must not contain loop-based child task creation."""
    skill_path = SPACE_ROOT / ".claude" / "skills" / "create-delivery-goal" / "SKILL.md"
    if not skill_path.exists():
        pytest.skip("create-delivery-goal/SKILL.md not found")

    content = skill_path.read_text()

    # The Procedure must not contain a loop that creates multiple tasks
    # "for sl in slices" / "for phase in PHASES" patterns are banned
    phase_loop_patterns = [
        r"for\s+\w+\s+in\s+PHASES",
        r"for\s+sl\s+in\s+slices",
        r"for\s+phase",
    ]
    for pattern in phase_loop_patterns:
        match = re.search(pattern, content)
        assert match is None, (
            f"create-delivery-goal/SKILL.md Procedure contains a phase-creation loop "
            f"({match.group()!r}). The skill must create ONE goal and NO child tasks; "
            f"the runner handles child task creation from the workflow spec."
        )
